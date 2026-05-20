from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from surveys_app import signals as survey_signals
from surveys_app.models import (
    Field,
    FieldResponse,
    FieldType,
    MapsTo,
    Respondent,
    Section,
    Survey,
    SurveyResponse,
    SurveyResponseStatus,
    SurveyStatus,
)
from surveys_app.service import RespondentService
from surveys_app.views import respondent_views


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stub_redis(monkeypatch):
    cache = {}
    client = SimpleNamespace(
        get=Mock(side_effect=lambda key: cache.get(key)),
        setex=Mock(side_effect=lambda key, ttl, value: cache.__setitem__(key, value)),
        delete=Mock(side_effect=lambda key: cache.pop(key, None)),
    )
    monkeypatch.setattr(respondent_views, 'REDIS_CLIENT', client)
    monkeypatch.setattr(survey_signals, 'REDIS_CLIENT', client)
    return client


@pytest.fixture
def survey_fields(published_survey):
    fields = list(
        Field.objects.filter(section__survey=published_survey)
        .select_related('section')
        .order_by('section__order', 'order')
    )
    return {
        'car': next(field for field in fields if field.label == 'Own a car?'),
        'full_name': next(field for field in fields if field.label == 'Full Name'),
        'car_brand': next(field for field in fields if field.label == 'Car Brand'),
    }


def public_detail_url(survey):
    return reverse('surveys_public:survey-public-detail', kwargs={'survey_id': survey.id})


def create_session_url(survey):
    return reverse('surveys_public:respondent-session-create', kwargs={'survey_id': survey.id})


def session_detail_url(survey, token):
    return reverse(
        'surveys_public:respondent-session-detail',
        kwargs={'survey_id': survey.id, 'session_token': token},
    )


def submit_url(token):
    return reverse('surveys_public:respondent-submit', kwargs={'session_token': token})


def expired_session_token(survey):
    respondent = Respondent.objects.create()
    payload = {
        'respondent_id': str(respondent.id),
        'survey_id': str(survey.id),
        'exp': datetime.now(tz=timezone.utc) - timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def answer_payload(*answers):
    return {'answers': [{'field_id': str(field.id), 'value': value} for field, value in answers]}


def test_public_detail_returns_published_survey_in_order(api_client, published_survey):
    response = api_client.get(public_detail_url(published_survey))

    assert response.status_code == 200
    assert response.data['id'] == str(published_survey.id)
    assert [section['title'] for section in response.data['sections']] == [
        'Section 1',
        'Section 2 (conditional)',
    ]
    assert [field['label'] for field in response.data['sections'][0]['fields']] == [
        'Own a car?',
        'Full Name',
    ]


def test_public_detail_rejects_draft_and_caches_published_response(
    api_client,
    draft_survey,
    published_survey,
    stub_redis,
):
    draft_response = api_client.get(public_detail_url(draft_survey))
    first_response = api_client.get(public_detail_url(published_survey))
    second_response = api_client.get(public_detail_url(published_survey))

    assert draft_response.status_code == 404
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.data == second_response.data
    assert stub_redis.get.call_count == 3
    assert stub_redis.setex.call_count == 1
    cached_payload = json.loads(
        stub_redis.setex.call_args.args[2]
    )
    assert cached_payload['id'] == str(published_survey.id)


def test_public_detail_returns_not_found_for_unknown_survey(api_client):
    response = api_client.get(
        reverse('surveys_public:survey-public-detail', kwargs={'survey_id': uuid4()})
    )

    assert response.status_code == 404
    assert response.data['message'] == 'Survey not found.'


def test_create_session_returns_token_and_creates_related_rows(
    api_client,
    published_survey,
    survey_fields,
):
    response = api_client.post(
        create_session_url(published_survey),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    assert response.status_code == 200
    assert 'session_token' in response.data
    assert 'survey_response_id' in response.data
    assert Respondent.objects.count() == 1

    survey_response = SurveyResponse.objects.get(id=response.data['survey_response_id'])
    saved_answer = FieldResponse.objects.get(survey_response=survey_response, field=survey_fields['car'])
    assert survey_response.status == SurveyResponseStatus.IN_PROGRESS
    assert saved_answer.value == 'Yes'


def test_create_session_returns_404_for_unknown_or_unpublished_survey(api_client, draft_survey):
    draft_response = api_client.post(create_session_url(draft_survey), data={}, format='json')
    missing_response = api_client.post(
        reverse('surveys_public:respondent-session-create', kwargs={'survey_id': uuid4()}),
        data={},
        format='json',
    )

    assert draft_response.status_code == 404
    assert missing_response.status_code == 404


@override_settings(FIELD_ENCRYPTION_KEY="12345678901234567890123456789012")
def test_resume_returns_saved_answers_and_decrypts_sensitive_fields(
    api_client,
    session_token,
    survey_fields,
    monkeypatch,
):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    sensitive_field = survey_fields['full_name']
    sensitive_field.is_sensitive = True
    sensitive_field.save(update_fields=['is_sensitive'])
    monkeypatch.setattr(
        respondent_views,
        'decrypt_value',
        lambda value: 'Alice' if value == 'encrypted-value' else value,
    )
    RespondentService.save_partial(survey_response, [{'field_id': survey_fields['car'].id, 'value': 'Yes'}])
    FieldResponse.objects.create(
        survey_response=survey_response,
        field=sensitive_field,
        value='encrypted-value',
    )

    response = api_client.get(session_detail_url(survey, token))

    assert response.status_code == 200
    assert response.data['status'] == SurveyResponseStatus.IN_PROGRESS
    assert len(response.data['answers']) == 2
    answers = {item['field_id']: item['value'] for item in response.data['answers']}
    assert answers[str(survey_fields['car'].id)] == 'Yes'
    assert answers[str(sensitive_field.id)] == 'Alice'
    assert FieldResponse.objects.get(survey_response=survey_response, field=sensitive_field).value == 'encrypted-value'


def test_resume_rejects_invalid_or_expired_token(api_client, published_survey):
    invalid_response = api_client.get(session_detail_url(published_survey, 'not-a-jwt'))
    expired_response = api_client.get(
        session_detail_url(published_survey, expired_session_token(published_survey))
    )

    assert invalid_response.status_code == 401
    assert expired_response.status_code == 401


def test_resume_rejects_token_for_different_survey(api_client, published_survey, admin_user):
    other_survey = Survey.objects.create(
        title='Other Survey',
        status='published',
        created_by=admin_user,
    )
    _, token = RespondentService.create_session(published_survey)

    response = api_client.get(session_detail_url(other_survey, token))

    assert response.status_code == 401


def test_autosave_upserts_answers_and_updates_last_saved_at(
    api_client,
    session_token,
    survey_fields,
):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)

    first_response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((survey_fields['car'], 'No')),
        format='json',
    )
    second_response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    survey_response.refresh_from_db()
    saved_answer = FieldResponse.objects.get(survey_response=survey_response, field=survey_fields['car'])
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert survey_response.last_saved_at is not None
    assert FieldResponse.objects.filter(
        survey_response=survey_response,
        field=survey_fields['car'],
    ).count() == 1
    assert saved_answer.value == 'Yes'


