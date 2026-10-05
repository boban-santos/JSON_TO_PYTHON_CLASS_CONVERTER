"""Pydantic v2 code generator."""

from __future__ import annotations

from typing import Any

from json2py.generators.base import (
    BaseCodeGenerator,
    consolidate_imports,
    format_python_code,
    topological_sort_classes,
)
from json2py.models import ClassSchema, FieldSchema, OutputFormat, SchemaPlan


class PydanticV2Generator(BaseCodeGenerator):
    """Generates idiomatic Pydantic v2 models."""

    def __init__(self):
        super().__init__(format_type=OutputFormat.PYDANTIC)

    def generate(self, plan: SchemaPlan, **kwargs: Any) -> str:
        """Render Python code for Pydantic v2."""
        ordered_classes = topological_sort_classes(plan.classes, plan.root_class_name)

        # Collect all imports needed
        imports: set[str] = {
            "from __future__ import annotations",
            "from typing import Any, Optional",
            "from pydantic import BaseModel, ConfigDict, Field",
        }

        if plan.top_level_is_array:
            imports.add("from pydantic import RootModel")

        for cls_schema in ordered_classes:
            for f in cls_schema.fields.values():
                imports.update(f.field_type.get_imports(self.format_type))

        if plan.top_level_is_array and plan.array_item_type:
            imports.update(plan.array_item_type.get_imports(self.format_type))

        import_block = consolidate_imports(imports)
        if import_block and not import_block.endswith("\n\n"):
            import_block += "\n"

        # Generate classes
        class_blocks: list[str] = []
        for cls_schema in ordered_classes:
            class_blocks.append(self._render_class(cls_schema))

        # Handle top-level array
        if plan.top_level_is_array:
            item_hint = (
                plan.array_item_type.to_type_hint(self.format_type)
                if plan.array_item_type
                else "Any"
            )
            top_level_block = (
                f"class {plan.root_class_name}(RootModel[list[{item_hint}]]):\n"
                f'    """Root collection of {item_hint} items."""\n'
                f"    pass\n\n"
                f"{plan.root_class_name}List = list[{item_hint}]\n"
            )
            class_blocks.append(top_level_block)

        raw_code = import_block + "\n\n".join(class_blocks) + "\n"
        return format_python_code(raw_code)

    def _render_class(self, cls_schema: ClassSchema) -> str:
        lines: list[str] = [f"class {cls_schema.name}(BaseModel):"]

        if cls_schema.docstring:
            lines.append(f'    """{cls_schema.docstring}"""')

        lines.append("    model_config = ConfigDict(populate_by_name=True)")

        if cls_schema.is_empty or not cls_schema.fields:
            lines.append("    pass")
            return "\n".join(lines)

        lines.append("")

        for field_schema in cls_schema.fields.values():
            type_hint = field_schema.field_type.to_type_hint(self.format_type)
            clean_name = field_schema.clean_name
            alias = field_schema.alias

            # Construct Field definition
            if field_schema.is_optional:
                if alias:
                    lines.append(
                        f'    {clean_name}: {type_hint} = Field(default=None, alias="{alias}")'
                    )
                else:
                    lines.append(f"    {clean_name}: {type_hint} = None")
            else:
                if alias:
                    lines.append(
                        f'    {clean_name}: {type_hint} = Field(..., alias="{alias}")'
                    )
                else:
                    lines.append(f"    {clean_name}: {type_hint}")

        return "\n".join(lines)
