import pytest

from audit_app.models import AuditLog
from surveys_app import signals as survey_signals
from surveys_app.models import (
    ExportReport,
    ExportStatus,
    Respondent,
    Survey,
    SurveyResponse,
    SurveyResponseStatus,
    SurveyStatus,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolate_audit_signal_tests(monkeypatch):
    monkeypatch.setattr(survey_signals.REDIS_CLIENT, 'delete', lambda *args, **kwargs: None)


def test_survey_created_triggers_audit_log(admin_user):
    survey = Survey.objects.create(
        title='Created Survey',
        status=SurveyStatus.DRAFT,
        created_by=admin_user,
    )

    audit_log = AuditLog.objects.get(action='survey.created', resource_id=str(survey.id))
    assert audit_log.actor == admin_user
    assert audit_log.resource_type == 'Survey'
    assert audit_log.payload == {'title': 'Created Survey', 'status': SurveyStatus.DRAFT}


def test_survey_published_triggers_audit_log_only_on_transition(draft_survey):
    draft_survey.status = SurveyStatus.PUBLISHED
    draft_survey.save()
    draft_survey.description = 'still published'
    draft_survey.save()

    publish_logs = AuditLog.objects.filter(
        action='survey.published',
        resource_id=str(draft_survey.id),
    )
    assert publish_logs.count() == 1
    assert publish_logs.get().payload['status'] == SurveyStatus.PUBLISHED


def test_survey_deleted_triggers_audit_log(draft_survey):
    survey_id = str(draft_survey.id)
    draft_survey.delete()

    audit_log = AuditLog.objects.get(action='survey.deleted', resource_id=survey_id)
    assert audit_log.resource_type == 'Survey'
    assert audit_log.payload['title'] == 'Draft Survey'


def test_response_submitted_triggers_audit_log(published_survey):
    respondent = Respondent.objects.create()
    survey_response = SurveyResponse.objects.create(
        survey=published_survey,
        respondent=respondent,
        status=SurveyResponseStatus.IN_PROGRESS,
    )

    survey_response.status = SurveyResponseStatus.COMPLETED
    survey_response.save(update_fields=['status'])

    audit_log = AuditLog.objects.get(
        action='response.submitted',
        resource_id=str(survey_response.id),
    )
    assert audit_log.resource_type == 'SurveyResponse'
    assert audit_log.payload == {
        'survey_id': str(published_survey.id),
        'respondent_id': str(respondent.id),
    }


def test_response_creation_does_not_trigger_submitted_log(published_survey):
    SurveyResponse.objects.create(
        survey=published_survey,
        respondent=Respondent.objects.create(),
        status=SurveyResponseStatus.IN_PROGRESS,
    )

    assert not AuditLog.objects.filter(action='response.submitted').exists()


def test_export_report_created_triggers_audit_log(published_survey, analyst_user):
    export_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.PENDING,
    )

    audit_log = AuditLog.objects.get(
        action='survey.export_triggered',
        resource_id=str(published_survey.id),
    )
    assert audit_log.actor == analyst_user
    assert audit_log.payload == {
        'survey_id': str(published_survey.id),
        'export_report_id': str(export_report.id),
    }


def test_export_report_update_does_not_retrigger_audit_log(published_survey, analyst_user):
    export_report = ExportReport.objects.create(
        survey=published_survey,
        requested_by=analyst_user,
        status=ExportStatus.PENDING,
    )
    export_report.status = ExportStatus.READY
    export_report.save(update_fields=['status'])

    export_logs = AuditLog.objects.filter(
        action='survey.export_triggered',
        resource_id=str(published_survey.id),
    )
    assert export_logs.count() == 1
