import pytest

from surveys_app.logic import ConditionalLogicEngine
from surveys_app.models import Field, FieldType, Section, Survey


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


@pytest.mark.parametrize(
    ("operator", "field_value", "condition_value", "expected"),
    [
        ("eq", "Yes", "Yes", True),
        ("eq", "Yes", "No", False),
        ("neq", "Yes", "No", True),
        ("neq", "Yes", "Yes", False),
        ("gt", "10", "5", True),
        ("gt", "3", "5", False),
        ("gt", "5", "5", False),
        ("lt", "3", "5", True),
        ("lt", "10", "5", False),
        ("gte", "5", "5", True),
        ("gte", "6", "5", True),
        ("gte", "4", "5", False),
        ("lte", "5", "5", True),
        ("lte", "4", "5", True),
        ("lte", "6", "5", False),
        ("contains", "hello world", "hello", True),
        ("contains", "hello world", "xyz", False),
        ("in", "Yes", ["Yes", "No"], True),
        ("in", "Maybe", ["Yes", "No"], False),
        ("exists", "x", "x", False),
        ("gt", "abc", "5", False),
        ("lt", "abc", "5", False),
        ("contains", 42, "x", False),
        ("in", "x", 42, False),
        ("eq", "", "", True),
        ("eq", "yes", "Yes", False),
    ],
)
def test_evaluate_operator(engine, operator, field_value, condition_value, expected):
    assert engine.evaluate_operator(operator, field_value, condition_value) is expected


@pytest.mark.parametrize(
    ("conditions", "answers", "expected"),
    [
        (None, {}, True),
        ({}, {}, True),
        ({"conditions": []}, {}, True),
        (
            {"conditions": [{"field_id": "id", "operator": "eq", "value": "Yes"}]},
            {"id": "Yes"},
            True,
        ),
        (
            {
                "conditions": [
                    {"field_id": "id", "operator": "eq", "value": "Yes"},
                    {"field_id": "id", "operator": "eq", "value": "No"},
                ]
            },
            {"id": "Yes"},
            False,
        ),
        (
            {"conditions": [{"field_id": "missing", "operator": "eq", "value": "Yes"}]},
            {},
            False,
        ),
        (
            {
                "conditions": [
                    {"field_id": "car", "operator": "eq", "value": "Yes"},
                    {"field_id": "age", "operator": "gte", "value": "18"},
                    {"field_id": "country", "operator": "contains", "value": "Egypt"},
                ]
            },
            {"car": "Yes", "age": "25", "country": "Cairo, Egypt"},
            True,
        ),
    ],
)
def test_evaluate(engine, conditions, answers, expected):
    assert engine.evaluate(conditions, answers) is expected


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_section_condition_fails_skips_entire_section(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["section_two_first_field"] not in active_fields
    assert conditional_survey["required_conditional_field"] not in active_fields
    assert conditional_survey["always_field"] in active_fields


@pytest.mark.django_db
def test_section_condition_passes_includes_fields(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "Yes"},
    )

    assert conditional_survey["section_two_first_field"] in active_fields
    assert conditional_survey["required_conditional_field"] in active_fields


@pytest.mark.django_db
def test_field_condition_fails_skips_single_field(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["conditional_field"] not in active_fields
    assert conditional_survey["always_field"] in active_fields
    assert conditional_survey["car_field"] in active_fields


@pytest.mark.django_db
def test_required_inactive_field_not_returned(engine, conditional_survey):
    active_fields = engine.get_active_fields(
        conditional_survey["survey"],
        {str(conditional_survey["car_field"].id): "No"},
    )

    assert conditional_survey["required_conditional_field"] not in active_fields


@pytest.mark.django_db
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

