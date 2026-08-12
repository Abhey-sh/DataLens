"""Reusable validation routes for one dataset domain.

``build_validation_router`` produces the full upload → validate → review →
download surface for a single dataset under ``/api/{domain}/...``. Each domain
gets its own job store, session store, and session cookie, so validating one
dataset never disturbs another.

``routes/members.py`` still declares its own equivalent endpoints and can be
folded into this factory later.
"""

from io import BytesIO
from typing import Literal

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
    AutoFixIssueRequest,
    AutoFixRequest,
    BulkFillRequest,
    BulkFillResponse,
    FileRowsResponse,
    ManualEditRequest,
    OperationResponse,
    ValidationJobStarted,
    ValidationProgress,
    ValidationResponse,
)
from app.services.validation_jobs import ServiceFactory, ValidationJobStore
from app.services.validation_sessions import (
    SESSION_TTL_SECONDS,
    ValidationSessionStore,
)
from app.utils.csv_reader import CsvReadError, read_csv_bytes
from app.validation.dataset_service import ValidationService

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ReportName = Literal["summary", "errors", "audit", "corrected", "removed"]
FileFormat = Literal["csv", "xlsx"]


def build_validation_router(
    *,
    domain: str,
    service_factory: ServiceFactory,
    session_cookie: str,
) -> APIRouter:
    """Build the validation routes for one dataset domain."""
    router = APIRouter(prefix="/api", tags=[domain])
    session_store = ValidationSessionStore()
    validation_jobs = ValidationJobStore(service_factory)

    def require_session(session_id: str | None) -> ValidationService:
        service = session_store.get(session_id) or validation_jobs.service(
            session_id
        )
        if not service:
            raise HTTPException(
                status_code=404,
                detail="No active validation session. Upload a CSV first.",
            )
        return service

    def sync_job_result(
        session_id: str | None,
        result: ValidationResponse,
        service: ValidationService,
    ) -> None:
        """Keep a completed job's cached result in step with a repair pass."""
        if session_id and validation_jobs.service(session_id):
            validation_jobs.update_completed_result(session_id, result, service)

    def set_session_cookie(response: Response, session_id: str) -> None:
        response.set_cookie(
            key=session_cookie,
            value=session_id,
            httponly=True,
            max_age=SESSION_TTL_SECONDS,
            samesite="lax",
        )

    async def read_upload(file: UploadFile) -> bytes:
        if not (file.filename or "").lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail="CSV exceeds the 50 MB limit"
            )
        return content

    @router.post(f"/{domain}/validate", response_model=ValidationResponse)
    async def validate(
        response: Response,
        file: UploadFile = File(...),
    ) -> ValidationResponse:
        """Parse and validate an uploaded CSV in one request."""
        try:
            content = await read_upload(file)
            dataframe = read_csv_bytes(content)
            service = service_factory()
            result = service.validate_dataframe(dataframe)
            set_session_cookie(response, session_store.put(service))
            return result
        except HTTPException:
            raise
        except CsvReadError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid CSV: {exc}"
            ) from exc
        except FileValidationException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BusinessRuleException as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValidationException as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(f"Unexpected {domain} validation failure")
            raise HTTPException(
                status_code=500, detail="Internal server error"
            ) from exc
        finally:
            await file.close()

    @router.post(
        f"/{domain}/validate/start",
        response_model=ValidationJobStarted,
        status_code=202,
    )
    async def start_validation(
        response: Response,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
    ) -> ValidationJobStarted:
        """Upload a CSV and start a trackable background validation job."""
        try:
            content = await read_upload(file)
            dataframe = read_csv_bytes(content)
            job = validation_jobs.create(dataframe)
            set_session_cookie(response, job.validation_id)
            background_tasks.add_task(
                validation_jobs.run, job.validation_id, dataframe
            )
            return ValidationJobStarted(
                validation_id=job.validation_id,
                status=job.status,
                total_records=job.total_records,
            )
        except HTTPException:
            raise
        except CsvReadError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid CSV: {exc}"
            ) from exc
        finally:
            await file.close()

    @router.get(
        f"/{domain}/validate/{{validation_id}}/progress",
        response_model=ValidationProgress,
    )
    async def get_progress(validation_id: str) -> ValidationProgress:
        progress = validation_jobs.progress(validation_id)
        if not progress:
            raise HTTPException(
                status_code=404, detail="Validation job not found"
            )
        return progress

    @router.get(f"/{domain}/rows", response_model=FileRowsResponse)
    async def get_rows(
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> FileRowsResponse:
        """Return one page of rows from the uploaded file."""
        return require_session(validation_session).get_file_rows(offset, limit)

    @router.get(f"/{domain}/report/{{report_name}}")
    async def download_report(
        report_name: ReportName,
        format: FileFormat = "csv",
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> StreamingResponse:
        service = require_session(validation_session)
        generated = service.create_report_generator().generate(
            report_name, format
        )
        return StreamingResponse(
            BytesIO(generated.content),
            media_type=generated.media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{generated.filename}"'
                )
            },
        )

    @router.post(
        f"/{domain}/file-review/add-missing-columns",
        response_model=AddMissingColumnsResponse,
    )
    async def add_missing_mandatory_columns(
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> AddMissingColumnsResponse:
        """Add missing mandatory columns as empty fields and re-validate."""
        service = require_session(validation_session)
        try:
            added_columns, result = service.add_missing_mandatory_columns()
        except BusinessRuleException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sync_job_result(validation_session, result, service)
        return AddMissingColumnsResponse(
            status="success",
            message=(
                f"Added {len(added_columns)} missing column"
                f"{'' if len(added_columns) == 1 else 's'} "
                "and re-validated the file."
            ),
            added_columns=added_columns,
            result=result,
        )

    @router.post(f"/{domain}/auto-fix", response_model=OperationResponse)
    async def apply_auto_fix(
        request: AutoFixRequest,
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> OperationResponse:
        """Apply the configured automatic fix for one business rule."""
        service = require_session(validation_session)
        try:
            result = service.apply_auto_fix(request.rule_id)
        except BusinessRuleException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sync_job_result(validation_session, result, service)
        return OperationResponse(
            status="success",
            message=f"Auto-fix applied for {request.rule_id}",
            result=result,
        )

    @router.post(f"/{domain}/auto-fix/issue", response_model=OperationResponse)
    async def apply_issue_auto_fix(
        request: AutoFixIssueRequest,
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> OperationResponse:
        """Apply one configured automatic fix to one row."""
        service = require_session(validation_session)
        try:
            result = service.apply_issue_auto_fix(
                request.rule_id, request.row_number
            )
        except BusinessRuleException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sync_job_result(validation_session, result, service)
        return OperationResponse(
            status="success",
            message="Automatic fix applied",
            result=result,
        )

    @router.post(f"/{domain}/edit", response_model=OperationResponse)
    async def apply_manual_edit(
        request: ManualEditRequest,
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> OperationResponse:
        """Apply one user-provided cell edit."""
        service = require_session(validation_session)
        try:
            result = service.apply_manual_edit(
                request.row_number, request.field_name, request.value
            )
        except BusinessRuleException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sync_job_result(validation_session, result, service)
        return OperationResponse(
            status="success",
            message="Manual edit applied",
            result=result,
        )

    @router.post(f"/{domain}/bulk-fill", response_model=BulkFillResponse)
    async def bulk_fill_blank_cells(
        request: BulkFillRequest,
        validation_session: str | None = Cookie(
            default=None, alias=session_cookie
        ),
    ) -> BulkFillResponse:
        """Fill blank cells in one allowed column and re-validate."""
        service = require_session(validation_session)
        try:
            updated_rows, result = service.bulk_fill_blank_cells(
                request.field_name, request.value
            )
        except BusinessRuleException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sync_job_result(validation_session, result, service)
        return BulkFillResponse(
            status="success",
            message=(
                f"Filled {updated_rows} blank value"
                f"{'' if updated_rows == 1 else 's'} in {request.field_name}."
            ),
            field_name=request.field_name,
            updated_rows=updated_rows,
            result=result,
        )

    return router
