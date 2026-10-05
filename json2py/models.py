"""Data models and type definitions for json2py."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class OutputFormat(str, Enum):
    DATACLASS = "dataclass"
    PYDANTIC = "pydantic"


class BaseType:
    """Base class for inferred types."""

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        raise NotImplementedError

    def get_dependencies(self) -> set[str]:
        """Return names of any custom classes this type references."""
        return set()

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        """Return required imports for this type."""
        return set()


@dataclass(frozen=True)
class PrimitiveType(BaseType):
    name: str  # 'int', 'float', 'bool', 'str', 'Any'

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        return self.name

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        if self.name == "Any":
            return {"from typing import Any"}
        return set()


@dataclass(frozen=True)
class FormattedStringType(BaseType):
    format_name: str  # 'datetime', 'date', 'UUID', 'EmailStr', 'HttpUrl'

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        if format_type == OutputFormat.PYDANTIC:
            return self.format_name
        # Dataclass format mapping
        if self.format_name in ("datetime", "date", "UUID"):
            return self.format_name
        return "str"

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        if format_type == OutputFormat.PYDANTIC:
            if self.format_name == "datetime":
                return {"from datetime import datetime"}
            elif self.format_name == "date":
                return {"from datetime import date"}
            elif self.format_name == "UUID":
                return {"from uuid import UUID"}
            elif self.format_name == "EmailStr":
                return {"from pydantic import EmailStr"}
            elif self.format_name == "HttpUrl":
                return {"from pydantic import HttpUrl"}
        else:
            if self.format_name == "datetime":
                return {"from datetime import datetime"}
            elif self.format_name == "date":
                return {"from datetime import date"}
            elif self.format_name == "UUID":
                return {"from uuid import UUID"}
        return set()


@dataclass(frozen=True)
class ClassRefType(BaseType):
    class_name: str

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        return self.class_name

    def get_dependencies(self) -> set[str]:
        return {self.class_name}


@dataclass(frozen=True)
class ListType(BaseType):
    item_type: BaseType

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        return f"list[{self.item_type.to_type_hint(format_type)}]"

    def get_dependencies(self) -> set[str]:
        return self.item_type.get_dependencies()

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        return self.item_type.get_imports(format_type)


@dataclass(frozen=True)
class DictType(BaseType):
    key_type: BaseType = field(default_factory=lambda: PrimitiveType("str"))
    value_type: BaseType = field(default_factory=lambda: PrimitiveType("Any"))

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        return f"dict[{self.key_type.to_type_hint(format_type)}, {self.value_type.to_type_hint(format_type)}]"

    def get_dependencies(self) -> set[str]:
        return self.key_type.get_dependencies() | self.value_type.get_dependencies()

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        return self.key_type.get_imports(format_type) | self.value_type.get_imports(format_type)


@dataclass(frozen=True)
class UnionType(BaseType):
    types: tuple[BaseType, ...]

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        # Deduplicate type representations
        hints: list[str] = []
        for t in self.types:
            h = t.to_type_hint(format_type)
            if h not in hints:
                hints.append(h)
        if len(hints) == 1:
            return hints[0]
        return " | ".join(hints)

    def get_dependencies(self) -> set[str]:
        deps: set[str] = set()
        for t in self.types:
            deps.update(t.get_dependencies())
        return deps

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        imports: set[str] = set()
        for t in self.types:
            imports.update(t.get_imports(format_type))
        return imports


@dataclass(frozen=True)
class OptionalType(BaseType):
    inner_type: BaseType

    def to_type_hint(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> str:
        inner = self.inner_type.to_type_hint(format_type)
        if inner == "Any":
            return "Any | None"
        if " | None" in inner:
            return inner
        return f"{inner} | None"

    def get_dependencies(self) -> set[str]:
        return self.inner_type.get_dependencies()

    def get_imports(self, format_type: OutputFormat = OutputFormat.PYDANTIC) -> set[str]:
        return self.inner_type.get_imports(format_type)


@dataclass
class FieldSchema:
    original_name: str
    clean_name: str
    field_type: BaseType
    is_optional: bool = False
    default_value: Any = None
    alias: Optional[str] = None
    description: Optional[str] = None

    @property
    def needs_alias(self) -> bool:
        return self.alias is not None and self.alias != self.clean_name


@dataclass
class ClassSchema:
    name: str
    fields: dict[str, FieldSchema] = field(default_factory=dict)
    parent_key: Optional[str] = None
    is_empty: bool = False
    is_recursive: bool = False
    docstring: Optional[str] = None

    def get_dependencies(self) -> set[str]:
        deps: set[str] = set()
        for f in self.fields.values():
            deps.update(f.field_type.get_dependencies())
        # Exclude self reference to avoid self dependency
        deps.discard(self.name)
        return deps


@dataclass
class SchemaPlan:
    root_class_name: str
    classes: dict[str, ClassSchema] = field(default_factory=dict)
    top_level_is_array: bool = False
    array_item_type: Optional[BaseType] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionLogEntry:
    category: str  # 'naming', 'type_inference', 'format_detection', 'nullability', 'union', 'repair', 'ambiguity'
    message: str
    details: Optional[dict[str, Any]] = None


@dataclass
class ValidationResult:
    is_valid: bool
    status: str  # 'validated', 'unvalidated', 'error'
    errors: list[str] = field(default_factory=list)
    warning: Optional[str] = None
    instantiated_object: Optional[Any] = None
    roundtrip_success: bool = False


@dataclass
class ClarifyingQuestion:
    id: str
    field_path: str
    question: str
    options: list[str]
    chosen_option: Optional[str] = None
    context: Optional[dict[str, Any]] = None
