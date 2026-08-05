"""Members validation and report download routes."""

from io import BytesIO
from threading import RLock
from time import monotonic
from typing import Literal
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.exceptions import (
    BusinessRuleException,
    FileValidationException,
    ValidationException,
)
from app.schemas.validation import (
    AddMissingColumnsResponse,
    AutoFixRequest,
    AutoFixIssueRequest,
    FileRowsResponse,
    HealthResponse,
    OperationResponse,
    ManualEditRequest,
    ValidationJobStarted,
    ValidationProgress,
    ValidationResponse,
)
from app.services.validation_jobs import validation_jobs
from app.utils.csv_reader import CsvReadError, read_csv_bytes
from app.validation.members.service import MembersValidationService

router = APIRouter(prefix="/api", tags=["members"])
SESSION_COOKIE = "datalens_validation_session"
SESSION_TTL_SECONDS = 60 * 60
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class ValidationSessionStore:
    """Thread-safe, expiring validation session storage."""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[float, MembersValidationService]] = {}
        self._lock = RLock()

    def put(self, service: MembersValidationService) -> str:
        session_id = uuid4().hex
        with self._lock:
            self._remove_expired()
            self._sessions[session_id] = (monotonic(), service)
        return session_id

    def get(self, session_id: str | None) -> MembersValidationService | None:
        if not session_id:
            return None
        with self._lock:
            self._remove_expired()
            stored = self._sessions.get(session_id)
            if not stored:
                return None
            self._sessions[session_id] = (monotonic(), stored[1])
            return stored[1]

    def _remove_expired(self) -> None:
        cutoff = monotonic() - SESSION_TTL_SECONDS
        expired = [
            session_id
            for session_id, (last_accessed, _) in self._sessions.items()
            if last_accessed < cutoff
        ]
        for session_id in expired:
            del self._sessions[session_id]


session_store = ValidationSessionStore()


@router.post("/members/validate", response_model=ValidationResponse)
async def validate_members(
    response: Response,
    file: UploadFile = File(...),
) -> ValidationResponse:
    """Parse and validate an uploaded members CSV."""
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV exceeds the 50 MB limit")
        dataframe = read_csv_bytes(content)
        service = MembersValidationService()
        result = service.validate_dataframe(dataframe)
        session_id = session_store.put(service)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_id,
            httponly=True,
            max_age=SESSION_TTL_SECONDS,
            samesite="lax",
        )
        return result
    except HTTPException:
        raise
    except CsvReadError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc
    except FileValidationException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BusinessRuleException as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValidationException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected members validation failure")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    finally:
        await file.close()


@router.post(
    "/members/validate/start",
    response_model=ValidationJobStarted,
    status_code=202,
)
async def start_members_validation(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ValidationJobStarted:
    """Upload a CSV and start a trackable background validation job."""
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV exceeds the 50 MB limit")
        dataframe = read_csv_bytes(content)
        job = validation_jobs.create(dataframe)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=job.validation_id,
            httponly=True,
            max_age=SESSION_TTL_SECONDS,
            samesite="lax",
        )
        background_tasks.add_task(
            validation_jobs.run,
            job.validation_id,
            dataframe,
        )
        return ValidationJobStarted(
            validation_id=job.validation_id,
            status=job.status,
            total_records=job.total_records,
        )
    except HTTPException:
        raise
    except CsvReadError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc
    finally:
        await file.close()


@router.get(
    "/members/validate/{validation_id}/progress",
    response_model=ValidationProgress,
)
async def get_validation_progress(validation_id: str) -> ValidationProgress:
    progress = validation_jobs.progress(validation_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Validation job not found")
    return progress


@router.get("/members/rows", response_model=FileRowsResponse)
async def get_members_rows(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> FileRowsResponse:
    """Return one page of rows from the uploaded members file."""
    return _require_session(validation_session).get_file_rows(offset, limit)


@router.get("/members/report/summary")
async def download_summary(
    format: Literal["csv", "xlsx"] = "csv",
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    return _download_report("summary", format, validation_session)


@router.get("/members/report/errors")
async def download_errors(
    format: Literal["csv", "xlsx"] = "csv",
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    return _download_report("errors", format, validation_session)


@router.get("/members/report/audit")
async def download_audit(
    format: Literal["csv", "xlsx"] = "csv",
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    return _download_report("audit", format, validation_session)


@router.get("/members/report/corrected")
async def download_corrected(
    format: Literal["csv", "xlsx"] = "csv",
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    return _download_report("corrected", format, validation_session)


@router.post(
    "/members/file-review/add-missing-columns",
    response_model=AddMissingColumnsResponse,
)
async def add_missing_mandatory_columns(
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> AddMissingColumnsResponse:
    """Add missing mandatory columns as empty fields and re-validate."""
    service = _require_session(validation_session)
    try:
        added_columns, result = service.add_missing_mandatory_columns()
    except BusinessRuleException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if validation_session and validation_jobs.service(validation_session):
        validation_jobs.update_completed_result(
            validation_session,
            result,
            service,
        )

    return AddMissingColumnsResponse(
        status="success",
        message=(
            f"Added {len(added_columns)} missing column"
            f"{'' if len(added_columns) == 1 else 's'} and re-validated the file."
        ),
        added_columns=added_columns,
        result=result,
    )


@router.post("/members/auto-fix", response_model=OperationResponse)
async def apply_auto_fix(
    request: AutoFixRequest,
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> OperationResponse:
    """Apply the configured automatic fix for one business rule."""
    service = _require_session(validation_session)
    try:
        service.apply_auto_fix(request.rule_id)
    except BusinessRuleException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationResponse(
        status="success",
        message=f"Auto-fix applied for {request.rule_id}",
    )


@router.post("/members/auto-fix/issue", response_model=OperationResponse)
async def apply_issue_auto_fix(
    request: AutoFixIssueRequest,
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> OperationResponse:
    """Apply one configured automatic fix to one row."""
    service = _require_session(validation_session)
    try:
        service.apply_issue_auto_fix(request.rule_id, request.row_number)
    except BusinessRuleException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationResponse(status="success", message="Automatic fix applied")


@router.post("/members/edit", response_model=OperationResponse)
async def apply_manual_edit(
    request: ManualEditRequest,
    validation_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> OperationResponse:
    """Apply one user-provided cell edit."""
    service = _require_session(validation_session)
    try:
        service.apply_manual_edit(
            request.row_number, request.field_name, request.value
        )
    except BusinessRuleException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationResponse(status="success", message="Manual edit applied")


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy")


def _require_session(session_id: str | None) -> MembersValidationService:
    service = session_store.get(session_id) or validation_jobs.service(session_id)
    if not service:
        raise HTTPException(
            status_code=404,
            detail="No active validation session. Upload a CSV first.",
        )
    return service


def _download_report(
    report_name: Literal["summary", "errors", "audit", "corrected"],
    file_format: Literal["csv", "xlsx"],
    session_id: str | None,
) -> StreamingResponse:
    service = _require_session(session_id)
    generated = service.create_report_generator().generate(
        report_name, file_format
    )
    headers = {"Content-Disposition": f'attachment; filename="{generated.filename}"'}
    return StreamingResponse(
        BytesIO(generated.content),
        media_type=generated.media_type,
        headers=headers,
    )
