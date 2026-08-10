"""
Members-specific validators implementing business rules.
"""

import pandas as pd
import numpy as np
from typing import Optional
from loguru import logger
import phonenumbers
import pycountry
from datetime import datetime
import unicodedata

from app.core.exceptions import (
    ValidationIssue,
    ValidationSeverity,
    FileValidationException,
)
from app.validation.base import FileValidator, RowValidator, FieldValidator
from app.validation.members.field_cleaning import (
    CleanResult,
    clean_date,
    clean_email,
    clean_gender,
    clean_lead_status,
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

# Allowed values
ALLOWED_GENDERS = {"M", "F", "P"}
ALLOWED_LEAD_STATUSES = {"MEMBER", "LEAD", "COLD", "TRIALS"}


class RequiredHeaderValidator(FileValidator):
    """Validate that all mandatory file-review headers are present."""

    def __init__(self):
        super().__init__(
            rule_id="required_headers",
            rule_name="File Review",
            category="File Level",
            severity=ValidationSeverity.ERROR,
            description=(
                "Checking mandatory columns and blank lead status"
            ),
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Check for missing required headers."""
        issues = []
        missing_headers = [h for h in REQUIRED_HEADERS if h not in df.columns]
        
        if missing_headers:
            msg = f"Missing required headers: {', '.join(missing_headers)}"
            logger.warning(msg)
            # File-level issue (no specific row)
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
        """Cannot fix missing headers."""
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
        """Check for multiple studioForeignId values."""
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
        """Cannot fix studio consistency."""
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
        """Check for missing required field values."""
        issues = []
        
        for field in REQUIRED_FIELDS:
            if field not in df.columns:
                continue
            
            # Find rows where required field is missing
            missing_mask = df[field].isna() | (df[field] == "")
            missing_rows = df[missing_mask].index.tolist()
            
            for row_idx in missing_rows:
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,  # 1-indexed for display
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
        """Cannot auto-fix missing required fields."""
        return df


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


class EmailValidator(FieldValidator):
    """Clean and validate email format.

    Strip junk/spaces/extra @; still invalid → Change need (manual edit).
    Cleanable values get a suggested fix that can be auto-applied.
    """

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
                severity_suggest=ValidationSeverity.INFO,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        logger.info(f"Email validation: {len(issues)} issues found")
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        if "email" not in df.columns:
            return df
        result = clean_email(df.at[row_idx, "email"])
        if result.status == "suggest" and result.suggested is not None:
            df.at[row_idx, "email"] = result.suggested
        return df


class GenderValidator(FieldValidator):
    """Normalize gender to M, F, or P. Blank → P."""

    def __init__(self):
        super().__init__(
            rule_id="gender_validation",
            rule_name="Gender Validation",
            category="Allowed Values",
            field_name="gender",
            severity=ValidationSeverity.WARNING,
            description="Gender must be M, F, or P. Blank → P; male/female aliases normalized.",
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
                severity_suggest=ValidationSeverity.INFO,
                severity_change=ValidationSeverity.ERROR,
            )
            if issue:
                issues.append(issue)
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        if "gender" not in df.columns:
            return df
        result = clean_gender(df.at[row_idx, "gender"])
        if result.status == "suggest" and result.suggested is not None:
            df.at[row_idx, "gender"] = result.suggested
        return df


class BirthDateValidator(FieldValidator):
    """Validate and apply defaults for birth date."""

    def __init__(self):
        super().__init__(
            rule_id="birthdate_validation",
            rule_name="Birth Date Validation",
            category="Format Validation",
            field_name="birthDate",
            severity=ValidationSeverity.WARNING,
            description="Birth date must be a valid date. Blank values default to 1970-01-01",
            auto_fix_available=True,
            default_value="1970-01-01",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Validate birth date values."""
        issues = []
        
        if "birthDate" not in df.columns:
            return issues
        
        for row_idx, date_val in df["birthDate"].items():
            # Blank date is auto-fixable
            if pd.isna(date_val) or date_val == "":
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="birthDate",
                        current_value=None,
                        suggested_value="1970-01-01",
                        severity=ValidationSeverity.INFO,
                        message="Blank birth date will be set to 1970-01-01",
                        auto_fix_available=True,
                    )
                )
            else:
                # Try to parse the date
                try:
                    from dateutil import parser
                    parsed_date = parser.parse(str(date_val))
                except (ValueError, TypeError):
                    issues.append(
                        ValidationIssue(
                            row_number=row_idx + 1,
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            field_name="birthDate",
                            current_value=str(date_val),
                            suggested_value=None,
                            severity=ValidationSeverity.ERROR,
                            message=f"Invalid date format: {date_val}",
                            auto_fix_available=False,
                        )
                    )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply birth date default."""
        if "birthDate" in df.columns:
            df.at[row_idx, "birthDate"] = "1970-01-01"
        return df


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
        if "joinedDate" not in df.columns:
            return df
        result = clean_date(df.at[row_idx, "joinedDate"])
        if result.status == "suggest" and result.suggested is not None:
            df.at[row_idx, "joinedDate"] = result.suggested
        return df


class CountryCodeValidator(FieldValidator):
    """Validate ISO Alpha-2 country codes."""

    def __init__(self):
        super().__init__(
            rule_id="country_code_validation",
            rule_name="Country Code Validation",
            category="Format Validation",
            field_name="countryCode",
            severity=ValidationSeverity.ERROR,
            description="Country code must be a valid ISO Alpha-2 code",
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Validate country codes."""
        issues = []
        
        if "countryCode" not in df.columns:
            return issues
        
        for row_idx, code_val in df["countryCode"].items():
            if pd.isna(code_val) or code_val == "":
                continue  # Required field validator handles this
            
            try:
                pycountry.countries.get(alpha_2=str(code_val).upper())
            except (AttributeError, KeyError):
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="countryCode",
                        current_value=str(code_val),
                        suggested_value=None,
                        severity=self.severity,
                        message=f"Invalid ISO Alpha-2 country code: {code_val}",
                        auto_fix_available=False,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Cannot auto-fix invalid country codes."""
        return df


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


class PostalCodeDefaultValidator(RowValidator):
    """Apply default for blank postal code."""

    def __init__(self):
        super().__init__(
            rule_id="postal_code_default",
            rule_name="Postal Code Default",
            category="Auto Defaults",
            severity=ValidationSeverity.INFO,
            description="Blank postal code will be set to '-'",
            auto_fix_available=True,
            default_value="-",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Find rows with blank postal code."""
        issues = []
        
        if "postalCode" not in df.columns:
            return issues
        
        for row_idx, code_val in df["postalCode"].items():
            if pd.isna(code_val) or code_val == "":
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="postalCode",
                        current_value=None,
                        suggested_value="-",
                        severity=self.severity,
                        message="Blank postal code will be set to '-'",
                        auto_fix_available=True,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply postal code default."""
        if "postalCode" in df.columns:
            df.at[row_idx, "postalCode"] = "-"
        return df
