"""
Base validator class and validation pipeline.
"""

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Callable, Optional
import pandas as pd
from loguru import logger

from app.core.exceptions import (
    ValidationIssue,
    ValidationSeverity,
    BusinessRuleException,
)


class BaseValidator(ABC):
    """
    Base class for all validators.
    Each validator is responsible for a single business rule.
    """

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        category: str,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        description: str = "",
        auto_fix_available: bool = False,
        default_value: Optional[str] = None,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.category = category
        self.severity = severity
        self.description = description
        self.auto_fix_available = auto_fix_available
        self.default_value = default_value

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """
        Execute validation on the DataFrame.
        
        Args:
            df: Pandas DataFrame to validate
            
        Returns:
            List of ValidationIssue objects
        """
        pass

    @abstractmethod
    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """
        Apply automatic fix to a single row.
        
        Args:
            df: DataFrame
            row_idx: Row index to fix
            
        Returns:
            Modified DataFrame
        """
        pass


class FileValidator(BaseValidator):
    """
    Validator for file-level rules.
    Executes before row processing.
    """
    
    @abstractmethod
    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Execute file-level validation."""
        pass


class RowValidator(BaseValidator):
    """
    Validator for row-level rules.
    Executes for each row.
    """

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Execute row-level validation."""
        pass


