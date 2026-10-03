# Screen & Refer

Health screening app for field health workers (phone first) with a doctor review side.
**Angular** frontend, **FastAPI** backend, **PostgreSQL** in production (SQLite locally, no install needed).

```
frontend/   Angular 20 app (standalone components, signals)
backend/    FastAPI app, tests, app/form_config.json (the screening questions)
```

## Test logins

| Role | Email | Password |
|---|---|---|
| Health worker | worker1@example.com | `Test@1234` |
| Health worker (to check isolation) | worker2@example.com | `Test@1234` |
| Doctor | doctor@example.com | `Test@1234` |

Created on first start. In production set `SEED_PASSWORD` before the first start to choose the password.

## Run locally

**Backend** (Python 3.11+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs. The SQLite file `screen_refer.db` is created automatically.
To use a `.env` file: `uvicorn app.main:app --reload --env-file .env` (copy `.env.example` first).

**Frontend** (Node 20.19+ or 22+)
```bash
cd frontend
npm install
npm start          # http://localhost:4200, talks to http://localhost:8000
```

**Tests**
```bash
cd backend && python -m pytest -q
```

## AI summary (optional, server side only)

Set `LLM_PROVIDER` (`gemini` or `anthropic`) and `LLM_API_KEY` in the backend environment.
Gemini has a free tier (key from Google AI Studio). Without a key the app works the same and the summary box says
"AI summary unavailable. The screening result is unaffected." The key never reaches the frontend.

## Deploy

1. **Database**: create a free Postgres on Neon and copy the connection string.
2. **Backend** on Render: Web Service, root directory `backend`, build `pip install -r requirements.txt`,
   start `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (`backend/render.yaml` has the same).
   Environment: `DATABASE_URL`, `JWT_SECRET`, `SEED_PASSWORD`, `CORS_ORIGINS` (your frontend URL), `LLM_PROVIDER`, `LLM_API_KEY`.
3. **Frontend** on Vercel or Netlify: root directory `frontend`. First put the Render URL in
   `frontend/src/app/core/config.ts` (the one `YOUR-BACKEND` line). Build `npm run build`, output `dist/frontend/browser`.
   `vercel.json` already sends every path to `index.html`.
4. Open the live URL once before anyone reviews it. Render's free tier sleeps, so the first request takes 30-60 seconds.

## What is where

| Requirement | Where |
|---|---|
| Roles enforced on the server | `backend/app/access.py` (every query goes through it), `security.py` (`require_doctor`) |
| Patients: create, edit, soft delete, search, pagination | `routers/patients.py` |
| Branching form from config | `form_config.json`, `services/visibility.py`, `frontend/src/app/core/visibility.ts` |
| Risk scoring | `services/scoring.py` |
| Doctor review + audit log | `review_screening` in `routers/screenings.py`, `audit()` in `access.py` |
| AI summary with fallback | `services/ai.py`, `screening_summary` in `routers/screenings.py` |
| Phones, Devanagari, duplicates | `services/normalize.py`, `_check_duplicates` in `routers/patients.py` |

## Known limits

- Tables are created with `create_all` at startup; a real project would use Alembic migrations.
- The login token is kept in localStorage and login has no rate limiting.
- Drafts are saved on the phone (localStorage), not on the server, so they do not follow a worker to another phone.
- Hindi question labels are first-draft translations; a Hindi speaker should check them before real use.
