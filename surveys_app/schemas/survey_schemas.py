from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter


_VALIDATION_RULES_DOC = """
**`validation_rules` — supported keys by field type (enforced server-side):**

| Field type | Key | Type | Example |
|---|---|---|---|
| `number`, `rating` | `min` | number | `{"min": 1}` |
| `number`, `rating` | `max` | number | `{"max": 5}` |
| `text`, `textarea`, `email`, `url` | `min_length` | integer | `{"min_length": 2}` |
| `text`, `textarea`, `email`, `url` | `max_length` | integer | `{"max_length": 500}` |
| `text`, `textarea` | `regex` | string | `{"regex": "^[A-Za-z ]+$"}` |
| `checkbox` | `min_selections` | integer | `{"min_selections": 1}` |
| `checkbox` | `max_selections` | integer | `{"max_selections": 3}` |
| `date`, `datetime` | `min_date` | ISO string | `{"min_date": "2020-01-01"}` |
| `date`, `datetime` | `max_date` | ISO string | `{"max_date": "2030-12-31"}` |

Rules are validated on every autosave and submit. Sending an unknown key has no effect.
"""

_MAPS_TO_DOC = """
**`maps_to` — auto-populate respondent profile on submit:**

| Value | Populates |
|---|---|
| `respondent_full_name` | `Respondent.full_name` |
| `respondent_email` | `Respondent.email` |
| `respondent_phone` | `Respondent.phone` |

At most one field per survey should use each `maps_to` value. Set to `null` if the field does not map to a profile attribute.
"""

_CONDITIONS_DOC = """
**Conditions schema:**
```json
{
  "conditions": [
    {"field_id": "<uuid>", "operator": "<op>", "value": "<value>"}
  ]
}
```
All conditions in the list use AND logic. `null` or `{}` means always visible.

**Available operators:**

| Operator | Meaning | Example value |
|---|---|---|
| `eq` | Equals | `"Yes"` |
| `neq` | Not equals | `"No"` |
| `gt` | Greater than (numeric) | `"18"` |
| `lt` | Less than (numeric) | `"65"` |
| `gte` | Greater than or equal (numeric) | `"18"` |
| `lte` | Less than or equal (numeric) | `"100"` |
| `contains` | String contains substring | `"Toyota"` |
| `in` | Value is one of a list | `["Yes", "Maybe"]` |

Conditions can be placed on **sections** (skip the entire section if false) or on individual **fields** (hide a single field).
Numeric operators cast both sides to float — store numbers as strings in answers (e.g. `"42"`).
"""

# ── Shared nested survey body reused across multiple examples ─────────────────

_NESTED_SURVEY_BODY = {
    'id': 'b1c2d3e4-0000-0000-0000-000000000001',
    'title': 'Customer Satisfaction Survey',
    'description': 'Annual feedback survey.',
    'status': 'draft',
    'created_by': 'a0b1c2d3-0000-0000-0000-000000000001',
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
    'created_at': '2026-05-18T10:00:00Z',
}

# ── Full response bodies that mirror the request examples ─────────────────────

_SECTION_1_RESPONSE = {
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
            'validation_rules': {'min_length': 2, 'max_length': 100},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000002',
            'label': 'Email Address',
            'field_type': 'email',
            'order': 2,
            'is_required': True,
            'is_sensitive': False,
            'maps_to': 'respondent_email',
            'options': None,
            'validation_rules': {'max_length': 254},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000003',
            'label': 'Phone Number',
            'field_type': 'text',
            'order': 3,
            'is_required': False,
            'is_sensitive': False,
            'maps_to': 'respondent_phone',
            'options': None,
            'validation_rules': {'regex': '^\\+?[0-9\\s\\-]{7,15}$'},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000004',
            'label': 'Do you own a car?',
            'field_type': 'radio',
            'order': 4,
            'is_required': True,
            'is_sensitive': False,
            'maps_to': None,
            'options': ['Yes', 'No'],
            'validation_rules': None,
            'conditions': None,
        },
    ],
}

