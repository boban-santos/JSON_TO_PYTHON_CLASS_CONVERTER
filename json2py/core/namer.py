"""Naming resolver: key sanitization, keyword handling, class name singularization, and collision resolution."""

from __future__ import annotations

import keyword
import re
from typing import Optional

# Python keywords & built-in identifier conflicts
PYTHON_KEYWORDS = set(keyword.kwlist) | {
    "None", "True", "False", "match", "case"
}

# Names reserved or problematic in Pydantic BaseModel or standard dataclasses
RESERVED_FIELD_NAMES = {
    "dict", "json", "copy", "parse_obj", "parse_raw", "schema", "schema_json",
    "validate", "fields", "model_validate", "model_dump", "model_dump_json",
    "model_config", "model_fields", "model_extra", "model_computed_fields"
}

# Number words for prefixing leading numbers if desired
NUMBER_PREFIXES = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"
}


def to_snake_case(name: str) -> str:
    """Convert camelCase, PascalCase, kebab-case, or symbol-laden string to snake_case."""
    # Replace any non-alphanumeric characters with underscore
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    # Handle camelCase / PascalCase: e.g. 'firstName' -> 'first_Name', 'XMLHttpRequest' -> 'XML_Http_Request'
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    s = s.lower()
    # Collapse multiple consecutive underscores
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def sanitize_field_name(raw_key: str) -> tuple[str, Optional[str]]:
    """
    Sanitize a JSON key into a valid Python identifier.
    Returns (clean_name, alias).
    If clean_name != raw_key, alias is raw_key.
    """
    if not raw_key:
        return "empty_field", raw_key

    # Convert to snake_case
    clean = to_snake_case(raw_key)

    if not clean:
        # e.g. key was only punctuation like "---"
        clean = "field"

    # If starts with a digit, prefix with 'val_' (Pydantic forbids leading underscores for fields)
    if clean[0].isdigit():
        clean = f"val_{clean}"

    # Handle Python keywords and reserved names
    if clean in PYTHON_KEYWORDS or clean in RESERVED_FIELD_NAMES:
        clean = f"{clean}_"

    alias = raw_key if clean != raw_key else None
    return clean, alias


def singularize(word: str) -> str:
    """Basic English singularization for class names derived from list keys."""
    lower = word.lower()
    if lower.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    elif lower.endswith("ses") or lower.endswith("xes") or lower.endswith("ches") or lower.endswith("shes"):
        return word[:-2]
    elif lower.endswith("s") and not lower.endswith("ss") and len(word) > 2:
        return word[:-1]
    return word


def to_pascal_case(name: str) -> str:
    """Convert arbitrary string into PascalCase for class names."""
    words = re.split(r"[\s_\-./:@]+", name)
    pascal = "".join(w.capitalize() for w in words if w)
    if not pascal:
        pascal = "Item"
    # Ensure starts with a valid letter
    if pascal[0].isdigit():
        pascal = f"Class{pascal}"
    return pascal


def suggest_class_name(
    parent_key: Optional[str],
    is_list_item: bool = False,
    depth: int = 0,
    parent_class: Optional[str] = None,
) -> str:
    """Suggest a class name based on parent key, context, and whether it represents list items."""
    if not parent_key:
        return "Root"

    key = parent_key
    if is_list_item:
        key = singularize(key)

    name = to_pascal_case(key)

    # If parent class is provided and name is too generic (like 'Item', 'Data', 'Detail')
    if parent_class and name in ("Item", "Data", "Detail", "Info", "Entry", "Record"):
        name = f"{parent_class}{name}"

    return name
