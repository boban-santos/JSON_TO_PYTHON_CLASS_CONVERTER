"""Core engine package for parsing, format detection, naming, and type inferencing."""

from json2py.core.format_detector import detect_string_format
from json2py.core.inferencer import SchemaInferencer
from json2py.core.merger import merge_samples
from json2py.core.namer import sanitize_field_name, suggest_class_name, to_pascal_case, to_snake_case
from json2py.core.parser import JSONParseError, LimitExceededError, parse_json

__all__ = [
    "parse_json",
    "JSONParseError",
    "LimitExceededError",
    "SchemaInferencer",
    "detect_string_format",
    "sanitize_field_name",
    "suggest_class_name",
    "to_pascal_case",
    "to_snake_case",
    "merge_samples",
]
