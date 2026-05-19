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
cd Founding-Engineer---Test
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

## Frontend Integration — Respondent Flow

This section describes the exact sequence of API calls a frontend should make when a user visits and fills out a survey.

### Step 1 — Load the survey structure

```
GET /api/v1/surveys/{survey_id}/
```

No auth required. Returns all sections and fields including `conditions`, `options`, and `validation_rules`. Use this response to render the form. Cache it on the client — it only changes when an admin republishes the survey.

---

### Step 2 — Check for an existing session

Before creating a new session, check whether the user already has a saved token for this survey. Store and look up tokens keyed by survey ID so multiple surveys don't collide:

```js
const storageKey = `session_token_${surveyId}`;
const existingToken = localStorage.getItem(storageKey);
```

**If a token exists → attempt to resume:**

```
GET /api/v1/surveys/{survey_id}/respond/{session_token}/
```

| Response | What to do |
|---|---|
| `200 status: in_progress` | Pre-fill the form with the returned `answers` array and let the user continue |
| `200 status: completed` | Show a "you have already submitted this survey" message — do not allow resubmission |
| `401` | Token is expired or invalid — clear it from storage and fall through to Step 3 |

**If no token exists → go directly to Step 3.**

---

### Step 3 — Create a new session

```
POST /api/v1/surveys/{survey_id}/respond/
Body: {}
```

Returns a `session_token` (JWT, valid 7 days) and a `survey_response_id`. Persist the token immediately:

```js
localStorage.setItem(`session_token_${surveyId}`, data.session_token);
```

---

### Step 4 — Autosave periodically

While the user is filling out the form, autosave in the background on a timer (every 30 seconds is a reasonable default) and also on field blur for important fields.

```
POST /api/v1/surveys/{survey_id}/respond/{session_token}/
Body: { "answers": [{ "field_id": "...", "value": "..." }] }
```

Only send answers the user has touched — no need to send the full form every time. The server upserts: sending the same `field_id` again updates the existing value rather than duplicating it.

| Response | What to do |
|---|---|
| `200` | Silently update the last-saved timestamp in the UI |
| `400` | A field value failed validation — surface the error message next to the relevant field |
| `401` | Session expired — prompt the user to refresh and warn that progress may be lost |

---

### Step 5 — Final submit

When the user clicks submit, send all current answers in one request:

```
POST /api/v1/surveys/submit/{session_token}/
Body: { "answers": [{ "field_id": "...", "value": "..." }] }
```

The server merges these with any previously autosaved answers, evaluates conditional logic to determine which fields are active, then enforces required fields only on active sections.

| Response | What to do |
|---|---|
| `200` | Clear the token from storage, show a success screen |
| `400 "Field X is required."` | Scroll to the missing field and highlight it |
| `400` (validation rule) | Show the error message next to the relevant field |
| `401` | Session expired — same handling as autosave |

---

### Conditional logic — frontend responsibility

The server enforces conditions on submit, but the frontend should mirror the same logic in real time to show and hide sections and fields as the user types. The condition schema returned with the survey structure is straightforward to evaluate client-side:

```js
// condition: { "field_id": "...", "operator": "eq", "value": "Yes" }
// answers:   { [field_id]: currentValue }
// All conditions in the list use AND logic
```

If a section's condition evaluates to false, hide the entire section and do not include answers to fields inside it in the autosave or submit payload — they will not be enforced by the server regardless, but omitting them keeps the payload clean.

---

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
