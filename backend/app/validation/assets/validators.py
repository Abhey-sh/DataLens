"""Assets validation rules.

Completely separate from Members. Rules:

1. Required headers must be present (file blocked until the user fixes it).
2. Keep the most common (studioForeignId, studioId) pair; remove other full rows.
3. resourceType must be MEMBER or STAFF; remove other full rows.
4. assetURL must end with an allowed image extension; remove other full rows.
5. Duplicate resourceForeignId: keep the first row; remove later full rows.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

import pandas as pd
from loguru import logger

from app.core.exceptions import (
    ValidationAction,
    ValidationIssue,
    ValidationSeverity,
)
from app.validation.base import FileValidator

REQUIRED_HEADERS: tuple[str, ...] = (
    "resourceForeignId",
    "studioForeignId",
    "studioId",
    "resourceType",
    "assetURL",
)

RECORD_ID_COLUMN = "resourceForeignId"

BULK_FILL_PROTECTED_FIELDS: frozenset[str] = frozenset(
    {
        "resourceForeignId",
        "studioForeignId",
        "studioId",
        "resourceType",
        "assetURL",
    }
)

ALLOWED_RESOURCE_TYPES: frozenset[str] = frozenset({"MEMBER", "STAFF"})

#: Extensions that map to the allowed image MIME types.
ALLOWED_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".pjpeg"}
)


class RequiredHeaderValidator(FileValidator):
    """Block the file when mandatory Assets columns are missing."""

    def __init__(self) -> None:
        super().__init__(
            rule_id="required_headers",
            rule_name="Required Headers",
            category="File Level",
            severity=ValidationSeverity.ERROR,
            description=(
                "Assets files must include resourceForeignId, studioForeignId, "
                "studioId, resourceType, and assetURL"
            ),
            auto_fix_available=False,
        )

    def validate(self, df: pd.DataFrame) -> list[ValidationIssue]:
        missing = [header for header in REQUIRED_HEADERS if header not in df.columns]
        if not missing:
            return []

        message = f"Missing required headers: {', '.join(missing)}"
        logger.warning(message)
        return [
            ValidationIssue(
                row_number=0,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                field_name="headers",
                current_value=None,
                suggested_value=None,
                severity=self.severity,
                message=message,
                auto_fix_available=False,
                action=ValidationAction.MANUAL_REVIEW,
            )
        ]

    def apply_fix(self, df: pd.DataFrame, row_idx: int) -> pd.DataFrame:
        return df


def _cell(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def _issue(
    *,
    row_number: int,
    rule_id: str,
    rule_name: str,
    field_name: str,
    current_value: str | None,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(
        row_number=row_number,
        rule_id=rule_id,
        rule_name=rule_name,
        field_name=field_name,
        current_value=current_value,
        suggested_value=None,
        severity=ValidationSeverity.ERROR,
        message=message,
        auto_fix_available=False,
        action=ValidationAction.REMOVE,
        issue_type="removed",
    )


def find_majority_studio_pair(
    df: pd.DataFrame,
) -> tuple[str, str] | None:
    """Return the most common non-blank (studioForeignId, studioId) pair."""
    pairs: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        studio_foreign = _cell(row.get("studioForeignId"))
        studio_id = _cell(row.get("studioId"))
        if studio_foreign and studio_id:
            pairs.append((studio_foreign, studio_id))
    if not pairs:
        return None
    return Counter(pairs).most_common(1)[0][0]


def collect_studio_mismatch_removals(
    df: pd.DataFrame,
) -> tuple[list[int], list[ValidationIssue], tuple[str, str] | None]:
    """Rows whose studio pair is not the majority pair."""
    majority = find_majority_studio_pair(df)
    if majority is None:
        return [], [], None

    majority_foreign, majority_id = majority
    remove_indices: list[int] = []
    issues: list[ValidationIssue] = []

    for index, row in df.iterrows():
        studio_foreign = _cell(row.get("studioForeignId"))
        studio_id = _cell(row.get("studioId"))
        if studio_foreign == majority_foreign and studio_id == majority_id:
            continue

        remove_indices.append(int(index))
        issues.append(
            _issue(
                row_number=int(index) + 1,
                rule_id="primary_studio",
                rule_name="Primary Studio Filter",
                field_name="studioForeignId",
                current_value=(
                    f"{studio_foreign or ''} / {studio_id or ''}".strip(" /")
                    or None
                ),
                message=(
                    "Row removed: studioForeignId/studioId do not match the "
                    f"primary studio ({majority_foreign} / {majority_id})"
                ),
            )
        )

    return remove_indices, issues, majority


def collect_resource_type_removals(
    df: pd.DataFrame,
) -> tuple[list[int], list[ValidationIssue]]:
    """Rows whose resourceType is not MEMBER or STAFF."""
    remove_indices: list[int] = []
    issues: list[ValidationIssue] = []

    for index, row in df.iterrows():
        value = _cell(row.get("resourceType"))
        if value and value.upper() in ALLOWED_RESOURCE_TYPES:
            continue
        remove_indices.append(int(index))
        issues.append(
            _issue(
                row_number=int(index) + 1,
                rule_id="resource_type",
                rule_name="Resource Type",
                field_name="resourceType",
                current_value=value,
                message=(
                    "Row removed: resourceType must be MEMBER or STAFF"
                    + (f" (found '{value}')" if value else " (blank)")
                ),
            )
        )

    return remove_indices, issues


def asset_url_extension(url: str | None) -> str | None:
    """Return the lowercase file extension from an asset URL path."""
    if not url:
        return None
    path = urlparse(url).path if "://" in url else url
    # Handle plain s3:// and path-only values.
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    return "." + name.rsplit(".", 1)[-1].lower()


def collect_asset_url_removals(
    df: pd.DataFrame,
) -> tuple[list[int], list[ValidationIssue]]:
    """Rows whose assetURL is not an allowed image type."""
    remove_indices: list[int] = []
    issues: list[ValidationIssue] = []

    for index, row in df.iterrows():
        url = _cell(row.get("assetURL"))
        extension = asset_url_extension(url)
        if extension in ALLOWED_IMAGE_EXTENSIONS:
            continue
        remove_indices.append(int(index))
        issues.append(
            _issue(
                row_number=int(index) + 1,
                rule_id="asset_url",
                rule_name="Asset URL Image Type",
                field_name="assetURL",
                current_value=url,
                message=(
                    "Row removed: assetURL must be an image "
                    "(.jpg, .jpeg, .png, .bmp)"
                    + (f" (found '{extension}')" if extension else "")
                ),
            )
        )

    return remove_indices, issues


def collect_duplicate_resource_id_removals(
    df: pd.DataFrame,
) -> tuple[list[int], list[ValidationIssue]]:
    """Keep the first resourceForeignId; remove later duplicate full rows."""
    remove_indices: list[int] = []
    issues: list[ValidationIssue] = []
    seen: set[str] = set()

    for index, row in df.iterrows():
        resource_id = _cell(row.get("resourceForeignId"))
        if not resource_id:
            remove_indices.append(int(index))
            issues.append(
                _issue(
                    row_number=int(index) + 1,
                    rule_id="duplicate_resource_foreign_id",
                    rule_name="Duplicate Resource Foreign ID",
                    field_name="resourceForeignId",
                    current_value=None,
                    message="Row removed: resourceForeignId is blank",
                )
            )
            continue

        if resource_id in seen:
            remove_indices.append(int(index))
            issues.append(
                _issue(
                    row_number=int(index) + 1,
                    rule_id="duplicate_resource_foreign_id",
                    rule_name="Duplicate Resource Foreign ID",
                    field_name="resourceForeignId",
                    current_value=resource_id,
                    message=(
                        "Row removed: duplicate resourceForeignId "
                        f"'{resource_id}' (first occurrence kept)"
                    ),
                )
            )
            continue

        seen.add(resource_id)

    return remove_indices, issues


def build_file_validators() -> list[FileValidator]:
    return [RequiredHeaderValidator()]
