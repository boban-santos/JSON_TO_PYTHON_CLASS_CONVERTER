"""Format detector for common string patterns (ISO date/datetime, UUID, email, URL)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from uuid import UUID

# Regex patterns
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)
URL_REGEX = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)
UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def detect_string_format(val: str) -> Optional[str]:
    """
    Detect if a string value matches a well-known semantic type:
    - 'datetime': ISO 8601 datetime
    - 'date': YYYY-MM-DD date
    - 'UUID': standard UUID format
    - 'EmailStr': valid email address
    - 'HttpUrl': HTTP / HTTPS URL
    """
    val = val.strip()
    if not val:
        return None

    # 1. UUID
    if UUID_REGEX.match(val):
        try:
            UUID(val)
            return "UUID"
        except ValueError:
            pass

    # 2. Date (YYYY-MM-DD)
    if DATE_REGEX.match(val):
        try:
            date.fromisoformat(val)
            return "date"
        except ValueError:
            pass

    # 3. Datetime (ISO 8601 with T or space)
    if ("T" in val or " " in val) and len(val) >= 19:
        try:
            # Handle trailing Z
            iso_val = val.replace("Z", "+00:00")
            datetime.fromisoformat(iso_val)
            return "datetime"
        except ValueError:
            pass

    # 4. Email
    if "@" in val and EMAIL_REGEX.match(val):
        return "EmailStr"

    # 5. URL
    if (val.startswith("http://") or val.startswith("https://")) and URL_REGEX.match(val):
        return "HttpUrl"

    return None
