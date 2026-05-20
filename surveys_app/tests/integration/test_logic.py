import pytest

from surveys_app.logic import ConditionalLogicEngine
from surveys_app.models import Field, FieldType, Section, Survey


pytestmark = pytest.mark.django_db


@pytest.fixture
def engine():
    return ConditionalLogicEngine()


@pytest.fixture
def conditional_survey(db, admin_user):
    survey = Survey.objects.create(title="Logic Survey", created_by=admin_user)
    first_section = Section.objects.create(survey=survey, title="Section 1", order=2)
    car_field = Field.objects.create(
        section=first_section,
        label="Own a car?",
        field_type=FieldType.RADIO,
        order=2,
        options=["Yes", "No"],
    )
    always_field = Field.objects.create(
        section=first_section,
        label="Always visible",
        field_type=FieldType.TEXT,
        order=1,
    )
    conditional_field = Field.objects.create(
        section=first_section,
        label="Conditional field",
        field_type=FieldType.TEXT,
        order=3,
        conditions={
            "conditions": [
                {"field_id": str(car_field.id), "operator": "eq", "value": "Yes"},
            ]
        },
    )
    second_section = Section.objects.create(
        survey=survey,
        title="Section 2",
        order=1,
        conditions={
            "conditions": [
                {"field_id": str(car_field.id), "operator": "eq", "value": "Yes"},
            ]
        },
    )
    required_conditional_field = Field.objects.create(
        section=second_section,
        label="Required conditional field",
        field_type=FieldType.TEXT,
        order=2,
        is_required=True,
    )
    section_two_first_field = Field.objects.create(
        section=second_section,
        label="Section 2 first field",
        field_type=FieldType.TEXT,
        order=1,
    )
    return {
        "survey": survey,
        "car_field": car_field,
        "always_field": always_field,
        "conditional_field": conditional_field,
        "required_conditional_field": required_conditional_field,
        "section_two_first_field": section_two_first_field,
    }


def test_no_conditions_all_fields_active(engine, admin_user):
    survey = Survey.objects.create(title="No Conditions Survey", created_by=admin_user)
    first_section = Section.objects.create(survey=survey, title="Section A", order=2)
    second_section = Section.objects.create(survey=survey, title="Section B", order=1)
    field_a = Field.objects.create(
        section=first_section,
        label="Field A",
        field_type=FieldType.TEXT,
        order=2,
    )
    field_b = Field.objects.create(
        section=first_section,
        label="Field B",
        field_type=FieldType.TEXT,
        order=1,
    )
    field_c = Field.objects.create(
        section=second_section,
        label="Field C",
        field_type=FieldType.TEXT,
        order=1,
    )

    active_fields = engine.get_active_fields(survey, {})

    assert active_fields == [field_c, field_b, field_a]


def test_section_condition_fails_skips_entire_section(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["section_two_first_field"] not in active_fields
    assert conditional_survey["required_conditional_field"] not in active_fields
    assert conditional_survey["always_field"] in active_fields


def test_section_condition_passes_includes_fields(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "Yes"},
    )

    assert conditional_survey["section_two_first_field"] in active_fields
    assert conditional_survey["required_conditional_field"] in active_fields


def test_field_condition_fails_skips_single_field(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["conditional_field"] not in active_fields
    assert conditional_survey["always_field"] in active_fields
    assert conditional_survey["car_field"] in active_fields


def test_required_inactive_field_not_returned(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["required_conditional_field"] not in active_fields


def test_fields_ordered_by_section_then_field_order(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "Yes"},
    )

    assert active_fields == [
        conditional_survey["section_two_first_field"],
        conditional_survey["required_conditional_field"],
        conditional_survey["always_field"],
        conditional_survey["car_field"],
        conditional_survey["conditional_field"],
    ]
