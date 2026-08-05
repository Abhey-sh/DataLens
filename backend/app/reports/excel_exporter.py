"""Excel export utilities."""

from io import BytesIO

import pandas as pd


class ExcelExporter:
    """Serialize tabular report data to an in-memory XLSX workbook."""

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    extension = "xlsx"

    @staticmethod
    def export(data: pd.DataFrame, sheet_name: str = "Report") -> bytes:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        return buffer.getvalue()
