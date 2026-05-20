import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from rest_framework import status

from surveys_app.models import (
    ExportReport,
    ExportStatus,
    FieldResponse,
    Respondent,
    SurveyResponse,
    SurveyResponseStatus,
)


pytestmark = pytest.mark.django_db


class RedisStub:
    def __init__(self, cached=None):
        self.cached = cached
        self.setex_calls = []

    def get(self, key):
        return self.cached

    def setex(self, key, timeout, value):
        self.setex_calls.append((key, timeout, value))


def test_analytics_requires_auth(api_client, published_survey, monkeypatch):
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', RedisStub())

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['message'] == 'Authentication credentials were not provided.'


def test_analyst_can_fetch_survey_analytics_and_cache_them(
    api_client,
    analyst_user,
    published_survey,
    monkeypatch,
):
    redis_stub = RedisStub()
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', redis_stub)

    first_section = published_survey.sections.get(order=1)
    second_section = published_survey.sections.get(order=2)
    car_field = first_section.fields.get(order=1)
    brand_field = second_section.fields.get(order=1)

    completed_yes = SurveyResponse.objects.create(
        survey=published_survey,
        respondent=Respondent.objects.create(),
        status=SurveyResponseStatus.COMPLETED,
    )
    FieldResponse.objects.create(survey_response=completed_yes, field=car_field, value='Yes')
    FieldResponse.objects.create(survey_response=completed_yes, field=brand_field, value='Toyota')

    completed_no = SurveyResponse.objects.create(
        survey=published_survey,
        respondent=Respondent.objects.create(),
        status=SurveyResponseStatus.COMPLETED,
    )
    FieldResponse.objects.create(survey_response=completed_no, field=car_field, value='No')

    in_progress = SurveyResponse.objects.create(
        survey=published_survey,
        respondent=Respondent.objects.create(),
        status=SurveyResponseStatus.IN_PROGRESS,
    )
    FieldResponse.objects.create(survey_response=in_progress, field=car_field, value='Yes')
    FieldResponse.objects.create(survey_response=in_progress, field=brand_field, value='Honda')

    api_client.force_authenticate(user=analyst_user)
    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data['survey_id'] == str(published_survey.id)
    assert response.data['total_responses'] == 3
    assert response.data['completed_responses'] == 2
    assert response.data['completion_rate'] == 66.67
    assert response.data['field_distributions'][str(car_field.id)] == {
        'label': car_field.label,
        'distribution': {'Yes': 2, 'No': 1},
    }
    assert response.data['field_distributions'][str(brand_field.id)] == {
        'label': brand_field.label,
        'distribution': {'Toyota': 1, 'Honda': 1},
    }
    assert redis_stub.setex_calls
    assert redis_stub.setex_calls[0][0] == f'analytics:{published_survey.id}'
    assert redis_stub.setex_calls[0][1] == 300


def test_admin_can_access_analytics_with_no_responses(
    api_client,
    admin_user,
    published_survey,
    monkeypatch,
):
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', RedisStub())
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_responses'] == 0
    assert response.data['completed_responses'] == 0
    assert response.data['completion_rate'] == 0


def test_analytics_returns_cached_payload_when_available(
    api_client,
    analyst_user,
    published_survey,
    monkeypatch,
):
    cached_payload = {
        'survey_id': str(published_survey.id),
        'total_responses': 99,
        'completed_responses': 80,
        'completion_rate': 80.81,
        'field_distributions': {'cached': {'label': 'Cached field', 'distribution': {'Yes': 99}}},
    }
    redis_stub = RedisStub(cached=json.dumps(cached_payload))
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', redis_stub)
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data == cached_payload
    assert redis_stub.setex_calls == []


def test_analytics_returns_not_found_for_unknown_survey(api_client, analyst_user, monkeypatch):
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', RedisStub())
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': uuid.uuid4()})
    )

    assert response.status_code == 404
    assert response.data['message'] == 'Survey not found.'
    assert response.data['status'] == 404


