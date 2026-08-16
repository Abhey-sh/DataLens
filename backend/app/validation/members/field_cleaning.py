"""Field cleaning helpers for members review suggestions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pycountry
import tldextract
from dateutil import parser as date_parser
from email_validator import EmailNotValidError, validate_email

EMAIL_ALLOWED = re.compile(r"[^A-Za-z0-9.@_+-]")
NAME_ALLOWED_PUNCTUATION = frozenset("'’‘-.():#,")
NAME_URL_PREFIX = re.compile(r"(?i)(?:https?://|www\.)")
NAME_HOST_CANDIDATE = re.compile(r"[\w-]+(?:\.[\w-]+)+")
PUBLIC_SUFFIX_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())
LEAD_ALIASES = {
    "lead": "LEAD",
    "leads": "LEAD",
    "member": "MEMBER",
    "members": "MEMBER",
    "cold": "COLD",
    "trial": "TRIALS",
    "trials": "TRIALS",
}
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


def sanitize_name_input(value):
    """Trim a member name and remove Unicode control/format characters."""
    if _is_blank(value):
        return None
    normalized = unicodedata.normalize("NFC", str(value))
    sanitized = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    ).strip()
    return sanitized or None


def is_allowed_name_text(value: str) -> bool:
    """Return whether every character belongs to the member-name allowlist."""
    return all(
        character.isalpha()
        or unicodedata.category(character).startswith("M")
        or character.isdigit()
        or character.isspace()
        or character in NAME_ALLOWED_PUNCTUATION
        for character in value
    )


def contains_name_url(value: str) -> bool:
    """Detect URL-shaped content, including bare names with a TLD suffix."""
    if NAME_URL_PREFIX.search(value):
        return True
    return any(
        bool(PUBLIC_SUFFIX_EXTRACTOR(candidate.group()).suffix)
        for candidate in NAME_HOST_CANDIDATE.finditer(value)
    )


def validate_name_text(
    value: str, *, field_label: str, max_length: int | None = None
) -> str | None:
    """Return a manual-review reason when a nonblank name is invalid."""
    if max_length is not None and len(value) > max_length:
        return f"{field_label} must be between 1 and {max_length} characters"
    if not is_allowed_name_text(value):
        return f"{field_label} contains unsupported characters"
    if contains_name_url(value):
        return f"{field_label} must not contain a URL-like value"
    return None


def validate_name_pair(first_name: str, last_name: str) -> str | None:
    """Validate all four concatenations in addition to the two fields."""
    combinations = (
        first_name + last_name,
        first_name + " " + last_name,
        last_name + first_name,
        last_name + " " + first_name,
    )
    for value in combinations:
        reason = validate_name_text(value, field_label="Combined name")
        if reason:
            return reason
    return None


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


def sanitize_phone_for_export(value) -> str:
    """Remove phone formatting for exports while preserving a leading plus."""
    current = _current(value)
    if current is None:
        return ""
    digits = re.sub(r"\D", "", current)
    if not digits:
        return ""
    return f"+{digits}" if current.strip().startswith("+") else digits


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

    if stripped.count("@") == 1:
        local, domain = stripped.split("@", 1)
        local = re.sub(r"\.{2,}", ".", local).strip(".")
        domain = re.sub(r"\.{2,}", ".", domain).strip(".")
        stripped = f"{local}@{domain}"

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
            status="suggest",
            suggested="P",
            current=current,
            message="Gender contains no usable letters and will default to 'P'",
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

    return CleanResult(
        status="suggest",
        suggested="P",
        current=current,
        message=f"Unrecognized gender value '{current}' will default to 'P'",
    )


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


def fill_country_code_for_export(code, country_name) -> str:
    """Fill a blank export country code from a recognized country name."""
    current_code = _current(code)
    if current_code is not None:
        return current_code

    country = _current(country_name)
    if country is None:
        return ""
    try:
        return pycountry.countries.lookup(country).alpha_2
    except LookupError:
        return ""


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
