"""Public API schemas for validation and report generation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ValidationSummary(ApiSchema):
    total_records: int = Field(ge=0)
    valid: int = Field(ge=0)
    warnings: int = Field(ge=0)
    critical_errors: int = Field(ge=0)
    auto_fix_available: int = Field(ge=0)
    manual_review: int = Field(default=0, ge=0)
    validation_score: float = Field(ge=0, le=100)
    execution_time: float = Field(default=0, ge=0)


class ValidationIssue(ApiSchema):
    row_number: int = Field(ge=0)
    member_id: str | None = None
    rule_id: str
    rule_name: str
    field_name: str
    current_value: str | None = None
    suggested_value: str | None = None
    severity: str
    reason: str
    auto_fix_available: bool = False


class BusinessRuleResult(ApiSchema):
    rule_id: str
    rule_name: str
    category: str
    severity: str
    affected_rows: int = Field(ge=0)
    auto_fix_available: bool
    default_value: str | None = None
    business_logic: str


class AffectedRow(ApiSchema):
    row_number: int = Field(ge=0)
    member_id: str | None = None
    rule_id: str
    rule_name: str
    field_name: str
    current_value: str | None = None
    suggested_value: str | None = None
    severity: str
    reason: str
    auto_fix_available: bool = False
    row_data: dict[str, str | None] = Field(default_factory=dict)
    status: str = "Pending"
    action: str = "Edit"


class AuditEntry(ApiSchema):
    row: int = Field(ge=0)
    field: str
    old_value: str | None = None
    new_value: str | None = None
    business_rule: str
    changed_by: str
    timestamp: datetime
    reason: str


class ReportMetadata(ApiSchema):
    name: str
    url: str
    formats: list[str] = Field(default_factory=lambda: ["csv", "xlsx"])


class ValidationResponse(ApiSchema):
    summary: ValidationSummary
    business_rules: list[BusinessRuleResult]
    affected_rows: list[AffectedRow]
    reports: dict[str, ReportMetadata] = Field(default_factory=dict)


class FileRowsResponse(ApiSchema):
    columns: list[str]
    rows: list[dict[str, str | None]]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class ValidationJobStarted(ApiSchema):
    validation_id: str
    status: str
    total_records: int = Field(ge=0)


class ValidationCheckProgress(ApiSchema):
    check_id: str
    name: str
    status: str
    issues_found: int = Field(default=0, ge=0)
    duration_ms: float | None = Field(default=None, ge=0)


class ValidationProgress(ApiSchema):
    validation_id: str
    status: str
    stage: str
    current_step: str
    completed_steps: int = Field(ge=0)
    total_steps: int = Field(ge=0)
    records_scanned: int = Field(ge=0)
    total_records: int = Field(ge=0)
    potential_issues: int = Field(ge=0)
    validation_score: float | None = Field(default=None, ge=0, le=100)
    elapsed_time: float = Field(default=0, ge=0)
    estimated_remaining: float | None = Field(default=None, ge=0)
    checks: list[ValidationCheckProgress] = Field(default_factory=list)
    error: str | None = None
    result: ValidationResponse | None = None


class HealthResponse(ApiSchema):
    status: str


class AutoFixRequest(ApiSchema):
    rule_id: str


class AutoFixIssueRequest(ApiSchema):
    rule_id: str
    row_number: int = Field(ge=1)


class ManualEditRequest(ApiSchema):
    row_number: int = Field(ge=1)
    field_name: str
    value: str


class OperationResponse(ApiSchema):
    status: str
    message: str
    result: ValidationResponse | None = None


class AddMissingColumnsResponse(ApiSchema):
    status: str
    message: str
    added_columns: list[str] = Field(default_factory=list)
    result: ValidationResponse


# Compatibility aliases for existing imports.
ValidationSummarySchema = ValidationSummary
ValidationResponseSchema = ValidationResponse
AffectedRowSchema = AffectedRow
BusinessRuleSchema = BusinessRuleResult
HealthCheckSchema = HealthResponse
AutoFixRequestSchema = AutoFixRequest
