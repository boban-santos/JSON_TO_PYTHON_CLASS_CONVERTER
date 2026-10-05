"""Tests for SchemaInferencer and multi-sample merger."""

from json2py.core.inferencer import SchemaInferencer
from json2py.models import (
    ClassRefType,
    ListType,
    OptionalType,
    PrimitiveType,
    UnionType,
)


def test_infer_primitives():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({"name": "Bob", "age": 25, "active": True, "score": 98.6})
    root = plan.classes["Root"]
    assert isinstance(root.fields["name"].field_type, PrimitiveType)
    assert root.fields["name"].field_type.name == "str"
    assert root.fields["age"].field_type.name == "int"
    assert root.fields["active"].field_type.name == "bool"
    assert root.fields["score"].field_type.name == "float"


def test_int_float_promotion():
    inferencer = SchemaInferencer()
    # List with int and float promotes to float
    plan = inferencer.infer({"values": [1, 2.5, 3]})
    root = plan.classes["Root"]
    list_type = root.fields["values"].field_type
    assert isinstance(list_type, ListType)
    assert isinstance(list_type.item_type, PrimitiveType)
    assert list_type.item_type.name == "float"


def test_nested_class_inference():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({
        "user": {
            "id": 1,
            "profile": {
                "bio": "AI Developer"
            }
        }
    })
    assert "Root" in plan.classes
    assert "User" in plan.classes
    assert "Profile" in plan.classes
    assert isinstance(plan.classes["Root"].fields["user"].field_type, ClassRefType)


def test_nullability_and_optionals():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({"optional_field": None, "req_field": "val"})
    root = plan.classes["Root"]
    assert root.fields["optional_field"].is_optional is True
    assert isinstance(root.fields["optional_field"].field_type, OptionalType)


def test_multi_sample_merging():
    inferencer = SchemaInferencer()
    s1 = {"id": 1, "name": "Alice"}
    s2 = {"id": 2, "name": "Bob", "department": "Engineering"}
    plan = inferencer.infer(s1, additional_samples=[s2])
    root = plan.classes["Root"]
    assert root.fields["id"].is_optional is False
    assert root.fields["name"].is_optional is False
    assert root.fields["department"].is_optional is True


def test_mixed_array_types():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({"mixed": [10, "string_val"]})
    field_t = plan.classes["Root"].fields["mixed"].field_type
    assert isinstance(field_t, ListType)
    assert isinstance(field_t.item_type, UnionType)
