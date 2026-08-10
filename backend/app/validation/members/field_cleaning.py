"""Field cleaning helpers for members review suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd
from dateutil import parser as date_parser
from email_validator import EmailNotValidError, validate_email

EMAIL_ALLOWED = re.compile(r"[^A-Za-z0-9.@_+-]")
ALLOWED_GENDERS = {"M", "F", "P"}
GENDER_ALIASES = {
    "m": "M",
    "male": "M",
    "man": "M",
    "f": "F",
    "female": "F",
    "woman": "F",
    "w": "F",
    "p": "P",
    "prefernottosay": "P",
    "unknown": "P",
    "other": "P",
    "nonbinary": "P",
    "nb": "P",
}
ALLOWED_LEAD_STATUSES = {"MEMBER", "LEAD", "COLD", "TRIALS"}
LEAD_ALIASES = {
    "lead": "LEAD",
    "leads": "LEAD",
    "member": "MEMBER",
    "members": "MEMBER",
    "cold": "COLD",
    "trial": "TRIALS",
    "trials": "TRIALS",
}


@dataclass
class CleanResult:
    status: Literal["ok", "suggest", "change_need"]
    suggested: str | None = None
    current: str | None = None
    message: str = ""


def _is_blank(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _current(value) -> str | None:
    if _is_blank(value):
        return None
    return str(value)


def clean_email(value) -> CleanResult:
    """Strip junk/spaces/extra @; still invalid → change_need."""
    current = _current(value)
    if current is None:
        return CleanResult(status="ok")  # required-field validator handles blank

    stripped = current.strip()
    stripped = re.sub(r"\s+", "", stripped)
    stripped = EMAIL_ALLOWED.sub("", stripped)
    # Collapse multiple @ into a single @ (keep first local@domain shape)
    if stripped.count("@") > 1:
        local, *rest = stripped.split("@")
        domain = "".join(rest).replace("@", "")
        stripped = f"{local}@{domain}" if local and domain else stripped

    try:
        validate_email(stripped, check_deliverability=False)
    except EmailNotValidError as exc:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message=f"Email still invalid after cleaning: {exc}",
        )

    if stripped != current:
        return CleanResult(
            status="suggest",
            suggested=stripped,
            current=current,
            message="Email will be cleaned",
        )
    return CleanResult(status="ok", current=current)


def clean_date(value, *, blank_default: str = "-") -> CleanResult:
    """Normalize dates to yyyy-mm-dd. Blank → blank_default."""
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested=blank_default,
            current=None,
            message=f"Blank date will be set to '{blank_default}'",
        )

    if current == blank_default:
        return CleanResult(status="ok", current=current)

    # Collapse odd spacing so values like "01-jan -2005" still parse
    compacted = re.sub(r"\s+", " ", current.strip())
    compacted = re.sub(r"\s*([-/])\s*", r"\1", compacted)

    try:
        parsed = date_parser.parse(compacted, dayfirst=False, fuzzy=False)
        normalized = parsed.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError):
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message=f"Date is not a valid yyyy-mm-dd value: {current}",
        )

    if normalized != current:
        return CleanResult(
            status="suggest",
            suggested=normalized,
            current=current,
            message="Date will be normalized to yyyy-mm-dd",
        )
    return CleanResult(status="ok", current=current)


def clean_gender(value) -> CleanResult:
    """Normalize gender to M, F, or P. Blank → P."""
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested="P",
            current=None,
            message="Blank gender will be set to 'P'",
        )

    letters_only = re.sub(r"[^A-Za-z]", "", current)
    if not letters_only:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Gender contains no usable letters. Must be M, F, or P",
        )

    key = letters_only.lower()
    if key in GENDER_ALIASES:
        suggested = GENDER_ALIASES[key]
        if suggested != current:
            return CleanResult(
                status="suggest",
                suggested=suggested,
                current=current,
                message=f"Gender will be set to '{suggested}'",
            )
        return CleanResult(status="ok", current=current)

    upper = letters_only.upper()
    if upper not in ALLOWED_GENDERS:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message=f"Invalid gender value: {current}. Must be M, F, or P",
        )

    if upper != current:
        return CleanResult(
            status="suggest",
            suggested=upper,
            current=current,
            message=f"Gender will be set to '{upper}'",
        )
    return CleanResult(status="ok", current=current)


def clean_lead_status(value) -> CleanResult:
    """Normalize lead status to MEMBER, LEAD, COLD, or TRIALS."""
    current = _current(value)
    if current is None:
        return CleanResult(status="ok")  # required-field handles blank

    key = current.strip().lower()
    if key in LEAD_ALIASES:
        suggested = LEAD_ALIASES[key]
        if suggested != current:
            return CleanResult(
                status="suggest",
                suggested=suggested,
                current=current,
                message=f"Lead status will be set to {suggested}",
            )
        return CleanResult(status="ok", current=current)

    compact = re.sub(r"[^A-Za-z]", "", current).lower()
    if compact in LEAD_ALIASES:
        suggested = LEAD_ALIASES[compact]
        if suggested != current:
            return CleanResult(
                status="suggest",
                suggested=suggested,
                current=current,
                message=f"Lead status will be set to {suggested}",
            )
        return CleanResult(status="ok", current=current)

    upper = current.strip().upper()
    if upper in ALLOWED_LEAD_STATUSES:
        if upper != current:
            return CleanResult(
                status="suggest",
                suggested=upper,
                current=current,
                message=f"Lead status will be set to {upper}",
            )
        return CleanResult(status="ok", current=current)

    return CleanResult(
        status="change_need",
        suggested=None,
        current=current,
        message=(
            f"Invalid lead status: {current}. "
            "Must be MEMBER, LEAD, COLD, or TRIALS"
        ),
    )
