"""
Format Validation rules for members review.

Owns: email, birth date, country code.
Keep this file self-contained so it can be developed/merged independently.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger

from app.core.exceptions import ValidationIssue, ValidationSeverity
from app.validation.base import FieldValidator
from app.validation.members.field_cleaning import (
    CleanResult,
    clean_country_code,
    clean_date,
    clean_email,
)


def _issue_from_clean(
    *,
    row_idx: int,
    rule_id: str,
    rule_name: str,
    field_name: str,
    result: CleanResult,
    severity_suggest=ValidationSeverity.INFO,
    severity_change=ValidationSeverity.ERROR,
) -> ValidationIssue | None:
    if result.status == "ok":
        return None
    issue_type = (
        "blank"
        if result.current is None and result.status == "suggest"
        else "validation"
    )
    if result.status == "suggest":
        return ValidationIssue(
            row_number=row_idx + 1,
            rule_id=rule_id,
            rule_name=rule_name,
            field_name=field_name,
            current_value=result.current,
            suggested_value=result.suggested,
            severity=severity_suggest,
            message=result.message,
            auto_fix_available=True,
            issue_type=issue_type,
        )
    return ValidationIssue(
        row_number=row_idx + 1,
        rule_id=rule_id,
        rule_name=rule_name,
        field_name=field_name,
        current_value=result.current,
        suggested_value=None,
        severity=severity_change,
        message=result.message,
        auto_fix_available=False,
        issue_type=issue_type,
    )


def _apply_suggested(df: pd.DataFrame, row_idx: int, field: str, cleaner) -> pd.DataFrame:
    if field not in df.columns:
        return df
    result = cleaner(df.at[row_idx, field])
    if result.status == "suggest" and result.suggested is not None:
        df.at[row_idx, field] = result.suggested
    return df


class EmailValidator(FieldValidator):
    """Clean and validate email format."""

    def __init__(self):
        super().__init__(
            rule_id="email_format",
            rule_name="Email Format",
            category="Format Validation",
            field_name="email",
            severity=ValidationSeverity.ERROR,
            description="Strip junk/spaces/extra @; still invalid → Change need",
            auto_fix_available=True,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "email" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["email"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="email",
                result=clean_email(value),
                severity_suggest=ValidationSeverity.ERROR,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        logger.info(f"Email validation: {len(issues)} issues found")
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "email", clean_email)


class BirthDateValidator(FieldValidator):
    """Normalize birth dates; blank → '1970-01-01'."""

    BLANK_DEFAULT = "1970-01-01"

    def __init__(self):
        super().__init__(
            rule_id="birthdate_validation",
            rule_name="Birth Date",
            category="Format Validation",
            field_name="birthDate",
            severity=ValidationSeverity.WARNING,
            description="Normalize birthDate to yyyy-mm-dd; blank → '1970-01-01'",
            auto_fix_available=True,
            default_value=self.BLANK_DEFAULT,
        )

    def _clean(self, value):
        return clean_date(value, blank_default=self.BLANK_DEFAULT)

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "birthDate" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["birthDate"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="birthDate",
                result=self._clean(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "birthDate", self._clean)


class CountryCodeValidator(FieldValidator):
    """Validate ISO Alpha-2 style country codes (exactly 2 letters)."""

    def __init__(self):
        super().__init__(
            rule_id="country_code_validation",
            rule_name="Country Code",
            category="Format Validation",
            field_name="countryCode",
            severity=ValidationSeverity.ERROR,
            description="Country code must be exactly 2 letters; uppercased on fix",
            auto_fix_available=True,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "countryCode" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["countryCode"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="countryCode",
                result=clean_country_code(value),
                severity_suggest=ValidationSeverity.INFO,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "countryCode", clean_country_code)
