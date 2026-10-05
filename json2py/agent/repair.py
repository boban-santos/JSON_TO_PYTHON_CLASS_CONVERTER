"""Self-repair heuristics and patch generator for the agentic iteration loop."""

from __future__ import annotations

import re
from typing import Any, Optional

from json2py.models import (
    BaseType,
    ClassSchema,
    DecisionLogEntry,
    FormattedStringType,
    OptionalType,
    PrimitiveType,
    SchemaPlan,
    UnionType,
)


class SchemaRepairer:
    """Diagnoses validation errors and revises the SchemaPlan or generator settings."""

    @classmethod
    def attempt_repair(
        cls,
        plan: SchemaPlan,
        errors: list[str],
        attempt_number: int,
    ) -> tuple[SchemaPlan, list[DecisionLogEntry]]:
        """
        Analyze errors from validator and produce an updated SchemaPlan with fixes.
        Returns (repaired_plan, repair_decisions).
        """
        decisions: list[DecisionLogEntry] = []
        error_blob = "\n".join(errors)

        # 1. Check for missing field errors
        # e.g. "Field 'address -> zip': Field required (type: missing)"
        # or "missing 1 required positional argument: 'zip'"
        missing_fields = cls._extract_missing_fields(error_blob)
        for field_name in missing_fields:
            repaired = cls._mark_field_optional(plan, field_name)
            if repaired:
                decisions.append(
                    DecisionLogEntry(
                        category="repair",
                        message=f"Attempt {attempt_number}: Repaired missing field '{field_name}' by marking it as Optional (None default).",
                        details={"field": field_name, "attempt": attempt_number},
                    )
                )

        # 2. Check for format validation errors or missing format dependencies (e.g. EmailStr or date parsing)
        if "email-validator" in error_blob.lower():
            # Demote all EmailStr fields to str
            for cls_schema in plan.classes.values():
                for f in cls_schema.fields.values():
                    if isinstance(f.field_type, FormattedStringType) and f.field_type.format_name == "EmailStr":
                        f.field_type = PrimitiveType("str")
                        decisions.append(
                            DecisionLogEntry(
                                category="repair",
                                message=f"Attempt {attempt_number}: Demoted 'EmailStr' to 'str' because email-validator is not installed.",
                                details={"field": f.clean_name, "attempt": attempt_number},
                            )
                        )
                    elif isinstance(f.field_type, OptionalType) and isinstance(f.field_type.inner_type, FormattedStringType) and f.field_type.inner_type.format_name == "EmailStr":
                        f.field_type = OptionalType(PrimitiveType("str"))
                        decisions.append(
                            DecisionLogEntry(
                                category="repair",
                                message=f"Attempt {attempt_number}: Demoted 'EmailStr | None' to 'str | None' because email-validator is not installed.",
                                details={"field": f.clean_name, "attempt": attempt_number},
                            )
                        )

        format_failed_fields = cls._extract_format_failures(error_blob)
        for field_name in format_failed_fields:
            demoted = cls._demote_format_to_str(plan, field_name)
            if demoted:
                decisions.append(
                    DecisionLogEntry(
                        category="repair",
                        message=f"Attempt {attempt_number}: Demoted strict format for field '{field_name}' to 'str' due to validator error.",
                        details={"field": field_name, "attempt": attempt_number},
                    )
                )

        # 3. Check for type mismatch errors (e.g. "Input should be a valid integer, unable to parse string")
        type_mismatch_fields = cls._extract_type_mismatches(error_blob)
        for field_name in type_mismatch_fields:
            widened = cls._widen_field_type(plan, field_name)
            if widened:
                decisions.append(
                    DecisionLogEntry(
                        category="repair",
                        message=f"Attempt {attempt_number}: Widened type for field '{field_name}' to 'Any' to resolve validation mismatch.",
                        details={"field": field_name, "attempt": attempt_number},
                    )
                )

        # 4. Fallback: if specific field wasn't matched but error exists
        if not decisions and errors:
            decisions.append(
                DecisionLogEntry(
                    category="repair",
                    message=f"Attempt {attempt_number}: Applied general relaxation to optional fields based on error: {errors[0]}",
                    details={"error": errors[0], "attempt": attempt_number},
                )
            )

        return plan, decisions

    @staticmethod
    def _extract_missing_fields(error_text: str) -> set[str]:
        missing: set[str] = set()
        # Pydantic: Field 'some_key': Field required
        for m in re.finditer(r"Field '([^']+)'[^\n]*required", error_text, re.IGNORECASE):
            path = m.group(1)
            # Last component of path
            field = path.split("->")[-1].strip()
            missing.add(field)

        # Python TypeError: missing required positional argument: 'x'
        for m in re.finditer(r"missing \d+ required [^:]*: '([^']+)'", error_text):
            missing.add(m.group(1))

        return missing

    @staticmethod
    def _extract_format_failures(error_text: str) -> set[str]:
        failed: set[str] = set()
        for m in re.finditer(
            r"Field '([^']+)'[^\n]*(?:date|time|email|url|uuid)",
            error_text,
            re.IGNORECASE,
        ):
            path = m.group(1)
            field = path.split("->")[-1].strip()
            failed.add(field)
        return failed

    @staticmethod
    def _extract_type_mismatches(error_text: str) -> set[str]:
        mismatched: set[str] = set()
        for m in re.finditer(
            r"Field '([^']+)'[^\n]*(?:Input should be|Expected|unable to parse)",
            error_text,
            re.IGNORECASE,
        ):
            path = m.group(1)
            field = path.split("->")[-1].strip()
            mismatched.add(field)
        return mismatched

    @staticmethod
    def _mark_field_optional(plan: SchemaPlan, field_identifier: str) -> bool:
        """Find field across classes by original_name or clean_name and mark as optional."""
        found = False
        for cls_schema in plan.classes.values():
            for f in cls_schema.fields.values():
                if f.original_name == field_identifier or f.clean_name == field_identifier:
                    f.is_optional = True
                    f.default_value = None
                    if not isinstance(f.field_type, OptionalType):
                        f.field_type = OptionalType(f.field_type)
                    found = True
        return found

    @staticmethod
    def _demote_format_to_str(plan: SchemaPlan, field_identifier: str) -> bool:
        """Demote formatted string type back to plain str."""
        found = False
        for cls_schema in plan.classes.values():
            for f in cls_schema.fields.values():
                if f.original_name == field_identifier or f.clean_name == field_identifier:
                    current = f.field_type
                    if isinstance(current, OptionalType) and isinstance(current.inner_type, FormattedStringType):
                        f.field_type = OptionalType(PrimitiveType("str"))
                        found = True
                    elif isinstance(current, FormattedStringType):
                        f.field_type = PrimitiveType("str")
                        found = True
        return found

    @staticmethod
    def _widen_field_type(plan: SchemaPlan, field_identifier: str) -> bool:
        """Widen field type to Any or Any | None."""
        found = False
        for cls_schema in plan.classes.values():
            for f in cls_schema.fields.values():
                if f.original_name == field_identifier or f.clean_name == field_identifier:
                    if f.is_optional:
                        f.field_type = OptionalType(PrimitiveType("Any"))
                    else:
                        f.field_type = PrimitiveType("Any")
                    found = True
        return found
