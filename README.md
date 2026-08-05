# DataLens

Enterprise CSV validation platform for member imports. Upload a members CSV, run the business-rule engine, review affected rows, and download summary / error / audit / corrected reports.

## Quick start (single command)

**Prerequisites**

- Node.js 18+
- Python 3.12+ (tested with 3.14; dependency ranges allow modern wheels)

**First time**

```bash
npm run setup
```

This installs root tooling, creates `backend/.venv`, installs Python packages, and installs frontend dependencies.

**Run backend + frontend together**

```bash
npm start
# or
npm run dev:full
```

Or on Windows:

```powershell
.\start.ps1
# first time:
.\start.ps1 -Setup
```

```bat
start.bat
REM first time:
start.bat --setup
```

| Service  | URL                         |
|----------|-----------------------------|
| Frontend | http://localhost:5173       |
| Backend  | http://localhost:8000       |
| API docs | http://localhost:8000/docs  |
| Health   | http://localhost:8000/api/health |

Stop with `Ctrl+C`.

## Project layout

```
DataLens/
├── backend/                 FastAPI + pandas validation engine
│   ├── app/
│   │   ├── api/routes/      HTTP routes
│   │   ├── reports/         CSV / Excel report generation
│   │   ├── schemas/         Pydantic API models
│   │   └── validation/      Reusable validation pipeline + members rules
│   └── requirements.txt
├── frontend/                React + Vite UI
│   └── src/
│       ├── features/members/
│       └── services/validationApi.js
├── scripts/                 Setup & run helpers
├── package.json             Root scripts (npm start)
├── start.ps1 / start.bat    Windows one-click starters
└── README.md
```

## Members workflow

1. **Upload** — choose a members CSV  
2. **Validate** — `POST /api/members/validate` runs cleaning + business rules  
3. **Review** — inspect affected rows and rule summaries  
4. **Download** — summary, errors, audit log, corrected dataset (CSV or XLSX)

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/members/validate` | Upload CSV and validate |
| `GET`  | `/api/members/report/summary` | Validation summary download |
| `GET`  | `/api/members/report/errors` | Error report (affected rows only) |
| `GET`  | `/api/members/report/audit` | Audit log |
| `GET`  | `/api/members/report/corrected` | Corrected dataset |
| `GET`  | `/api/health` | `{ "status": "healthy" }` |

Report endpoints accept `?format=csv` (default) or `?format=xlsx`.

## Run services separately

```bash
# Backend only
npm run dev:backend

# Frontend only
npm run dev:frontend
```

Manual backend (after setup):

```bash
cd backend
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Manual frontend:

```bash
cd frontend
npm install
npm run dev
```

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `DATALENS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins |
| `VITE_API_BASE_URL` | `/api` (via Vite proxy in dev) | Override if the API is on another host |

Optional frontend env file: `frontend/.env`

```
VITE_API_BASE_URL=/api
```

## Suggested values (configured rules only)

| Condition | Suggested value |
|-----------|-----------------|
| Blank gender | `P` |
| Blank birth date | `1970-01-01` |
| Blank postal code | `-` |
| Blank first name | `Change Me` |
| Invalid email / phone / lead status | `Manual Review Required` |

Suggestions never invent values outside configured business rules.
