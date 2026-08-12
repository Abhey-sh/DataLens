"""Assets validation service — independent of Members rules."""

from __future__ import annotations

from time import perf_counter
from typing import Callable

import pandas as pd
from loguru import logger

from app.core.exceptions import BusinessRuleException, ValidationIssue
from app.reports.report_generator import ReportGenerator
from app.schemas.validation import (
    AffectedRow,
    BusinessRuleResult,
    ReportMetadata,
    ValidationResponse,
    ValidationSummary,
)
from app.validation.assets.validators import (
    BULK_FILL_PROTECTED_FIELDS,
    RECORD_ID_COLUMN,
    REQUIRED_HEADERS,
    RequiredHeaderValidator,
    collect_asset_url_removals,
    collect_duplicate_resource_id_removals,
    collect_resource_type_removals,
    collect_studio_mismatch_removals,
)
from app.validation.base import ValidationPipeline
from app.validation.cleaning import DataCleaningPipeline
from app.validation.dataset_service import DatasetValidationService

REPORT_NAMES = ("summary", "errors", "audit", "corrected", "removed")


class AssetsValidationService(DatasetValidationService):
    """Validate an Assets CSV and drop invalid full rows automatically."""

    domain = "assets"
    domain_label = "Assets"
    required_headers = REQUIRED_HEADERS
    bulk_fill_protected_fields = BULK_FILL_PROTECTED_FIELDS
    record_id_column = RECORD_ID_COLUMN
    record_id_label = "Resource Foreign ID"

    def __init__(
        self,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__(progress_callback=progress_callback)
        self.removed_row_numbers: set[int] = set()
        self.majority_studio: tuple[str, str] | None = None

    def file_validators(self):
        return [RequiredHeaderValidator()]

    def row_validators(self):
        return []

    def field_validators(self):
        return []

    def add_missing_mandatory_columns(self) -> tuple[list[str], ValidationResponse]:
        """Assets does not auto-add columns — the user must fix the file."""
        raise BusinessRuleException(
            "Missing Assets headers cannot be added automatically. "
            "Fix the CSV columns and upload the file again."
        )

    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResponse:
        """Clean, check headers, remove invalid rows, then build the response."""
        started_at = perf_counter()
        cleaned = DataCleaningPipeline.clean(df.copy())
        self.removed_row_numbers = set()
        self.majority_studio = None

        self.pipeline = ValidationPipeline(
            progress_callback=self.progress_callback
        )
        self.pipeline.load_data(cleaned)

        checks = [
            ("required_headers", "Required Headers"),
            ("primary_studio", "Primary Studio Filter"),
            ("resource_type", "Resource Type"),
            ("asset_url", "Asset URL Image Type"),
            ("duplicate_resource_foreign_id", "Duplicate Resource Foreign ID"),
        ]
        self._emit_catalog(checks)

        header_issues = RequiredHeaderValidator().validate(cleaned)
        self._emit_check(
            "required_headers",
            "Required Headers",
            "completed",
            completed_steps=1,
            total_steps=len(checks),
            issues_found=len(header_issues),
        )

        if header_issues:
            self.pipeline.all_issues = header_issues
            self.execution_time = perf_counter() - started_at
            self.response = self._build_assets_response(
                header_issues, total_input_rows=len(cleaned)
            )
            return self.response

        working = cleaned.copy()
        all_issues: list[ValidationIssue] = []
        completed = 1

        studio_indices, studio_issues, majority = collect_studio_mismatch_removals(
            working
        )
        self.majority_studio = majority
        working, removed = self._drop_rows(
            working, studio_indices, studio_issues, "primary_studio"
        )
        all_issues.extend(studio_issues)
        completed += 1
        self._emit_check(
            "primary_studio",
            "Primary Studio Filter",
            "completed",
            completed_steps=completed,
            total_steps=len(checks),
            issues_found=len(studio_issues),
        )

        type_indices, type_issues = collect_resource_type_removals(working)
        working, _ = self._drop_rows(
            working, type_indices, type_issues, "resource_type"
        )
        all_issues.extend(type_issues)
        completed += 1
        self._emit_check(
            "resource_type",
            "Resource Type",
            "completed",
            completed_steps=completed,
            total_steps=len(checks),
            issues_found=len(type_issues),
        )

        url_indices, url_issues = collect_asset_url_removals(working)
        working, _ = self._drop_rows(working, url_indices, url_issues, "asset_url")
        all_issues.extend(url_issues)
        completed += 1
        self._emit_check(
            "asset_url",
            "Asset URL Image Type",
            "completed",
            completed_steps=completed,
            total_steps=len(checks),
            issues_found=len(url_issues),
        )

        dup_indices, dup_issues = collect_duplicate_resource_id_removals(working)
        working, _ = self._drop_rows(
            working, dup_indices, dup_issues, "duplicate_resource_foreign_id"
        )
        all_issues.extend(dup_issues)
        completed += 1
        self._emit_check(
            "duplicate_resource_foreign_id",
            "Duplicate Resource Foreign ID",
            "completed",
            completed_steps=completed,
            total_steps=len(checks),
            issues_found=len(dup_issues),
        )

        # Keep original_df as the uploaded file; working_df is the cleaned output.
        self.pipeline.working_df = working.reset_index(drop=True)
        self.pipeline.all_issues = all_issues
        self.execution_time = perf_counter() - started_at

        if self.progress_callback:
            self.progress_callback(
                {
                    "stage": "preparing",
                    "current_step": "Preparing validation results",
                    "completed_steps": len(checks),
                    "total_steps": len(checks),
                    "potential_issues": len(all_issues),
                    "affected_rows": len(self.removed_row_numbers),
                }
            )

        self.response = self._build_assets_response(
            all_issues, total_input_rows=len(cleaned)
        )
        logger.info(
            f"Assets validation complete: kept {len(working)} / {len(cleaned)} rows "
            f"({len(self.removed_row_numbers)} removed)"
        )
        return self.response

    def _drop_rows(
        self,
        frame: pd.DataFrame,
        indices: list[int],
        issues: list[ValidationIssue],
        rule_id: str,
    ) -> tuple[pd.DataFrame, int]:
        if not indices:
            return frame, 0

        unique_indices = sorted(set(indices))
        for index in unique_indices:
            self.removed_row_numbers.add(index + 1)
            row = frame.loc[index] if index in frame.index else None
            old_id = None
            if row is not None and "resourceForeignId" in frame.columns:
                value = row.get("resourceForeignId")
                old_id = None if pd.isna(value) else str(value)
            self.pipeline._record_audit(
                rule_id=rule_id,
                row_number=index + 1,
                field="row",
                old_value=old_id,
                new_value=None,
                changed_by="system",
                auto=True,
            )

        updated = frame.drop(index=unique_indices, errors="ignore")
        logger.info(f"Assets {rule_id}: removed {len(unique_indices)} row(s)")
        return updated, len(unique_indices)

    def _emit_catalog(self, checks: list[tuple[str, str]]) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            {
                "current_step": "Starting validation checks",
                "completed_steps": 0,
                "total_steps": len(checks),
                "potential_issues": 0,
                "affected_rows": 0,
                "checks": [
                    {
                        "check_id": check_id,
                        "name": name,
                        "status": "pending",
                        "issues_found": 0,
                        "duration_ms": None,
                    }
                    for check_id, name in checks
                ],
            }
        )

    def _emit_check(
        self,
        check_id: str,
        name: str,
        status: str,
        *,
        completed_steps: int,
        total_steps: int,
        issues_found: int,
    ) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            {
                "current_step": name,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "potential_issues": len(self.pipeline.all_issues)
                if self.pipeline
                else issues_found,
                "affected_rows": len(self.removed_row_numbers),
                "check_id": check_id,
                "check_name": name,
                "check_status": status,
                "check_issues_found": issues_found,
                "check_duration_ms": None,
            }
        )

    def _build_assets_response(
        self,
        issues: list[ValidationIssue],
        *,
        total_input_rows: int,
    ) -> ValidationResponse:
        kept_rows = (
            len(self.pipeline.working_df)
            if self.pipeline and self.pipeline.working_df is not None
            else 0
        )
        removed_count = len(self.removed_row_numbers)
        header_blocked = any(issue.rule_id == "required_headers" for issue in issues)

        if header_blocked:
            valid = 0
            score = 0.0
        else:
            valid = kept_rows
            score = (
                round(100 * kept_rows / total_input_rows, 2)
                if total_input_rows
                else 100.0
            )

        summary = ValidationSummary(
            total_records=total_input_rows,
            valid=valid,
            critical_errors=len(
                [issue for issue in issues if issue.severity.value == "error"]
            ),
            warnings=0,
            auto_fix_available=0,
            manual_review=1 if header_blocked else 0,
            validation_score=score,
            execution_time=round(self.execution_time, 4),
        )

        grouped: dict[str, list[ValidationIssue]] = {}
        for issue in issues:
            grouped.setdefault(issue.rule_id, []).append(issue)

        rule_meta = {
            "required_headers": (
                "Required Headers",
                "File Level",
                "Assets files must include all mandatory columns",
            ),
            "primary_studio": (
                "Primary Studio Filter",
                "Row Removal",
                "Keep rows for the most common studioForeignId/studioId pair; remove other full rows",
            ),
            "resource_type": (
                "Resource Type",
                "Row Removal",
                "Only MEMBER or STAFF are allowed; other rows are removed",
            ),
            "asset_url": (
                "Asset URL Image Type",
                "Row Removal",
                "Only .jpg/.jpeg/.png/.bmp image URLs are kept",
            ),
            "duplicate_resource_foreign_id": (
                "Duplicate Resource Foreign ID",
                "Row Removal",
                "Keep the first resourceForeignId; remove later duplicates",
            ),
        }

        business_rules = []
        for rule_id, rule_issues in grouped.items():
            name, category, logic = rule_meta.get(
                rule_id, (rule_id, "Assets", rule_id)
            )
            business_rules.append(
                BusinessRuleResult(
                    rule_id=rule_id,
                    rule_name=name,
                    category=category,
                    severity="Critical",
                    auto_fix_available=False,
                    default_value=None,
                    affected_rows=len(
                        {
                            issue.row_number
                            for issue in rule_issues
                            if issue.row_number > 0
                        }
                    )
                    or len(rule_issues),
                    business_logic=logic,
                )
            )

        affected_rows = [
            AffectedRow(
                row_number=issue.row_number,
                member_id=self._original_record_id(issue.row_number),
                rule_id=issue.rule_id,
                rule_name=issue.rule_name,
                field_name=issue.field_name,
                current_value=issue.current_value,
                suggested_value=issue.suggested_value,
                severity="Error",
                reason=issue.message,
                auto_fix_available=False,
                issue_type=issue.issue_type,
                row_data=self._original_row_data(issue.row_number),
                status=(
                    "Blocked"
                    if issue.rule_id == "required_headers"
                    else "Removed"
                ),
                action=(
                    "Fix File"
                    if issue.rule_id == "required_headers"
                    else "Removed"
                ),
            )
            for issue in issues
        ]

        return ValidationResponse(
            summary=summary,
            business_rules=business_rules,
            affected_rows=affected_rows,
            reports={
                name: ReportMetadata(
                    name=name.title(),
                    url=f"/api/{self.domain}/report/{name}",
                )
                for name in REPORT_NAMES
            },
        )

    def _original_record_id(self, row_number: int) -> str | None:
        if (
            not self.pipeline
            or row_number <= 0
            or self.pipeline.original_df is None
            or "resourceForeignId" not in self.pipeline.original_df.columns
        ):
            return None
        index = row_number - 1
        if index not in self.pipeline.original_df.index:
            return None
        value = self.pipeline.original_df.at[index, "resourceForeignId"]
        return None if pd.isna(value) else str(value)

    def _original_row_data(self, row_number: int) -> dict[str, str | None]:
        """Return the uploaded row values for display / removed-row preview."""
        if (
            not self.pipeline
            or row_number <= 0
            or self.pipeline.original_df is None
        ):
            return {}
        index = row_number - 1
        if index not in self.pipeline.original_df.index:
            return {}
        row = self.pipeline.original_df.loc[index]
        return {
            str(column): None if pd.isna(value) else str(value)
            for column, value in row.items()
        }

    def create_report_generator(self) -> ReportGenerator:
        if not self.pipeline or not self.response:
            raise RuntimeError("Pipeline not initialized")
        return ReportGenerator(
            source=self.pipeline.original_df,
            corrected=self.pipeline.working_df,
            issues=self.pipeline.all_issues,
            audit_log=self.pipeline.audit_log,
            response=self.response,
            removed_rows=set(self.removed_row_numbers),
            filename_prefix="assets_validation",
            record_id_column=self.record_id_column,
            record_id_label=self.record_id_label,
            apply_contact_export_rules=False,
        )
