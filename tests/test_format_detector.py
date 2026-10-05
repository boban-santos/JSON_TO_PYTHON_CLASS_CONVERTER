"""Tests for format detection of ISO dates, datetimes, UUIDs, Emails, and URLs."""

from json2py.core.format_detector import detect_string_format


def test_detect_datetime():
    assert detect_string_format("2026-09-28T17:31:29Z") == "datetime"
    assert detect_string_format("2026-09-28T17:31:29+05:30") == "datetime"
    assert detect_string_format("2026-09-28 17:31:29") == "datetime"


def test_detect_date():
    assert detect_string_format("2026-09-28") == "date"
    assert detect_string_format("1995-12-31") == "date"


def test_detect_uuid():
    assert detect_string_format("123e4567-e89b-12d3-a456-426614174000") == "UUID"
    assert detect_string_format("c9bf9e57-1685-4c89-bafb-ff5af830be8a") == "UUID"


def test_detect_email():
    assert detect_string_format("user@example.com") == "EmailStr"
    assert detect_string_format("john.doe+test@sub.domain.org") == "EmailStr"


def test_detect_url():
    assert detect_string_format("https://github.com/google/antigravity") == "HttpUrl"
    assert detect_string_format("http://localhost:8501") == "HttpUrl"


def test_non_formats():
    assert detect_string_format("plain text") is None
    assert detect_string_format("12345") is None
    assert detect_string_format("2026/09/28") is None
