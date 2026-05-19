from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status

from surveys_app.models import Field, FieldType, Section, Survey, SurveyStatus


pytestmark = pytest.mark.django_db


def _builder_payload(title='Customer Experience Survey'):
    return {
        'title': title,
        'description': 'Quarterly customer feedback collection',
        'sections': [
            {
                'title': 'Profile',
                'order': 1,
                'fields': [
                    {
                        'label': 'Full name',
                        'field_type': FieldType.TEXT,
                        'order': 1,
                        'is_required': True,
                    },
                    {
                        'label': 'Email',
                        'field_type': FieldType.EMAIL,
                        'order': 2,
                        'is_required': False,
                    },
                ],
            },
            {
                'title': 'Feedback',
                'order': 2,
                'fields': [
                    {
                        'label': 'Satisfaction',
                        'field_type': FieldType.RATING,
                        'order': 1,
                        'is_required': True,
                    }
                ],
            },
        ],
    }


def test_admin_can_list_surveys(api_client, admin_user):
    older = Survey.objects.create(title='Older Survey', created_by=admin_user)
    newer = Survey.objects.create(title='Newer Survey', created_by=admin_user)

    api_client.force_authenticate(user=admin_user)
    response = api_client.get(reverse('surveys_dashboard:survey-list-create'))

    assert response.status_code == 200
    assert response.data['status'] == 200
    assert response.data['total_number_of_objects'] == 2
    assert [item['id'] for item in response.data['results']] == [str(newer.id), str(older.id)]


def test_list_requires_auth(api_client):
    response = api_client.get(reverse('surveys_dashboard:survey-list-create'))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['message'] == 'Authentication credentials were not provided.'


def test_list_is_paginated(api_client, admin_user):
    for index in range(15):
        Survey.objects.create(title=f'Survey {index}', created_by=admin_user)

    api_client.force_authenticate(user=admin_user)
    response = api_client.get(reverse('surveys_dashboard:survey-list-create'))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 15
    assert response.data['count_items_in_page'] == 10
    assert response.data['next'] is not None


def test_admin_can_create_survey_with_nested_sections_and_fields(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-list-create'),
        _builder_payload(),
        format='json',
    )

    assert response.status_code == 201
    assert response.data['message'] == 'Survey created successfully.'
    assert response.data['status'] == SurveyStatus.DRAFT
    assert response.data['created_by'] == admin_user.id
    assert Survey.objects.count() == 1

    survey = Survey.objects.get(id=response.data['id'])
    assert survey.title == 'Customer Experience Survey'
    assert survey.status == SurveyStatus.DRAFT
    assert survey.sections.count() == 2
    assert Section.objects.count() == 2
    assert Field.objects.filter(section__survey=survey).count() == 3


def test_create_minimal_survey_defaults_to_draft(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-list-create'),
        {'title': 'Minimal Survey'},
        format='json',
    )

    survey = Survey.objects.get(id=response.data['id'])
    assert response.status_code == status.HTTP_201_CREATED
    assert survey.status == SurveyStatus.DRAFT
    assert survey.created_by == admin_user


def test_create_conditions_stripped_from_sections(api_client, admin_user):
    payload = {
        'title': 'Conditions Survey',
        'sections': [
            {
                'title': 'Section 1',
                'order': 1,
                'conditions': {'conditions': [{'field_id': 'abc', 'operator': 'eq', 'value': 'Yes'}]},
                'fields': [
                    {'label': 'Q1', 'field_type': FieldType.TEXT, 'order': 1, 'is_required': True}
                ],
            }
        ],
    }
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(reverse('surveys_dashboard:survey-list-create'), payload, format='json')

    survey = Survey.objects.get(id=response.data['id'])
    assert response.status_code == status.HTTP_201_CREATED
    assert survey.sections.get().conditions is None


def test_create_conditions_stripped_from_fields(api_client, admin_user):
    payload = {
        'title': 'Field Conditions Survey',
        'sections': [
            {
                'title': 'Section 1',
                'order': 1,
                'fields': [
                    {
                        'label': 'Q1',
                        'field_type': FieldType.TEXT,
                        'order': 1,
                        'is_required': True,
                        'conditions': {'conditions': [{'field_id': 'abc', 'operator': 'eq', 'value': 'Yes'}]},
                    }
                ],
            }
        ],
    }
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(reverse('surveys_dashboard:survey-list-create'), payload, format='json')

    survey = Survey.objects.get(id=response.data['id'])
    assert response.status_code == status.HTTP_201_CREATED
    assert survey.sections.get().fields.get().conditions is None