class FieldValidator(BaseValidator):
    """
    Validator for field-level rules.
    Executes for specific fields.
    """

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        category: str,
        field_name: str,
        **kwargs
    ):
        super().__init__(rule_id, rule_name, category, **kwargs)
        self.field_name = field_name

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Execute field-level validation."""
        pass


class ValidationPipeline:
    """
    Main validation pipeline that orchestrates all validators.
    Maintains original, working, and corrected DataFrames.
    """

    def __init__(
        self,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self.original_df: Optional[pd.DataFrame] = None
        self.working_df: Optional[pd.DataFrame] = None
        self.corrected_df: Optional[pd.DataFrame] = None
        
        self.file_validators: list[FileValidator] = []
        self.row_validators: list[RowValidator] = []
        self.field_validators: list[FieldValidator] = []
        
        self.all_issues: list[ValidationIssue] = []
        self.audit_log: list[dict] = []
        self.progress_callback = progress_callback

    def register_file_validator(self, validator: FileValidator):
        """Register a file-level validator."""
        self.file_validators.append(validator)
        logger.info(f"Registered file validator: {validator.rule_name}")

    def register_row_validator(self, validator: RowValidator):
        """Register a row-level validator."""
        self.row_validators.append(validator)
        logger.info(f"Registered row validator: {validator.rule_name}")

    def register_field_validator(self, validator: FieldValidator):
        """Register a field-level validator."""
        self.field_validators.append(validator)
        logger.info(f"Registered field validator: {validator.rule_name}")

    def load_data(self, df: pd.DataFrame):
        """Load data into the pipeline."""
        self.original_df = df.copy()
        self.working_df = df.copy()
        logger.info(f"Loaded {len(df)} rows into pipeline")

    def execute(self) -> list[ValidationIssue]:
        """
        Execute the complete validation pipeline.
        
        Returns:
            List of all validation issues
        """
        if self.working_df is None:
            raise BusinessRuleException("No data loaded into pipeline")

        logger.info("Starting validation pipeline")
        all_validators = (
            self.file_validators
            + self.row_validators
            + self.field_validators
        )
        total_steps = len(all_validators)
        completed_steps = 0
        self._emit_check_catalog(all_validators, total_steps)

        # File-level validation
        logger.info("Executing file validators")
        for validator in self.file_validators:
            started_at = perf_counter()
            try:
                self._emit_progress(
                    validator, "running", completed_steps, total_steps
                )
                issues = validator.validate(self.working_df)
                self.all_issues.extend(issues)
                completed_steps += 1
                self._emit_progress(
                    validator,
                    "completed",
                    completed_steps,
                    total_steps,
                    issues_found=len(issues),
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.info(f"File validator {validator.rule_name}: {len(issues)} issues")
            except Exception as e:
                self._emit_progress(
                    validator,
                    "failed",
                    completed_steps,
                    total_steps,
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.error(f"File validator {validator.rule_name} failed: {e}")
                raise BusinessRuleException(f"Validator {validator.rule_name} failed: {e}")

        # Row-level validation
        logger.info("Executing row validators")
        for validator in self.row_validators:
            started_at = perf_counter()
            try:
                self._emit_progress(
                    validator, "running", completed_steps, total_steps
                )
                issues = validator.validate(self.working_df)
                self.all_issues.extend(issues)
                completed_steps += 1
                self._emit_progress(
                    validator,
                    "completed",
                    completed_steps,
                    total_steps,
                    issues_found=len(issues),
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.info(f"Row validator {validator.rule_name}: {len(issues)} issues")
            except Exception as e:
                self._emit_progress(
                    validator,
                    "failed",
                    completed_steps,
                    total_steps,
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.error(f"Row validator {validator.rule_name} failed: {e}")
                raise BusinessRuleException(f"Validator {validator.rule_name} failed: {e}")

        # Field-level validation
        logger.info("Executing field validators")
        for validator in self.field_validators:
            started_at = perf_counter()
            try:
                self._emit_progress(
                    validator, "running", completed_steps, total_steps
                )
                issues = validator.validate(self.working_df)
                self.all_issues.extend(issues)
                completed_steps += 1
                self._emit_progress(
                    validator,
                    "completed",
                    completed_steps,
                    total_steps,
                    issues_found=len(issues),
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.info(f"Field validator {validator.rule_name}: {len(issues)} issues")
            except Exception as e:
                self._emit_progress(
                    validator,
                    "failed",
                    completed_steps,
                    total_steps,
                    duration_ms=(perf_counter() - started_at) * 1000,
                )
                logger.error(f"Field validator {validator.rule_name} failed: {e}")
                raise BusinessRuleException(f"Validator {validator.rule_name} failed: {e}")

        logger.info(f"Validation complete: {len(self.all_issues)} total issues")
        return self.all_issues

    def _emit_progress(
        self,
        validator: BaseValidator,
        status: str,
        completed_steps: int,
        total_steps: int,
        issues_found: int = 0,
        duration_ms: float | None = None,
    ) -> None:
        if not self.progress_callback:
            return
        affected_rows = {
            issue.row_number for issue in self.all_issues if issue.row_number > 0
        }
        self.progress_callback(
            {
                "current_step": validator.rule_name,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "potential_issues": len(self.all_issues),
                "affected_rows": len(affected_rows),
                "check_id": validator.rule_id,
                "check_name": validator.rule_name,
                "check_status": status,
                "check_issues_found": issues_found,
                "check_duration_ms": duration_ms,
            }
        )

    def _emit_check_catalog(
        self,
        validators: list[BaseValidator],
        total_steps: int,
    ) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            {
                "current_step": "Starting validation checks",
                "completed_steps": 0,
                "total_steps": total_steps,
                "potential_issues": 0,
                "affected_rows": 0,
                "checks": [
                    {
                        "check_id": validator.rule_id,
                        "name": validator.rule_name,
                        "status": "pending",
                        "issues_found": 0,
                        "duration_ms": None,
                    }
                    for validator in validators
                ],
            }
        )

    def get_issues_for_rule(self, rule_id: str) -> list[ValidationIssue]:
        """Get all issues for a specific rule."""
        return [issue for issue in self.all_issues if issue.rule_id == rule_id]

    def apply_auto_fix(self, rule_id: str):
        """Apply automatic fixes for a rule."""
        validator = self._get_validator_by_rule_id(rule_id)
        if not validator or not validator.auto_fix_available:
            raise BusinessRuleException(f"Auto-fix not available for rule {rule_id}")

        issues = [
            issue
            for issue in self.get_issues_for_rule(rule_id)
            if issue.auto_fix_available
        ]
        for issue in issues:
            self.working_df = validator.apply_fix(
                self.working_df, issue.row_number - 1
            )
            self._record_audit(
                rule_id=rule_id,
                row_number=issue.row_number,
                field=issue.field_name,
                old_value=issue.current_value,
                new_value=issue.suggested_value,
                changed_by="system",
                auto=True,
            )

        logger.info(f"Applied auto-fix for rule {rule_id}: {len(issues)} rows")

    def apply_issue_auto_fix(self, rule_id: str, row_number: int) -> None:
        """Apply a configured automatic fix to one affected row."""
        validator = self._get_validator_by_rule_id(rule_id)
        if not validator or not validator.auto_fix_available:
            raise BusinessRuleException(f"Auto-fix not available for rule {rule_id}")
        issue = next(
            (
                item
                for item in self.get_issues_for_rule(rule_id)
                if item.row_number == row_number and item.auto_fix_available
            ),
            None,
        )
        if not issue:
            raise BusinessRuleException(
                f"No auto-fixable issue for rule {rule_id} on row {row_number}"
            )
        self.working_df = validator.apply_fix(
            self.working_df, issue.row_number - 1
        )
        self._record_audit(
            rule_id=rule_id,
            row_number=issue.row_number,
            field=issue.field_name,
            old_value=issue.current_value,
            new_value=issue.suggested_value,
            changed_by="system",
            auto=True,
        )

    def _get_validator_by_rule_id(self, rule_id: str) -> Optional[BaseValidator]:
        """Get validator by rule ID."""
        all_validators = (
            self.file_validators + self.row_validators + self.field_validators
        )
        for validator in all_validators:
            if validator.rule_id == rule_id:
                return validator
        return None

    def _record_audit(
        self,
        rule_id: str,
        row_number: int,
        field: str,
        old_value: Optional[str],
        new_value: Optional[str],
        changed_by: str,
        auto: bool,
    ):
        """Record an audit log entry."""
        import datetime
        self.audit_log.append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "rule_id": rule_id,
            "row_number": row_number,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
            "auto": auto,
        })
