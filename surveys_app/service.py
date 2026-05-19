import base64
import jwt
from datetime import datetime, timezone, timedelta

from cryptography.fernet import Fernet, InvalidToken
from rest_framework.exceptions import ValidationError

from django.conf import settings
from helper_files.status_code import StatusCode
from surveys_app.models import SurveyStatus, Section, Field


class SurveyService:
    @staticmethod
    def create_survey(serializer):
        """Args: serializer (validated SurveySerializer). Returns: created Survey instance."""
        from django.db import transaction
        sections_data = serializer.validated_data.pop('sections', [])
        with transaction.atomic():
            survey = serializer.save()
            for section_data in sections_data:
                fields_data = section_data.pop('fields', [])
                section_data.pop('id', None)
                section_data['conditions'] = None  # field UUIDs don't exist yet — conditions set via PUT
                section = Section.objects.create(survey=survey, **section_data)
                for field_data in fields_data:
                    field_data.pop('id', None)
                    field_data['conditions'] = None  # same reason
                    Field.objects.create(section=section, **field_data)
        return survey

    @staticmethod
    def update_survey(serializer):
        """Args: serializer (validated SurveySerializer).
        Full replace: sections/fields not in payload are deleted. Returns: updated Survey."""
        from django.db import transaction
        sections_data = serializer.validated_data.pop('sections', [])
        with transaction.atomic():
            # Update top-level survey fields
            survey = serializer.save()
            # Full replace: delete all existing sections (cascades to fields)
            survey.sections.all().delete()
            # Recreate from payload
            for section_data in sections_data:
                fields_data = section_data.pop('fields', [])
                section_data.pop('id', None)  # ignore ids — full replace
                section = Section.objects.create(survey=survey, **section_data)
                for field_data in fields_data:
                    field_data.pop('id', None)
                    Field.objects.create(section=section, **field_data)
        return survey

    @staticmethod
    def publish_survey(survey):
        """Args: survey (Survey instance). Returns: updated survey instance."""
        sections = survey.sections.prefetch_related('fields').all()
        if not sections.exists():
            raise ValidationError(detail={'message': 'Survey must have at least one section.', 'status': StatusCode.bad_request})
        has_field = any(s.fields.exists() for s in sections)
        if not has_field:
            raise ValidationError(detail={'message': 'Survey must have at least one field.', 'status': StatusCode.bad_request})
        survey.status = SurveyStatus.PUBLISHED
        survey.save()
        return survey


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        return None
    # Fernet requires 32 url-safe base64-encoded bytes
    # If key is a plain string, encode it to 32 bytes
    key_bytes = key.encode() if isinstance(key, str) else key
    # Pad/truncate and base64-encode if not already base64
    try:
        return Fernet(key_bytes)
    except Exception:
        # Try encoding as base64
        padded = key_bytes[:32].ljust(32, b'=')
        return Fernet(base64.urlsafe_b64encode(padded))


def encrypt_value(value: str) -> str:
    f = _get_fernet()
    if not f:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    f = _get_fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value  # return as-is if decryption fails