def test_autosave_rejects_completed_response(api_client, session_token, survey_fields):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    survey_response.status = SurveyResponseStatus.COMPLETED
    survey_response.save(update_fields=['status'])

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    assert response.status_code == 400
    assert response.data['message'] == 'You have already submitted this survey.'


def test_autosave_rejects_invalid_token(api_client, published_survey, survey_fields):
    response = api_client.post(
        session_detail_url(published_survey, 'not-a-jwt'),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    assert response.status_code == 401
    assert response.data['message'] == 'Session token is invalid or has expired.'


def test_autosave_rejects_value_below_min(api_client, session_token, survey_fields):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Rating',
        field_type=FieldType.RATING,
        order=3,
        validation_rules={'min': 1, 'max': 5},
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, '0')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Rating' in str(response.data['message'])
    assert not FieldResponse.objects.filter(survey_response=survey_response, field=field).exists()


def test_autosave_rejects_value_above_max(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Rating',
        field_type=FieldType.RATING,
        order=3,
        validation_rules={'min': 1, 'max': 5},
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, '10')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Rating' in str(response.data['message'])


def test_autosave_rejects_non_numeric_on_number_field(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Age',
        field_type=FieldType.NUMBER,
        order=3,
        validation_rules={'min': 18},
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, 'abc')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Age' in str(response.data['message'])


def test_autosave_rejects_text_exceeding_max_length(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Nickname',
        field_type=FieldType.TEXT,
        order=3,
        validation_rules={'max_length': 5},
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, 'toolongvalue')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Nickname' in str(response.data['message'])


def test_autosave_rejects_checkbox_too_many_selections(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Preferences',
        field_type=FieldType.CHECKBOX,
        order=3,
        options=['A', 'B', 'C'],
        validation_rules={'max_selections': 2},
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, '["A","B","C"]')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Preferences' in str(response.data['message'])


def test_submit_completes_response_and_populates_profile(
    api_client,
    session_token,
    survey_fields,
):
    respondent, token, survey = session_token

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
        ),
        format='json',
    )

    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    respondent.refresh_from_db()
    assert response.status_code == 200
    assert survey_response.status == SurveyResponseStatus.COMPLETED
    assert survey_response.submitted_at is not None
    assert respondent.full_name == 'Alice Example'


