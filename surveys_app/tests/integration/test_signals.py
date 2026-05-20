import pytest

from surveys_app import signals as survey_signals
from surveys_app.models import Field, FieldType, Section


pytestmark = pytest.mark.django_db


def test_survey_save_invalidates_cache(monkeypatch, draft_survey):
    delete_calls = []
    monkeypatch.setattr(
        survey_signals.REDIS_CLIENT,
        'delete',
        lambda key: delete_calls.append(key),
    )

    draft_survey.title = 'Updated Title'
    draft_survey.save()

    assert f'survey:{draft_survey.id}' in delete_calls


def test_survey_delete_invalidates_cache(monkeypatch, draft_survey):
    delete_calls = []
    survey_id = draft_survey.id
    monkeypatch.setattr(
        survey_signals.REDIS_CLIENT,
        'delete',
        lambda key: delete_calls.append(key),
    )

    draft_survey.delete()

    assert f'survey:{survey_id}' in delete_calls


def test_section_save_invalidates_survey_cache(monkeypatch, draft_survey):
    delete_calls = []
    monkeypatch.setattr(
        survey_signals.REDIS_CLIENT,
        'delete',
        lambda key: delete_calls.append(key),
    )

    section = Section.objects.create(survey=draft_survey, title='Section 1', order=1)

    assert f'survey:{section.survey_id}' in delete_calls


def test_field_save_invalidates_survey_cache(monkeypatch, draft_survey):
    delete_calls = []
    monkeypatch.setattr(
        survey_signals.REDIS_CLIENT,
        'delete',
        lambda key: delete_calls.append(key),
    )
    section = Section.objects.create(survey=draft_survey, title='Section 1', order=1)

    field = Field.objects.create(
        section=section,
        label='Q1',
        field_type=FieldType.TEXT,
        order=1,
    )

    assert f'survey:{field.section.survey_id}' in delete_calls
