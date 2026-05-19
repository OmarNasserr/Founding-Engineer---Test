import csv
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from surveys_app.models import (
    ExportReport,
    ExportStatus,
    Field,
    FieldResponse,
    Respondent,
    SurveyResponse,
    SurveyResponseStatus,
)
from surveys_app.tasks import export_survey_responses_csv


pytestmark = pytest.mark.django_db


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def export_setup(admin_user, published_survey):
    """One completed response with answers + a pending ExportReport."""
    respondent = Respondent.objects.create()
    survey_response = SurveyResponse.objects.create(
        survey=published_survey,
        respondent=respondent,
        status=SurveyResponseStatus.COMPLETED,
        submitted_at=datetime(2026, 5, 18, 10, 0, 0, tzinfo=timezone.utc),
    )
    car_field = Field.objects.get(section__survey=published_survey, label='Own a car?')
    name_field = Field.objects.get(section__survey=published_survey, label='Full Name')
    FieldResponse.objects.create(survey_response=survey_response, field=car_field, value='Yes')
    FieldResponse.objects.create(survey_response=survey_response, field=name_field, value='Alice')

    export_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=admin_user,
        status=ExportStatus.PENDING,
    )
    return {
        'survey': published_survey,
        'admin_user': admin_user,
        'respondent': respondent,
        'survey_response': survey_response,
        'export_report': export_report,
        'car_field': car_field,
        'name_field': name_field,
    }


def _run(setup, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    return export_survey_responses_csv.apply(kwargs={
        'survey_id': str(setup['survey'].id),
        'requested_by_id': str(setup['admin_user'].id),
        'export_report_id': str(setup['export_report'].id),
    })


# ── Happy path ────────────────────────────────────────────────────────────────

def test_export_creates_csv_file_and_marks_report_ready(export_setup, tmp_path, settings):
    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    assert report.status == ExportStatus.READY
    assert report.file_path
    assert os.path.isfile(report.file_path)


def test_export_csv_has_correct_headers(export_setup, tmp_path, settings):
    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        headers = next(csv.reader(f))

    assert headers[:3] == ['response_id', 'respondent_id', 'submitted_at']
    assert 'Own a car?' in headers
    assert 'Full Name' in headers
    assert 'Car Brand' in headers


def test_export_csv_row_data_is_correct(export_setup, tmp_path, settings):
    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row['response_id'] == str(export_setup['survey_response'].id)
    assert row['respondent_id'] == str(export_setup['respondent'].id)
    assert row['submitted_at'] == export_setup['survey_response'].submitted_at.isoformat()
    assert row['Own a car?'] == 'Yes'
    assert row['Full Name'] == 'Alice'
    assert row['Car Brand'] == ''  # unanswered field → empty string


def test_export_fields_ordered_by_section_then_field_order(export_setup, tmp_path, settings):
    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        headers = next(csv.reader(f))

    field_headers = headers[3:]  # strip response_id, respondent_id, submitted_at
    # published_survey: section 1 (order 1) has Own a car? (order 1), Full Name (order 2)
    #                   section 2 (order 2) has Car Brand (order 1)
    assert field_headers == ['Own a car?', 'Full Name', 'Car Brand']


def test_export_excludes_in_progress_responses(export_setup, tmp_path, settings):
    SurveyResponse.objects.create(
        survey=export_setup['survey'],
        respondent=Respondent.objects.create(),
        status=SurveyResponseStatus.IN_PROGRESS,
    )

    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]['response_id'] == str(export_setup['survey_response'].id)


def test_export_produces_header_only_csv_when_no_completed_responses(export_setup, tmp_path, settings):
    export_setup['survey_response'].status = SurveyResponseStatus.IN_PROGRESS
    export_setup['survey_response'].save(update_fields=['status'])

    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    assert report.status == ExportStatus.READY
    with open(report.file_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert rows == []


def test_export_handles_multiple_responses(export_setup, tmp_path, settings):
    second_respondent = Respondent.objects.create()
    second_response = SurveyResponse.objects.create(
        survey=export_setup['survey'],
        respondent=second_respondent,
        status=SurveyResponseStatus.COMPLETED,
        submitted_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
    )
    FieldResponse.objects.create(
        survey_response=second_response,
        field=export_setup['car_field'],
        value='No',
    )

    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    response_ids = {row['response_id'] for row in rows}
    assert str(export_setup['survey_response'].id) in response_ids
    assert str(second_response.id) in response_ids


# ── Sensitive field decryption ────────────────────────────────────────────────

def test_export_decrypts_sensitive_field_values(export_setup, tmp_path, settings, monkeypatch):
    export_setup['name_field'].is_sensitive = True
    export_setup['name_field'].save(update_fields=['is_sensitive'])
    FieldResponse.objects.filter(
        survey_response=export_setup['survey_response'],
        field=export_setup['name_field'],
    ).update(value='encrypted-alice')
    monkeypatch.setattr(
        'surveys_app.service.decrypt_value',
        lambda v: 'Alice' if v == 'encrypted-alice' else v,
    )

    _run(export_setup, tmp_path, settings)

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    with open(report.file_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    assert rows[0]['Full Name'] == 'Alice'


def test_export_does_not_decrypt_non_sensitive_fields(export_setup, tmp_path, settings, monkeypatch):
    decrypt_calls = []
    monkeypatch.setattr(
        'surveys_app.service.decrypt_value',
        lambda v: decrypt_calls.append(v) or v,
    )

    _run(export_setup, tmp_path, settings)

    # No field is sensitive — decrypt_value must never be called
    assert decrypt_calls == []


# ── Failure path ──────────────────────────────────────────────────────────────

def test_export_marks_report_failed_after_max_retries(export_setup, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)

    # Non-existent survey UUID → Survey.DoesNotExist on every attempt.
    # Setting retries=max_retries tells Celery this is already the final attempt,
    # so self.request.retries >= self.max_retries is True immediately and the
    # task marks the report FAILED without scheduling further retries.
    export_survey_responses_csv.apply(
        kwargs={
            'survey_id': str(uuid4()),
            'requested_by_id': str(export_setup['admin_user'].id),
            'export_report_id': str(export_setup['export_report'].id),
        },
        retries=export_survey_responses_csv.max_retries,
        throw=False,
    )

    report = ExportReport.objects.get(id=export_setup['export_report'].id)
    assert report.status == ExportStatus.FAILED
