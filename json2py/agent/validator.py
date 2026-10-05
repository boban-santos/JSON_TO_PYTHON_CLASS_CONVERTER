"""Validator tool: compiles generated code and instantiates classes with input JSON payloads."""

from __future__ import annotations

import copy
from typing import Any, Optional

from json2py.models import OutputFormat, ValidationResult


class CodeValidator:
    """Executes generated code in a sandboxed namespace and instantiates root models."""

    @staticmethod
    def validate(
        code: str,
        test_payload: Any,
        root_class_name: str,
        output_format: OutputFormat = OutputFormat.PYDANTIC,
    ) -> ValidationResult:
        """
        Validate generated code by:
        1. Compiling with compile(..., 'exec')
        2. Executing in an isolated namespace
        3. Instantiating the root class using the test payload
        4. Validating round-trip or field access
        """
        # Step 1: Compilation check
        try:
            compiled_code = compile(code, "<generated_model>", "exec")
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                status="error",
                errors=[f"SyntaxError in generated code at line {e.lineno}: {e.msg}"],
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                status="error",
                errors=[f"Compilation error: {type(e).__name__}: {str(e)}"],
            )

        # Step 2: Namespace execution
        namespace: dict[str, Any] = {}
        try:
            exec(compiled_code, namespace)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                status="error",
                errors=[f"Runtime error during class definition: {type(e).__name__}: {str(e)}"],
            )

        # Step 3: Rebuild Pydantic models with namespace context if needed
        for val in list(namespace.values()):
            if isinstance(val, type) and hasattr(val, "model_rebuild"):
                try:
                    val.model_rebuild(_types_namespace=namespace)
                except Exception:
                    pass

        # Step 4: Locate Root class
        if root_class_name not in namespace:
            # Check if Root is an array alias or helper
            if f"{root_class_name}List" in namespace:
                return ValidationResult(
                    is_valid=True,
                    status="validated",
                    roundtrip_success=True,
                )
            return ValidationResult(
                is_valid=False,
                status="error",
                errors=[f"Root class '{root_class_name}' not found in generated namespace."],
            )

        root_cls = namespace[root_class_name]

        # Step 4: Instantiation against payload
        try:
            instance = None
            payload_copy = copy.deepcopy(test_payload)

            if output_format == OutputFormat.PYDANTIC:
                # Pydantic v2 model_validate
                if hasattr(root_cls, "model_validate"):
                    instance = root_cls.model_validate(payload_copy)
                else:
                    instance = root_cls(payload_copy)
            else:
                # Dataclass from_dict or constructor
                if hasattr(root_cls, "from_dict") and isinstance(payload_copy, dict):
                    instance = root_cls.from_dict(payload_copy)
                elif isinstance(payload_copy, dict):
                    instance = root_cls(**payload_copy)
                else:
                    instance = root_cls(payload_copy)

            return ValidationResult(
                is_valid=True,
                status="validated",
                instantiated_object=instance,
                roundtrip_success=True,
            )

        except Exception as e:
            error_details = []
            # Check for Pydantic ValidationError
            if hasattr(e, "errors") and callable(e.errors):
                for err in e.errors():
                    loc = " -> ".join(str(x) for x in err.get("loc", []))
                    msg = err.get("msg", "")
                    etype = err.get("type", "")
                    error_details.append(f"Field '{loc}': {msg} (type: {etype})")
            else:
                error_details.append(f"{type(e).__name__}: {str(e)}")

            return ValidationResult(
                is_valid=False,
                status="unvalidated",
                errors=error_details,
            )