def validate_field_value(field, value):
    """Validates value against field.options and field.validation_rules. Raises ValidationError on failure.
    Args: field (Field instance), value (str). Returns: None."""
    import re
    import json as _json
    from rest_framework.exceptions import ValidationError as DRFValidationError
    from helper_files.status_code import StatusCode

    if value is None or value == '':
        return

    rules = field.validation_rules or {}
    field_type = field.field_type

    # ── Options validation (enforced whenever field.options is set) ───────────

    if field_type in ('radio', 'dropdown'):
        if field.options and value not in field.options:
            raise DRFValidationError(detail={
                'message': f'Field "{field.label}" must be one of: {", ".join(str(o) for o in field.options)}.',
                'status': StatusCode.bad_request,
            })

    elif field_type == 'checkbox':
        try:
            selections = _json.loads(value) if isinstance(value, str) else value
            if not isinstance(selections, list):
                selections = [selections]
        except (_json.JSONDecodeError, TypeError):
            selections = [value]

        if field.options:
            invalid = [s for s in selections if s not in field.options]
            if invalid:
                raise DRFValidationError(detail={
                    'message': f'Field "{field.label}" contains invalid selection(s): {", ".join(str(s) for s in invalid)}.',
                    'status': StatusCode.bad_request,
                })

        count = len(selections)
        if 'min_selections' in rules and count < int(rules['min_selections']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" requires at least {rules["min_selections"]} selection(s).', 'status': StatusCode.bad_request})
        if 'max_selections' in rules and count > int(rules['max_selections']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" allows at most {rules["max_selections"]} selection(s).', 'status': StatusCode.bad_request})
        return  # checkbox fully handled above

    # ── Validation rules for non-choice field types ───────────────────────────

    if not rules:
        return

    if field_type in ('number', 'rating'):
        try:
            num = float(value)
        except (ValueError, TypeError):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be a number.', 'status': StatusCode.bad_request})
        if 'min' in rules and num < float(rules['min']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be at least {rules["min"]}.', 'status': StatusCode.bad_request})
        if 'max' in rules and num > float(rules['max']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be at most {rules["max"]}.', 'status': StatusCode.bad_request})

    elif field_type in ('text', 'textarea', 'email', 'url'):
        str_val = str(value)
        if 'min_length' in rules and len(str_val) < int(rules['min_length']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be at least {rules["min_length"]} characters.', 'status': StatusCode.bad_request})
        if 'max_length' in rules and len(str_val) > int(rules['max_length']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be at most {rules["max_length"]} characters.', 'status': StatusCode.bad_request})
        if 'regex' in rules:
            try:
                if not re.match(rules['regex'], str_val):
                    raise DRFValidationError(detail={'message': f'Field "{field.label}" format is invalid.', 'status': StatusCode.bad_request})
            except re.error:
                pass  # malformed regex in rules — skip silently

    elif field_type in ('date', 'datetime'):
        str_val = str(value)
        if 'min_date' in rules and str_val < str(rules['min_date']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be on or after {rules["min_date"]}.', 'status': StatusCode.bad_request})
        if 'max_date' in rules and str_val > str(rules['max_date']):
            raise DRFValidationError(detail={'message': f'Field "{field.label}" must be on or before {rules["max_date"]}.', 'status': StatusCode.bad_request})


# ---------------------------------------------------------------------------
# RespondentService
# ---------------------------------------------------------------------------

class RespondentService:

    @staticmethod
    def create_session(survey):
        """Args: survey (Survey instance). Returns: (Respondent, jwt_token_str)."""
        from surveys_app.models import Respondent
        respondent = Respondent.objects.create()
        payload = {
            'respondent_id': str(respondent.id),
            'survey_id': str(survey.id),
            'exp': datetime.now(tz=timezone.utc) + timedelta(days=7),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        return respondent, token

    @staticmethod
    def decode_session(token):
        """Args: token (str). Returns: (respondent_id str, survey_id str).
        Raises: InvalidSessionTokenException if invalid/expired."""
        from helper_files.custom_exceptions import InvalidSessionTokenException
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload['respondent_id'], payload['survey_id']
        except Exception:
            raise InvalidSessionTokenException()

    @staticmethod
    def save_partial(survey_response, answers):
        """Args: survey_response (SurveyResponse), answers (list of {field_id, value} dicts).
        Upserts FieldResponse rows. Encrypts sensitive fields."""
        from surveys_app.models import Field, FieldResponse
        from django.utils import timezone as tz

        # Bulk-fetch all referenced fields in one query
        field_ids = [a.get('field_id') for a in answers if a.get('field_id')]
        fields_by_id = {
            str(f.id): f
            for f in Field.objects.filter(
                id__in=field_ids,
                section__survey=survey_response.survey,
            )
        }

        for answer in answers:
            field_id = str(answer.get('field_id', ''))
            field = fields_by_id.get(field_id)
            if not field:
                continue
            value = str(answer.get('value', ''))
            validate_field_value(field, value)
            if field.is_sensitive:
                value = encrypt_value(value)
            FieldResponse.objects.update_or_create(
                survey_response=survey_response,
                field=field,
                defaults={'value': value},
            )
        survey_response.last_saved_at = tz.now()
        survey_response.save(update_fields=['last_saved_at'])

    @staticmethod
    def submit(survey_response, answers, active_fields):
        """Args: survey_response, answers (list of dicts), active_fields (list of Field).
        Saves answers, marks response completed, populates Respondent profile fields."""
        from surveys_app.models import Field
        from django.utils import timezone as tz

        RespondentService.save_partial(survey_response, answers)
        survey_response.status = 'completed'
        survey_response.submitted_at = tz.now()
        survey_response.save(update_fields=['status', 'submitted_at'])

        # Populate respondent profile from maps_to fields (bulk fetch)
        field_ids = [a.get('field_id') for a in answers if a.get('field_id')]
        fields_by_id = {
            str(f.id): f
            for f in Field.objects.filter(
                id__in=field_ids,
                section__survey=survey_response.survey,
            )
        }

        respondent = survey_response.respondent
        changed = False
        for answer in answers:
            field = fields_by_id.get(str(answer.get('field_id', '')))
            if not field or not field.maps_to:
                continue
            value = answer.get('value', '')
            if field.maps_to == 'respondent_full_name':
                respondent.full_name = value
                changed = True
            elif field.maps_to == 'respondent_email':
                respondent.email = value
                changed = True
            elif field.maps_to == 'respondent_phone':
                respondent.phone = value
                changed = True
        if changed:
            respondent.save()
