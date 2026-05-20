import pytest

from surveys_app.logic import ConditionalLogicEngine


@pytest.fixture
def engine():
    return ConditionalLogicEngine()


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