def test_export_queues_task_and_creates_report(
    api_client,
    analyst_user,
    published_survey,
    monkeypatch,
):
    delay_mock = MagicMock()
    monkeypatch.setattr(
        'surveys_app.views.analytics_views.export_survey_responses_csv',
        SimpleNamespace(delay=delay_mock),
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-export-trigger', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data['message'] == 'Export task queued.'
    assert response.data['status'] == 200

    report = ExportReport.objects.get(id=response.data['export_report_id'])
    assert report.survey == published_survey
    assert report.requested_by == analyst_user
    assert report.status == ExportStatus.PENDING
    delay_mock.assert_called_once_with(
        survey_id=str(published_survey.id),
        requested_by_id=str(analyst_user.id),
        export_report_id=str(report.id),
    )


def test_export_returns_not_found_for_unknown_survey(api_client, analyst_user, monkeypatch):
    monkeypatch.setattr(
        'surveys_app.views.analytics_views.export_survey_responses_csv',
        SimpleNamespace(delay=MagicMock()),
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-export-trigger', kwargs={'survey_id': uuid.uuid4()})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data['message'] == 'Survey not found.'


def test_analyst_can_list_export_reports_on_reports_url(api_client, analyst_user, published_survey):
    older = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.PENDING,
    )
    newer = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.READY,
        file_path='/tmp/latest-report.csv',
    )
    api_client.force_authenticate(user=analyst_user)

    url = reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    response = api_client.get(url)

    assert url.endswith('/analytics/reports/')
    assert response.status_code == 200
    assert response.data['status'] == 200
    assert response.data['total_number_of_objects'] == 2
    assert [item['id'] for item in response.data['results']] == [str(newer.id), str(older.id)]
    assert response.data['results'][0]['status'] == ExportStatus.READY
    assert response.data['results'][0]['requested_by'] == analyst_user.email
    assert response.data['results'][0]['file_url'] == '/tmp/latest-report.csv'


def test_reports_list_only_returns_reports_for_the_requested_survey(
    api_client,
    analyst_user,
    admin_user,
    published_survey,
):
    other_survey = type(published_survey).objects.create(
        title='Other Survey',
        status='published',
        created_by=admin_user,
    )
    ExportReport.objects.create(survey=published_survey, requested_by=analyst_user)
    ExportReport.objects.create(survey=other_survey, requested_by=analyst_user)
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1


def test_filter_reports_by_status_ready(api_client, analyst_user, published_survey):
    ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.PENDING,
    )
    ready_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.READY,
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id}),
        {'status': ExportStatus.READY},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(ready_report.id)


def test_filter_reports_by_requester_email(
    api_client,
    analyst_user,
    admin_user,
    published_survey,
):
    ExportReport.objects.create(survey=published_survey, requested_by=admin_user, status=ExportStatus.PENDING)
    analyst_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.READY,
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id}),
        {'requested_by__email': analyst_user.email},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(analyst_report.id)


def test_reports_file_url_is_absolute(api_client, analyst_user, published_survey, settings):
    report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.READY,
        file_path=f"{settings.MEDIA_ROOT}/exports/{published_survey.id}/report.csv",
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    )

    report_data = next(item for item in response.data['results'] if item['id'] == str(report.id))
    assert report_data['file_url'].startswith('http://')


def test_reports_file_url_empty_when_pending(api_client, analyst_user, published_survey):
    pending_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.PENDING,
        file_path='',
    )
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    )

    report_data = next(item for item in response.data['results'] if item['id'] == str(pending_report.id))
    assert report_data['file_url'] == ''


def test_viewer_can_access_analytics(api_client, viewer_user, published_survey, monkeypatch):
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', RedisStub())
    api_client.force_authenticate(user=viewer_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert 'total_responses' in response.data


def test_unauthenticated_cannot_access_analytics(api_client, published_survey, monkeypatch):
    monkeypatch.setattr('surveys_app.views.analytics_views.REDIS_CLIENT', RedisStub())

    response = api_client.get(
        reverse('surveys_dashboard:survey-analytics', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 401


def test_viewer_cannot_trigger_export(api_client, viewer_user, published_survey, monkeypatch):
    monkeypatch.setattr(
        'surveys_app.views.analytics_views.export_survey_responses_csv',
        SimpleNamespace(delay=MagicMock()),
    )
    api_client.force_authenticate(user=viewer_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-export-trigger', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 403
    assert ExportReport.objects.count() == 0


def test_viewer_can_list_export_reports(api_client, viewer_user, published_survey):
    ExportReport.objects.create(
        survey=published_survey,
        requested_by=viewer_user,
        status=ExportStatus.PENDING,
    )
    api_client.force_authenticate(user=viewer_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data['total_number_of_objects'] == 1


def test_unauthenticated_cannot_list_export_reports(api_client, published_survey):
    response = api_client.get(
        reverse('surveys_dashboard:survey-reports-list', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 401
