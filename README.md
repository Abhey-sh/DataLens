# DataLens

Enterprise CSV validation platform for import datasets. Validate **Members** (review and repair) or **Assets** (auto-clean and finalize), then download summary / audit / corrected reports.

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
│   │   └── validation/      Pipeline + members/ and assets/ rule packs
│   ├── tests/                Backend validation and repair tests
│   └── requirements.txt
├── frontend/                React + Vite UI
│   └── src/
│       ├── features/members/
│       ├── features/assets/
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
- Blank first and last names participate in the bulk-fill workflow; nonblank
  invalid names require manual correction.
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

## Assets workflow

1. **Upload** — choose an assets CSV with columns `resourceForeignId`, `studioForeignId`, `studioId`, `resourceType`, and `assetURL`.
2. **Validate** — start a background validation job and monitor its checks, timing, progress, and engine output.
3. **Auto-clean** — invalid **full rows** are removed during validation (no Review & Map step for Assets).
4. **Finalize** — inspect kept/removed counts and a removed-rows preview.
5. **Download** — export the summary, errors, audit log, corrected dataset, or removed-rows report as CSV/XLSX.

### Validation and cleanup behavior

- Required headers must be present. Missing headers **block** the file; fix the CSV and re-upload (headers are not auto-added for Assets).
- **Primary Studio Filter** keeps rows matching the most common `(studioForeignId, studioId)` pair and removes other full rows.
- **Resource Type** allows only `MEMBER` or `STAFF`; other values remove the full row.
- **Asset URL Image Type** keeps only image URLs ending in `.jpg` / `.jpeg` / `.png` / `.bmp` (and `.pjpeg`); other URLs remove the full row.
- **Duplicate Resource Foreign ID** keeps the first occurrence and removes later duplicate full rows.
- There is **no Rule Navigator / manual repair step** for Assets — cleanup happens in validation.
- The Finalize page shows removed rows and supports downloading a dedicated **removed** report.

## Assets API overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/assets/validate` | Upload CSV and validate |
| `POST` | `/api/assets/validate/start` | Start background validation |
| `GET` | `/api/assets/validate/{validation_id}/progress` | Read live validation progress and result |
| `GET` | `/api/assets/rows` | Read paginated cleaned rows |
| `GET`  | `/api/assets/report/summary` | Validation summary download |
| `GET`  | `/api/assets/report/errors` | Error report (affected / removed rows) |
| `GET`  | `/api/assets/report/audit` | Audit log |
| `GET`  | `/api/assets/report/corrected` | Cleaned / corrected dataset |
| `GET`  | `/api/assets/report/removed` | Rows removed during Assets cleanup |
| `GET`  | `/api/health` | `{ "status": "healthy" }` |

Report endpoints accept `?format=csv` (default) or `?format=xlsx`.

Assets validation uses an HTTP-only session cookie (`datalens_assets_session`), separate from the Members session cookie. Keep credentials enabled when calling the API from a separate frontend origin.

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
| Invalid email / lead status | `Manual Review Required` |

Suggestions never invent values outside configured business rules.

### Name validation

- `firstName` must contain 1–30 characters; `lastName` must contain 1–60.
- Unicode letters and combining marks, digits, whitespace, and
  `' ’ ‘ - . ( ) : # ,` are allowed.
- Other punctuation, symbols, quotes, emoji, and URL-shaped values are rejected.
- Bidi and control characters are removed and outer whitespace is trimmed before
  validation.
- Both fields and the four direct/space-separated first/last-name
  concatenations are validated. URL detection uses recognized public suffixes,
  and a concatenation-only failure produces one **Combined Name** issue.
- Blank names retain their configured defaults. Other violations require manual
  correction and are never silently stripped or auto-fixed.

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
