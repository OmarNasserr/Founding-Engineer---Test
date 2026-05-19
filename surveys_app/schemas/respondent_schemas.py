from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse, OpenApiExample


# ── Shared nested survey structure used in the public detail response ──────────

_PUBLISHED_SURVEY = {
    'id': 'b1c2d3e4-0000-0000-0000-000000000001',
    'title': 'Customer Satisfaction Survey',
    'description': 'Annual feedback survey.',
    'status': 'published',
    'sections': [
        {
            'id': 'c3d4e5f6-0000-0000-0000-000000000001',
            'title': 'Personal Info',
            'order': 1,
            'conditions': None,
            'fields': [
                {
                    'id': 'd4e5f6a7-0000-0000-0000-000000000001',
                    'label': 'Full Name',
                    'field_type': 'text',
                    'order': 1,
                    'is_required': True,
                    'is_sensitive': False,
                    'maps_to': 'respondent_full_name',
                    'options': None,
                    'validation_rules': None,
                    'conditions': None,
                },
                {
                    'id': 'e5f6a7b8-0000-0000-0000-000000000001',
                    'label': 'Do you own a car?',
                    'field_type': 'radio',
                    'order': 2,
                    'is_required': True,
                    'is_sensitive': False,
                    'maps_to': None,
                    'options': ['Yes', 'No'],
                    'validation_rules': None,
                    'conditions': None,
                },
            ],
        },
        {
            'id': 'f6a7b8c9-0000-0000-0000-000000000001',
            'title': 'Vehicle Details',
            'order': 2,
            'conditions': {
                'conditions': [
                    {'field_id': 'e5f6a7b8-0000-0000-0000-000000000001', 'operator': 'eq', 'value': 'Yes'}
                ]
            },
            'fields': [
                {
                    'id': 'a7b8c9d0-0000-0000-0000-000000000001',
                    'label': 'Car Brand',
                    'field_type': 'dropdown',
                    'order': 1,
                    'is_required': True,
                    'is_sensitive': False,
                    'maps_to': None,
                    'options': ['Toyota', 'Honda', 'Ford', 'Tesla'],
                    'validation_rules': None,
                    'conditions': None,
                },
                {
                    'id': 'b8c9d0e1-0000-0000-0000-000000000001',
                    'label': 'Is it electric?',
                    'field_type': 'radio',
                    'order': 2,
                    'is_required': False,
                    'is_sensitive': False,
                    'maps_to': None,
                    'options': ['Yes', 'No'],
                    'validation_rules': None,
                    'conditions': {
                        'conditions': [
                            {'field_id': 'a7b8c9d0-0000-0000-0000-000000000001', 'operator': 'eq', 'value': 'Tesla'}
                        ]
                    },
                },
            ],
        },
    ],
}

# ── Request examples ──────────────────────────────────────────────────────────

SESSION_CREATE_EXAMPLE = OpenApiExample(
    'Start session with first answer',
    value={'answers': [{'field_id': 'e5f6a7b8-0000-0000-0000-000000000001', 'value': 'Yes'}]},
    request_only=True,
)

SESSION_CREATE_EMPTY_EXAMPLE = OpenApiExample(
    'Start session with no initial answers',
    value={},
    request_only=True,
)

AUTOSAVE_EXAMPLE = OpenApiExample(
    'Autosave multiple answers',
    value={
        'answers': [
            {'field_id': 'd4e5f6a7-0000-0000-0000-000000000001', 'value': 'Alice Smith'},
            {'field_id': 'e5f6a7b8-0000-0000-0000-000000000001', 'value': 'Yes'},
            {'field_id': 'a7b8c9d0-0000-0000-0000-000000000001', 'value': 'Toyota'},
        ],
    },
    request_only=True,
)

SUBMIT_EXAMPLE = OpenApiExample(
    'Final submission — remaining answers only (merged with autosaved)',
    value={
        'answers': [
            {'field_id': 'b8c9d0e1-0000-0000-0000-000000000001', 'value': 'No'},
        ],
    },
    request_only=True,
)

# ── Schema decorators ─────────────────────────────────────────────────────────

