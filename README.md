# ⚡ JSON-to-Python Class Converter (Agentic AI)

An agentic AI tool that takes raw JSON payloads and produces ready-to-use, idiomatic Python class definitions as standard-library **Dataclasses** or **Pydantic v2** models.

Built per the PRD specification with a **Plan-Act-Observe-Repair** loop, runtime code execution validation, and autonomous self-repair.

---

## 🌟 Key Features

1. **Dual Code Generation Targets**:
   - **Pydantic v2**: Generates `BaseModel` classes with `ConfigDict(populate_by_name=True)`, `Field(alias=...)`, and modern type unions (`T | None`).
   - **Python Dataclass**: Generates `@dataclass` classes with ordering guarantees (non-default fields before default fields), optional flags (`frozen`, `slots`, `kw_only`), and a built-in recursive `from_dict()` helper.
2. **Autonomous Self-Repair (up to 3 retries)**:
   - Compiles and executes generated code in a sandboxed namespace.
   - Instantiates the root class with the original JSON payload.
   - On validation failure, diagnoses errors (missing fields, format errors, type mismatches), patches the schema plan, and re-validates.
3. **Format & Type Inference**:
   - Detects ISO 8601 datetimes, dates, UUIDs, Email addresses, and URLs.
   - Reconciles mixed numeric types (`int` + `float` $\rightarrow$ `float`).
   - Handles mixed arrays, empty arrays (`list[Any]`), and empty objects (`pass`).
4. **Key Sanitization & Naming**:
   - Converts kebab-case, camelCase, symbols (`$`, `@`, `-`), and spaces into valid Python `snake_case` identifiers.
   - Handles Python keywords (`class`, `from`, `def`, `import`, `in`, `is`) via trailing underscores (`class_`) and aliases.
   - Resolves class name collisions across depths and singularizes list item names (`users` $\rightarrow$ `User`).
5. **Multi-Sample Merging**:
   - Merges multiple JSON sample payloads and automatically marks keys missing in some samples as optional (`T | None = None`).
6. **Explainability & Decision Logging**:
   - Returns a structured decision log explaining naming decisions, format detections, nullability rules, and self-repair actions.
7. **Clean PEP 8 Output**:
   - Formatted via Ruff with grouped, deduplicated import blocks.

---

## 🚀 Quickstart & Usage

### 1. Launch the Streamlit Web UI

Run the Streamlit web application:

```bash
streamlit run app.py
```

or via python module:

```bash
python -m streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

**Web UI Features**:
- **Preset Payloads**: 1-click loading of complex JSON payloads (e-commerce orders, webhooks, edge cases).
- **Format Toggle**: Switch between Pydantic v2 and Python Dataclass.
- **Advanced Options**: Custom Root class name, format detection toggle, Dataclass flags (`frozen`, `slots`, `kw_only`), and multi-sample tabs.
- **Live Status Badge**: Instant feedback showing `Validated`, `Validated via Self-Repair`, or `Syntax Error`.
- **Code Viewer & Download**: Syntax-highlighted output with a 1-click `Download <name>_models.py` button.
- **Decision Log & Ambiguities Expander**: Transparent view of all AI decisions and choices.

---

### 2. Run the CLI

Convert JSON from standard input:

```bash
echo '{"id": 1, "first-name": "Alice"}' | python -m json2py.cli
```

Convert a JSON file to a Python file:

```bash
python -m json2py.cli payload.json -f pydantic -r User -o user_models.py --explain
```

Dataclass output with frozen and slots flags:

```bash
python -m json2py.cli payload.json -f dataclass --frozen --slots -o user_models.py
```

Multi-sample merging:

```bash
python -m json2py.cli sample1.json -s sample2.json -s sample3.json
```

---

### 3. Run the Test Suite (pytest)

Run all unit tests and the 55+ payload test corpus:

```bash
python -m pytest -v
```

All 154+ tests validate the entire pipeline, sandboxed instantiation, edge cases, and corpus pass rate (100% pass rate achieved!).

---

## 📂 Project Architecture

```
JSON2PY/
├── app.py                      # Streamlit Web Application
├── json2py/
│   ├── __init__.py             # Package exports
│   ├── models.py               # AST & Type system schema definitions
│   ├── cli.py                  # Command-line interface
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py           # JSON parser, line/col error pinpointing, depth/size guards
│   │   ├── inferencer.py       # Recursive type inference, array reconciliation, recursion
│   │   ├── namer.py            # Key sanitization, Python keyword handling, PascalCase class naming
│   │   ├── format_detector.py  # Regex & parser for ISO dates, UUID, Email, URL
│   │   └── merger.py           # Multi-sample JSON merger with key presence tracking
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── base.py             # Topological sorting & import consolidation
│   │   ├── pydantic_gen.py     # Pydantic v2 generator with ConfigDict & Field aliases
│   │   └── dataclass_gen.py    # Dataclass generator with from_dict & field ordering
│   └── agent/
│       ├── __init__.py
│       ├── tools.py            # Deterministic and interactive agent tools
│       ├── validator.py        # Sandboxed execution & runtime instantiation tester
│       ├── repair.py           # Diagnosis heuristics & schema plan self-repair
│       └── loop.py             # Plan-Act-Observe-Repair execution loop
└── tests/
    ├── test_parser.py          # Syntax errors, duplicate keys, safety limits
    ├── test_namer.py           # Snake_case, keywords, digit prefixes, singularization
    ├── test_format_detector.py # Date, datetime, UUID, Email, URL checks
    ├── test_inferencer.py      # Primitives, promotion, nested objects, multi-sample
    ├── test_generators.py      # Pydantic & Dataclass generation & ordering
    ├── test_validator_and_repair.py # Sandbox compilation, runtime checks & repairs
    ├── test_agent_loop.py      # End-to-end agent converter & decision logs
    ├── test_edge_cases.py      # Empty containers, symbols, recursive structures
    └── test_corpus.py          # 55+ diverse real-world JSON payloads
```
