"""CSV parsing helpers with safe, deterministic encoding fallbacks."""

from io import BytesIO

import pandas as pd


class CsvReadError(ValueError):
    """Raised when uploaded bytes cannot be parsed as a supported CSV."""


SUPPORTED_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    """Read CSV bytes while preserving identifiers as strings.

    UTF-8 is preferred. Windows-1252 and Latin-1 are supported for files
    exported by common spreadsheet applications.
    """
    decode_errors: list[str] = []

    for encoding in SUPPORTED_ENCODINGS:
        try:
            return pd.read_csv(BytesIO(content), dtype=str, encoding=encoding)
        except UnicodeDecodeError as exc:
            decode_errors.append(f"{encoding}: {exc}")
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise CsvReadError(f"Invalid CSV structure: {exc}") from exc

    attempted = ", ".join(SUPPORTED_ENCODINGS)
    raise CsvReadError(
        f"Unable to decode CSV. Supported encodings: {attempted}. "
        f"Details: {'; '.join(decode_errors)}"
    )
