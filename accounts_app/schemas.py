from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse, OpenApiExample


# ── Request examples ──────────────────────────────────────────────────────────

REGISTER_EXAMPLE = OpenApiExample(
    'Register an admin user',
    value={'email': 'admin@example.com', 'username': 'admin', 'password': 'SecurePass1!', 'role': 'admin'},
    request_only=True,
)

LOGIN_EXAMPLE = OpenApiExample(
    'Login with email and password',
    value={'email': 'admin@example.com', 'password': 'SecurePass1!'},
    request_only=True,
)

TOKEN_REFRESH_EXAMPLE = OpenApiExample(
    'Refresh token request',
    value={'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWJjMTIzIn0.refresh_sig'},
    request_only=True,
)

# ── Response examples ─────────────────────────────────────────────────────────

register_schema = extend_schema_view(
    post=extend_schema(
        summary='Register a new user',
        description=(
            'Creates a new staff user account.\n\n'
            '**Available roles:**\n'
            '- `admin` — full access\n'
            '- `analyst` — read surveys and responses, trigger exports\n'
            '- `data_viewer` — read-only access (default if role is omitted)\n\n'
            'Passwords are hashed before storage. Email must be unique.'
        ),
        tags=['Authentication'],
        examples=[REGISTER_EXAMPLE],
        responses={
            201: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='User registered successfully',
                examples=[
                    OpenApiExample(
                        'Successful registration',
                        value={'message': 'Registered successfully.', 'status': 201, 'email': 'admin@example.com', 'username': 'admin', 'role': 'admin'},
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Validation error',
                examples=[
                    OpenApiExample(
                        'Duplicate email',
                        value={'message': 'A user with this email already exists.', 'status': 400},
                    ),
                    OpenApiExample(
                        'Missing required field',
                        value={'message': "The field 'email' is required", 'status': 400},
                    ),
                ],
            ),
        },
    )
)

login_schema = extend_schema_view(
    post=extend_schema(
        summary='Login and obtain JWT tokens',
        description=(
            'Authenticates using email + password.\n\n'
            'Returns two tokens:\n'
            '- `access` — include as `Authorization: Bearer <token>` on all authenticated requests. Valid for **1 day**.\n'
            '- `refresh` — use at `POST /api/v1/auth/token/refresh/` to get a new access token. Valid for **7 days**.'
        ),
        tags=['Authentication'],
        examples=[LOGIN_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Login successful',
                examples=[
                    OpenApiExample(
                        'Successful login',
                        value={
                            'message': 'Login successful.',
                            'status': 200,
                            'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWJjMTIzIn0.signature',
                            'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWJjMTIzIn0.refresh_sig',
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Missing or invalid fields',
                examples=[
                    OpenApiExample(
                        'Missing password',
                        value={'message': "The field 'password' is required", 'status': 400},
                    )
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Wrong email or password',
                examples=[
                    OpenApiExample(
                        'Invalid credentials',
                        value={'message': 'Invalid email or password.', 'status': 401},
                    )
                ],
            ),
        },
    )
)

token_refresh_schema = extend_schema_view(
    post=extend_schema(
        summary='Refresh access token',
        description='Exchange a valid refresh token for a new access token. Use this when the access token expires.',
        tags=['Authentication'],
        examples=[TOKEN_REFRESH_EXAMPLE],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='New access token returned',
                examples=[
                    OpenApiExample(
                        'New access token',
                        value={'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYWJjMTIzIn0.new_sig'},
                    )
                ],
            ),
            401: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Refresh token is invalid or expired',
                examples=[
                    OpenApiExample(
                        'Expired refresh token',
                        value={'detail': 'Token is invalid or expired', 'code': 'token_not_valid'},
                    )
                ],
            ),
        },
    )
)
