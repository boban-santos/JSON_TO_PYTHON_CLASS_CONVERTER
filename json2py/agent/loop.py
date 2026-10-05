"""Agent loop: plan-act-observe-repair workflow with validation and decision logging."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from json2py.agent.repair import SchemaRepairer
from json2py.agent.tools import AgentTools
from json2py.core.parser import JSONParseError, LimitExceededError
from json2py.models import (
    ClarifyingQuestion,
    DecisionLogEntry,
    OutputFormat,
    SchemaPlan,
    ValidationResult,
)


@dataclass
class ConversionResult:
    """Result returned by the AgentConverter."""
    code: str
    status: str  # 'validated', 'unvalidated', 'clarification_needed', 'syntax_error', 'limit_exceeded'
    decision_log: list[DecisionLogEntry]
    repair_attempts: int
    validation_result: Optional[ValidationResult] = None
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    schema_plan: Optional[SchemaPlan] = None


class AgentConverter:
    """
    Agentic JSON-to-Python Class Converter.
    Coordinates parsing, inference, naming, code generation, validation, and self-repair.
    """

    def __init__(self, max_repair_attempts: int = 3):
        self.max_repair_attempts = max_repair_attempts

    def convert(
        self,
        raw_json: str,
        output_format: OutputFormat = OutputFormat.PYDANTIC,
        root_name: str = "Root",
        detect_formats: bool = True,
        additional_samples: Optional[list[str]] = None,
        generator_options: Optional[dict[str, Any]] = None,
        clarification_callback: Optional[Callable[[str, list[str]], str]] = None,
    ) -> ConversionResult:
        """
        Execute the agentic conversion loop:
        1. Validate & Parse input JSON
        2. Infer schema & ambiguities
        3. Clarify if needed
        4. Generate code
        5. Validate (compile & instantiate)
        6. Self-repair loop (up to max_repair_attempts)
        7. Return code, decision log, and status
        """
        gen_opts = generator_options or {}
        decision_log: list[DecisionLogEntry] = []
        warnings: list[str] = []

        # Step 1: Parse primary JSON
        try:
            parse_res = AgentTools.parse_json(raw_json)
            primary_data = parse_res.data
            warnings.extend(parse_res.warnings)
            decision_log.append(
                DecisionLogEntry(
                    category="type_inference",
                    message="Successfully parsed primary JSON input.",
                )
            )
        except JSONParseError as e:
            return ConversionResult(
                code="",
                status="syntax_error",
                decision_log=[
                    DecisionLogEntry(
                        category="repair",
                        message=f"JSON syntax error detected at line {e.line}, column {e.column}.",
                    )
                ],
                repair_attempts=0,
                error_message=str(e),
            )
        except LimitExceededError as e:
            return ConversionResult(
                code="",
                status="limit_exceeded",
                decision_log=[
                    DecisionLogEntry(
                        category="repair",
                        message=f"Payload safety limit exceeded: {str(e)}",
                    )
                ],
                repair_attempts=0,
                error_message=str(e),
            )

        # Parse any additional samples (FR-13)
        extra_data_list: list[Any] = []
        if additional_samples:
            for idx, sample_text in enumerate(additional_samples, start=2):
                if not sample_text.strip():
                    continue
                try:
                    s_res = AgentTools.parse_json(sample_text)
                    extra_data_list.append(s_res.data)
                    warnings.extend(s_res.warnings)
                    decision_log.append(
                        DecisionLogEntry(
                            category="type_inference",
                            message=f"Successfully parsed additional sample #{idx}.",
                        )
                    )
                except Exception as e:
                    warnings.append(f"Sample #{idx} failed to parse: {str(e)}")

        # Step 2: Infer schema & detect ambiguities
        schema_plan, infer_decisions, raw_ambiguities = AgentTools.infer_schema(
            data=primary_data,
            additional_samples=extra_data_list if extra_data_list else None,
            root_name=root_name,
            detect_formats=detect_formats,
        )
        decision_log.extend(infer_decisions)

        # Step 3: Handle Ambiguities / Clarifying Questions (FR-16)
        clarifying_questions: list[ClarifyingQuestion] = []
        for amb in raw_ambiguities:
            if amb.get("type") == "empty_array":
                q = AgentTools.ask_user(
                    question=f"Array at '{amb['field']}' is empty. How would you like to model its item type?",
                    options=["list[Any] (default)", "list[str]", "list[int]", "list[dict[str, Any]]"],
                    field_path=amb["field"],
                    user_callback=clarification_callback,
                )
                clarifying_questions.append(q)
            elif amb.get("type") == "type_conflict":
                q = AgentTools.ask_user(
                    question=f"Field '{amb['field']}' has conflicting types across samples ({', '.join(amb['observed_types'])}). How should it be typed?",
                    options=[f"Union [{ ' | '.join(amb['observed_types']) }]", "Any", amb['observed_types'][0]],
                    field_path=amb["field"],
                    user_callback=clarification_callback,
                )
                clarifying_questions.append(q)

        # Step 4: Generate Code
        current_plan = copy.deepcopy(schema_plan)
        generated_code = AgentTools.generate_code(
            plan=current_plan,
            output_format=output_format,
            **gen_opts,
        )

        # Step 5: Validate code (FR-8)
        validation_res = AgentTools.validate_code(
            code=generated_code,
            test_payload=primary_data,
            root_class_name=schema_plan.root_class_name,
            output_format=output_format,
        )

        # Step 6: Self-repair loop (FR-9: up to 3 repair attempts)
        repair_attempts = 0
        best_code = generated_code
        last_val_res = validation_res

        while not last_val_res.is_valid and repair_attempts < self.max_repair_attempts:
            repair_attempts += 1
            decision_log.append(
                DecisionLogEntry(
                    category="repair",
                    message=f"Validation failed (Attempt {repair_attempts}/{self.max_repair_attempts}). Initiating self-repair...",
                    details={"errors": last_val_res.errors},
                )
            )

            # Analyze errors and repair schema plan
            repaired_plan, repair_decisions = SchemaRepairer.attempt_repair(
                plan=current_plan,
                errors=last_val_res.errors,
                attempt_number=repair_attempts,
            )
            decision_log.extend(repair_decisions)
            current_plan = repaired_plan

            # Re-generate code
            new_code = AgentTools.generate_code(
                plan=current_plan,
                output_format=output_format,
                **gen_opts,
            )
            best_code = new_code

            # Re-validate
            new_val_res = AgentTools.validate_code(
                code=new_code,
                test_payload=primary_data,
                root_class_name=current_plan.root_class_name,
                output_format=output_format,
            )
            last_val_res = new_val_res

        # Step 7: Final Status
        if last_val_res.is_valid:
            status = "validated"
            if repair_attempts > 0:
                decision_log.append(
                    DecisionLogEntry(
                        category="repair",
                        message=f"Self-repair successful! Code validated after {repair_attempts} attempt(s).",
                    )
                )
            else:
                decision_log.append(
                    DecisionLogEntry(
                        category="repair",
                        message="Code passed compilation and payload instantiation on the first attempt.",
                    )
                )
        else:
            status = "unvalidated"
            warning_msg = (
                f"Generated code could not be fully validated after {repair_attempts} repair attempts. "
                f"Last error: {'; '.join(last_val_res.errors)}"
            )
            warnings.append(warning_msg)
            decision_log.append(
                DecisionLogEntry(
                    category="repair",
                    message=f"Self-repair limit reached. Returning best attempt. {warning_msg}",
                )
            )

        return ConversionResult(
            code=best_code,
            status=status,
            decision_log=decision_log,
            repair_attempts=repair_attempts,
            validation_result=last_val_res,
            clarifying_questions=clarifying_questions,
            warnings=warnings,
            schema_plan=current_plan,
        )
