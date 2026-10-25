# AI Receptionist

A FastAPI-based virtual receptionist for clinics. It uses Gemini to answer from
clinic-specific information, check appointment availability, make bookings, and
save callback requests.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- A Gemini API key

## Setup

From the repository root, install the project dependencies:

```powershell
uv sync
```

Create a local environment file and add your Gemini API key:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY`. `GEMINI_MODEL` is optional and defaults
to `gemini-2.5-flash`. `OWNER_EMAIL` is currently an unused placeholder.

Keep `.env` private. Do not commit API keys or put real credentials in
`.env.example`. If a key has been exposed, revoke it and create a replacement.

## Current project status

This project is currently validated in the workspace:

- `pytest` passes: 20 tests passed
- `ruff check .` passes with no lint findings
- FastAPI smoke test succeeds: the `/health` endpoint returns `200` with
  `{"status":"healthy"}`

These checks confirm the app boots and the baseline API/test workflow is
working as expected.

## Run

Start the service on `127.0.0.1:8000`:

```powershell
uv run ai-receptionist
```

For development with automatic reload:

```powershell
uv run uvicorn app.main:app --reload
```

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Tests and linting

The development dependency group includes pytest and Ruff. Install all project
and development dependencies with `uv sync`, then run:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

To apply Ruff's formatter after making changes:

```powershell
uv run ruff format .
```

## API

### Health check

```http
GET /health
```

Returns `{"status":"healthy"}` when the service is running.

### Chat

```http
POST /chat
Content-Type: application/json
```

Example request in PowerShell:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/chat `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"session_id":"demo-session","message":"What services do you offer?"}'
```

Request fields:

| Field | Required | Description |
| --- | --- | --- |
| `session_id` | Yes | Conversation identifier (1–64 characters). Reuse it to continue a conversation. |
| `message` | Yes | Patient message (1–1000 characters). |
| `clinic_id` | No | Clinic configuration name; defaults to `demo_clinic`. |

The response contains a `reply` string. Unknown clinic IDs return `404`;
invalid request bodies return `422`; Gemini initialization or request failures
return `503`.

## Clinic configuration and data

Clinic configurations are YAML files in `clinics/`. The filename (without
`.yaml`) is the `clinic_id`; for example, `clinics/demo_clinic.yaml` is selected
with `"clinic_id": "demo_clinic"`. Configure clinic details, hours, services,
prices, FAQs, timezone, and appointment slot length in the YAML file.

Bookings and callback leads are stored in the local SQLite database at
`data/receptionist.db`. The `data/` directory is generated at runtime and is
excluded from version control.

## Operational notes

- Conversation history is held in application memory and is lost when the
  service restarts. Use the same `session_id` to continue a conversation while
  the process is running.
- The current in-memory conversations are not shared between multiple worker
  processes. Run a single worker unless session storage is moved to a shared
  backend.
- The API does not implement authentication. Keep it on a trusted network and
  add authentication and transport security before exposing it publicly.
- Appointment and lead records contain patient contact information. Protect
  the database and deploy according to your privacy and retention requirements.
