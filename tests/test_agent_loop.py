"""Tests for the complete agent execution loop."""

import json
from json2py.agent.loop import AgentConverter
from json2py.models import OutputFormat


def test_agent_end_to_end_pydantic():
    converter = AgentConverter()
    payload = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "first-name": "Avinaash",
        "user_email": "avinaash@example.com",
        "address": {"city": "Chennai", "country": "India"},
        "tags": ["agent", "python"],
    }
    result = converter.convert(json.dumps(payload), OutputFormat.PYDANTIC, root_name="User")
    assert result.status == "validated"
    assert "class User(BaseModel):" in result.code
    assert "class Address(BaseModel):" in result.code
    assert len(result.decision_log) > 0


def test_agent_end_to_end_dataclass():
    converter = AgentConverter()
    payload = {
        "name": "Widget",
        "price": 19.99,
        "in_stock": True,
        "specs": {"weight_kg": 0.5},
    }
    result = converter.convert(json.dumps(payload), OutputFormat.DATACLASS, root_name="Product")
    assert result.status == "validated"
    assert "class Product:" in result.code
    assert "class Specs:" in result.code
    assert "def from_dict(" in result.code


def test_agent_invalid_json():
    converter = AgentConverter()
    result = converter.convert('{"bad": json}', OutputFormat.PYDANTIC)
    assert result.status == "syntax_error"
    assert "JSON Syntax Error" in result.error_message


def test_decision_log_generation():
    converter = AgentConverter()
    payload = {
        "class": "Senior",
        "2fa": True,
        "timestamp": "2026-09-28T17:31:29Z",
    }
    result = converter.convert(json.dumps(payload), OutputFormat.PYDANTIC)
    categories = [d.category for d in result.decision_log]
    assert "naming" in categories
    assert "format_detection" in categories
