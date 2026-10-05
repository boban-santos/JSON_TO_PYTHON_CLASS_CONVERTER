"""Type inferencer: walks JSON data / samples to infer Python types, nested classes, and schema plan."""

from __future__ import annotations

from typing import Any, Optional

from json2py.core.format_detector import detect_string_format
from json2py.core.namer import (
    sanitize_field_name,
    singularize,
    suggest_class_name,
    to_pascal_case,
)
from json2py.models import (
    BaseType,
    ClassRefType,
    ClassSchema,
    DecisionLogEntry,
    DictType,
    FieldSchema,
    FormattedStringType,
    ListType,
    OptionalType,
    PrimitiveType,
    SchemaPlan,
    UnionType,
)


class SchemaInferencer:
    """Infers a SchemaPlan and logs decisions from JSON input data or multiple samples."""

    def __init__(
        self,
        root_name: str = "Root",
        detect_formats: bool = True,
    ):
        self.root_name = to_pascal_case(root_name) if root_name else "Root"
        self.detect_formats = detect_formats
        self.classes: dict[str, ClassSchema] = {}
        self.decision_log: list[DecisionLogEntry] = []
        self.ambiguities: list[dict[str, Any]] = []
        # Ancestor stack to detect recursion: list of (class_name, set of field_names)
        self.ancestor_stack: list[tuple[str, set[str]]] = []

    def infer(self, data: Any, additional_samples: Optional[list[Any]] = None) -> SchemaPlan:
        """
        Infer a full SchemaPlan from primary data and optional extra sample payloads.
        Supports single dict, top-level array, or multi-sample list of dicts.
        """
        all_samples = [data]
        if additional_samples:
            all_samples.extend(additional_samples)

        # Handle top-level JSON array (FR-18)
        if isinstance(data, list):
            self.decision_log.append(
                DecisionLogEntry(
                    category="type_inference",
                    message="Top-level JSON payload is an array. Modeling the item type.",
                )
            )
            item_class_name = to_pascal_case(singularize(self.root_name))
            if item_class_name == self.root_name:
                item_class_name = f"{self.root_name}Item"

            item_type = self._infer_list_item_type(
                items=data,
                field_path="root_item",
                parent_key=item_class_name,
                parent_class=None,
            )
            return SchemaPlan(
                root_class_name=self.root_name,
                classes=self.classes,
                top_level_is_array=True,
                array_item_type=item_type,
            )

        if not isinstance(data, dict):
            # Primitive top-level: wrap in simple plan
            ptype = self._infer_value_type(data, "root", "root", None)
            return SchemaPlan(
                root_class_name=self.root_name,
                classes=self.classes,
                top_level_is_array=False,
                metadata={"primitive_root": ptype.to_type_hint()},
            )

        # Merge samples if multiple are provided (FR-13)
        dict_samples = [s for s in all_samples if isinstance(s, dict)]
        self._infer_class(
            samples=dict_samples,
            class_name=self.root_name,
            parent_key=None,
            parent_class=None,
            field_path="",
        )

        return SchemaPlan(
            root_class_name=self.root_name,
            classes=self.classes,
            top_level_is_array=False,
        )

    def _infer_class(
        self,
        samples: list[dict[str, Any]],
        class_name: str,
        parent_key: Optional[str],
        parent_class: Optional[str],
        field_path: str,
    ) -> ClassRefType:
        """Infer ClassSchema from a list of dict instances corresponding to the same entity."""
        # Check for empty object edge case
        all_empty = all(len(s) == 0 for s in samples)
        if all_empty:
            if class_name not in self.classes:
                self.classes[class_name] = ClassSchema(
                    name=class_name,
                    fields={},
                    parent_key=parent_key,
                    is_empty=True,
                )
                self.decision_log.append(
                    DecisionLogEntry(
                        category="type_inference",
                        message=f"Empty object for class '{class_name}'. Generating empty class with pass.",
                    )
                )
            return ClassRefType(class_name)

        # Collect all unique keys and value lists across all samples
        sample_count = len(samples)
        key_presence: dict[str, int] = {}
        key_values: dict[str, list[Any]] = {}

        for s in samples:
            for k, v in s.items():
                key_presence[k] = key_presence.get(k, 0) + 1
                if k not in key_values:
                    key_values[k] = []
                key_values[k].append(v)

        # Check recursion: does this shape closely match an active ancestor class?
        current_keys = set(key_presence.keys())
        for ancestor_name, ancestor_keys in reversed(self.ancestor_stack):
            # If at least 75% key overlap with an ancestor
            overlap = len(current_keys & ancestor_keys)
            union = len(current_keys | ancestor_keys)
            if union > 0 and (overlap / union) >= 0.75:
                self.decision_log.append(
                    DecisionLogEntry(
                        category="type_inference",
                        message=f"Detected recursive structure at '{field_path}'. Reusing ancestor class '{ancestor_name}'.",
                    )
                )
                return ClassRefType(ancestor_name)

        # Disambiguate class name if a class with the same name already exists with a different shape
        resolved_class_name = self._resolve_class_name(class_name, current_keys, parent_class)

        # Push to ancestor stack
        self.ancestor_stack.append((resolved_class_name, current_keys))

        fields: dict[str, FieldSchema] = {}
        for raw_key, values in key_values.items():
            child_path = f"{field_path}.{raw_key}" if field_path else raw_key
            clean_name, alias = sanitize_field_name(raw_key)

            if alias:
                self.decision_log.append(
                    DecisionLogEntry(
                        category="naming",
                        message=f"Sanitized field '{raw_key}' to '{clean_name}' (alias='{alias}').",
                        details={"original": raw_key, "clean": clean_name},
                    )
                )

            # Determine if missing in some samples or explicitly None
            is_missing_in_some_samples = key_presence[raw_key] < sample_count
            has_none_value = any(v is None for v in values)
            is_optional = is_missing_in_some_samples or has_none_value

            if is_missing_in_some_samples:
                self.decision_log.append(
                    DecisionLogEntry(
                        category="nullability",
                        message=f"Field '{raw_key}' missing in {sample_count - key_presence[raw_key]} of {sample_count} sample(s). Marked as Optional.",
                        details={"field": child_path},
                    )
                )
            elif has_none_value:
                self.decision_log.append(
                    DecisionLogEntry(
                        category="nullability",
                        message=f"Field '{raw_key}' contains null values. Marked as Optional (T | None).",
                        details={"field": child_path},
                    )
                )

            # Infer field type from all non-None values
            non_null_values = [v for v in values if v is not None]
            field_type = self._infer_field_type_from_values(
                values=non_null_values,
                field_path=child_path,
                parent_key=raw_key,
                parent_class=resolved_class_name,
            )

            # If optional, wrap in OptionalType
            final_type: BaseType
            if is_optional:
                final_type = OptionalType(field_type)
            else:
                final_type = field_type

            fields[clean_name] = FieldSchema(
                original_name=raw_key,
                clean_name=clean_name,
                field_type=final_type,
                is_optional=is_optional,
                default_value=None if is_optional else ...,
                alias=alias,
            )

        self.ancestor_stack.pop()

        self.classes[resolved_class_name] = ClassSchema(
            name=resolved_class_name,
            fields=fields,
            parent_key=parent_key,
            is_empty=False,
        )

        return ClassRefType(resolved_class_name)

    def _resolve_class_name(
        self, candidate: str, current_keys: set[str], parent_class: Optional[str]
    ) -> str:
        """Disambiguate class name if candidate already exists with different fields."""
        if candidate not in self.classes:
            return candidate

        existing = self.classes[candidate]
        existing_keys = {f.original_name for f in existing.fields.values()}

        # If identical keys, reuse
        if existing_keys == current_keys:
            return candidate

        # Disambiguate with parent_class prefix
        if parent_class and not candidate.startswith(parent_class):
            prefixed = f"{parent_class}{candidate}"
            if prefixed not in self.classes:
                self.decision_log.append(
                    DecisionLogEntry(
                        category="naming",
                        message=f"Disambiguated class name '{candidate}' -> '{prefixed}' to avoid collision.",
                    )
                )
                return prefixed

        # Disambiguate with index
        idx = 2
        while f"{candidate}{idx}" in self.classes:
            idx += 1
        disambiguated = f"{candidate}{idx}"
        self.decision_log.append(
            DecisionLogEntry(
                category="naming",
                message=f"Disambiguated class name '{candidate}' -> '{disambiguated}' due to distinct shape.",
            )
        )
        return disambiguated

    def _infer_field_type_from_values(
        self,
        values: list[Any],
        field_path: str,
        parent_key: str,
        parent_class: str,
    ) -> BaseType:
        """Infer a unified BaseType from a list of non-None values for a field."""
        if not values:
            return PrimitiveType("Any")

        # Group values by high-level category
        dict_values = [v for v in values if isinstance(v, dict)]
        list_values = [v for v in values if isinstance(v, list)]
        prim_values = [v for v in values if not isinstance(v, (dict, list))]

        inferred_types: list[BaseType] = []

        # 1. Dict values -> infer nested class
        if dict_values:
            suggested_name = suggest_class_name(parent_key, parent_class=parent_class)
            inferred_types.append(
                self._infer_class(
                    samples=dict_values,
                    class_name=suggested_name,
                    parent_key=parent_key,
                    parent_class=parent_class,
                    field_path=field_path,
                )
            )

        # 2. List values -> infer ListType
        if list_values:
            # Flatten lists to examine elements
            all_items = [item for lst in list_values for item in lst]
            list_item_type = self._infer_list_item_type(
                items=all_items,
                field_path=f"{field_path}[]",
                parent_key=parent_key,
                parent_class=parent_class,
            )
            inferred_types.append(ListType(list_item_type))

        # 3. Primitive values -> infer primitive or union
        if prim_values:
            prim_type = self._infer_primitives_type(prim_values, field_path)
            inferred_types.append(prim_type)

        if len(inferred_types) == 1:
            return inferred_types[0]

        # Mixed kinds across samples -> Union
        self.decision_log.append(
            DecisionLogEntry(
                category="union",
                message=f"Field '{field_path}' contains mixed value types across samples -> UnionType.",
                details={"field": field_path},
            )
        )
        return UnionType(tuple(inferred_types))

    def _infer_primitives_type(self, values: list[Any], field_path: str) -> BaseType:
        """Infer type for a list of primitive values (ints, floats, bools, strings)."""
        has_bool = any(isinstance(v, bool) for v in values)
        has_int = any(isinstance(v, int) and not isinstance(v, bool) for v in values)
        has_float = any(isinstance(v, float) for v in values)
        has_str = any(isinstance(v, str) for v in values)

        # Int vs Float promotion rule (Section 6: If any sample has decimal for same key, use float)
        if has_int and has_float and not has_str and not has_bool:
            self.decision_log.append(
                DecisionLogEntry(
                    category="type_inference",
                    message=f"Field '{field_path}' contains both int and float values. Promoted to 'float'.",
                )
            )
            return PrimitiveType("float")

        types: list[BaseType] = []
        if has_bool:
            types.append(PrimitiveType("bool"))
        if has_int and not (has_int and has_float and not has_str and not has_bool):
            types.append(PrimitiveType("int"))
        if has_float:
            types.append(PrimitiveType("float"))
        if has_str:
            # Check format detection for strings
            str_values = [v for v in values if isinstance(v, str)]
            detected_format: Optional[str] = None
            if self.detect_formats:
                formats = [detect_string_format(s) for s in str_values]
                # If all strings match the same format
                if formats and all(f == formats[0] and f is not None for f in formats):
                    detected_format = formats[0]
                    self.decision_log.append(
                        DecisionLogEntry(
                            category="format_detection",
                            message=f"Detected string format '{detected_format}' for field '{field_path}'.",
                        )
                    )

            if detected_format:
                types.append(FormattedStringType(detected_format))
            else:
                types.append(PrimitiveType("str"))

        if len(types) == 1:
            return types[0]

        # Conflicting primitive types across samples (e.g. str vs int)
        self.ambiguities.append({
            "type": "type_conflict",
            "field": field_path,
            "observed_types": [t.to_type_hint() for t in types],
            "message": f"Field '{field_path}' observed with conflicting types: {', '.join(t.to_type_hint() for t in types)}.",
        })
        return UnionType(tuple(types))

    def _infer_list_item_type(
        self,
        items: list[Any],
        field_path: str,
        parent_key: Optional[str],
        parent_class: Optional[str],
    ) -> BaseType:
        """Infer the item BaseType for an array/list."""
        if not items:
            self.decision_log.append(
                DecisionLogEntry(
                    category="type_inference",
                    message=f"Empty array at '{field_path}'. Inferred list[Any].",
                )
            )
            self.ambiguities.append({
                "type": "empty_array",
                "field": field_path,
                "message": f"Array at '{field_path}' is empty. Inferred list[Any]. Provide sample items to specify type.",
            })
            return PrimitiveType("Any")

        # Separate items into dicts, lists, primitives
        dict_items = [item for item in items if isinstance(item, dict)]
        other_items = [item for item in items if not isinstance(item, dict)]

        inferred_item_types: list[BaseType] = []

        if dict_items:
            # Check if dict items can be merged into a single class or need Union (FR-10, Section 8)
            # If all dict items have identical or overlapping keys (> 40% overlap), merge them!
            class_name = suggest_class_name(parent_key, is_list_item=True, parent_class=parent_class)
            inferred_class = self._infer_class(
                samples=dict_items,
                class_name=class_name,
                parent_key=parent_key,
                parent_class=parent_class,
                field_path=field_path,
            )
            inferred_item_types.append(inferred_class)

        if other_items:
            # Flatten any sub-lists if present or infer primitives
            non_null_other = [x for x in other_items if x is not None]
            if any(x is None for x in other_items):
                self.decision_log.append(
                    DecisionLogEntry(
                        category="nullability",
                        message=f"Array at '{field_path}' contains null elements.",
                    )
                )

            prim_type = self._infer_primitives_type(non_null_other, field_path)
            if any(x is None for x in other_items):
                inferred_item_types.append(OptionalType(prim_type))
            else:
                inferred_item_types.append(prim_type)

        if len(inferred_item_types) == 1:
            return inferred_item_types[0]

        return UnionType(tuple(inferred_item_types))

    def _infer_value_type(
        self, val: Any, field_path: str, parent_key: Optional[str], parent_class: Optional[str]
    ) -> BaseType:
        """Infer type for an arbitrary value."""
        if val is None:
            return OptionalType(PrimitiveType("Any"))
        if isinstance(val, bool):
            return PrimitiveType("bool")
        if isinstance(val, int):
            return PrimitiveType("int")
        if isinstance(val, float):
            return PrimitiveType("float")
        if isinstance(val, str):
            if self.detect_formats:
                fmt = detect_string_format(val)
                if fmt:
                    return FormattedStringType(fmt)
            return PrimitiveType("str")
        if isinstance(val, list):
            item_type = self._infer_list_item_type(val, f"{field_path}[]", parent_key, parent_class)
            return ListType(item_type)
        if isinstance(val, dict):
            cname = suggest_class_name(parent_key, parent_class=parent_class)
            return self._infer_class([val], cname, parent_key, parent_class, field_path)
        return PrimitiveType("Any")
