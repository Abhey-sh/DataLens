"""Field cleaning helpers for members review suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd
from dateutil import parser as date_parser
from email_validator import EmailNotValidError, validate_email

NAME_JUNK = re.compile(r"[^A-Za-z\s\-'.]")
MULTI_SPACE = re.compile(r"\s+")
HYPHEN_SPACE = re.compile(r"\s*-\s*")
EMAIL_ALLOWED = re.compile(r"[^A-Za-z0-9.@_+-]")
LEAD_ALIASES = {
    "lead": "LEAD",
    "leads": "LEAD",
    "member": "MEMBER",
    "members": "MEMBER",
}
ALLOWED_GENDERS = {"M", "F", "P"}
ALLOWED_LEAD_STATUSES = {"MEMBER", "LEAD", "COLD", "TRIALS"}


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


def clean_name(value) -> CleanResult:
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested="-",
            current=None,
            message="Blank name will be set to '-'",
        )

    cleaned = NAME_JUNK.sub("", current)
    cleaned = HYPHEN_SPACE.sub("-", cleaned)
    cleaned = MULTI_SPACE.sub(" ", cleaned).strip(" -'.")
    cleaned = cleaned.strip()

    if not cleaned:
        return CleanResult(
            status="suggest",
            suggested="-",
            current=current,
            message="Name contained only junk characters; will be set to '-'",
        )

    if len(cleaned) > 80 or not re.fullmatch(r"[A-Za-z][A-Za-z\s\-'.]*", cleaned):
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Name is still invalid after cleaning (pattern or max 80 chars)",
        )

    if cleaned != current:
        return CleanResult(
            status="suggest",
            suggested=cleaned,
            current=current,
            message="Name will be cleaned",
        )
    return CleanResult(status="ok", current=current)


def clean_phone(value) -> CleanResult:
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested="-",
            current=None,
            message="Blank phone will be set to '-'",
        )

    raw = current.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return CleanResult(
            status="suggest",
            suggested="-",
            current=current,
            message="Phone contained only junk; will be set to '-'",
        )

    cleaned = f"+{digits}" if has_plus else digits
    if has_plus and not cleaned.startswith("+"):
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Phone has an invalid leading + form",
        )

    digit_count = len(digits)
    if digit_count < 7 or digit_count > 15:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Phone must contain 7–15 digits",
        )

    if cleaned != current:
        return CleanResult(
            status="suggest",
            suggested=cleaned,
            current=current,
            message="Phone will be sanitized",
        )
    return CleanResult(status="ok", current=current)


def clean_email(value) -> CleanResult:
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

    try:
        parsed = date_parser.parse(str(current), dayfirst=False, fuzzy=False)
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
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested="P",
            current=None,
            message="Blank gender will be set to 'P'",
        )

    letters_only = re.sub(r"[^A-Za-z]", "", current)
    if letters_only != current.strip() or not letters_only:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Gender contains non-letters",
        )

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
            message="Gender will be normalized",
        )
    return CleanResult(status="ok", current=current)


def clean_country_code(value) -> CleanResult:
    current = _current(value)
    if current is None:
        return CleanResult(status="ok")  # required-field handles blank

    letters = re.sub(r"[^A-Za-z]", "", current)
    if len(letters) != 2:
        return CleanResult(
            status="change_need",
            suggested=None,
            current=current,
            message="Country code must be exactly 2 letters",
        )

    upper = letters.upper()
    if upper != current:
        return CleanResult(
            status="suggest",
            suggested=upper,
            current=current,
            message="Country code will be uppercased",
        )
    return CleanResult(status="ok", current=current)


def clean_postal_code(value) -> CleanResult:
    current = _current(value)
    if current is None:
        return CleanResult(
            status="suggest",
            suggested="-",
            current=None,
            message="Blank postal code will be set to '-'",
        )
    return CleanResult(status="ok", current=current)


def clean_lead_status(value) -> CleanResult:
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