_SECTION_2_RESPONSE_NO_CONDITIONS = {
    'id': 'c3d4e5f6-0000-0000-0000-000000000002',
    'title': 'Vehicle Details',
    'order': 2,
    'conditions': None,
    'fields': [
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000005',
            'label': 'Car Brand',
            'field_type': 'dropdown',
            'order': 1,
            'is_required': True,
            'is_sensitive': False,
            'maps_to': None,
            'options': ['Toyota', 'Honda', 'Ford', 'BMW', 'Tesla', 'Other'],
            'validation_rules': None,
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000006',
            'label': 'Favourite Features',
            'field_type': 'checkbox',
            'order': 2,
            'is_required': False,
            'is_sensitive': False,
            'maps_to': None,
            'options': ['Safety', 'Fuel Economy', 'Performance', 'Design', 'Tech'],
            'validation_rules': {'min_selections': 1, 'max_selections': 3},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000007',
            'label': 'Year of Manufacture',
            'field_type': 'number',
            'order': 3,
            'is_required': True,
            'is_sensitive': False,
            'maps_to': None,
            'options': None,
            'validation_rules': {'min': 1990, 'max': 2025},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000008',
            'label': 'Purchase Date',
            'field_type': 'date',
            'order': 4,
            'is_required': False,
            'is_sensitive': False,
            'maps_to': None,
            'options': None,
            'validation_rules': {'min_date': '1990-01-01', 'max_date': '2025-12-31'},
            'conditions': None,
        },
    ],
}

_SECTION_2_RESPONSE_WITH_CONDITIONS = {
    **_SECTION_2_RESPONSE_NO_CONDITIONS,
    'conditions': {
        'conditions': [
            {'field_id': 'd4e5f6a7-0000-0000-0000-000000000004', 'operator': 'eq', 'value': 'Yes'}
        ]
    },
    'fields': [
        {**_SECTION_2_RESPONSE_NO_CONDITIONS['fields'][0], 'conditions': None},
        {
            **_SECTION_2_RESPONSE_NO_CONDITIONS['fields'][1],
            'conditions': {
                'conditions': [
                    {'field_id': 'd4e5f6a7-0000-0000-0000-000000000005', 'operator': 'neq', 'value': 'Other'}
                ]
            },
        },
        {**_SECTION_2_RESPONSE_NO_CONDITIONS['fields'][2], 'conditions': None},
        {
            **_SECTION_2_RESPONSE_NO_CONDITIONS['fields'][3],
            'conditions': {
                'conditions': [
                    {'field_id': 'd4e5f6a7-0000-0000-0000-000000000007', 'operator': 'gte', 'value': '2000'}
                ]
            },
        },
    ],
}

_SECTION_3_RESPONSE = {
    'id': 'c3d4e5f6-0000-0000-0000-000000000003',
    'title': 'General Feedback',
    'order': 3,
    'conditions': None,
    'fields': [
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000009',
            'label': 'Additional Comments',
            'field_type': 'textarea',
            'order': 1,
            'is_required': False,
            'is_sensitive': False,
            'maps_to': None,
            'options': None,
            'validation_rules': {'max_length': 1000},
            'conditions': None,
        },
        {
            'id': 'd4e5f6a7-0000-0000-0000-000000000010',
            'label': 'Overall Satisfaction',
            'field_type': 'rating',
            'order': 2,
            'is_required': True,
            'is_sensitive': False,
            'maps_to': None,
            'options': None,
            'validation_rules': {'min': 1, 'max': 5},
            'conditions': None,
        },
    ],
}

_SURVEY_BASE_RESPONSE = {
    'id': 'b1c2d3e4-0000-0000-0000-000000000001',
    'title': 'Customer Satisfaction Survey',
    'description': 'Annual feedback survey.',
    'status': 'draft',
    'created_by': 'a0b1c2d3-0000-0000-0000-000000000001',
    'created_at': '2026-05-18T10:00:00Z',
}

_NESTED_SURVEY_BODY_POST_RESPONSE = {
    **_SURVEY_BASE_RESPONSE,
    'sections': [_SECTION_1_RESPONSE, _SECTION_2_RESPONSE_NO_CONDITIONS, _SECTION_3_RESPONSE],
}

