from types import SimpleNamespace

import pytest
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from helper_files.custom_exceptions import InvalidSessionTokenException
from surveys_app.models import FieldType
from surveys_app.service import RespondentService, decrypt_value, encrypt_value, validate_field_value


@override_settings(FIELD_ENCRYPTION_KEY="12345678901234567890123456789012")
def test_encrypt_decrypt_roundtrip():
    value = "sensitive data"

    encrypted = encrypt_value(value)

    assert encrypted != value
    assert decrypt_value(encrypted) == value


@override_settings(FIELD_ENCRYPTION_KEY="12345678901234567890123456789012")
def test_encrypt_produces_different_output():
    assert encrypt_value("hello") != "hello"


@override_settings(FIELD_ENCRYPTION_KEY="12345678901234567890123456789012")
def test_decrypt_invalid_token_returns_value():
    assert decrypt_value("not-encrypted-garbage") == "not-encrypted-garbage"


@override_settings(FIELD_ENCRYPTION_KEY="")
def test_no_key_configured_passthrough():
    assert encrypt_value("hello") == "hello"
    assert decrypt_value("hello") == "hello"


def test_decode_garbage_string():
    with pytest.raises(InvalidSessionTokenException):
        RespondentService.decode_session("not-a-jwt")


def _field(label="Test Field", field_type=FieldType.TEXT, validation_rules=None, options=None):
    return SimpleNamespace(
        label=label,
        field_type=field_type,
        validation_rules=validation_rules,
        options=options,
    )


def test_validate_number_below_min():
    field = _field("Birth Year", FieldType.NUMBER, {"min": 1990})

    with pytest.raises(ValidationError, match='Birth Year'):
        validate_field_value(field, "1800")


def test_validate_number_above_max():
    field = _field("Rating", FieldType.RATING, {"max": 5})

    with pytest.raises(ValidationError, match='Rating'):
        validate_field_value(field, "10")


def test_validate_number_at_boundary():
    min_field = _field("Birth Year", FieldType.NUMBER, {"min": 1990})
    max_field = _field("Rating", FieldType.RATING, {"max": 5})

    validate_field_value(min_field, "1990")
    validate_field_value(max_field, "5")


def test_validate_non_numeric_on_number_field():
    field = _field("Age", FieldType.NUMBER, {"min": 1})

    with pytest.raises(ValidationError, match='Age'):
        validate_field_value(field, "abc")


def test_validate_text_below_min_length():
    field = _field("Short Bio", FieldType.TEXT, {"min_length": 5})

    with pytest.raises(ValidationError, match='Short Bio'):
        validate_field_value(field, "Hi")


def test_validate_text_above_max_length():
    field = _field("Description", FieldType.TEXTAREA, {"max_length": 10})

    with pytest.raises(ValidationError, match='Description'):
        validate_field_value(field, "a" * 11)


def test_validate_text_regex_match():
    field = _field("Digits Only", FieldType.TEXT, {"regex": "^[0-9]+$"})

    validate_field_value(field, "12345")


def test_validate_text_regex_no_match():
    field = _field("Digits Only", FieldType.TEXT, {"regex": "^[0-9]+$"})

    with pytest.raises(ValidationError, match='Digits Only'):
        validate_field_value(field, "abc")


def test_validate_checkbox_below_min_selections():
    field = _field("Choices", FieldType.CHECKBOX, {"min_selections": 2})

    with pytest.raises(ValidationError, match='Choices'):
        validate_field_value(field, '["A"]')


def test_validate_checkbox_above_max_selections():
    field = _field("Choices", FieldType.CHECKBOX, {"max_selections": 2})

    with pytest.raises(ValidationError, match='Choices'):
        validate_field_value(field, '["A","B","C"]')


def test_validate_date_before_min_date():
    field = _field("Start Date", FieldType.DATE, {"min_date": "2020-01-01"})

    with pytest.raises(ValidationError, match='Start Date'):
        validate_field_value(field, "2019-12-31")


def test_validate_date_after_max_date():
    field = _field("End Date", FieldType.DATE, {"max_date": "2030-12-31"})

    with pytest.raises(ValidationError, match='End Date'):
        validate_field_value(field, "2031-01-01")


def test_validate_no_rules_passes_anything():
    validate_field_value(_field(validation_rules=None), "any value")


def test_validate_empty_value_skipped():
    validate_field_value(_field(validation_rules={"min_length": 5}), "")


def test_validate_unknown_rule_key_ignored():
    validate_field_value(_field(validation_rules={"unknown_key": 99}), "anything")


# ── Options validation — radio / dropdown / checkbox ─────────────────────────

def test_validate_radio_rejects_value_not_in_options():
    field = _field('Car Choice', FieldType.RADIO, options=['Yes', 'No'])
    with pytest.raises(ValidationError, match='Car Choice'):
        validate_field_value(field, 'Maybe')


def test_validate_radio_accepts_value_in_options():
    validate_field_value(_field('Car Choice', FieldType.RADIO, options=['Yes', 'No']), 'Yes')


def test_validate_dropdown_rejects_value_not_in_options():
    field = _field('Brand', FieldType.DROPDOWN, options=['Toyota', 'Honda'])
    with pytest.raises(ValidationError, match='Brand'):
        validate_field_value(field, 'Ferrari')


def test_validate_dropdown_accepts_value_in_options():
    validate_field_value(_field('Brand', FieldType.DROPDOWN, options=['Toyota', 'Honda']), 'Honda')


def test_validate_options_not_enforced_when_field_has_no_options():
    field = _field('Free Choice', FieldType.RADIO, options=None)
    validate_field_value(field, 'anything goes')


def test_validate_checkbox_rejects_selection_not_in_options():
    field = _field('Prefs', FieldType.CHECKBOX, options=['A', 'B', 'C'])
    with pytest.raises(ValidationError, match='Prefs'):
        validate_field_value(field, '["A", "D"]')


def test_validate_checkbox_accepts_all_valid_selections():
    validate_field_value(_field('Prefs', FieldType.CHECKBOX, options=['A', 'B', 'C']), '["A", "C"]')


def test_validate_checkbox_options_checked_before_min_selections():
    field = _field('Prefs', FieldType.CHECKBOX, validation_rules={'min_selections': 2}, options=['A', 'B', 'C'])
    with pytest.raises(ValidationError, match='invalid selection'):
        validate_field_value(field, '["D"]')


def test_validate_checkbox_no_options_still_enforces_min_selections():
    field = _field('Prefs', FieldType.CHECKBOX, validation_rules={'min_selections': 2}, options=None)
    with pytest.raises(ValidationError, match='Prefs'):
        validate_field_value(field, '["A"]')
