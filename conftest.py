import pytest
from rest_framework.test import APIClient

from accounts_app.models import User
from surveys_app.models import Field, FieldType, MapsTo, Section, Survey, SurveyResponse, SurveyStatus


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='admin',
        email='admin@test.com',
        password='Pass1234!',
        role='admin',
    )


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        username='analyst',
        email='analyst@test.com',
        password='Pass1234!',
        role='analyst',
    )


@pytest.fixture
def viewer_user(db):
    return User.objects.create_user(
        username='viewer',
        email='viewer@test.com',
        password='Pass1234!',
        role='data_viewer',
    )


@pytest.fixture
def draft_survey(db, admin_user):
    return Survey.objects.create(
        title='Draft Survey',
        status=SurveyStatus.DRAFT,
        created_by=admin_user,
    )


@pytest.fixture
def published_survey(db, admin_user):
    survey = Survey.objects.create(
        title='Published Survey',
        status=SurveyStatus.PUBLISHED,
        created_by=admin_user,
    )
    first_section = Section.objects.create(
        survey=survey,
        title='Section 1',
        order=1,
        conditions=None,
    )
    car_field = Field.objects.create(
        section=first_section,
        label='Own a car?',
        field_type=FieldType.RADIO,
        order=1,
        is_required=True,
        options=['Yes', 'No'],
    )
    Field.objects.create(
        section=first_section,
        label='Full Name',
        field_type=FieldType.TEXT,
        order=2,
        is_required=True,
        maps_to=MapsTo.RESPONDENT_FULL_NAME,
    )
    second_section = Section.objects.create(
        survey=survey,
        title='Section 2 (conditional)',
        order=2,
        conditions={
            'conditions': [
                {
                    'field_id': str(car_field.id),
                    'operator': 'eq',
                    'value': 'Yes',
                }
            ]
        },
    )
    Field.objects.create(
        section=second_section,
        label='Car Brand',
        field_type=FieldType.DROPDOWN,
        order=1,
        is_required=True,
        options=['Toyota', 'Honda'],
    )
    return survey


@pytest.fixture
def session_token(db, published_survey):
    from surveys_app.service import RespondentService

    respondent, token = RespondentService.create_session(published_survey)
    SurveyResponse.objects.create(survey=published_survey, respondent=respondent)
    return respondent, token, published_survey