_NESTED_SURVEY_BODY_PUT_RESPONSE = {
    **_SURVEY_BASE_RESPONSE,
    'sections': [_SECTION_1_RESPONSE, _SECTION_2_RESPONSE_WITH_CONDITIONS, _SECTION_3_RESPONSE],
}

# ── Request examples ──────────────────────────────────────────────────────────

# Shared section structure used in both create and PUT examples.
# PUT adds conditions; create keeps them all null.
_SECTION_1 = {
    'title': 'Personal Info',
    'order': 1,
    'conditions': None,
    'fields': [
        {
            'label': 'Full Name',
            'field_type': 'text',
            'order': 1,
            'is_required': True,
            'maps_to': 'respondent_full_name',
            'validation_rules': {'min_length': 2, 'max_length': 100},
            'conditions': None,
        },
        {
            'label': 'Email Address',
            'field_type': 'email',
            'order': 2,
            'is_required': True,
            'maps_to': 'respondent_email',
            'validation_rules': {'max_length': 254},
            'conditions': None,
        },
        {
            'label': 'Phone Number',
            'field_type': 'text',
            'order': 3,
            'is_required': False,
            'maps_to': 'respondent_phone',
            'validation_rules': {'regex': '^\\+?[0-9\\s\\-]{7,15}$'},
            'conditions': None,
        },
        {
            'label': 'Do you own a car?',
            'field_type': 'radio',
            'order': 4,
            'is_required': True,
            'maps_to': None,
            'options': ['Yes', 'No'],
            'conditions': None,
        },
    ],
}

_SECTION_2_NO_CONDITIONS = {
    'title': 'Vehicle Details',
    'order': 2,
    'conditions': None,
    'fields': [
        {
            'label': 'Car Brand',
            'field_type': 'dropdown',
            'order': 1,
            'is_required': True,
            'maps_to': None,
            'options': ['Toyota', 'Honda', 'Ford', 'BMW', 'Tesla', 'Other'],
            'conditions': None,
        },
        {
            'label': 'Favourite Features',
            'field_type': 'checkbox',
            'order': 2,
            'is_required': False,
            'maps_to': None,
            'options': ['Safety', 'Fuel Economy', 'Performance', 'Design', 'Tech'],
            'validation_rules': {'min_selections': 1, 'max_selections': 3},
            'conditions': None,
        },
        {
            'label': 'Year of Manufacture',
            'field_type': 'number',
            'order': 3,
            'is_required': True,
            'maps_to': None,
            'validation_rules': {'min': 1990, 'max': 2025},
            'conditions': None,
        },
        {
            'label': 'Purchase Date',
            'field_type': 'date',
            'order': 4,
            'is_required': False,
            'maps_to': None,
            'validation_rules': {'min_date': '1990-01-01', 'max_date': '2025-12-31'},
            'conditions': None,
        },
    ],
}

_SECTION_2_WITH_CONDITIONS = {
    **_SECTION_2_NO_CONDITIONS,
    'conditions': {
        'conditions': [
            {'field_id': 'd4e5f6a7-0000-0000-0000-000000000004', 'operator': 'eq', 'value': 'Yes'}
        ]
    },
    'fields': [
        {
            **_SECTION_2_NO_CONDITIONS['fields'][0],  # Car Brand — no field condition
            'conditions': None,
        },
        {
            **_SECTION_2_NO_CONDITIONS['fields'][1],  # Favourite Features — only when a known brand is selected
            'conditions': {
                'conditions': [
                    {'field_id': 'd4e5f6a7-0000-0000-0000-000000000005', 'operator': 'neq', 'value': 'Other'}
                ]
            },
        },
        {
            **_SECTION_2_NO_CONDITIONS['fields'][2],  # Year of Manufacture — no field condition
            'conditions': None,
        },
        {
            **_SECTION_2_NO_CONDITIONS['fields'][3],  # Purchase Date — only for cars made from 2000 onward
            'conditions': {
                'conditions': [
                    {'field_id': 'd4e5f6a7-0000-0000-0000-000000000007', 'operator': 'gte', 'value': '2000'}
                ]
            },
        },
    ],
}

