"""
Members-specific validators implementing business rules.
"""

import pandas as pd
import numpy as np
from typing import Optional
from loguru import logger
from email_validator import validate_email, EmailNotValidError
import phonenumbers
import pycountry
from datetime import datetime

from app.core.exceptions import (
    ValidationIssue,
    ValidationSeverity,
    FileValidationException,
)
from app.validation.base import FileValidator, RowValidator, FieldValidator


# Required headers for members
REQUIRED_HEADERS = [
    "userForeignId",
    "studioForeignId",
    "studioId",
    "email",
    "firstName",
    "lastName",
    "gender",
    "birthDate",
    "leadStatus",
    "countryCode",
    "country",
    "postalCode",
]

# Required fields per row
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
    """Validate that all required headers are present."""

    def __init__(self):
        super().__init__(
            rule_id="required_headers",
            rule_name="Required Headers",
            category="File Level",
            severity=ValidationSeverity.ERROR,
            description="All required column headers must be present",
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
            rule_name="Required Fields",
            category="Required Fields",
            severity=ValidationSeverity.ERROR,
            description="Required fields must not be empty",
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


class EmailValidator(FieldValidator):
    """Validate email format."""

    def __init__(self):
        super().__init__(
            rule_id="email_format",
            rule_name="Email Format Validation",
            category="Format Validation",
            field_name="email",
            severity=ValidationSeverity.ERROR,
            description="Email must be a valid email address",
            auto_fix_available=False,
            default_value="Manual Review Required",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Validate email format for all rows."""
        issues = []
        
        if "email" not in df.columns:
            return issues
        
        for row_idx, email_val in df["email"].items():
            if pd.isna(email_val) or email_val == "":
                continue  # Required field validator handles this
            
            try:
                # Normalize email
                validate_email(
                    str(email_val).strip(),
                    check_deliverability=False,
                )
            except EmailNotValidError as e:
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="email",
                        current_value=str(email_val),
                        suggested_value=self.default_value,
                        severity=self.severity,
                        message=f"Invalid email format: {str(e)}",
                        auto_fix_available=False,
                    )
                )
        
        logger.info(f"Email validation: {len(issues)} issues found")
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Cannot auto-fix invalid emails."""
        return df


class GenderValidator(FieldValidator):
    """Validate and apply defaults for gender field."""

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
        """Validate gender values."""
        issues = []
        
        if "gender" not in df.columns:
            return issues
        
        for row_idx, gender_val in df["gender"].items():
            # Blank gender is auto-fixable
            if pd.isna(gender_val) or gender_val == "":
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="gender",
                        current_value=None,
                        suggested_value="P",
                        severity=ValidationSeverity.INFO,
                        message="Blank gender will be set to 'P'",
                        auto_fix_available=True,
                    )
                )
            elif str(gender_val).upper() not in ALLOWED_GENDERS:
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="gender",
                        current_value=str(gender_val),
                        suggested_value=None,
                        severity=ValidationSeverity.ERROR,
                        message=f"Invalid gender value: {gender_val}. Must be M, F, or P",
                        auto_fix_available=False,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply gender default."""
        if "gender" in df.columns:
            df.at[row_idx, "gender"] = "P"
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
    """Validate lead status values."""

    def __init__(self):
        super().__init__(
            rule_id="lead_status_validation",
            rule_name="Lead Status Validation",
            category="Allowed Values",
            field_name="leadStatus",
            severity=ValidationSeverity.ERROR,
            description="Lead status must be MEMBER, LEAD, COLD, or TRIALS",
            auto_fix_available=False,
            default_value="Manual Review Required",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Validate lead status values."""
        issues = []
        
        if "leadStatus" not in df.columns:
            return issues
        
        for row_idx, status_val in df["leadStatus"].items():
            if pd.isna(status_val) or status_val == "":
                continue  # Required field validator handles this
            
            if str(status_val).upper() not in ALLOWED_LEAD_STATUSES:
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="leadStatus",
                        current_value=str(status_val),
                        suggested_value=self.default_value,
                        severity=self.severity,
                        message=f"Invalid lead status: {status_val}. Must be MEMBER, LEAD, COLD, or TRIALS",
                        auto_fix_available=False,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Cannot auto-fix invalid lead status."""
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


class FirstNameDefaultValidator(RowValidator):
    """Apply default for blank first name."""

    def __init__(self):
        super().__init__(
            rule_id="first_name_default",
            rule_name="First Name Default",
            category="Auto Defaults",
            severity=ValidationSeverity.INFO,
            description="Blank first name will be set to 'Change Me'",
            auto_fix_available=True,
            default_value="Change Me",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Find rows with blank first name."""
        issues = []
        
        if "firstName" not in df.columns:
            return issues
        
        for row_idx, name_val in df["firstName"].items():
            if pd.isna(name_val) or name_val == "":
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="firstName",
                        current_value=None,
                        suggested_value=self.default_value,
                        severity=self.severity,
                        message="Blank first name will be set to 'Change Me'",
                        auto_fix_available=True,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply first name default."""
        if "firstName" in df.columns:
            df.at[row_idx, "firstName"] = self.default_value
        return df


class LastNameDefaultValidator(RowValidator):
    """Apply default for blank last name."""

    def __init__(self):
        super().__init__(
            rule_id="last_name_default",
            rule_name="Last Name Default",
            category="Auto Defaults",
            severity=ValidationSeverity.INFO,
            description="Blank last name will be set to 'Me'",
            auto_fix_available=True,
            default_value="Me",
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Find rows with blank last name."""
        issues = []
        
        if "lastName" not in df.columns:
            return issues
        
        for row_idx, name_val in df["lastName"].items():
            if pd.isna(name_val) or name_val == "":
                issues.append(
                    ValidationIssue(
                        row_number=row_idx + 1,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        field_name="lastName",
                        current_value=None,
                        suggested_value="Me",
                        severity=self.severity,
                        message="Blank last name will be set to 'Me'",
                        auto_fix_available=True,
                    )
                )
        
        return issues

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        """Apply last name default."""
        if "lastName" in df.columns:
            df.at[row_idx, "lastName"] = "Me"
        return df


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