def test_create_survey_returns_validation_error_for_missing_title(api_client, admin_user):
    payload = _builder_payload()
    payload.pop('title')
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-list-create'),
        payload,
        format='json',
    )

    assert response.status_code == 400
    assert response.data['message'] == "The field 'title' is required"
    assert response.data['status'] == 400
    assert Survey.objects.count() == 0


def test_non_admin_cannot_create_surveys(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.post(
        reverse('surveys_dashboard:survey-list-create'),
        {'title': 'Forbidden Survey'},
        format='json',
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Survey.objects.count() == 0


def test_admin_can_retrieve_nested_survey_detail(api_client, admin_user, published_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data['id'] == str(published_survey.id)
    assert response.data['title'] == published_survey.title
    sections = sorted(response.data['sections'], key=lambda item: item['order'])
    assert [section['title'] for section in sections] == ['Section 1', 'Section 2 (conditional)']
    assert len(sections[0]['fields']) == 2
    assert len(sections[1]['fields']) == 1


def test_filter_by_status_published(api_client, admin_user):
    Survey.objects.create(title='Draft Survey', status=SurveyStatus.DRAFT, created_by=admin_user)
    published = Survey.objects.create(title='Published Survey', status=SurveyStatus.PUBLISHED, created_by=admin_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'), {'status': SurveyStatus.PUBLISHED})

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(published.id)


def test_filter_by_status_draft(api_client, admin_user):
    draft = Survey.objects.create(title='Draft Survey', status=SurveyStatus.DRAFT, created_by=admin_user)
    Survey.objects.create(title='Published Survey', status=SurveyStatus.PUBLISHED, created_by=admin_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'), {'status': SurveyStatus.DRAFT})

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(draft.id)


def test_filter_by_creator_email(api_client, admin_user, analyst_user):
    admin_survey = Survey.objects.create(title='Admin Survey', created_by=admin_user)
    Survey.objects.create(title='Analyst Survey', created_by=analyst_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-list-create'),
        {'created_by__email': admin_user.email},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(admin_survey.id)


def test_search_by_title(api_client, admin_user):
    matching = Survey.objects.create(title='Customer Survey', created_by=admin_user)
    Survey.objects.create(title='Employee Survey', created_by=admin_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'), {'search': 'Customer'})

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(matching.id)


def test_search_by_description(api_client, admin_user):
    matching = Survey.objects.create(
        title='NPS',
        description='quarterly customer pulse',
        created_by=admin_user,
    )
    Survey.objects.create(title='Annual', description='annual planning', created_by=admin_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'), {'search': 'quarterly'})

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(matching.id)


def test_filter_and_search_combined(api_client, admin_user):
    matching = Survey.objects.create(
        title='Customer Published',
        status=SurveyStatus.PUBLISHED,
        created_by=admin_user,
    )
    Survey.objects.create(title='Customer Draft', status=SurveyStatus.DRAFT, created_by=admin_user)
    Survey.objects.create(title='Employee Published', status=SurveyStatus.PUBLISHED, created_by=admin_user)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-list-create'),
        {'status': SurveyStatus.PUBLISHED, 'search': 'Customer'},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['total_number_of_objects'] == 1
    assert response.data['results'][0]['id'] == str(matching.id)


def test_admin_can_retrieve_draft_survey(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['id'] == str(draft_survey.id)


def test_update_survey_replaces_existing_sections_and_fields(api_client, admin_user, draft_survey):
    old_section = Section.objects.create(survey=draft_survey, title='Old Section', order=1)
    Field.objects.create(
        section=old_section,
        label='Old Question',
        field_type=FieldType.TEXT,
        order=1,
    )
    api_client.force_authenticate(user=admin_user)

    replacement_payload = {
        'title': 'Replacement Survey',
        'description': 'Rebuilt from scratch',
        'status': SurveyStatus.DRAFT,
        'sections': [
            {
                'title': 'Replacement Section',
                'order': 1,
                'fields': [
                    {
                        'label': 'Replacement Question',
                        'field_type': FieldType.NUMBER,
                        'order': 1,
                        'is_required': True,
                    }
                ],
            }
        ],
    }
    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        replacement_payload,
        format='json',
    )

    assert response.status_code == 200
    assert response.data['message'] == 'Survey updated successfully.'
    assert response.data['status'] == SurveyStatus.DRAFT

    draft_survey.refresh_from_db()
    assert draft_survey.title == 'Replacement Survey'
    assert not Section.objects.filter(id=old_section.id).exists()
    assert list(draft_survey.sections.values_list('title', flat=True)) == ['Replacement Section']
    assert list(
        Field.objects.filter(section__survey=draft_survey).values_list('label', flat=True)
    ) == ['Replacement Question']


def test_update_survey_requires_title(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        {'description': 'Missing title'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['message'] == "The field 'title' is required"


def test_put_conditions_preserved(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        {
            'title': 'Conditional Survey',
            'sections': [
                {
                    'title': 'Section 1',
                    'order': 1,
                    'conditions': {'conditions': [{'field_id': 'abc', 'operator': 'eq', 'value': 'Yes'}]},
                    'fields': [
                        {'label': 'Q1', 'field_type': FieldType.TEXT, 'order': 1, 'is_required': True}
                    ],
                }
            ],
        },
        format='json',
    )

    draft_survey.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert draft_survey.sections.get().conditions == {
        'conditions': [{'field_id': 'abc', 'operator': 'eq', 'value': 'Yes'}]
    }


def test_detail_without_trailing_slash_does_not_return_success(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}).rstrip('/'),
        {'title': 'Missing Slash', 'sections': []},
        format='json',
    )

    # With APPEND_SLASH=True (Django default) the server redirects (301).
    # With APPEND_SLASH=False it returns 404.  Either way the call must not
    # silently succeed — a 2xx response here would be a routing bug.
    assert response.status_code not in (200, 201)


def test_partial_update_is_not_allowed(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        {'title': 'Patched Title'},
        format='json',
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_admin_can_delete_survey(api_client, admin_user, draft_survey):
    section = Section.objects.create(survey=draft_survey, title='Delete Me', order=1)
    Field.objects.create(section=section, label='Delete Me Too', field_type=FieldType.TEXT, order=1)
    api_client.force_authenticate(user=admin_user)

    response = api_client.delete(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 200
    assert response.data['message'] == 'Survey deleted successfully.'
    assert response.data['status'] == 200
    assert not Survey.objects.filter(id=draft_survey.id).exists()
    assert Section.objects.count() == 0
    assert Field.objects.count() == 0


def test_publish_requires_at_least_one_section(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 400
    assert str(response.data['message']) == 'Survey must have at least one section.'
    assert draft_survey.status == SurveyStatus.DRAFT


def test_publish_requires_at_least_one_field(api_client, admin_user, draft_survey):
    Section.objects.create(survey=draft_survey, title='Empty Section', order=1)
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 400
    assert str(response.data['message']) == 'Survey must have at least one field.'
    assert draft_survey.status == SurveyStatus.DRAFT


def test_admin_can_publish_valid_survey(api_client, admin_user, draft_survey):
    section = Section.objects.create(survey=draft_survey, title='Launch', order=1)
    Field.objects.create(
        section=section,
        label='Are you ready?',
        field_type=FieldType.RADIO,
        order=1,
        options=['Yes', 'No'],
        is_required=True,
    )
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 200
    assert response.data['message'] == 'Survey published successfully.'
    assert response.data['status'] == SurveyStatus.PUBLISHED
    draft_survey.refresh_from_db()
    assert draft_survey.status == SurveyStatus.PUBLISHED


def test_publish_is_idempotent_for_published_surveys(api_client, admin_user, published_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data['status'] == SurveyStatus.PUBLISHED


def test_non_admin_cannot_access_builder_endpoints(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'))

    assert response.status_code == 403
    assert response.data['message'] == 'You do not have permission to perform this action.'
    assert str(response.data['status']) == '403'


# ── 404 on non-existent resource ──────────────────────────────────────────────

def test_retrieve_nonexistent_survey_returns_404(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': uuid4()})
    )

    assert response.status_code == 404


def test_delete_nonexistent_survey_returns_404(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.delete(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': uuid4()})
    )

    assert response.status_code == 404


def test_publish_nonexistent_survey_returns_404(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': uuid4()})
    )

    assert response.status_code == 404


# ── Role-based access control — viewer and analyst on all builder endpoints ───

def test_viewer_cannot_list_surveys(api_client, viewer_user):
    api_client.force_authenticate(user=viewer_user)

    response = api_client.get(reverse('surveys_dashboard:survey-list-create'))

    assert response.status_code == 403


def test_analyst_cannot_retrieve_survey(api_client, analyst_user, draft_survey):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403


def test_viewer_cannot_retrieve_survey(api_client, viewer_user, draft_survey):
    api_client.force_authenticate(user=viewer_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403


def test_analyst_cannot_update_survey(api_client, analyst_user, draft_survey):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        {'title': 'Forbidden', 'sections': []},
        format='json',
    )

    assert response.status_code == 403


def test_viewer_cannot_update_survey(api_client, viewer_user, draft_survey):
    api_client.force_authenticate(user=viewer_user)

    response = api_client.put(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id}),
        {'title': 'Forbidden', 'sections': []},
        format='json',
    )

    assert response.status_code == 403


def test_analyst_cannot_delete_survey(api_client, analyst_user, draft_survey):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.delete(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403
    assert Survey.objects.filter(id=draft_survey.id).exists()


def test_viewer_cannot_delete_survey(api_client, viewer_user, draft_survey):
    api_client.force_authenticate(user=viewer_user)

    response = api_client.delete(
        reverse('surveys_dashboard:survey-detail', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403
    assert Survey.objects.filter(id=draft_survey.id).exists()


def test_analyst_cannot_publish_survey(api_client, analyst_user, draft_survey):
    api_client.force_authenticate(user=analyst_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403
    draft_survey.refresh_from_db()
    assert draft_survey.status == SurveyStatus.DRAFT


def test_viewer_cannot_publish_survey(api_client, viewer_user, draft_survey):
    api_client.force_authenticate(user=viewer_user)

    response = api_client.patch(
        reverse('surveys_dashboard:survey-publish', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 403
    draft_survey.refresh_from_db()
    assert draft_survey.status == SurveyStatus.DRAFT


# ── GET /dashboard/surveys/{survey_id}/fields/ ────────────────────────────────

def test_fields_list_returns_all_fields_flat_and_ordered(api_client, admin_user, published_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 200
    assert response.data['status'] == 200
    fields = response.data['fields']
    # published_survey has 3 fields: Own a car? + Full Name (section 1), Car Brand (section 2)
    assert len(fields) == 3
    # ordered by section order then field order
    labels = [f['label'] for f in fields]
    assert labels == ['Own a car?', 'Full Name', 'Car Brand']


def test_fields_list_includes_correct_shape_and_section_context(api_client, admin_user, published_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': published_survey.id})
    )

    car_field = next(f for f in response.data['fields'] if f['label'] == 'Own a car?')
    assert set(car_field.keys()) == {'id', 'label', 'field_type', 'options', 'section_title', 'section_order', 'order'}
    assert car_field['field_type'] == FieldType.RADIO
    assert car_field['options'] == ['Yes', 'No']
    assert car_field['section_title'] == 'Section 1'
    assert car_field['section_order'] == 1

    brand_field = next(f for f in response.data['fields'] if f['label'] == 'Car Brand')
    assert brand_field['section_title'] == 'Section 2 (conditional)'
    assert brand_field['section_order'] == 2


def test_fields_list_returns_empty_list_for_survey_with_no_fields(api_client, admin_user, draft_survey):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': draft_survey.id})
    )

    assert response.status_code == 200
    assert response.data['fields'] == []


def test_fields_list_returns_404_for_nonexistent_survey(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(
        reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': uuid4()})
    )

    assert response.status_code == 404


def test_fields_list_requires_auth(api_client, published_survey):
    response = api_client.get(
        reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': published_survey.id})
    )

    assert response.status_code == 401


def test_fields_list_requires_admin(api_client, analyst_user, viewer_user, published_survey):
    for user in (analyst_user, viewer_user):
        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse('surveys_dashboard:survey-fields-list', kwargs={'survey_id': published_survey.id})
        )
        assert response.status_code == 403