def test_submit_can_populate_respondent_email(
    api_client,
    session_token,
    survey_fields,
):
    respondent, token, survey = session_token
    first_section = survey.sections.get(order=1)
    email_field = Field.objects.create(
        section=first_section,
        label='Email',
        field_type=FieldType.EMAIL,
        order=3,
        maps_to=MapsTo.RESPONDENT_EMAIL,
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (email_field, 'alice@example.com'),
        ),
        format='json',
    )

    respondent.refresh_from_db()
    assert response.status_code == 200
    assert respondent.email == 'alice@example.com'


def test_submit_rejects_invalid_value(api_client, session_token, survey_fields):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Score',
        field_type=FieldType.NUMBER,
        order=3,
        validation_rules={'min': 10, 'max': 20},
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (field, '5'),
        ),
        format='json',
    )

    assert response.status_code == 400
    assert 'Score' in str(response.data['message'])


def test_submit_valid_values_with_rules(api_client, session_token, survey_fields):
    respondent, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Score',
        field_type=FieldType.NUMBER,
        order=3,
        validation_rules={'min': 10, 'max': 20},
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (field, '15'),
        ),
        format='json',
    )

    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    assert response.status_code == 200
    assert survey_response.status == SurveyResponseStatus.COMPLETED


def test_submit_requires_missing_active_fields_but_not_inactive_conditional_fields(
    api_client,
    session_token,
    survey_fields,
):
    _, token, _ = session_token

    missing_required = api_client.post(
        submit_url(token),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    assert missing_required.status_code == 400
    assert missing_required.data['message'] == 'Field "Full Name" is required.'

    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    survey_response.field_responses.all().delete()

    inactive_required = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Bob Example'),
        ),
        format='json',
    )

    assert inactive_required.status_code == 200
    assert not FieldResponse.objects.filter(
        survey_response=survey_response,
        field=survey_fields['car_brand'],
    ).exists()


def test_submit_merges_existing_autosaved_answers_and_rejects_second_submission(
    api_client,
    session_token,
    survey_fields,
):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)

    RespondentService.save_partial(
        survey_response,
        [{'field_id': survey_fields['car'].id, 'value': 'No'}],
    )

    first_response = api_client.post(
        submit_url(token),
        data=answer_payload((survey_fields['full_name'], 'Merged User')),
        format='json',
    )
    second_response = api_client.post(
        submit_url(token),
        data=answer_payload((survey_fields['full_name'], 'Merged User')),
        format='json',
    )

    survey_response.refresh_from_db()
    stored_answers = {
        field_response.field_id: field_response.value
        for field_response in FieldResponse.objects.filter(survey_response=survey_response)
    }
    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert stored_answers[survey_fields['car'].id] == 'No'
    assert stored_answers[survey_fields['full_name'].id] == 'Merged User'


def test_submit_rejects_invalid_token(api_client, survey_fields):
    response = api_client.post(
        submit_url('not-a-jwt'),
        data=answer_payload((survey_fields['car'], 'Yes')),
        format='json',
    )

    assert response.status_code == 401
    assert response.data['message'] == 'Session token is invalid or has expired.'


# ── Archived survey — public endpoint must treat it like draft ────────────────

def test_public_detail_archived_survey_returns_404(api_client, admin_user):
    archived_survey = Survey.objects.create(
        title='Archived Survey',
        status=SurveyStatus.ARCHIVED,
        created_by=admin_user,
    )

    response = api_client.get(public_detail_url(archived_survey))

    assert response.status_code == 404


# ── Autosave edge cases ───────────────────────────────────────────────────────

def test_autosave_empty_answers_list_is_noop(api_client, session_token):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)

    response = api_client.post(
        session_detail_url(survey, token),
        data={'answers': []},
        format='json',
    )

    assert response.status_code == 200
    assert not FieldResponse.objects.filter(survey_response=survey_response).exists()


def test_autosave_does_not_save_field_from_different_survey(api_client, session_token, admin_user):
    respondent, token, survey = session_token
    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)

    other_survey = Survey.objects.create(
        title='Other Survey',
        status=SurveyStatus.PUBLISHED,
        created_by=admin_user,
    )
    other_section = Section.objects.create(survey=other_survey, title='S1', order=1)
    foreign_field = Field.objects.create(
        section=other_section,
        label='Foreign Field',
        field_type=FieldType.TEXT,
        order=1,
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((foreign_field, 'injected')),
        format='json',
    )

    assert response.status_code == 200
    assert not FieldResponse.objects.filter(
        survey_response=survey_response,
        field=foreign_field,
    ).exists()


# ── maps_to — phone number ────────────────────────────────────────────────────

