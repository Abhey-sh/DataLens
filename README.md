# DataLens

Enterprise CSV validation platform for member imports. Upload a members CSV, monitor the live business-rule pipeline, resolve affected rows in the review workspace, and download summary / error / audit / corrected reports.

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
│   ├── tests/                Backend validation and repair tests
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

1. **Upload** — choose a members CSV.
2. **Validate** — start a background validation job and monitor its checks, timing, progress, and engine output.
3. **Review** — inspect issues through the Rule Navigator, including a dedicated Blank Values category.
4. **Correct** — apply configured automatic fixes, edit individual cells, or fill missing values in bulk.
5. **Download** — export the summary, errors, audit log, or corrected dataset as CSV/XLSX.

### Review and repair behavior

- The Rule Navigator keeps **Auto Defaults** first and **Blank Values** last.
- Blank values can be filtered independently from other validation issues.
- **Fill Missing Values** previews affected rows, changes only eligible blank cells, records every original value in the audit log, and revalidates the dataset.
- A first or last name containing no usable letters after cleaning (for example, `00932`) is treated as an **effective blank** and participates in the same bulk-fill workflow.
- Invalid bulk replacement values are rejected and the dataset is rolled back.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/members/validate` | Upload CSV and validate |
| `POST` | `/api/members/validate/start` | Start background validation |
| `GET` | `/api/members/validate/{validation_id}/progress` | Read live validation progress and result |
| `GET` | `/api/members/rows` | Read paginated corrected rows |
| `POST` | `/api/members/file-review/add-missing-columns` | Add missing mandatory columns |
| `POST` | `/api/members/auto-fix` | Apply every available fix for one rule |
| `POST` | `/api/members/auto-fix/issue` | Apply one configured row fix |
| `POST` | `/api/members/edit` | Apply one manual cell edit |
| `POST` | `/api/members/bulk-fill` | Fill physical and effective blank values |
| `GET`  | `/api/members/report/summary` | Validation summary download |
| `GET`  | `/api/members/report/errors` | Error report (affected rows only) |
| `GET`  | `/api/members/report/audit` | Audit log |
| `GET`  | `/api/members/report/corrected` | Corrected dataset |
| `GET`  | `/api/health` | `{ "status": "healthy" }` |

Report endpoints accept `?format=csv` (default) or `?format=xlsx`.

Validation and repair requests use an HTTP-only validation-session cookie. Keep credentials enabled when calling the API from a separate frontend origin.

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
| Blank last name | `Me` |
| Name containing no usable letters after cleaning | First/last-name blank default |
| Invalid email / lead status | `Manual Review Required` |

Suggestions never invent values outside configured business rules.

### Name cleanup

First and last names allow Unicode letters and spaces. Cleanup is deterministic:

- A zero between letters is mapped to `o` (`j0hn` → `john`).
- Other numbers and special characters are removed (`J@hn123` → `Jhn`).
- If no letters remain (`00932`), the issue is classified under **Blank Values** and receives the configured first- or last-name default.
- The uploaded value remains available as `currentValue` and is preserved in the audit trail when a fix is applied.

## Verification

```bash
# Backend
cd backend
.venv\Scripts\python.exe -m pytest

# Frontend
cd ../frontend
npm run lint
npm run build
```