_SECTION_3 = {
    'title': 'General Feedback',
    'order': 3,
    'conditions': None,
    'fields': [
        {
            'label': 'Additional Comments',
            'field_type': 'textarea',
            'order': 1,
            'is_required': False,
            'maps_to': None,
            'validation_rules': {'max_length': 1000},
            'conditions': None,
        },
        {
            'label': 'Overall Satisfaction',
            'field_type': 'rating',
            'order': 2,
            'is_required': True,
            'maps_to': None,
            'validation_rules': {'min': 1, 'max': 5},
            'conditions': None,
        },
    ],
}

SURVEY_CREATE_EXAMPLE = OpenApiExample(
    'Create survey — all conditions null (step 1 of 2)',
    value={
        'title': 'Customer Satisfaction Survey',
        'description': 'Annual feedback survey.',
        'sections': [_SECTION_1, _SECTION_2_NO_CONDITIONS, _SECTION_3],
    },
    request_only=True,
)

SURVEY_UPDATE_WITH_CONDITIONS_EXAMPLE = OpenApiExample(
    'Update survey — add conditions (step 2 of 2)',
    value={
        'title': 'Customer Satisfaction Survey',
        'description': 'Annual feedback survey.',
        'sections': [_SECTION_1, _SECTION_2_WITH_CONDITIONS, _SECTION_3],
    },
    request_only=True,
)

# ── Schema decorators ─────────────────────────────────────────────────────────

