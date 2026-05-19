# Survey Platform

A production-ready dynamic survey platform built with Django REST Framework. Admins build surveys with conditional logic, respondents fill them out through a token-based session flow, and analysts access response analytics and CSV exports — all served through a clean REST API.

---

## Tech Stack

- **Backend** — Django 5.1, Django REST Framework
- **Database** — PostgreSQL 16
- **Cache / Broker** — Redis 7
- **Async Tasks** — Celery
- **Auth** — JWT via SimpleJWT
- **Docs** — drf-spectacular (Swagger / ReDoc)
- **Containerisation** — Docker, Docker Compose

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/OmarNasserr/Founding-Engineer---Test.git
```

A `.env` file is included in the repo with working values for local development. No changes needed to get started.

### 2. Build the image

```bash
docker compose build
```

This builds and tags the image as `survey_backend:latest`. Only needed once (or after a `Dockerfile` change).

### 3. Start all services

```bash
docker compose up
```

This starts PostgreSQL, Redis, the Django backend, and the Celery worker. On first boot the backend automatically runs migrations and seeds demo data.

### 4. Access the API

| Interface | URL |
|---|---|
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| API root | http://localhost:8000/api/v1/ |

### 5. Demo credentials

The seed command creates the following users:

| Role | Email | Password |
|---|---|---|
| Admin | admin@survey.com | Admin1234! |
| Analyst | analyst@survey.com | Analyst1234! |
| Data Viewer | viewer@survey.com | Viewer1234! |

---

## Project Structure

```
survey_platform/          # Django project settings and root URL config
accounts_app/             # User model, registration, JWT login
surveys_app/
├── models.py             # Survey, Section, Field, Respondent, SurveyResponse, ExportReport
├── views/
│   ├── survey_views.py   # Builder endpoints (admin only)
│   ├── respondent_views.py  # Public respondent flow
│   └── analytics_views.py   # Analytics and CSV export
├── service.py            # Business logic — survey CRUD, session management, encryption
├── logic.py              # ConditionalLogicEngine — evaluates field/section conditions
├── tasks.py              # Celery task — async CSV export
├── signals.py            # Cache invalidation on model changes
└── schemas/              # drf-spectacular Swagger documentation
audit_app/                # AuditLog model + signals — records key events automatically
core/                     # BaseModel (UUID pk, timestamps), global exception handler
helper_files/             # Shared utilities — permissions, pagination, Redis client, exceptions
```

---

## Architecture & Design Decisions

### Role-based access control

Three roles with distinct access levels:

| Endpoint group | Admin | Analyst | Data Viewer |
|---|---|---|---|
| Survey builder (CRUD, publish) | ✅ | ❌ | ❌ |
| Analytics (GET) | ✅ | ✅ | ✅ |
| Export trigger (POST) | ✅ | ✅ | ❌ |
| Export reports (GET) | ✅ | ✅ | ✅ |

### Two-step survey creation

Field UUIDs are generated server-side on `POST`. Because conditions reference fields by UUID (`{"field_id": "<uuid>", "operator": "eq", "value": "Yes"}`), conditions cannot be set at creation time — the UUIDs don't exist yet. The intended flow is:

1. `POST /dashboard/surveys/` — create the full structure, all conditions `null`. Response returns the assigned field UUIDs.
2. `PUT /dashboard/surveys/{id}/` — full replace with conditions populated using those UUIDs.

A dedicated `GET /dashboard/surveys/{id}/fields/` endpoint returns a flat ordered field list specifically to support the frontend conditions builder.

### Conditional logic engine

`ConditionalLogicEngine` (`logic.py`) evaluates conditions at submit time to determine which sections and fields are "active". Inactive fields are excluded from the required-field check — a required field inside a skipped section is never enforced. Conditions use AND logic and support 8 operators: `eq`, `neq`, `gt`, `lt`, `gte`, `lte`, `contains`, `in`.

### Redis caching

Two caching layers:

- **Survey structure** (`survey:{id}`) — cached on first public `GET`, invalidated via Django signals whenever the survey, any of its sections, or any of its fields is saved or deleted. TTL: 1 hour.
- **Analytics** (`analytics:{id}`) — cached after first computation. TTL: 5 minutes.

Cache is accessed directly via the Redis client (`helper_files/redis_client.py`), not through Django's cache framework.

### Sensitive field encryption

Fields can be marked `is_sensitive=True`. Answers to those fields are encrypted at rest using Fernet symmetric encryption (`FIELD_ENCRYPTION_KEY`) before being written to `FieldResponse`. They are decrypted transparently when the respondent resumes their session. If `FIELD_ENCRYPTION_KEY` is not set, values are stored in plain text.

### Audit logging

Key events are recorded to `AuditLog` automatically via Django signals — not in view code. Events captured: `survey.created`, `survey.published`, `survey.deleted`, `response.submitted`, `survey.export_triggered`. This keeps views clean and ensures logging cannot be accidentally skipped.

### Async CSV export

Export jobs are queued via Celery (`tasks.py`). The view creates an `ExportReport` record with status `pending` and returns immediately. The worker fetches completed responses, builds the CSV, writes it to `MEDIA_ROOT/exports/{survey_id}/`, and updates the record to `ready` (or `failed` after 3 retries with exponential backoff).

---

## API Reference

Full interactive documentation is available at `/api/docs/` (Swagger) or `/api/redoc/`.

A ready-to-use Postman collection is also included at `survey_platform_postman.json`. Import it into Postman (**File → Import**), then run **Login as Admin** first — the access token is saved automatically and used by all subsequent requests. Seeded field UUIDs are pre-filled in every request body so you can test the full respondent flow immediately.

## Testing

Run the full test suite inside Docker:

```bash
docker exec survey-backend pytest -v
```

With coverage report:

```bash
docker exec survey-backend pytest --cov=surveys_app --cov=accounts_app --cov=audit_app --cov=core --cov-report=term-missing
```

**202 tests — 94% coverage**
