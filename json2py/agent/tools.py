"""Agent tool implementations (parse_json, infer_schema, suggest_names, generate_code, validate_code, ask_user)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from json2py.agent.validator import CodeValidator
from json2py.core.inferencer import SchemaInferencer
from json2py.core.namer import sanitize_field_name, suggest_class_name, to_pascal_case
from json2py.core.parser import ParseResult, parse_json
from json2py.generators.dataclass_gen import DataclassGenerator
from json2py.generators.pydantic_gen import PydanticV2Generator
from json2py.models import (
    ClarifyingQuestion,
    DecisionLogEntry,
    OutputFormat,
    SchemaPlan,
    ValidationResult,
)


class AgentTools:
    """Provides the tool set for the agent loop."""

    @staticmethod
    def parse_json(raw_text: str, max_size_bytes: int = 1_048_576, max_depth: int = 20) -> ParseResult:
        """Deterministic tool: parse raw JSON text and detect syntax errors or duplicate keys."""
        return parse_json(raw_text, max_size_bytes=max_size_bytes, max_depth=max_depth)

    @staticmethod
    def infer_schema(
        data: Any,
        additional_samples: Optional[list[Any]] = None,
        root_name: str = "Root",
        detect_formats: bool = True,
    ) -> tuple[SchemaPlan, list[DecisionLogEntry], list[dict[str, Any]]]:
        """Deterministic tool: infer schema tree with types, nullability, and formats."""
        inferencer = SchemaInferencer(root_name=root_name, detect_formats=detect_formats)
        plan = inferencer.infer(data, additional_samples=additional_samples)
        return plan, inferencer.decision_log, inferencer.ambiguities

    @staticmethod
    def suggest_names(
        raw_key: str,
        parent_class: Optional[str] = None,
        is_list_item: bool = False,
    ) -> dict[str, str]:
        """Naming tool: sanitizes field names and suggests class names."""
        clean_name, alias = sanitize_field_name(raw_key)
        cls_name = suggest_class_name(raw_key, is_list_item=is_list_item, parent_class=parent_class)
        return {
            "clean_name": clean_name,
            "alias": alias or "",
            "suggested_class_name": cls_name,
        }

    @staticmethod
    def generate_code(
        plan: SchemaPlan,
        output_format: OutputFormat = OutputFormat.PYDANTIC,
        **generator_options: Any,
    ) -> str:
        """Template-based tool: render Python source code for the specified format."""
        if output_format == OutputFormat.PYDANTIC:
            generator = PydanticV2Generator()
        else:
            generator = DataclassGenerator(
                frozen=generator_options.get("frozen", False),
                slots=generator_options.get("slots", False),
                kw_only=generator_options.get("kw_only", False),
            )
        return generator.generate(plan, **generator_options)

    @staticmethod
    def validate_code(
        code: str,
        test_payload: Any,
        root_class_name: str,
        output_format: OutputFormat = OutputFormat.PYDANTIC,
    ) -> ValidationResult:
        """Sandboxed execution tool: compiles code and tests root class instantiation."""
        return CodeValidator.validate(
            code=code,
            test_payload=test_payload,
            root_class_name=root_class_name,
            output_format=output_format,
        )

    @staticmethod
    def ask_user(
        question: str,
        options: list[str],
        field_path: str = "",
        user_callback: Optional[Callable[[str, list[str]], str]] = None,
    ) -> ClarifyingQuestion:
        """Interactive tool: records or poses a clarifying question."""
        q = ClarifyingQuestion(
            id=f"q_{field_path or 'general'}",
            field_path=field_path,
            question=question,
            options=options,
        )
        if user_callback:
            q.chosen_option = user_callback(question, options)
        return q