survey_list_create_schema = extend_schema_view(
    get=extend_schema(
        summary='List all surveys',
        description='Returns a paginated list of all surveys regardless of status. Admin only.\n\nUse `page_number` and `page_size` query params to paginate.',
        tags=['Survey Builder'],
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by survey status. Values: `draft`, `published`, `archived`.',
            ),
            OpenApiParameter(
                name='created_by__email',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by the email address of the user who created the survey. Example: `admin@example.com`',
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Search across survey title and description (case-insensitive).',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Paginated list of surveys',
                examples=[
                    OpenApiExample(
                        'Paginated survey list',
                        value={
                            'status': 200,
                            'next': 'http://localhost:8000/api/v1/dashboard/surveys/?page_number=2&page_size=10',
                            'previous': None,
                            'total_number_of_objects': 25,
                            'number_of_pages': 3,
                            'current_page': 1,
                            'last_page': 3,
                            'count_items_in_page': 2,
                            'results': [
                                {'id': 'b1c2d3e4-0000-0000-0000-000000000001', 'title': 'Customer Satisfaction Survey', 'status': 'published', 'created_at': '2026-05-18T10:00:00Z'},
                                {'id': 'b1c2d3e4-0000-0000-0000-000000000002', 'title': 'Employee Onboarding Survey', 'status': 'draft', 'created_at': '2026-05-17T09:00:00Z'},
                            ],
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
        },
    ),
    post=extend_schema(
        summary='Create a survey with nested sections and fields',
        description=(
            'Creates a survey in a single request. Sections and fields are created atomically inside a transaction. '
            'The survey starts as `draft` — call `PATCH /{survey_id}/publish/` when ready.\n\n'
            '**Important — conditions must be null on create.** Field UUIDs are generated server-side, so they are '
            'not known at creation time. Send all `conditions` as `null` in this request, then use `PUT` to add '
            'conditional logic once you have the field UUIDs from the response.\n\n'
            + _MAPS_TO_DOC
            + _VALIDATION_RULES_DOC
            + _CONDITIONS_DOC
        ),
        tags=['Survey Builder'],
        examples=[SURVEY_CREATE_EXAMPLE],
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey created with full nested structure',
                examples=[
                    OpenApiExample(
                        'Survey created',
                        value={'message': 'Survey created successfully.', 'status': 201, **_NESTED_SURVEY_BODY_POST_RESPONSE},
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Validation error',
                examples=[
                    OpenApiExample('Missing title', value={'message': "The field 'title' is required", 'status': 400})
                ],
            ),
            403: OpenApiResponse(description='Admin role required'),
        },
    ),
)

survey_retrieve_update_destroy_schema = extend_schema_view(
    get=extend_schema(
        summary='Retrieve a survey with full structure',
        description='Returns the complete survey including all sections, fields, options, validation rules, and conditions. Works for any status (draft/published/archived).',
        tags=['Survey Builder'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Full survey structure with nested sections and fields',
                examples=[OpenApiExample('Full survey', value=_NESTED_SURVEY_BODY)],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    ),
    put=extend_schema(
        summary='Full replace a survey (PUT)',
        description=(
            'Replaces the entire survey structure in one atomic transaction.\n\n'
            '⚠️ **All sections and fields not included in the payload are permanently deleted.**\n\n'
            'This is also the step where you add conditional logic. After `POST` returns the field UUIDs, '
            'send a `PUT` with the full structure including `conditions` referencing those UUIDs.\n\n'
            + _MAPS_TO_DOC
            + _VALIDATION_RULES_DOC
            + _CONDITIONS_DOC
        ),
        tags=['Survey Builder'],
        examples=[SURVEY_UPDATE_WITH_CONDITIONS_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey replaced with new structure',
                examples=[
                    OpenApiExample(
                        'Survey updated',
                        value={'message': 'Survey updated successfully.', 'status': 200, **_NESTED_SURVEY_BODY_PUT_RESPONSE},
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Validation error',
                examples=[OpenApiExample('Missing title', value={'message': "The field 'title' is required", 'status': 400})],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    ),  
    delete=extend_schema(
        summary='Delete a survey',
        description='Permanently deletes the survey and all its sections, fields, responses, and export reports.',
        tags=['Survey Builder'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey deleted successfully',
                examples=[OpenApiExample('Deleted', value={'message': 'Survey deleted successfully.', 'status': 200})],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    ),
)

survey_fields_list_schema = extend_schema_view(
    get=extend_schema(
        summary='List all fields in a survey (flat)',
        description=(
            'Returns every field in the survey as a flat, ordered list — sorted by section order '
            'then field order. Intended for the conditions builder UI so the frontend can render '
            'a field picker without parsing the full nested survey structure.\n\n'
            'Each item includes `field_type` (so the UI knows which operators apply) and `options` '
            '(so the UI can suggest valid values for `eq` / `in` conditions).\n\n'
        ),
        tags=['Survey Builder'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Flat ordered list of all fields in the survey',
                examples=[
                    OpenApiExample(
                        'Fields list',
                        value={
                            'status': 200,
                            'fields': [
                                {
                                    'id': 'd4e5f6a7-0000-0000-0000-000000000001',
                                    'label': 'Full Name',
                                    'field_type': 'text',
                                    'options': None,
                                    'section_title': 'Personal Info',
                                    'section_order': 1,
                                    'order': 1,
                                },
                                {
                                    'id': 'd4e5f6a7-0000-0000-0000-000000000004',
                                    'label': 'Do you own a car?',
                                    'field_type': 'radio',
                                    'options': ['Yes', 'No'],
                                    'section_title': 'Personal Info',
                                    'section_order': 1,
                                    'order': 4,
                                },
                                {
                                    'id': 'd4e5f6a7-0000-0000-0000-000000000005',
                                    'label': 'Car Brand',
                                    'field_type': 'dropdown',
                                    'options': ['Toyota', 'Honda', 'Ford', 'BMW', 'Tesla', 'Other'],
                                    'section_title': 'Vehicle Details',
                                    'section_order': 2,
                                    'order': 1,
                                },
                            ],
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)

survey_publish_schema = extend_schema_view(
    patch=extend_schema(
        summary='Publish a survey',
        description=(
            'Changes the survey status to `published`, making it accessible to respondents.\n\n'
            '**Requirements:** at least one section with at least one field.\n\n'
            'Once published, the survey is served from Redis cache on first respondent load.'
        ),
        tags=['Survey Builder'],
        request=None,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey is now published',
                examples=[
                    OpenApiExample(
                        'Published',
                        value={'message': 'Survey published successfully.', 'status': 200, 'id': 'b1c2d3e4-0000-0000-0000-000000000001', 'title': 'Customer Satisfaction Survey', 'status': 'published', 'created_at': '2026-05-18T10:00:00Z'},
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Publish requirements not met',
                examples=[
                    OpenApiExample('No sections', value={'message': 'Survey must have at least one section.', 'status': 400}),
                    OpenApiExample('No fields', value={'message': 'Survey must have at least one field.', 'status': 400}),
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)
