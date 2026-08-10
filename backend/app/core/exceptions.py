"""
Core validation framework and exceptions.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationAction(str, Enum):
    """Actions that can be taken on affected rows."""
    EDIT = "edit"
    REMOVE = "remove"
    AUTO_FIX = "auto_fix"
    MANUAL_REVIEW = "manual_review"


class ValidationIssue(BaseModel):
    """A single validation issue found during processing."""
    row_number: int
    rule_id: str
    rule_name: str
    field_name: str
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    severity: ValidationSeverity
    message: str
    auto_fix_available: bool = False
    action: Optional[ValidationAction] = None
    issue_type: str = "validation"


class BusinessRuleResponse(BaseModel):
    """Response for a single business rule."""
    rule_id: str
    rule_name: str
    category: str
    severity: ValidationSeverity
    description: str
    auto_fix_available: bool
    default_value: Optional[str] = None
    affected_rows: int
    resolved_rows: int = 0
    pending_rows: int = 0
    removed_rows: int = 0


class ValidationSummary(BaseModel):
    """Overall validation summary."""
    total_rows: int
    valid_rows: int
    rows_with_issues: int
    rows_removed: int
    critical_errors: int
    warnings: int
    auto_fixes_available: int
    validation_score: float


class ValidationResponse(BaseModel):
    """Complete validation response."""
    summary: ValidationSummary
    business_rules: list[BusinessRuleResponse]
    affected_rows: list[ValidationIssue]
    reports: dict = {}


class ValidationException(Exception):
    """Base validation exception."""
    pass


class FileValidationException(ValidationException):
    """File-level validation error."""
    pass


class BusinessRuleException(ValidationException):
    """Business rule execution error."""
    pass


class ParsingException(ValidationException):
    """Data parsing error."""
    pass
