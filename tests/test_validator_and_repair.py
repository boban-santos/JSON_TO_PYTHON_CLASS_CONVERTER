"""Tests for sandboxed validation and the self-repair loop."""

from json2py.agent.repair import SchemaRepairer
from json2py.agent.validator import CodeValidator
from json2py.core.inferencer import SchemaInferencer
from json2py.generators.pydantic_gen import PydanticV2Generator
from json2py.models import OutputFormat


def test_validator_success():
    code = """
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    name: str
"""
    res = CodeValidator.validate(code, {"id": 1, "name": "Alice"}, "User", OutputFormat.PYDANTIC)
    assert res.is_valid is True
    assert res.status == "validated"


def test_validator_syntax_error():
    bad_code = "class User(BaseModel: id: int"
    res = CodeValidator.validate(bad_code, {"id": 1}, "User", OutputFormat.PYDANTIC)
    assert res.is_valid is False
    assert res.status == "error"
    assert "SyntaxError" in res.errors[0]


def test_validator_validation_failure():
    code = """
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: int
    name: str
"""
    # Payload missing required 'name' field
    res = CodeValidator.validate(code, {"id": 1}, "User", OutputFormat.PYDANTIC)
    assert res.is_valid is False
    assert res.status == "unvalidated"
    assert any("name" in e for e in res.errors)


def test_repair_missing_field():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({"id": 1, "missing_key": "val"})
    # Initially missing_key is required
    assert plan.classes["Root"].fields["missing_key"].is_optional is False

    repaired_plan, decisions = SchemaRepairer.attempt_repair(
        plan=plan,
        errors=["Field 'missing_key': Field required (type: missing)"],
        attempt_number=1,
    )
    assert repaired_plan.classes["Root"].fields["missing_key"].is_optional is True
    assert len(decisions) >= 1
    assert "Repaired missing field 'missing_key'" in decisions[0].message


def test_agent_self_repair_on_demote_format():
    """Verify that when a formatted string fails strict validation, the repairer demotes to str."""
    from json2py.agent.loop import AgentConverter
    import json

    # A string that looks like a URL initially or email, but if validation fails, repair demotes it
    converter = AgentConverter()
    payload = {"email_contact": "not_an_email_actually@"}
    # The converter parses it as str or EmailStr, validates it against Pydantic
    res = converter.convert(json.dumps(payload), OutputFormat.PYDANTIC)
    assert res.status == "validated"
    assert "email_contact: str" in res.code
