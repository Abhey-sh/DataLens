"""Domain-agnostic orchestration for a single CSV validation session.

`DatasetValidationService` owns the parts of a validation run that do not
depend on which dataset is being validated: reading and cleaning the file,
executing the pipeline, projecting issues into an API response, and applying
fixes or edits afterwards. A domain subclass supplies its own rules.

`MembersValidationService` predates this base and still carries its own copy
of this orchestration; it can be migrated onto this class without changing
its public surface.
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable, ClassVar, Protocol

import pandas as pd
from loguru import logger

from app.core.exceptions import (
    BusinessRuleException,
    FileValidationException,
    ValidationIssue,
)
from app.reports.report_generator import ReportGenerator
from app.schemas.validation import (
    AffectedRow,
    BusinessRuleResult,
    FileRowsResponse,
    ReportMetadata,
    ValidationResponse,
    ValidationSummary,
)
from app.utils.csv_reader import read_csv_bytes
from app.validation.base import (
    FieldValidator,
    FileValidator,
    RowValidator,
    ValidationPipeline,
)
from app.validation.cleaning import DataCleaningPipeline

REPORT_NAMES = ("summary", "errors", "audit", "corrected")


class ValidationService(Protocol):
    """Everything the validation routes need from a domain service."""

    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResponse: ...

    def missing_mandatory_columns(self) -> list[str]: ...

    def add_missing_mandatory_columns(
        self,
    ) -> tuple[list[str], ValidationResponse]: ...

    def apply_auto_fix(
        self, rule_id: str, issue_type: str | None = None
    ) -> ValidationResponse: ...

    def apply_issue_auto_fix(
        self, rule_id: str, row_number: int
    ) -> ValidationResponse: ...

    def apply_manual_edit(
        self, row_number: int, field_name: str, value: str
    ) -> ValidationResponse: ...

    def bulk_fill_blank_cells(
        self, field_name: str, value: str
    ) -> tuple[int, ValidationResponse]: ...

    def get_file_rows(self, offset: int, limit: int) -> FileRowsResponse: ...

    def create_report_generator(self) -> ReportGenerator: ...


class DatasetValidationService:
    """Run one dataset through the validation pipeline and serve its results."""

    #: URL and report-filename segment for this dataset, e.g. "assets".
    domain: ClassVar[str] = "dataset"
    #: Human-readable dataset name used in messages.
    domain_label: ClassVar[str] = "Dataset"
    #: Columns the file must contain; drives add-missing-columns repair.
    required_headers: ClassVar[tuple[str, ...]] = ()
    #: Columns that must stay unique, so bulk fill is refused for them.
    bulk_fill_protected_fields: ClassVar[frozenset[str]] = frozenset()
    #: Column holding the business identifier of a row, when one exists.
    record_id_column: ClassVar[str | None] = None
    #: Column header for the identifier in the errors report.
    record_id_label: ClassVar[str] = "Record ID"
    #: Rules reported as critical even when their issues are only warnings.
    always_critical_rule_ids: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> None:
        self.pipeline: ValidationPipeline | None = None
        self.response: ValidationResponse | None = None
        self.execution_time = 0.0
        self.progress_callback = progress_callback

    # --- validators -----------------------------------------------------

    def file_validators(self) -> list[FileValidator]:
        """File-level rules for this dataset."""
        return []

    def row_validators(self) -> list[RowValidator]:
        """Row-level rules for this dataset."""
        return []

    def field_validators(self) -> list[FieldValidator]:
        """Field-level rules for this dataset."""
        return []

    def _register_validators(self) -> None:
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        for file_validator in self.file_validators():
            self.pipeline.register_file_validator(file_validator)
        for row_validator in self.row_validators():
            self.pipeline.register_row_validator(row_validator)
        for field_validator in self.field_validators():
            self.pipeline.register_field_validator(field_validator)

    # --- validation -----------------------------------------------------

    def validate(self, file_content: bytes) -> ValidationResponse:
        """Read CSV bytes and validate them."""
        logger.info(f"Starting {self.domain} validation")
        try:
            df = read_csv_bytes(file_content)
        except Exception as exc:
            logger.error(f"Failed to read CSV: {exc}")
            raise FileValidationException(f"Failed to read CSV: {exc}") from exc
        return self.validate_dataframe(df)

    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResponse:
        """Validate a parsed DataFrame and build the API response."""
        started_at = perf_counter()
        cleaned = DataCleaningPipeline.clean(df.copy())

        self.pipeline = ValidationPipeline(
            progress_callback=self.progress_callback
        )
        self.pipeline.load_data(cleaned)
        self._register_validators()

        issues = self.pipeline.execute()
        self._report_preparing(issues)

        self.execution_time = perf_counter() - started_at
        self.response = self._build_response(issues)
        logger.info(
            f"{self.domain_label} validation complete: {len(issues)} issues found"
        )
        return self.response

    def _report_preparing(self, issues: list[ValidationIssue]) -> None:
        """Emit the final progress frame before results are assembled."""
        if not self.progress_callback or not self.pipeline:
            return
        total_steps = (
            len(self.pipeline.file_validators)
            + len(self.pipeline.row_validators)
            + len(self.pipeline.field_validators)
        )
        self.progress_callback(
            {
                "stage": "preparing",
                "current_step": "Preparing validation results",
                "completed_steps": total_steps,
                "total_steps": total_steps,
                "potential_issues": len(issues),
                "affected_rows": len(self._affected_row_numbers(issues)),
            }
        )

    # --- mandatory columns ----------------------------------------------

    def missing_mandatory_columns(self) -> list[str]:
        """Required headers that are still absent from the working dataset."""
        working = self._require_working_df()
        return [
            column
            for column in self.required_headers
            if column not in working.columns
        ]

    def add_missing_mandatory_columns(self) -> tuple[list[str], ValidationResponse]:
        """Add absent required headers as empty columns, then re-validate."""
        working = self._require_working_df()
        missing = self.missing_mandatory_columns()
        if not missing:
            raise BusinessRuleException("No missing mandatory columns to add")

        updated = working.copy()
        for column in missing:
            updated[column] = pd.NA
            logger.info(f"Added missing mandatory column: {column}")

        return missing, self._validate_quietly(updated)

    # --- fixes and edits ------------------------------------------------

    def apply_auto_fix(
        self, rule_id: str, issue_type: str | None = None
    ) -> ValidationResponse:
        """Apply matching automatic fixes for one rule, then re-validate."""
        pipeline = self._require_pipeline()
        pipeline.apply_auto_fix(rule_id, issue_type)
        logger.info(f"Auto-fix applied for rule {rule_id}")
        return self._revalidate()

    def apply_issue_auto_fix(
        self, rule_id: str, row_number: int
    ) -> ValidationResponse:
        """Apply one rule's automatic fix to one row, then re-validate."""
        pipeline = self._require_pipeline()
        pipeline.apply_issue_auto_fix(rule_id, row_number)
        return self._revalidate()

    def apply_manual_edit(
        self, row_number: int, field_name: str, value: str
    ) -> ValidationResponse:
        """Apply and audit a user-provided cell value, then re-validate."""
        pipeline = self._require_pipeline()
        working = self._require_working_df()
        if field_name not in working.columns:
            raise BusinessRuleException(f"Unknown field: {field_name}")
        row_index = row_number - 1
        if row_index not in working.index:
            raise BusinessRuleException(f"Unknown row: {row_number}")

        old_value = working.at[row_index, field_name]
        working.at[row_index, field_name] = value
        pipeline._record_audit(
            rule_id="manual_edit",
            row_number=row_number,
            field=field_name,
            old_value=None if pd.isna(old_value) else str(old_value),
            new_value=value,
            changed_by="user",
            auto=False,
        )
        return self._revalidate()

    def bulk_fill_blank_cells(
        self, field_name: str, value: str
    ) -> tuple[int, ValidationResponse]:
        """Fill every blank cell in one column, then re-validate."""
        pipeline = self._require_pipeline()
        current = self._require_working_df()

        column = field_name.strip()
        filler = value.strip()
        if not filler:
            raise BusinessRuleException("Bulk fill value cannot be blank")
        if column not in current.columns:
            raise BusinessRuleException(f"Unknown field: {column}")
        if column in self.bulk_fill_protected_fields:
            raise BusinessRuleException(
                f"Bulk fill is not allowed for unique field: {column}"
            )

        affected_indices = self._blank_indices(current, column)
        if not affected_indices:
            raise BusinessRuleException(f"No blank values found in {column}")

        previous_state = (self.pipeline, self.response, self.execution_time)
        previous_audit = list(pipeline.audit_log)
        old_values = {
            row_index: (
                None
                if pd.isna(current.at[row_index, column])
                else str(current.at[row_index, column])
            )
            for row_index in affected_indices
        }

        updated = current.copy()
        updated.loc[affected_indices, column] = filler
        try:
            result = self._validate_quietly(updated)
        except Exception:
            self.pipeline, self.response, self.execution_time = previous_state
            raise

        affected_rows = {row_index + 1 for row_index in affected_indices}
        if any(
            issue.row_number in affected_rows and issue.field_name == column
            for issue in result.affected_rows
        ):
            self.pipeline, self.response, self.execution_time = previous_state
            raise BusinessRuleException(f"'{filler}' is not valid for {column}")

        if self.pipeline:
            self.pipeline.audit_log = previous_audit
            for row_index in affected_indices:
                self.pipeline._record_audit(
                    rule_id="bulk_fill_blank",
                    row_number=row_index + 1,
                    field=column,
                    old_value=old_values[row_index],
                    new_value=filler,
                    changed_by="user",
                    auto=False,
                )

        return len(affected_indices), result

    def _blank_indices(self, frame: pd.DataFrame, column: str) -> list[int]:
        """Row indexes that are physically blank or flagged blank by a rule."""
        blank_mask = (
            frame[column].isna()
            | frame[column].astype("string").str.strip().eq("").fillna(True)
        )
        eligible = set(frame.index[blank_mask].tolist())
        if self.pipeline:
            eligible.update(
                issue.row_number - 1
                for issue in self.pipeline.all_issues
                if issue.row_number > 0
                and issue.field_name == column
                and issue.issue_type == "blank"
                and issue.row_number - 1 in frame.index
            )
        return [index for index in frame.index if index in eligible]

    def _revalidate(self) -> ValidationResponse:
        """Re-run validation on the working dataset, preserving the audit log."""
        working = self._require_working_df()
        audit = list(self._require_pipeline().audit_log)
        result = self._validate_quietly(working.copy())
        if self.pipeline:
            self.pipeline.audit_log = audit + self.pipeline.audit_log
        return result

    def _validate_quietly(self, frame: pd.DataFrame) -> ValidationResponse:
        """Validate without emitting progress, used for repair passes."""
        previous_callback = self.progress_callback
        self.progress_callback = None
        try:
            return self.validate_dataframe(frame)
        finally:
            self.progress_callback = previous_callback

    # --- results --------------------------------------------------------

    def _build_response(self, issues: list[ValidationIssue]) -> ValidationResponse:
        pipeline = self._require_pipeline()
        working = self._require_working_df()
        total_rows = len(working)

        affected_row_numbers = self._affected_row_numbers(issues)
        rows_with_issues = len(affected_row_numbers)
        row_data_by_number = {
            row_number: self._row_data(row_number)
            for row_number in affected_row_numbers
        }

        return ValidationResponse(
            summary=self._build_summary(issues, total_rows, rows_with_issues),
            business_rules=self._build_business_rules(issues),
            affected_rows=[
                AffectedRow(
                    row_number=issue.row_number,
                    # Schema field is named member_id for backward
                    # compatibility; it carries this domain's record id.
                    member_id=self._record_id(issue.row_number),
                    rule_id=issue.rule_id,
                    rule_name=issue.rule_name,
                    field_name=issue.field_name,
                    current_value=issue.current_value,
                    suggested_value=issue.suggested_value,
                    severity=self._severity_label(issue.severity.value),
                    reason=issue.message,
                    auto_fix_available=issue.auto_fix_available,
                    issue_type=issue.issue_type,
                    row_data=row_data_by_number.get(issue.row_number, {}),
                    status="Pending",
                    action="Auto Fix" if issue.auto_fix_available else "Edit",
                )
                for issue in issues
            ],
            reports={
                name: ReportMetadata(
                    name=name.title(),
                    url=f"/api/{self.domain}/report/{name}",
                )
                for name in REPORT_NAMES
            },
        )

    def _build_summary(
        self,
        issues: list[ValidationIssue],
        total_rows: int,
        rows_with_issues: int,
    ) -> ValidationSummary:
        row_issues = [issue for issue in issues if issue.row_number > 0]
        # Blank cells are surfaced as warnings; anything a rule marks as an
        # error, plus rules pinned as always critical, are critical errors.
        warnings = sum(
            1
            for issue in row_issues
            if self._is_blank_issue(issue)
            or (
                issue.rule_id not in self.always_critical_rule_ids
                and issue.severity.value == "warning"
            )
        )
        critical_errors = sum(
            1
            for issue in row_issues
            if not self._is_blank_issue(issue)
            and (
                issue.rule_id in self.always_critical_rule_ids
                or issue.severity.value == "error"
            )
        )
        validation_score = (
            max(0.0, 100 - (rows_with_issues / total_rows * 100))
            if total_rows and rows_with_issues
            else 100.0
        )

        return ValidationSummary(
            total_records=total_rows,
            valid=total_rows - rows_with_issues,
            critical_errors=critical_errors,
            warnings=warnings,
            auto_fix_available=len(
                [issue for issue in issues if issue.auto_fix_available]
            ),
            manual_review=len(
                [issue for issue in issues if not issue.auto_fix_available]
            ),
            validation_score=round(validation_score, 2),
            execution_time=round(self.execution_time, 4),
        )

    def _build_business_rules(
        self, issues: list[ValidationIssue]
    ) -> list[BusinessRuleResult]:
        pipeline = self._require_pipeline()
        grouped: dict[str, list[ValidationIssue]] = {}
        for issue in issues:
            grouped.setdefault(issue.rule_id, []).append(issue)

        results = []
        for rule_id, rule_issues in grouped.items():
            validator = pipeline._get_validator_by_rule_id(rule_id)
            if not validator:
                continue
            unique_rows = len(self._affected_row_numbers(rule_issues))
            results.append(
                BusinessRuleResult(
                    rule_id=validator.rule_id,
                    rule_name=validator.rule_name,
                    category=validator.category,
                    severity=self._highest_severity(rule_issues),
                    auto_fix_available=any(
                        issue.auto_fix_available for issue in rule_issues
                    ),
                    default_value=validator.default_value,
                    affected_rows=unique_rows or len(rule_issues),
                    business_logic=validator.description,
                )
            )
        return results

    def get_audit_log(self) -> list[dict]:
        """Every recorded change for this session."""
        return self._require_pipeline().audit_log

    def get_file_rows(self, offset: int, limit: int) -> FileRowsResponse:
        """One page of the working dataset, as strings."""
        source = self._require_working_df()
        page = source.iloc[offset : offset + limit]
        return FileRowsResponse(
            columns=[str(column) for column in source.columns],
            rows=[
                {
                    str(column): None if pd.isna(value) else str(value)
                    for column, value in record.items()
                }
                for record in page.to_dict(orient="records")
            ],
            total=len(source),
            offset=offset,
            limit=limit,
        )

    def create_report_generator(self) -> ReportGenerator:
        """Report generator bound to this session's data."""
        pipeline = self._require_pipeline()
        if not self.response:
            raise RuntimeError("Pipeline not initialized")
        return ReportGenerator(
            source=pipeline.original_df,
            corrected=pipeline.working_df,
            issues=pipeline.all_issues,
            audit_log=pipeline.audit_log,
            response=self.response,
            filename_prefix=f"{self.domain}_validation",
            record_id_column=self.record_id_column,
            record_id_label=self.record_id_label,
            apply_contact_export_rules=False,
        )

    # --- helpers --------------------------------------------------------

    def _require_pipeline(self) -> ValidationPipeline:
        if not self.pipeline:
            raise BusinessRuleException("No active validation dataset available")
        return self.pipeline

    def _require_working_df(self) -> pd.DataFrame:
        pipeline = self._require_pipeline()
        if pipeline.working_df is None:
            raise BusinessRuleException("No active validation dataset available")
        return pipeline.working_df

    def _record_id(self, row_number: int) -> str | None:
        if not self.record_id_column or row_number <= 0 or not self.pipeline:
            return None
        working = self.pipeline.working_df
        if working is None or self.record_id_column not in working.columns:
            return None
        row_index = row_number - 1
        if row_index not in working.index:
            return None
        value = working.at[row_index, self.record_id_column]
        return None if pd.isna(value) else str(value)

    def _row_data(self, row_number: int) -> dict[str, str | None]:
        if not self.pipeline or row_number <= 0:
            return {}
        working = self.pipeline.working_df
        if working is None or row_number - 1 not in working.index:
            return {}
        return {
            str(column): None if pd.isna(value) else str(value)
            for column, value in working.loc[row_number - 1].items()
        }

    @staticmethod
    def _affected_row_numbers(issues: list[ValidationIssue]) -> set[int]:
        return {issue.row_number for issue in issues if issue.row_number > 0}

    @staticmethod
    def _is_blank_issue(issue: ValidationIssue) -> bool:
        if issue.row_number <= 0:
            return False
        if issue.issue_type == "blank":
            return True
        return (
            issue.current_value is None
            or str(issue.current_value).strip() == ""
        )

    @staticmethod
    def _highest_severity(issues: list[ValidationIssue]) -> str:
        rank = {"info": 0, "warning": 1, "error": 2}
        highest = max(
            issues, key=lambda issue: rank[issue.severity.value]
        ).severity.value
        return {"error": "Critical", "warning": "Warning", "info": "Info"}[highest]

    @staticmethod
    def _severity_label(value: str) -> str:
        return {"error": "Error", "warning": "Warning", "info": "Info"}[value]
