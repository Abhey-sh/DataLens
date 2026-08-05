"""
Members validation service - orchestrates the validation pipeline.
"""

from time import perf_counter
from typing import Callable

import pandas as pd
from loguru import logger

from app.validation.cleaning import DataCleaningPipeline
from app.validation.base import ValidationPipeline
from app.core.exceptions import (
    BusinessRuleException,
    FileValidationException,
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
from app.validation.members.validators import (
    REQUIRED_HEADERS,
    RequiredHeaderValidator,
    StudioForeignIdValidator,
    RequiredFieldValidator,
    EmailValidator,
    GenderValidator,
    BirthDateValidator,
    LeadStatusValidator,
    CountryCodeValidator,
    FirstNameDefaultValidator,
    LastNameDefaultValidator,
    PostalCodeDefaultValidator,
)


class MembersValidationService:
    """
    Main service for validating members datasets.
    Coordinates the complete validation workflow.
    """

    def __init__(
        self,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self.pipeline = None
        self.response: ValidationResponse | None = None
        self.execution_time = 0.0
        self.progress_callback = progress_callback

    def validate(self, file_content: bytes) -> ValidationResponse:
        """
        Complete validation workflow.
        
        Args:
            file_content: CSV file bytes
            
        Returns:
            ValidationResponse with all results
        """
        logger.info("Starting members validation")
        
        # Read CSV
        try:
            df = read_csv_bytes(file_content)
            logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            raise FileValidationException(f"Failed to read CSV: {e}")

        return self.validate_dataframe(df)

    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResponse:
        """Validate a parsed members DataFrame."""
        started_at = perf_counter()
        df = DataCleaningPipeline.clean(df.copy())

        # Initialize pipeline
        self.pipeline = ValidationPipeline(
            progress_callback=self.progress_callback
        )
        self.pipeline.load_data(df)

        # Register validators
        self._register_validators()

        # Execute validation
        issues = self.pipeline.execute()
        if self.progress_callback:
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
                    "affected_rows": len(
                        {
                            issue.row_number
                            for issue in issues
                            if issue.row_number > 0
                        }
                    ),
                }
            )

        # Build response
        self.execution_time = perf_counter() - started_at
        self.response = self._build_response(issues)

        logger.info(f"Validation complete: {len(issues)} total issues found")
        return self.response

    def missing_mandatory_columns(self) -> list[str]:
        """Return mandatory headers that are still missing from the working dataset."""
        if not self.pipeline or self.pipeline.working_df is None:
            raise BusinessRuleException("No active validation dataset available")
        return [
            column
            for column in REQUIRED_HEADERS
            if column not in self.pipeline.working_df.columns
        ]

    def add_missing_mandatory_columns(self) -> tuple[list[str], ValidationResponse]:
        """
        Add any missing mandatory columns as empty fields, then re-run validation.
        """
        if not self.pipeline or self.pipeline.working_df is None:
            raise BusinessRuleException("No active validation dataset available")

        missing = self.missing_mandatory_columns()
        if not missing:
            raise BusinessRuleException("No missing mandatory columns to add")

        updated = self.pipeline.working_df.copy()
        for column in missing:
            updated[column] = pd.NA
            logger.info(f"Added missing mandatory column: {column}")

        # Re-validate without live progress updates for this repair pass
        previous_callback = self.progress_callback
        self.progress_callback = None
        try:
            result = self.validate_dataframe(updated)
        finally:
            self.progress_callback = previous_callback

        return missing, result

    def _register_validators(self):
        """Register all validators in the pipeline."""
        # File-level validators
        self.pipeline.register_file_validator(RequiredHeaderValidator())
        self.pipeline.register_file_validator(StudioForeignIdValidator())

        # Row-level validators
        self.pipeline.register_row_validator(RequiredFieldValidator())
        self.pipeline.register_row_validator(FirstNameDefaultValidator())
        self.pipeline.register_row_validator(LastNameDefaultValidator())
        self.pipeline.register_row_validator(PostalCodeDefaultValidator())

        # Field-level validators
        self.pipeline.register_field_validator(EmailValidator())
        self.pipeline.register_field_validator(GenderValidator())
        self.pipeline.register_field_validator(BirthDateValidator())
        self.pipeline.register_field_validator(LeadStatusValidator())
        self.pipeline.register_field_validator(CountryCodeValidator())

        logger.info("All validators registered")

    def _build_response(self, issues: list) -> ValidationResponse:
        """Build the validation response."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")

        # Calculate summary
        total_rows = len(self.pipeline.working_df)
        
        # Count issues by rule
        rule_issues = {}
        for issue in issues:
            if issue.rule_id not in rule_issues:
                rule_issues[issue.rule_id] = []
            rule_issues[issue.rule_id].append(issue)

        # Build business rule responses
        business_rules = []
        for rule_id, rule_issues_list in rule_issues.items():
            validator = self.pipeline._get_validator_by_rule_id(rule_id)
            if validator:
                unique_rows = len(
                    {
                        issue.row_number
                        for issue in rule_issues_list
                        if issue.row_number > 0
                    }
                )
                if unique_rows == 0 and rule_issues_list:
                    unique_rows = len(rule_issues_list)
                severity = self._highest_severity(rule_issues_list)
                business_rules.append(
                    BusinessRuleResult(
                        rule_id=validator.rule_id,
                        rule_name=validator.rule_name,
                        category=validator.category,
                        severity=severity,
                        auto_fix_available=any(
                            issue.auto_fix_available for issue in rule_issues_list
                        ),
                        default_value=validator.default_value,
                        affected_rows=unique_rows,
                        business_logic=validator.description,
                    )
                )

        # Calculate summary metrics
        affected_row_numbers = {issue.row_number for issue in issues if issue.row_number > 0}
        rows_with_issues = len(affected_row_numbers)
        critical_errors = len([i for i in issues if i.severity.value == "error"])
        warnings = len([i for i in issues if i.severity.value == "warning"])
        auto_fixes = len([i for i in issues if i.auto_fix_available])
        manual_review = len([i for i in issues if not i.auto_fix_available])
        
        # Calculate validation score (0-100)
        if rows_with_issues > 0:
            validation_score = max(0, 100 - (rows_with_issues / total_rows * 100))
        else:
            validation_score = 100.0

        summary = ValidationSummary(
            total_records=total_rows,
            valid=total_rows - rows_with_issues,
            critical_errors=critical_errors,
            warnings=warnings,
            auto_fix_available=auto_fixes,
            manual_review=manual_review,
            validation_score=round(validation_score, 2),
            execution_time=round(self.execution_time, 4),
        )

        row_data_by_number = {
            row_number: self._row_data(row_number)
            for row_number in affected_row_numbers
        }
        affected_rows = [
            AffectedRow(
                row_number=issue.row_number,
                member_id=self._member_id(issue.row_number)
                if issue.row_number > 0
                else None,
                rule_id=issue.rule_id,
                rule_name=issue.rule_name,
                field_name=issue.field_name,
                current_value=issue.current_value,
                suggested_value=issue.suggested_value,
                severity=self._severity_label(issue.severity.value),
                reason=issue.message,
                auto_fix_available=issue.auto_fix_available,
                row_data=row_data_by_number.get(issue.row_number, {}),
                status="Pending",
                action="Auto Fix" if issue.auto_fix_available else "Edit",
            )
            for issue in issues
        ]

        report_base = "/api/members/report"
        response = ValidationResponse(
            summary=summary,
            business_rules=business_rules,
            affected_rows=affected_rows,
            reports={
                name: ReportMetadata(
                    name=name.title(),
                    url=f"{report_base}/{name}",
                )
                for name in ("summary", "errors", "audit", "corrected")
            },
        )

        return response

    def apply_auto_fix(self, rule_id: str):
        """Apply automatic fix for a rule."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        self.pipeline.apply_auto_fix(rule_id)
        logger.info(f"Auto-fix applied for rule {rule_id}")

    def apply_issue_auto_fix(self, rule_id: str, row_number: int) -> None:
        """Apply one configured automatic fix."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        self.pipeline.apply_issue_auto_fix(rule_id, row_number)

    def apply_manual_edit(
        self, row_number: int, field_name: str, value: str
    ) -> None:
        """Apply and audit a user-provided value for one cell."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        if field_name not in self.pipeline.working_df.columns:
            raise BusinessRuleException(f"Unknown field: {field_name}")
        row_index = row_number - 1
        if row_index not in self.pipeline.working_df.index:
            raise BusinessRuleException(f"Unknown row: {row_number}")
        old_value = self.pipeline.working_df.at[row_index, field_name]
        self.pipeline.working_df.at[row_index, field_name] = value
        self.pipeline._record_audit(
            rule_id="manual_edit",
            row_number=row_number,
            field=field_name,
            old_value=None if pd.isna(old_value) else str(old_value),
            new_value=value,
            changed_by="user",
            auto=False,
        )

    def get_audit_log(self) -> list[dict]:
        """Get the audit log."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        return self.pipeline.audit_log

    def get_file_rows(self, offset: int, limit: int) -> FileRowsResponse:
        """Return a safe, paginated view of the uploaded file."""
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized")
        source = self.pipeline.working_df
        page = source.iloc[offset : offset + limit]
        rows = [
            {
                str(column): None if pd.isna(value) else str(value)
                for column, value in record.items()
            }
            for record in page.to_dict(orient="records")
        ]
        return FileRowsResponse(
            columns=[str(column) for column in source.columns],
            rows=rows,
            total=len(source),
            offset=offset,
            limit=limit,
        )

    def create_report_generator(self) -> ReportGenerator:
        """Create a report generator for the current validation session."""
        if not self.pipeline or not self.response:
            raise RuntimeError("Pipeline not initialized")
        return ReportGenerator(
            source=self.pipeline.original_df,
            corrected=self.pipeline.working_df,
            issues=self.pipeline.all_issues,
            audit_log=self.pipeline.audit_log,
            response=self.response,
        )

    def _member_id(self, row_number: int) -> str | None:
        if (
            not self.pipeline
            or row_number <= 0
            or "userForeignId" not in self.pipeline.working_df.columns
        ):
            return None
        row_index = row_number - 1
        if row_index not in self.pipeline.working_df.index:
            return None
        value = self.pipeline.working_df.at[row_index, "userForeignId"]
        return None if pd.isna(value) else str(value)

    def _row_data(self, row_number: int) -> dict[str, str | None]:
        """Return every available value for one validated source row."""
        if not self.pipeline or row_number <= 0:
            return {}
        row_index = row_number - 1
        if row_index not in self.pipeline.working_df.index:
            return {}
        row = self.pipeline.working_df.loc[row_index]
        return {
            str(column): None if pd.isna(value) else str(value)
            for column, value in row.items()
        }

    @staticmethod
    def _highest_severity(issues: list) -> str:
        rank = {"info": 0, "warning": 1, "error": 2}
        highest = max(issues, key=lambda issue: rank[issue.severity.value]).severity.value
        return {"error": "Critical", "warning": "Warning", "info": "Info"}[highest]

    @staticmethod
    def _severity_label(value: str) -> str:
        return {"error": "Error", "warning": "Warning", "info": "Info"}[value]
