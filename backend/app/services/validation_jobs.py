"""Thread-safe background validation job tracking."""

from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Callable
from uuid import uuid4

import pandas as pd

from app.schemas.validation import ValidationProgress, ValidationResponse
from app.validation.dataset_service import ValidationService
from app.validation.members.service import MembersValidationService


JOB_TTL_SECONDS = 60 * 60

ServiceFactory = Callable[..., ValidationService]


@dataclass
class ValidationJob:
    validation_id: str
    total_records: int
    status: str = "queued"
    stage: str = "reading"
    current_step: str = "Reading CSV file"
    completed_steps: int = 0
    total_steps: int = 0
    records_scanned: int = 0
    potential_issues: int = 0
    validation_score: float | None = None
    checks: list[dict] = field(default_factory=list)
    error: str | None = None
    result: ValidationResponse | None = None
    service: ValidationService | None = None
    started_at: float = field(default_factory=monotonic)
    completed_at: float | None = None
    last_accessed: float = field(default_factory=monotonic)


class ValidationJobStore:
    """Run validation work and expose truthful progress snapshots.

    One store serves one dataset domain; ``service_factory`` decides which
    validation service the background job runs.
    """

    def __init__(self, service_factory: ServiceFactory) -> None:
        self._jobs: dict[str, ValidationJob] = {}
        self._service_factory = service_factory
        self._lock = RLock()

    def create(self, dataframe: pd.DataFrame) -> ValidationJob:
        job = ValidationJob(
            validation_id=uuid4().hex,
            total_records=len(dataframe),
            records_scanned=len(dataframe),
        )
        with self._lock:
            self._remove_expired()
            self._jobs[job.validation_id] = job
        return job

    def run(self, validation_id: str, dataframe: pd.DataFrame) -> None:
        self._update(
            validation_id,
            status="running",
            stage="validating",
            current_step="Starting validation checks",
        )

        def report(payload: dict) -> None:
            total_records = len(dataframe)
            affected_rows = payload["affected_rows"]
            score = (
                max(0.0, 100 - (affected_rows / total_records * 100))
                if total_records
                else 100.0
            )
            self._update_checks(validation_id, payload)
            self._update(
                validation_id,
                status="running",
                stage=payload.get("stage", "validating"),
                current_step=payload["current_step"],
                completed_steps=payload["completed_steps"],
                total_steps=payload["total_steps"],
                potential_issues=payload["potential_issues"],
                validation_score=round(score, 2),
            )

        service = self._service_factory(progress_callback=report)
        try:
            result = service.validate_dataframe(dataframe)
            self._update(
                validation_id,
                status="completed",
                stage="complete",
                current_step="Validation complete",
                completed_steps=self._get(validation_id).total_steps,
                validation_score=result.summary.validation_score,
                potential_issues=len(result.affected_rows),
                result=result,
                service=service,
                completed_at=monotonic(),
            )
        except Exception as exc:
            self._update(
                validation_id,
                status="failed",
                stage="failed",
                current_step="Validation failed",
                error=str(exc),
                completed_at=monotonic(),
            )

    def progress(self, validation_id: str) -> ValidationProgress | None:
        with self._lock:
            self._remove_expired()
            job = self._jobs.get(validation_id)
            if not job:
                return None
            job.last_accessed = monotonic()
            now = monotonic()
            elapsed_time = (job.completed_at or now) - job.started_at
            estimated_remaining = None
            if (
                job.status == "running"
                and job.completed_steps > 0
                and job.total_steps > job.completed_steps
            ):
                average_step_time = elapsed_time / job.completed_steps
                estimated_remaining = average_step_time * (
                    job.total_steps - job.completed_steps
                )
            elif job.status == "completed":
                estimated_remaining = 0.0
            return ValidationProgress(
                validation_id=job.validation_id,
                status=job.status,
                stage=job.stage,
                current_step=job.current_step,
                completed_steps=job.completed_steps,
                total_steps=job.total_steps,
                records_scanned=job.records_scanned,
                total_records=job.total_records,
                potential_issues=job.potential_issues,
                validation_score=job.validation_score,
                elapsed_time=round(elapsed_time, 2),
                estimated_remaining=(
                    round(estimated_remaining, 2)
                    if estimated_remaining is not None
                    else None
                ),
                checks=job.checks,
                error=job.error,
                result=job.result,
            )

    def service(self, validation_id: str | None) -> ValidationService | None:
        if not validation_id:
            return None
        with self._lock:
            self._remove_expired()
            job = self._jobs.get(validation_id)
            if not job:
                return None
            job.last_accessed = monotonic()
            return job.service

    def update_completed_result(
        self,
        validation_id: str,
        result: ValidationResponse,
        service: ValidationService,
    ) -> None:
        """Replace a completed job's result after a repair pass."""
        issue_counts: dict[str, int] = {}
        for row in result.affected_rows:
            issue_counts[row.rule_id] = issue_counts.get(row.rule_id, 0) + 1

        with self._lock:
            job = self._jobs[validation_id]
            updated_checks = [
                {
                    **check,
                    "status": "completed",
                    "issues_found": issue_counts.get(check["check_id"], 0),
                }
                for check in job.checks
            ]

        self._update(
            validation_id,
            status="completed",
            stage="complete",
            current_step="Validation complete",
            validation_score=result.summary.validation_score,
            potential_issues=len(result.affected_rows),
            result=result,
            service=service,
            completed_at=monotonic(),
            checks=updated_checks,
        )

    def _get(self, validation_id: str) -> ValidationJob:
        with self._lock:
            return self._jobs[validation_id]

    def _update(self, validation_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[validation_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.last_accessed = monotonic()

    def _update_checks(self, validation_id: str, payload: dict) -> None:
        with self._lock:
            job = self._jobs[validation_id]
            if "checks" in payload:
                job.checks = [dict(check) for check in payload["checks"]]
                return
            check_id = payload.get("check_id")
            if not check_id:
                return
            for check in job.checks:
                if check["check_id"] == check_id:
                    check["status"] = payload["check_status"]
                    check["issues_found"] = payload["check_issues_found"]
                    check["duration_ms"] = payload["check_duration_ms"]
                    break

    def _remove_expired(self) -> None:
        cutoff = monotonic() - JOB_TTL_SECONDS
        expired = [
            validation_id
            for validation_id, job in self._jobs.items()
            if job.last_accessed < cutoff
        ]
        for validation_id in expired:
            del self._jobs[validation_id]


validation_jobs = ValidationJobStore(MembersValidationService)
