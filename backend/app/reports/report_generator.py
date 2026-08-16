"""Build and serialize reports from a completed validation run."""

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.core.exceptions import ValidationIssue as DomainValidationIssue
from app.reports.audit_exporter import AuditExporter
from app.reports.csv_exporter import CsvExporter
from app.reports.excel_exporter import ExcelExporter
from app.schemas.validation import AuditEntry, ValidationResponse
from app.validation.members.field_cleaning import (
    fill_country_code_for_export,
    sanitize_phone_for_export,
)


@dataclass(frozen=True)
class GeneratedReport:
    content: bytes
    media_type: str
    filename: str


class ReportGenerator:
    """Project one validation result into each supported report."""

    _report_names = {"summary", "errors", "audit", "corrected", "removed"}

    def __init__(
        self,
        source: pd.DataFrame,
        corrected: pd.DataFrame,
        issues: list[DomainValidationIssue],
        audit_log: list[dict],
        response: ValidationResponse,
        removed_rows: set[int] | None = None,
        *,
        filename_prefix: str = "members_validation",
        record_id_column: str | None = "userForeignId",
        record_id_label: str = "Member ID",
        apply_contact_export_rules: bool = True,
    ) -> None:
        self._source = source.copy()
        self._corrected = corrected.copy()
        self._issues = list(issues)
        self._audit_log = list(audit_log)
        self._response = response
        self._removed_rows = removed_rows or set()
        self._filename_prefix = filename_prefix
        self._record_id_column = record_id_column
        self._record_id_label = record_id_label
        self._apply_contact_export_rules = apply_contact_export_rules

    def generate(self, report_name: str, file_format: str = "csv") -> GeneratedReport:
        if report_name not in self._report_names:
            raise ValueError(f"Unknown report: {report_name}")

        normalized_format = file_format.lower()
        frame = self._build_dataframe(report_name)
        if normalized_format == "csv":
            exporter = CsvExporter
            content = exporter.export(frame)
        elif normalized_format in {"xlsx", "excel"}:
            exporter = ExcelExporter
            content = exporter.export(frame, sheet_name=report_name.title())
        else:
            raise ValueError("format must be 'csv' or 'xlsx'")

        return GeneratedReport(
            content=content,
            media_type=exporter.media_type,
            filename=f"{self._filename_prefix}_{report_name}.{exporter.extension}",
        )

    def _build_dataframe(self, report_name: str) -> pd.DataFrame:
        builders = {
            "summary": self._summary_dataframe,
            "errors": self._errors_dataframe,
            "audit": self._audit_dataframe,
            "corrected": self._corrected_dataframe,
            "removed": self._removed_dataframe,
        }
        return builders[report_name]()

    def _summary_dataframe(self) -> pd.DataFrame:
        summary = self._response.summary
        return pd.DataFrame(
            [
                {
                    "Total Records": summary.total_records,
                    "Valid": summary.valid,
                    "Warnings": summary.warnings,
                    "Critical Errors": summary.critical_errors,
                    "Auto Fix Available": summary.auto_fix_available,
                    "Manual Review": summary.manual_review,
                    "Validation Score": summary.validation_score,
                    "Execution Time": summary.execution_time,
                }
            ]
        )

    def _errors_dataframe(self) -> pd.DataFrame:
        columns = [
            "Row Number",
            self._record_id_label,
            "Field",
            "Current Value",
            "Suggested Value",
            "Business Rule",
            "Severity",
            "Reason",
            "Auto Fix Available",
        ]
        records = [
            {
                "Row Number": issue.row_number + 1,
                self._record_id_label: self._record_id(issue.row_number),
                "Field": issue.field_name,
                "Current Value": issue.current_value,
                "Suggested Value": issue.suggested_value,
                "Business Rule": issue.rule_name,
                "Severity": self._severity_label(issue),
                "Reason": issue.message,
                "Auto Fix Available": issue.auto_fix_available,
            }
            for issue in self._issues
            if issue.row_number > 0
        ]
        return pd.DataFrame.from_records(records, columns=columns)

    def _audit_dataframe(self) -> pd.DataFrame:
        issue_lookup = {
            (issue.rule_id, issue.row_number, issue.field_name): issue
            for issue in self._issues
        }
        entries: list[AuditEntry] = []
        for record in self._audit_log:
            issue = issue_lookup.get(
                (record["rule_id"], record["row_number"], record["field"])
            )
            entries.append(
                AuditEntry(
                    row=(
                        record["row_number"] + 1
                        if record["row_number"] > 0
                        else record["row_number"]
                    ),
                    field=record["field"],
                    old_value=record.get("old_value"),
                    new_value=record.get("new_value"),
                    business_rule=issue.rule_name if issue else record["rule_id"],
                    changed_by=record["changed_by"],
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    reason=issue.message if issue else "Value changed",
                )
            )
        return AuditExporter.to_dataframe(entries)

    def _removed_dataframe(self) -> pd.DataFrame:
        """Full original rows that were dropped, with removal reasons."""
        reasons_by_row: dict[int, list[str]] = {}
        rules_by_row: dict[int, list[str]] = {}
        for issue in self._issues:
            if issue.row_number <= 0:
                continue
            if self._removed_rows and issue.row_number not in self._removed_rows:
                continue
            if not self._removed_rows and issue.issue_type != "removed":
                continue
            reasons_by_row.setdefault(issue.row_number, []).append(issue.message)
            rules_by_row.setdefault(issue.row_number, []).append(issue.rule_name)

        row_numbers = sorted(
            self._removed_rows
            or {
                issue.row_number
                for issue in self._issues
                if issue.row_number > 0 and issue.issue_type == "removed"
            }
        )
        if not row_numbers:
            return pd.DataFrame(
                columns=[
                    "Row Number",
                    "Removal Rule",
                    "Removal Reason",
                    *list(self._source.columns),
                ]
            )

        records = []
        for row_number in row_numbers:
            index = row_number - 1
            if index not in self._source.index:
                continue
            source_row = self._source.loc[index]
            record = {
                "Row Number": row_number + 1,
                "Removal Rule": "; ".join(
                    dict.fromkeys(rules_by_row.get(row_number, []))
                ),
                "Removal Reason": "; ".join(
                    dict.fromkeys(reasons_by_row.get(row_number, []))
                ),
            }
            for column in self._source.columns:
                value = source_row[column]
                record[str(column)] = None if pd.isna(value) else value
            records.append(record)

        columns = [
            "Row Number",
            "Removal Rule",
            "Removal Reason",
            *[str(column) for column in self._source.columns],
        ]
        return pd.DataFrame.from_records(records, columns=columns)

    def _corrected_dataframe(self) -> pd.DataFrame:
        if not self._removed_rows:
            frame = self._corrected.copy()
        else:
            indexes_to_remove = [
                row_number - 1 for row_number in self._removed_rows
            ]
            frame = self._corrected.drop(
                index=indexes_to_remove, errors="ignore"
            )
        if not self._apply_contact_export_rules:
            return frame
        frame = self._apply_export_only_phone_cleaning(frame)
        return self._apply_export_only_country_code_fill(frame)

    _PHONE_EXPORT_COLUMNS = ("phone", "emergencyContact")

    @classmethod
    def _apply_export_only_phone_cleaning(cls, frame: pd.DataFrame) -> pd.DataFrame:
        """Sanitize phone fields for download only — never surfaces in review UI."""
        columns = [col for col in cls._PHONE_EXPORT_COLUMNS if col in frame.columns]
        if not columns:
            return frame
        cleaned = frame.copy()
        for column in columns:
            cleaned[column] = cleaned[column].map(sanitize_phone_for_export)
        return cleaned

    @classmethod
    def _apply_export_only_country_code_fill(cls, frame: pd.DataFrame) -> pd.DataFrame:
        """Fill blank countryCode from country name — download only, not review UI."""
        if "country" not in frame.columns:
            return frame
        cleaned = frame.copy()
        if "countryCode" not in cleaned.columns:
            cleaned["countryCode"] = ""
        cleaned["countryCode"] = [
            fill_country_code_for_export(code, name)
            for code, name in zip(cleaned["countryCode"], cleaned["country"])
        ]
        return cleaned

    def _record_id(self, row_number: int) -> str | None:
        if (
            not self._record_id_column
            or row_number <= 0
            or self._record_id_column not in self._source.columns
        ):
            return None
        index = row_number - 1
        if index not in self._source.index:
            return None
        value = self._source.at[index, self._record_id_column]
        return None if pd.isna(value) else str(value)

    @staticmethod
    def _severity_label(issue: DomainValidationIssue) -> str:
        labels = {"error": "Critical", "warning": "Warning", "info": "Info"}
        return labels[issue.severity.value]
