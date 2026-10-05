"""Base code generator interface and topological class dependency sorter."""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from json2py.models import ClassSchema, OutputFormat, SchemaPlan


def topological_sort_classes(classes: dict[str, ClassSchema], root_name: str) -> list[ClassSchema]:
    """
    Sort classes in topological order so that dependencies are defined before dependents.
    Handles cycles gracefully by falling back to standard order.
    The root class will always appear last.
    """
    ordered: list[ClassSchema] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(name: str):
        if name in visiting:
            # Cycle detected (e.g. recursive reference)
            return
        if name in visited:
            return
        if name not in classes:
            return

        visiting.add(name)
        schema = classes[name]
        for dep in sorted(schema.get_dependencies()):
            visit(dep)
        visiting.remove(name)
        visited.add(name)
        ordered.append(schema)

    # First visit non-root classes
    for name in sorted(classes.keys()):
        if name != root_name:
            visit(name)

    # Finally visit root
    if root_name in classes:
        visit(root_name)

    return ordered


def consolidate_imports(import_lines: set[str]) -> str:
    """Group and sort import statements cleanly."""
    future_imports: set[str] = set()
    from_imports: dict[str, set[str]] = {}
    direct_imports: set[str] = set()

    for line in import_lines:
        line = line.strip()
        if not line:
            continue
        if "future" in line:
            future_imports.add(line)
        elif line.startswith("from ") and " import " in line:
            parts = line[5:].split(" import ")
            mod = parts[0].strip()
            symbols = [s.strip() for s in parts[1].split(",") if s.strip()]
            if mod not in from_imports:
                from_imports[mod] = set()
            from_imports[mod].update(symbols)
        else:
            direct_imports.add(line)

    lines: list[str] = []
    if future_imports:
        lines.extend(sorted(future_imports))
        lines.append("")

    # Separate stdlib from third-party (pydantic)
    stdlib_mods = [m for m in sorted(from_imports.keys()) if not m.startswith("pydantic")]
    thirdparty_mods = [m for m in sorted(from_imports.keys()) if m.startswith("pydantic")]

    for mod in stdlib_mods:
        symbols_str = ", ".join(sorted(from_imports[mod]))
        lines.append(f"from {mod} import {symbols_str}")

    if direct_imports:
        lines.extend(sorted(direct_imports))

    if thirdparty_mods:
        if stdlib_mods or direct_imports:
            lines.append("")
        for mod in thirdparty_mods:
            symbols_str = ", ".join(sorted(from_imports[mod]))
            lines.append(f"from {mod} import {symbols_str}")

    if lines and lines[-1] != "":
        lines.append("")

    return "\n".join(lines)


def format_python_code(code: str) -> str:
    """Format Python code using ruff if available; fallback to original code."""
    try:
        proc = subprocess.run(
            ["ruff", "format", "-"],
            input=code,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        pass
    return code


class BaseCodeGenerator(ABC):
    """Abstract base class for Python code generators."""

    def __init__(self, format_type: OutputFormat):
        self.format_type = format_type

    @abstractmethod
    def generate(self, plan: SchemaPlan, **kwargs: Any) -> str:
        """Generate formatted Python source code from a SchemaPlan."""
        raise NotImplementedError
