"""CSV export utilities."""

from io import BytesIO

import pandas as pd


class CsvExporter:
    """Serialize tabular report data without touching the filesystem."""

    media_type = "text/csv"
    extension = "csv"

    @staticmethod
    def export(data: pd.DataFrame) -> bytes:
        buffer = BytesIO()
        data.to_csv(buffer, index=False, encoding="utf-8")
        return buffer.getvalue()
