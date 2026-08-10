"""
Members-specific validators implementing business rules.
"""

from __future__ import annotations

import pandas as pd
from loguru import logger
import unicodedata

from app.core.exceptions import ValidationIssue, ValidationSeverity
from app.validation.base import FieldValidator, FileValidator, RowValidator
from app.validation.members.field_cleaning import (
    CleanResult,
    clean_date,
    clean_gender,
    clean_lead_status,
    clean_name,
    clean_phone,
    clean_postal_code,
)

# Mandatory headers through joinedDate (file review)
REQUIRED_HEADERS = [
    "userForeignId",
    "studioForeignId",
    "studioId",
    "email",
    "firstName",
    "lastName",
    "phone",
    "gender",
    "birthDate",
    "leadStatus",
    "street",
    "city",
    "state",
    "countryCode",
    "country",
    "postalCode",
    "accessBarcode",
    "emergencyContact",
    "emailConsent",
    "pushConsent",
    "smsConsent",
    "joinedDate",
]

# Required fields per row (leadStatus must not be blank)
REQUIRED_FIELDS = [
    "userForeignId",
    "studioId",
    "country",
    "leadStatus",
    "countryCode",
    "email",
]


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


class RequiredHeaderValidator(FileValidator):
    """Validate that all mandatory file-review headers are present."""

    def __init__(self):
        super().__init__(
            rule_id="required_headers",
            rule_name="File Review",
            category="File Level",
            severity=ValidationSeverity.ERROR,
            description="Checking mandatory columns and blank lead status",
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        issues = []
        missing_headers = [h for h in REQUIRED_HEADERS if h not in df.columns]

        if missing_headers:
            msg = f"Missing required headers: {', '.join(missing_headers)}"
            logger.warning(msg)
            issues.append(
                ValidationIssue(
                    row_number=0,
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    field_name="headers",
                    current_value=None,
                    suggested_value=None,
                    severity=self.severity,
                    message=msg,
                    auto_fix_available=False,
                )
            )

        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return df


class StudioForeignIdValidator(FileValidator):
    """Validate that all rows have the same studioForeignId."""

    def __init__(self):
        super().__init__(
            rule_id="studio_foreign_id",
            rule_name="Studio Foreign ID Consistency",
            category="File Level",
            severity=ValidationSeverity.ERROR,
            description="All rows must contain the same studioForeignId value",
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        issues = []

        if "studioForeignId" not in df.columns:
            return issues

        unique_values = df["studioForeignId"].dropna().unique()

        if len(unique_values) > 1:
            msg = f"Multiple studioForeignId values found: {list(unique_values)}"
            logger.warning(msg)
            issues.append(
                ValidationIssue(
                    row_number=0,
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    field_name="studioForeignId",
                    current_value=str(unique_values),
                    suggested_value=None,
                    severity=self.severity,
                    message=msg,
                    auto_fix_available=False,
                )
            )

        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return df


class RequiredFieldValidator(RowValidator):
    """Validate that required fields are not empty."""

    def __init__(self):
        super().__init__(
            rule_id="required_fields",
            rule_name="Lead Status & Required Fields",
            category="Required Fields",
            severity=ValidationSeverity.ERROR,
            description="Required fields must not be empty; leadStatus must not be blank",
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        issues = []

        for field in REQUIRED_FIELDS:
            if field not in df.columns:
                continue

            missing_mask = df[field].isna() | (df[field] == "")
            missing_rows = df[missing_mask].index.tolist()

            for row_idx in missing_rows:
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name=field,
                        current_value=None,
                        suggested_value=None,
                        severity=self.severity,
                        message=f"Required field '{field}' is empty",
                        auto_fix_available=False,
                    )
                )

        logger.info(f"Required field validation: {len(issues)} issues found")
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return df


class FirstNameValidator(FieldValidator):
    """Clean and validate first names."""

    def __init__(self):
        super().__init__(
            rule_id="first_name_validation",
            rule_name="First Name",
            category="Format Validation",
            field_name="firstName",
            severity=ValidationSeverity.WARNING,
            description="Strip junk from firstName; blank/junk → '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "firstName" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["firstName"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="firstName",
                result=clean_name(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "firstName", clean_name)


class LastNameValidator(FieldValidator):
    """Clean and validate last names."""

    def __init__(self):
        super().__init__(
            rule_id="last_name_validation",
            rule_name="Last Name",
            category="Format Validation",
            field_name="lastName",
            severity=ValidationSeverity.WARNING,
            description="Strip junk from lastName; blank/junk → '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "lastName" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["lastName"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="lastName",
                result=clean_name(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "lastName", clean_name)


class PhoneValidator(FieldValidator):
    """Sanitize phone numbers."""

    def __init__(self):
        super().__init__(
            rule_id="phone_validation",
            rule_name="Phone Format",
            category="Format Validation",
            field_name="phone",
            severity=ValidationSeverity.WARNING,
            description="Keep digits and optional leading +; blank/junk → '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "phone" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["phone"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="phone",
                result=clean_phone(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "phone", clean_phone)


class EmergencyContactValidator(FieldValidator):
    """Sanitize emergency contact using phone rules."""

    def __init__(self):
        super().__init__(
            rule_id="emergency_contact_validation",
            rule_name="Emergency Contact",
            category="Format Validation",
            field_name="emergencyContact",
            severity=ValidationSeverity.WARNING,
            description="Same sanitize rules as phone",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "emergencyContact" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["emergencyContact"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="emergencyContact",
                result=clean_phone(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(
            df, row_idx, "emergencyContact", clean_phone
        )


class LeadStatusValidator(FieldValidator):
    """Normalize lead status to MEMBER, LEAD, COLD, or TRIALS."""

    def __init__(self):
        super().__init__(
            rule_id="lead_status_validation",
            rule_name="Lead Status Validation",
            category="Allowed Values",
            field_name="leadStatus",
            severity=ValidationSeverity.ERROR,
            description=(
                "Lead status must be MEMBER, LEAD, COLD, or TRIALS. "
                "Aliases like leads/members are normalized."
            ),
            auto_fix_available=True,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "leadStatus" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["leadStatus"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="leadStatus",
                result=clean_lead_status(value),
                severity_suggest=ValidationSeverity.INFO,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        if "leadStatus" not in df.columns:
            return df
        result = clean_lead_status(df.at[row_idx, "leadStatus"])
        if result.status == "suggest" and result.suggested is not None:
            df.at[row_idx, "leadStatus"] = result.suggested
        return df


class JoinedDateValidator(FieldValidator):
    """Normalize joinedDate to yyyy-mm-dd. Blank → '-'."""

    def __init__(self):
        super().__init__(
            rule_id="joined_date_validation",
            rule_name="Joined Date Validation",
            category="Allowed Values",
            field_name="joinedDate",
            severity=ValidationSeverity.WARNING,
            description="Normalize joinedDate to yyyy-mm-dd; blank → '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "joinedDate" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["joinedDate"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="joinedDate",
                result=clean_date(value),
                severity_suggest=ValidationSeverity.INFO,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "joinedDate", clean_date)


class GenderValidator(FieldValidator):
    """Validate and normalize gender."""

    def __init__(self):
        super().__init__(
            rule_id="gender_validation",
            rule_name="Gender Validation",
            category="Allowed Values",
            field_name="gender",
            severity=ValidationSeverity.WARNING,
            description="Gender must be M, F, or P. Blank values default to P.",
            auto_fix_available=True,
            default_value="P",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "gender" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["gender"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="gender",
                result=clean_gender(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "gender", clean_gender)


def _clean_name(value: object) -> str:
    """Return a conservative, letters-and-spaces-only name candidate."""
    if pd.isna(value):
        return ""

    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    if not any(character.isalpha() for character in normalized):
        return ""

    cleaned: list[str] = []
    for index, character in enumerate(normalized):
        if character.isalpha() or character.isspace():
            cleaned.append(character)
        elif (
            character == "0"
            and index > 0
            and index + 1 < len(normalized)
            and normalized[index - 1].isalpha()
            and normalized[index + 1].isalpha()
        ):
            # A zero between letters is the one configured high-confidence
            # substitution (for example, "j0hn" -> "john").
            cleaned.append("o")

    return " ".join("".join(cleaned).split())


class _NameDefaultValidator(RowValidator):
    """Clean a name field and apply its configured default if it becomes blank."""

    def __init__(
        self,
        *,
        rule_id: str,
        rule_name: str,
        field_name: str,
        default_value: str,
    ):
        super().__init__(
            rule_id=rule_id,
            rule_name=rule_name,
            category="Auto Defaults",
            severity=ValidationSeverity.INFO,
            description=(
                f"{field_name} must contain letters and spaces only. "
                f"Values with no remaining letters default to '{default_value}'."
            ),
            auto_fix_available=True,
            default_value=default_value,
        )
        self.field_name = field_name

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Find blank or non-alphabetic names and provide deterministic fixes."""
        if self.field_name not in df.columns:
            return []

        issues = []
        for row_idx, name_value in df[self.field_name].items():
            current_value = None if pd.isna(name_value) else str(name_value)
            cleaned_value = _clean_name(name_value)
            is_originally_blank = (
                current_value is None or not current_value.strip()
            )

            if is_originally_blank:
                suggested_value = self.default_value
                issue_type = "blank"
                message = (
                    f"Blank {self.field_name} will be set to "
                    f"'{self.default_value}'"
                )
            elif not cleaned_value:
                suggested_value = self.default_value
                issue_type = "blank"
                message = (
                    f"{self.field_name} contains no usable letters after "
                    f"cleaning and will be set to '{self.default_value}'"
                )
            elif cleaned_value != current_value.strip():
                suggested_value = cleaned_value
                issue_type = "validation"
                message = (
                    f"{self.field_name} contains numbers or special characters"
                )
            else:
                continue

            issues.append(
                ValidationIssue(
                    row_number=row_idx + 1,
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    field_name=self.field_name,
                    current_value=current_value,
                    suggested_value=suggested_value,
                    severity=self.severity,
                    message=message,
                    auto_fix_available=True,
                    issue_type=issue_type,
                )
            )

        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply the exact deterministic cleanup represented by this rule."""
        if self.field_name in df.columns:
            cleaned_value = _clean_name(df.at[row_idx, self.field_name])
            df.at[row_idx, self.field_name] = (
                cleaned_value or self.default_value
            )
        return df


class FirstNameDefaultValidator(_NameDefaultValidator):
    """Clean first names and default values that become blank."""

    def __init__(self):
        super().__init__(
            rule_id="first_name_default",
            rule_name="First Name Cleanup",
            field_name="firstName",
            default_value="Change Me",
        )


class LastNameDefaultValidator(_NameDefaultValidator):
    """Clean last names and default values that become blank."""

    def __init__(self):
        super().__init__(
            rule_id="last_name_default",
            rule_name="Last Name Cleanup",
            field_name="lastName",
            default_value="Me",
        )


class PostalCodeDefaultValidator(FieldValidator):
    """Apply default for blank postal code."""

    def __init__(self):
        super().__init__(
            rule_id="postal_code_default",
            rule_name="Postal Code Default",
            category="Auto Defaults",
            field_name="postalCode",
            severity=ValidationSeverity.INFO,
            description="Blank postal code will be set to '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        if "postalCode" not in df.columns:
            return []
        issues = []
        for row_idx, value in df["postalCode"].items():
            issue = _issue_from_clean(
                row_idx=row_idx,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="postalCode",
                result=clean_postal_code(value),
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return _apply_suggested(df, row_idx, "postalCode", clean_postal_code)