def test_submit_with_no_payload_fails_for_required_field(api_client, session_token, survey_fields):
    """POST {} with no autosaved answers — required fields are all missing → 400."""
    _, token, _ = session_token

    response = api_client.post(submit_url(token), data={}, format='json')

    assert response.status_code == 400
    assert 'is required' in str(response.data['message'])


def test_submit_null_and_blank_values_rejected_by_serializer(api_client, session_token, survey_fields):
    """Serializer must block null and blank values before they reach the required-field check."""
    _, token, survey = session_token

    null_response = api_client.post(
        submit_url(token),
        data={'answers': [{'field_id': str(survey_fields['car'].id), 'value': None}]},
        format='json',
    )
    blank_response = api_client.post(
        submit_url(token),
        data={'answers': [{'field_id': str(survey_fields['car'].id), 'value': ''}]},
        format='json',
    )
    whitespace_response = api_client.post(
        submit_url(token),
        data={'answers': [{'field_id': str(survey_fields['car'].id), 'value': '   '}]},
        format='json',
    )

    assert null_response.status_code == 400
    assert blank_response.status_code == 400
    assert whitespace_response.status_code == 400


def test_submit_integer_zero_counts_as_valid_required_answer(api_client, session_token, survey_fields):
    """Integer 0 is coerced to '0' by the serializer — non-empty string passes the required check."""
    respondent, token, survey = session_token
    first_section = survey.sections.get(order=1)
    score_field = Field.objects.create(
        section=first_section,
        label='Score',
        field_type=FieldType.NUMBER,
        order=3,
        is_required=True,
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (score_field, 0),
        ),
        format='json',
    )

    survey_response = SurveyResponse.objects.get(survey=survey, respondent=respondent)
    assert response.status_code == 200
    assert survey_response.status == SurveyResponseStatus.COMPLETED
    stored = FieldResponse.objects.get(survey_response=survey_response, field=score_field)
    assert stored.value == '0'


def test_submit_zero_that_violates_min_rule_gives_validation_error_not_required_error(
    api_client, session_token, survey_fields,
):
    """'0' passes the required check (non-empty) but is caught by the min validation rule.
    The error must mention the rule, not 'is required'."""
    _, token, survey = session_token
    first_section = survey.sections.get(order=1)
    rating_field = Field.objects.create(
        section=first_section,
        label='Rating',
        field_type=FieldType.RATING,
        order=3,
        is_required=True,
        validation_rules={'min': 1, 'max': 5},
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (rating_field, '0'),
        ),
        format='json',
    )

    assert response.status_code == 400
    message = str(response.data['message'])
    assert 'Rating' in message
    assert 'required' not in message.lower()


def test_submit_populates_respondent_phone(api_client, session_token, survey_fields):
    respondent, token, survey = session_token
    first_section = survey.sections.get(order=1)
    phone_field = Field.objects.create(
        section=first_section,
        label='Phone',
        field_type=FieldType.TEXT,
        order=3,
        maps_to=MapsTo.RESPONDENT_PHONE,
    )

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'No'),
            (survey_fields['full_name'], 'Alice Example'),
            (phone_field, '+1-555-0100'),
        ),
        format='json',
    )

    respondent.refresh_from_db()
    assert response.status_code == 200
    assert respondent.phone == '+1-555-0100'


# ── Options validation — integration ─────────────────────────────────────────

def test_autosave_rejects_radio_value_not_in_options(api_client, session_token, survey_fields):
    _, token, survey = session_token

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((survey_fields['car'], 'Maybe')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Own a car?' in str(response.data['message'])


def test_submit_rejects_radio_value_not_in_options(api_client, session_token, survey_fields):
    _, token, _ = session_token

    response = api_client.post(
        submit_url(token),
        data=answer_payload(
            (survey_fields['car'], 'Perhaps'),
            (survey_fields['full_name'], 'Alice Example'),
        ),
        format='json',
    )

    assert response.status_code == 400
    assert 'Own a car?' in str(response.data['message'])


def test_autosave_rejects_checkbox_selection_not_in_options(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Preferences',
        field_type=FieldType.CHECKBOX,
        order=3,
        options=['A', 'B', 'C'],
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, '["A", "D"]')),
        format='json',
    )

    assert response.status_code == 400
    assert 'Preferences' in str(response.data['message'])


def test_autosave_accepts_any_value_for_field_with_no_options(api_client, session_token):
    _, token, survey = session_token
    field = Field.objects.create(
        section=survey.sections.get(order=1),
        label='Open Choice',
        field_type=FieldType.RADIO,
        order=3,
        options=None,
    )

    response = api_client.post(
        session_detail_url(survey, token),
        data=answer_payload((field, 'absolutely anything')),
        format='json',
    )

    assert response.status_code == 200
