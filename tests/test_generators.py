"""Tests for Pydantic v2 and Dataclass code generators."""

from json2py.core.inferencer import SchemaInferencer
from json2py.generators.base import topological_sort_classes
from json2py.generators.dataclass_gen import DataclassGenerator
from json2py.generators.pydantic_gen import PydanticV2Generator
from json2py.models import OutputFormat


def test_topological_sort_order():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({
        "order": {
            "id": 100,
            "address": {
                "city": "Chennai"
            }
        }
    })
    ordered = topological_sort_classes(plan.classes, plan.root_class_name)
    names = [c.name for c in ordered]
    # Address must appear before Order, and Order before Root
    assert names.index("Address") < names.index("Order")
    assert names.index("Order") < names.index("Root")


def test_pydantic_generator():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({
        "first-name": "Alice",
        "class": "Senior",
        "tags": ["a", "b"]
    })
    gen = PydanticV2Generator()
    code = gen.generate(plan)
    assert "class Root(BaseModel):" in code
    assert 'first_name: str = Field(..., alias="first-name")' in code
    assert 'class_: str = Field(..., alias="class")' in code
    assert "tags: list[str]" in code


def test_dataclass_generator_with_from_dict():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({
        "id": 1,
        "detail": {"note": "test"},
        "extra": None
    })
    gen = DataclassGenerator()
    code = gen.generate(plan)
    assert "@dataclass" in code
    assert "class Root:" in code
    assert "class RootDetail:" in code
    assert "def from_dict(cls, data: dict[str, Any]) -> Root:" in code
    # Check field ordering: required fields before optional
    root_cls = plan.classes["Root"]
    lines = code.splitlines()
    id_line = next(i for i, l in enumerate(lines) if "id: int" in l)
    extra_line = next(i for i, l in enumerate(lines) if "extra:" in l)
    assert id_line < extra_line


def test_dataclass_flags():
    inferencer = SchemaInferencer()
    plan = inferencer.infer({"x": 10})
    gen = DataclassGenerator(frozen=True, slots=True, kw_only=True)
    code = gen.generate(plan)
    assert "@dataclass(frozen=True, slots=True, kw_only=True)" in code
