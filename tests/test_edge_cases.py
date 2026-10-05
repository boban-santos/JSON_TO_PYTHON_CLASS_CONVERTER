"""Tests covering PRD Section 8 edge cases."""

import json
import pytest
from json2py.agent.loop import AgentConverter
from json2py.core.parser import JSONParseError
from json2py.models import OutputFormat


def test_empty_object():
    converter = AgentConverter()
    res = converter.convert("{}", OutputFormat.PYDANTIC)
    assert res.status == "validated"
    assert "class Root(BaseModel):" in res.code
    assert "pass" in res.code

    res_dc = converter.convert("{}", OutputFormat.DATACLASS)
    assert res_dc.status == "validated"
    assert "class Root:" in res_dc.code


def test_empty_array():
    converter = AgentConverter()
    res = converter.convert('{"items": []}', OutputFormat.PYDANTIC)
    assert res.status == "validated"
    assert "items: list[Any]" in res.code
    assert len(res.clarifying_questions) > 0


def test_keywords_and_special_keys():
    converter = AgentConverter()
    payload = {
        "class": "A",
        "from": "B",
        "import": "C",
        "def": "D",
        "in": True,
        "first-name": "John",
        "user name": "jdoe",
        "2fa": False,
        "@type": "Person",
    }
    res_pydantic = converter.convert(json.dumps(payload), OutputFormat.PYDANTIC)
    assert res_pydantic.status == "validated"
    assert 'class_: str = Field(..., alias="class")' in res_pydantic.code
    assert 'from_: str = Field(..., alias="from")' in res_pydantic.code
    assert 'val_2fa: bool = Field(..., alias="2fa")' in res_pydantic.code

    res_dc = converter.convert(json.dumps(payload), OutputFormat.DATACLASS)
    assert res_dc.status == "validated"
    assert "class_: str" in res_dc.code
    assert "val_2fa: bool" in res_dc.code


def test_recursive_tree_structure():
    converter = AgentConverter()
    tree = {
        "name": "root_node",
        "children": [
            {
                "name": "child_node",
                "children": []
            }
        ]
    }
    res = converter.convert(json.dumps(tree), OutputFormat.PYDANTIC, root_name="Node")
    assert res.status == "validated"
    assert "from __future__ import annotations" in res.code
    assert "class Node(BaseModel):" in res.code


def test_duplicate_keys_warning():
    converter = AgentConverter()
    dup_json = '{"key": 1, "key": 2}'
    res = converter.convert(dup_json, OutputFormat.PYDANTIC)
    assert res.status == "validated"
    assert len(res.warnings) > 0
    assert "Duplicate key 'key'" in res.warnings[0]


def test_invalid_json_single_quotes_and_trailing_commas():
    converter = AgentConverter()
    # Single quotes
    res1 = converter.convert("{'name': 'invalid'}", OutputFormat.PYDANTIC)
    assert res1.status == "syntax_error"

    # Trailing comma
    res2 = converter.convert('{"name": "valid",}', OutputFormat.PYDANTIC)
    assert res2.status == "syntax_error"


def test_array_of_mixed_objects():
    converter = AgentConverter()
    payload = {
        "users": [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob"}  # missing 'role'
        ]
    }
    res = converter.convert(json.dumps(payload), OutputFormat.PYDANTIC)
    assert res.status == "validated"
    # Role should be optional (None default)
    assert "role: str | None = None" in res.code
