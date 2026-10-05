"""Python Dataclass code generator."""

from __future__ import annotations

from typing import Any

from json2py.generators.base import (
    BaseCodeGenerator,
    consolidate_imports,
    format_python_code,
    topological_sort_classes,
)
from json2py.models import (
    ClassRefType,
    ClassSchema,
    FieldSchema,
    ListType,
    OptionalType,
    OutputFormat,
    SchemaPlan,
)


class DataclassGenerator(BaseCodeGenerator):
    """Generates standard-library Python dataclasses with from_dict helper."""

    def __init__(
        self,
        frozen: bool = False,
        slots: bool = False,
        kw_only: bool = False,
    ):
        super().__init__(format_type=OutputFormat.DATACLASS)
        self.frozen = frozen
        self.slots = slots
        self.kw_only = kw_only

    def generate(self, plan: SchemaPlan, **kwargs: Any) -> str:
        """Render Python code for Dataclasses."""
        frozen = kwargs.get("frozen", self.frozen)
        slots = kwargs.get("slots", self.slots)
        kw_only = kwargs.get("kw_only", self.kw_only)

        ordered_classes = topological_sort_classes(plan.classes, plan.root_class_name)

        # Collect imports
        imports: set[str] = {
            "from __future__ import annotations",
            "from dataclasses import dataclass, field",
            "from typing import Any, Optional",
        }

        for cls_schema in ordered_classes:
            for f in cls_schema.fields.values():
                imports.update(f.field_type.get_imports(self.format_type))

        if plan.top_level_is_array and plan.array_item_type:
            imports.update(plan.array_item_type.get_imports(self.format_type))

        import_block = consolidate_imports(imports)
        if import_block and not import_block.endswith("\n\n"):
            import_block += "\n"

        # Generate decorator string
        flags = []
        if frozen:
            flags.append("frozen=True")
        if slots:
            flags.append("slots=True")
        if kw_only:
            flags.append("kw_only=True")

        decorator_str = f"@dataclass({', '.join(flags)})" if flags else "@dataclass"

        class_blocks: list[str] = []
        for cls_schema in ordered_classes:
            class_blocks.append(
                self._render_class(cls_schema, decorator_str, kw_only=kw_only)
            )

        # Handle top-level array
        if plan.top_level_is_array:
            item_hint = (
                plan.array_item_type.to_type_hint(self.format_type)
                if plan.array_item_type
                else "Any"
            )
            top_level_block = (
                f"{plan.root_class_name}List = list[{item_hint}]\n\n"
                f"def parse_{plan.root_class_name.lower()}_list(data: list[Any]) -> list[{item_hint}]:\n"
                f'    """Parse a list of raw items into {item_hint} objects."""\n'
            )
            if isinstance(plan.array_item_type, ClassRefType):
                top_level_block += (
                    f"    return [{plan.array_item_type.class_name}.from_dict(item) "
                    f"if isinstance(item, dict) else item for item in data]\n"
                )
            else:
                top_level_block += "    return data\n"
            class_blocks.append(top_level_block)

        raw_code = import_block + "\n\n".join(class_blocks) + "\n"
        return format_python_code(raw_code)

    def _render_class(
        self,
        cls_schema: ClassSchema,
        decorator_str: str,
        kw_only: bool = False,
    ) -> str:
        lines: list[str] = [decorator_str, f"class {cls_schema.name}:"]

        if cls_schema.docstring:
            lines.append(f'    """{cls_schema.docstring}"""')

        if cls_schema.is_empty or not cls_schema.fields:
            lines.append("    pass\n")
            lines.append(self._render_from_dict(cls_schema))
            return "\n".join(lines)

        # Field ordering: non-default fields MUST precede default fields unless kw_only=True
        fields_list = list(cls_schema.fields.values())
        if not kw_only:
            required_fields = [f for f in fields_list if not f.is_optional]
            optional_fields = [f for f in fields_list if f.is_optional]
            ordered_fields = required_fields + optional_fields
        else:
            ordered_fields = fields_list

        for f in ordered_fields:
            type_hint = f.field_type.to_type_hint(self.format_type)
            if f.is_optional:
                lines.append(f"    {f.clean_name}: {type_hint} = None")
            else:
                lines.append(f"    {f.clean_name}: {type_hint}")

        lines.append("")
        lines.append(self._render_from_dict(cls_schema))
        return "\n".join(lines)

    def _render_from_dict(self, cls_schema: ClassSchema) -> str:
        """Render robust from_dict helper method."""
        lines = [
            "    @classmethod",
            f"    def from_dict(cls, data: dict[str, Any]) -> {cls_schema.name}:",
            '        """Instantiate class from dictionary data with alias and nested object mapping."""',
            "        if not isinstance(data, dict):",
            "            raise TypeError(f'Expected dict, got {type(data).__name__}')",
            "        kwargs: dict[str, Any] = {}",
        ]

        if cls_schema.is_empty or not cls_schema.fields:
            lines.append("        return cls(**kwargs)")
            return "\n".join(lines)

        for f in cls_schema.fields.values():
            key_access = f'"{f.alias}"' if f.alias else f'"{f.clean_name}"'
            clean = f.clean_name
            actual_type = f.field_type
            if isinstance(actual_type, OptionalType):
                actual_type = actual_type.inner_type

            # Check if nested class or list of nested class
            if isinstance(actual_type, ClassRefType):
                ref_cls = actual_type.class_name
                field_lines = [
                    f"        val = data.get({key_access}, data.get('{clean}'))",
                    "        if val is not None:",
                    f"            kwargs['{clean}'] = {ref_cls}.from_dict(val) if isinstance(val, dict) else val",
                ]
                if f.is_optional:
                    field_lines.append(f"        else:\n            kwargs['{clean}'] = None")
                lines.extend(field_lines)
            elif isinstance(actual_type, ListType) and isinstance(actual_type.item_type, ClassRefType):
                ref_cls = actual_type.item_type.class_name
                field_lines = [
                    f"        val = data.get({key_access}, data.get('{clean}'))",
                    "        if val is not None and isinstance(val, list):",
                    f"            kwargs['{clean}'] = [{ref_cls}.from_dict(i) if isinstance(i, dict) else i for i in val]",
                    "        elif val is not None:",
                    f"            kwargs['{clean}'] = val",
                ]
                if f.is_optional:
                    field_lines.append(f"        else:\n            kwargs['{clean}'] = None")
                lines.extend(field_lines)
            else:
                field_lines = [
                    f"        if {key_access} in data:",
                    f"            kwargs['{clean}'] = data[{key_access}]",
                    f"        elif '{clean}' in data:",
                    f"            kwargs['{clean}'] = data['{clean}']",
                ]
                if f.is_optional:
                    field_lines.append(f"        else:\n            kwargs['{clean}'] = None")
                lines.extend(field_lines)

        lines.append("        return cls(**kwargs)")
        return "\n".join(lines)
