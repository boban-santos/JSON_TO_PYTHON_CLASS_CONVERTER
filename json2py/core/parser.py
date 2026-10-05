"""JSON Parser with precise syntax error reporting, duplicate key detection, and safety limits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


class JSONParseError(Exception):
    """Raised when JSON parsing fails with line/col details."""

    def __init__(self, message: str, line: int, column: int, snippet: str):
        super().__init__(f"JSON Syntax Error at line {line}, column {column}: {message}\n{snippet}")
        self.raw_message = message
        self.line = line
        self.column = column
        self.snippet = snippet


class LimitExceededError(Exception):
    """Raised when payload exceeds size or depth limits."""
    pass


@dataclass
class ParseResult:
    data: Any
    warnings: list[str]


def _check_depth(val: Any, current_depth: int = 1, max_depth: int = 20) -> int:
    """Calculate maximum nesting depth and check against limit."""
    if current_depth > max_depth:
        raise LimitExceededError(
            f"Payload exceeds maximum nesting depth limit of {max_depth} levels."
        )

    max_d = current_depth
    if isinstance(val, dict):
        for v in val.values():
            max_d = max(max_d, _check_depth(v, current_depth + 1, max_depth))
    elif isinstance(val, list):
        for v in val:
            max_d = max(max_d, _check_depth(v, current_depth + 1, max_depth))
    return max_d


def parse_json(
    raw_text: str,
    max_size_bytes: int = 1_048_576,  # 1 MB
    max_depth: int = 20,
) -> ParseResult:
    """
    Parse a JSON string into Python data.
    
    Checks:
    - Max size limit (FR-8 edge cases: 1 MB)
    - Syntax validation with exact line and column (FR-2)
    - Duplicate key detection with warning (FR-8 edge cases)
    - Max nesting depth limit (20 levels)
    """
    # 1. Size check
    byte_size = len(raw_text.encode("utf-8")) if raw_text else 0
    if byte_size > max_size_bytes:
        raise LimitExceededError(
            f"Payload size ({byte_size:,} bytes) exceeds maximum limit of {max_size_bytes:,} bytes (1 MB)."
        )

    if not raw_text or not raw_text.strip():
        raise JSONParseError("Empty JSON input provided.", line=1, column=1, snippet="")

    # 2. Syntax parse with duplicate key detector
    warnings: list[str] = []

    def dict_with_duplicate_detection(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for key, value in pairs:
            if key in d:
                warnings.append(
                    f"Duplicate key '{key}' encountered in JSON object. Python's parser retains the last value."
                )
            d[key] = value
        return d

    try:
        data = json.loads(raw_text, object_pairs_hook=dict_with_duplicate_detection)
    except json.JSONDecodeError as err:
        # Extract snippet around error position
        lines = raw_text.splitlines()
        line_idx = err.lineno - 1
        snippet_lines = []
        start_line = max(0, line_idx - 1)
        end_line = min(len(lines), line_idx + 2)

        for idx in range(start_line, end_line):
            prefix = f"{idx + 1:4d} | "
            line_content = lines[idx] if idx < len(lines) else ""
            snippet_lines.append(prefix + line_content)
            if idx == line_idx:
                pointer = " " * (len(prefix) + max(0, err.colno - 1)) + "^"
                snippet_lines.append(pointer)

        snippet = "\n".join(snippet_lines)
        raise JSONParseError(
            message=err.msg,
            line=err.lineno,
            column=err.colno,
            snippet=snippet,
        ) from err

    # 3. Depth check
    _check_depth(data, current_depth=1, max_depth=max_depth)

    return ParseResult(data=data, warnings=warnings)
