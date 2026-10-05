"""CLI interface for JSON-to-Python Class Converter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from json2py.agent.loop import AgentConverter
from json2py.models import OutputFormat


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="json2py",
        description="Agentic JSON-to-Python Class Converter: Generates Dataclasses or Pydantic v2 models.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="JSON file path or '-' to read from standard input (default: -)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["pydantic", "dataclass"],
        default="pydantic",
        help="Output class format (default: pydantic)",
    )
    parser.add_argument(
        "-r",
        "--root",
        default="Root",
        help="Name of the root generated class (default: Root)",
    )
    parser.add_argument(
        "-s",
        "--sample",
        action="append",
        default=[],
        help="Additional sample JSON files for schema merging and optional field detection",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output Python file path (default: stdout)",
    )
    parser.add_argument(
        "--no-formats",
        action="store_true",
        help="Disable automatic string format detection (dates, UUID, email, url)",
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Add frozen=True flag to generated Dataclasses",
    )
    parser.add_argument(
        "--slots",
        action="store_true",
        help="Add slots=True flag to generated Dataclasses",
    )
    parser.add_argument(
        "--kw-only",
        action="store_true",
        help="Add kw_only=True flag to generated Dataclasses",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print the agent's decision log to stderr",
    )

    args = parser.parse_args(argv)

    # Read primary input
    if args.input == "-":
        if sys.stdin.isatty():
            print("Enter JSON payload (Ctrl+Z then Enter on Windows, or Ctrl+D on Unix):", file=sys.stderr)
        raw_json = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
            return 1
        raw_json = path.read_text(encoding="utf-8")

    # Read extra samples
    extra_samples: list[str] = []
    for s_path in args.sample:
        p = Path(s_path)
        if not p.exists():
            print(f"Warning: Sample file '{s_path}' not found, skipping.", file=sys.stderr)
            continue
        extra_samples.append(p.read_text(encoding="utf-8"))

    fmt = OutputFormat.PYDANTIC if args.format == "pydantic" else OutputFormat.DATACLASS
    gen_opts = {
        "frozen": args.frozen,
        "slots": args.slots,
        "kw_only": args.kw_only,
    }

    converter = AgentConverter()
    result = converter.convert(
        raw_json=raw_json,
        output_format=fmt,
        root_name=args.root,
        detect_formats=not args.no_formats,
        additional_samples=extra_samples if extra_samples else None,
        generator_options=gen_opts,
    )

    if result.status == "syntax_error":
        print(f"Error: {result.error_message}", file=sys.stderr)
        return 1

    if result.status == "limit_exceeded":
        print(f"Error: {result.error_message}", file=sys.stderr)
        return 1

    # Print decision log if requested
    if args.explain:
        print("\n=== Agent Decision Log ===", file=sys.stderr)
        for entry in result.decision_log:
            print(f"[{entry.category.upper()}] {entry.message}", file=sys.stderr)
        print(f"Status: {result.status.upper()} (Self-repairs: {result.repair_attempts})", file=sys.stderr)
        print("==========================\n", file=sys.stderr)

    if result.warnings:
        for w in result.warnings:
            print(f"Warning: {w}", file=sys.stderr)

    if args.output:
        out_p = Path(args.output)
        out_p.write_text(result.code, encoding="utf-8")
        print(f"Code saved to '{args.output}'. Status: {result.status}", file=sys.stderr)
    else:
        print(result.code)

    return 0 if result.status == "validated" else 2


if __name__ == "__main__":
    sys.exit(main())
