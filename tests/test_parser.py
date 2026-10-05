"""Tests for the JSON parser, syntax error reporting, and limit guards."""

import json
import pytest
from json2py.core.parser import JSONParseError, LimitExceededError, parse_json


def test_parse_valid_json():
    raw = '{"name": "Alice", "age": 30, "active": true}'
    res = parse_json(raw)
    assert res.data == {"name": "Alice", "age": 30, "active": True}
    assert res.warnings == []


def test_parse_syntax_error_reporting():
    bad_raw = '{\n  "name": "Alice",\n  "age": 30\n  "active": true\n}'
    with pytest.raises(JSONParseError) as exc_info:
        parse_json(bad_raw)
    err = exc_info.value
    assert err.line == 4
    assert err.column >= 3
    assert "^" in err.snippet


def test_empty_string_error():
    with pytest.raises(JSONParseError):
        parse_json("   ")


def test_duplicate_key_detection():
    dup_raw = '{"key": 1, "key": 2}'
    res = parse_json(dup_raw)
    assert res.data["key"] == 2
    assert len(res.warnings) == 1
    assert "Duplicate key 'key' encountered" in res.warnings[0]


def test_depth_limit_exceeded():
    # Build deeply nested object exceeding depth 20
    nested = "val"
    for _ in range(25):
        nested = {"level": nested}
    raw = json.dumps(nested)
    with pytest.raises(LimitExceededError):
        parse_json(raw, max_depth=20)


def test_size_limit_exceeded():
    large_payload = " " * 2000
    with pytest.raises(LimitExceededError):
        parse_json(large_payload, max_size_bytes=1000)
