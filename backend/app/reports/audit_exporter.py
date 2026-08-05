"""Audit log tabular projection."""

import pandas as pd

from app.schemas.validation import AuditEntry


class AuditExporter:
    columns = [
        "Row",
        "Field",
        "Old Value",
        "New Value",
        "Business Rule",
        "Changed By",
        "Timestamp",
        "Reason",
    ]

    @classmethod
    def to_dataframe(cls, entries: list[AuditEntry]) -> pd.DataFrame:
        records = [
            {
                "Row": entry.row,
                "Field": entry.field,
                "Old Value": entry.old_value,
                "New Value": entry.new_value,
                "Business Rule": entry.business_rule,
                "Changed By": entry.changed_by,
                "Timestamp": entry.timestamp.isoformat(),
                "Reason": entry.reason,
            }
            for entry in entries
        ]
        return pd.DataFrame.from_records(records, columns=cls.columns)