survey_public_detail_schema = extend_schema_view(
    get=extend_schema(
        summary='Get published survey for respondents',
        description=(
            'Returns the full survey structure. Only `published` surveys are accessible.\n\n'
            'Response is **Redis-cached for 1 hour** and invalidated when the survey is updated.\n\n'
            '**Reading conditions on the frontend:**\n'
            '- `null` conditions → always visible.\n'
            '- Section condition fails → hide entire section and all its fields.\n'
            '- Field condition fails → hide that field only.\n'
            '- All conditions within one object use AND logic.'
        ),
        tags=['Respondent'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Published survey with ordered sections and fields',
                examples=[OpenApiExample('Published survey', value=_PUBLISHED_SURVEY)],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found or not published',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)

respondent_session_create_schema = extend_schema_view(
    post=extend_schema(
        operation_id='respondent_session_create',
        summary='Start a respondent session',
        description=(
            'Called on the respondent\'s **first input**. Creates a `Respondent` and `SurveyResponse` record '
            'and returns a JWT `session_token` valid for 7 days.\n\n'
            'Store the token and use it for all subsequent autosave and submit calls.\n\n'
            'Optionally pass initial answers in the body. Send `{}` if no answers yet.'
        ),
        tags=['Respondent'],
        examples=[SESSION_CREATE_EXAMPLE, SESSION_CREATE_EMPTY_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Session started — session_token and survey_response_id returned',
                examples=[
                    OpenApiExample(
                        'Session started',
                        value={
                            'message': 'Session started.',
                            'status': 200,
                            'session_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyZXNwb25kZW50X2lkIjoiYWJjMTIzIn0.sig',
                            'survey_response_id': 'a1b2c3d4-0000-0000-0000-000000000001',
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Invalid answer format',
                examples=[
                    OpenApiExample('Bad answer', value={'message': "The field 'field_id' is required", 'status': 400})
                ],
            ),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found or not published',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)

respondent_session_detail_schema = extend_schema_view(
    get=extend_schema(
        summary='Resume session — get saved answers',
        description=(
            'Returns all previously saved answers, the session `status`, and `last_saved_at`.\n\n'
            'Sensitive field values (`is_sensitive=true`) are decrypted — the frontend always receives plain text.'
        ),
        tags=['Respondent'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Saved answers, status, and last save timestamp',
                examples=[
                    OpenApiExample(
                        'In-progress session',
                        value={
                            'status': 'in_progress',
                            'last_saved_at': '2026-05-18T10:05:00Z',
                            'answers': [
                                {'field_id': 'd4e5f6a7-0000-0000-0000-000000000001', 'value': 'Alice Smith'},
                                {'field_id': 'e5f6a7b8-0000-0000-0000-000000000001', 'value': 'Yes'},
                                {'field_id': 'a7b8c9d0-0000-0000-0000-000000000001', 'value': 'Toyota'},
                            ],
                        },
                    )
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Invalid or expired session token',
                examples=[
                    OpenApiExample('Invalid token', value={'message': 'Session token is invalid or has expired.', 'status': 401})
                ],
            ),
        },
    ),
    post=extend_schema(
        operation_id='respondent_session_autosave',
        summary='Autosave partial answers',
        description=(
            'Upserts `FieldResponse` rows — sending the same `field_id` twice updates the existing value, not duplicates it. '
            'Updates `last_saved_at` on every call.\n\n'
            'Returns 400 if the session is already `completed`.'
        ),
        tags=['Respondent'],
        examples=[AUTOSAVE_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Answers upserted successfully',
                examples=[
                    OpenApiExample('Saved', value={'message': 'Progress saved.', 'status': 200})
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Session already submitted or invalid answers',
                examples=[
                    OpenApiExample('Already submitted', value={'message': 'You have already submitted this survey.', 'status': 400})
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Invalid or expired session token',
                examples=[
                    OpenApiExample('Invalid token', value={'message': 'Session token is invalid or has expired.', 'status': 401})
                ],
            ),
        },
    ),
)

respondent_submit_schema = extend_schema_view(
    post=extend_schema(
        summary='Submit survey — final submission',
        description=(
            'Finalises the survey response.\n\n'
            '**What happens on submit:**\n'
            '1. Submitted answers are merged with any previously autosaved answers (submitted values win).\n'
            '2. The conditional logic engine determines which fields were **active** (visible) based on the merged answers.\n'
            '3. Only required fields that were **active** are enforced — required fields behind unmet conditions are ignored.\n'
            '4. `SurveyResponse.status` → `completed`, `submitted_at` is recorded.\n'
            '5. Respondent profile (`full_name`, `email`, `phone`) is auto-populated from `maps_to` fields.\n\n'
            'Cannot be called twice on the same `session_token`.'
        ),
        tags=['Respondent'],
        examples=[SUBMIT_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey submitted and response marked completed',
                examples=[
                    OpenApiExample('Submitted', value={'message': 'Survey submitted successfully.', 'status': 200})
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Missing required active field or already submitted',
                examples=[
                    OpenApiExample('Missing field', value={'message': 'Field "Full Name" is required.', 'status': 400}),
                    OpenApiExample('Already submitted', value={'message': 'You have already submitted this survey.', 'status': 400}),
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Invalid or expired session token',
                examples=[
                    OpenApiExample('Invalid token', value={'message': 'Session token is invalid or has expired.', 'status': 401})
                ],
            ),
        },
    )
)
