"""Streamlit Web UI for JSON-to-Python Class Converter.

An agentic AI interface that converts raw JSON payloads into validated Python
Dataclasses or Pydantic v2 models with runtime execution verification and autonomous self-repair.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import streamlit as st

from json2py.agent.loop import AgentConverter, ConversionResult
from json2py.models import OutputFormat

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="JSON-to-Python Class Converter",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Main Layout */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* Hero Header Banner */
    .hero-banner {
        padding: 1.75rem 2rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border-radius: 14px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38ef7d 0%, #11998e 50%, #38bdf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.35rem;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1rem;
    }
    .badge-container {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
    }
    .badge {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 9999px;
        padding: 0.25rem 0.85rem;
        font-size: 0.8rem;
        font-weight: 500;
        color: #e2e8f0;
    }

    /* Status Badges */
    .status-card-pass {
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid #10b981;
        border-radius: 10px;
        padding: 0.85rem 1.2rem;
        color: #34d399;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .status-card-repair {
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid #f59e0b;
        border-radius: 10px;
        padding: 0.85rem 1.2rem;
        color: #fbbf24;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .status-card-fail {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid #ef4444;
        border-radius: 10px;
        padding: 0.85rem 1.2rem;
        color: #f87171;
        font-weight: 600;
        margin-bottom: 1rem;
    }

    /* Decision Log Items */
    .log-item-naming {
        border-left: 3px solid #38bdf8;
        padding-left: 0.8rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    .log-item-repair {
        border-left: 3px solid #f59e0b;
        padding-left: 0.8rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    .log-item-type {
        border-left: 3px solid #10b981;
        padding-left: 0.8rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    .log-item-null {
        border-left: 3px solid #a855f7;
        padding-left: 0.8rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    .log-item-general {
        border-left: 3px solid #64748b;
        padding-left: 0.8rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. Preset JSON Payloads
# -----------------------------------------------------------------------------
PRESETS: dict[str, dict[str, Any] | list[Any] | str] = {
    "User Profile & Address": {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "first-name": "Avinaash",
        "last_name": "Kumar",
        "email": "avinaash@example.com",
        "is_active": True,
        "created_at": "2026-09-28T17:31:29Z",
        "website": "https://github.com/google/antigravity",
        "address": {
            "street": "123 Innovation Way",
            "city": "Chennai",
            "country": "India",
            "postal_code": "600001",
        },
        "tags": ["developer", "ai", "python"],
    },
    "E-commerce Order (Nested Items)": {
        "order_id": "ORD-2026-99812",
        "total_amount": 149.95,
        "items": [
            {
                "product_id": 101,
                "name": "Wireless Mechanical Keyboard",
                "price": 89.99,
                "quantity": 1,
            },
            {
                "product_id": 204,
                "name": "USB-C Braided Cable",
                "price": 14.99,
                "quantity": 2,
            },
        ],
        "shipping_address": {
            "city": "Bengaluru",
            "country": "India",
        },
        "notes": None,
    },
    "Edge Cases (Keywords & Special Chars)": {
        "class": "AdvancedAgenticAI",
        "from": "DeepMind",
        "import": "models",
        "2fa_enabled": True,
        "$browser": "Chrome",
        "@context": "https://schema.org",
        "mixed_numeric": [1, 2.5, 3],
        "empty_list": [],
        "empty_object": {},
        "metadata": {
            "version": "1.0",
        },
    },
    "Top-Level Array (Collection)": [
        {"id": 1, "title": "First Article", "published": True},
        {"id": 2, "title": "Second Article", "published": False, "views": 1500},
    ],
    "Invalid JSON Syntax Demo": '{\n    "name": "Broken JSON",\n    "missing_comma": 123\n    "next": 456\n}',
}

# -----------------------------------------------------------------------------
# 3. Session State Initialization
# -----------------------------------------------------------------------------
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "compare_result" not in st.session_state:
    st.session_state.compare_result = None
if "execution_time" not in st.session_state:
    st.session_state.execution_time = 0.0
if "json_input_val" not in st.session_state:
    st.session_state.json_input_val = json.dumps(PRESETS["User Profile & Address"], indent=2)

# -----------------------------------------------------------------------------
# 4. Sidebar Controls & Settings
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Converter Configuration")

    format_choice = st.radio(
        "Target Output Format",
        options=["Pydantic v2", "Python Dataclass", "Compare Both (Side-by-Side)"],
        index=0,
        help="Select whether to generate modern Pydantic v2 models, standard-library Dataclasses, or both.",
    )

    root_class_name = st.text_input(
        "Root Class Name",
        value="Root",
        help="Custom name for the top-level Python class (e.g., 'User', 'Order', 'Root').",
    )

    detect_formats = st.checkbox(
        "Detect Semantic Formats",
        value=True,
        help="Detect datetime, date, UUID, EmailStr, and HttpUrl from string contents.",
    )

    multi_sample_mode = st.checkbox(
        "Multi-Sample Merging Mode",
        value=False,
        help="Supply multiple sample JSON payloads. Keys missing in some samples become optional (T | None = None).",
    )

    st.markdown("---")
    st.subheader("Python Dataclass Flags")
    is_frozen = st.checkbox(
        "frozen=True",
        value=False,
        disabled=(format_choice == "Pydantic v2"),
        help="Generates immutable dataclass instances.",
    )
    is_slots = st.checkbox(
        "slots=True",
        value=False,
        disabled=(format_choice == "Pydantic v2"),
        help="Generates __slots__ for reduced memory footprint.",
    )
    is_kw_only = st.checkbox(
        "kw_only=True",
        value=False,
        disabled=(format_choice == "Pydantic v2"),
        help="Generates keyword-only initializers.",
    )

    st.markdown("---")
    max_retries = st.slider(
        "Max Agent Self-Repairs",
        min_value=1,
        max_value=5,
        value=3,
        help="Maximum repair attempts the agent will take if sandboxed validation fails.",
    )

    st.markdown(
        """
        <div style="font-size: 0.78rem; color: #64748b; margin-top: 2rem;">
        🔒 <b>Privacy Notice:</b> Payloads are processed purely in-memory and are never stored.
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# 5. Header Banner
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-banner">
        <div class="hero-title">JSON-to-Python Class Converter</div>
        <div class="hero-subtitle">Agentic AI schema inference, sandboxed code validation & autonomous self-repair</div>
        <div class="badge-container">
            <span class="badge">🤖 Autonomous Self-Repair (up to 3 retries)</span>
            <span class="badge">⚡ Pydantic v2 & @dataclass</span>
            <span class="badge">🧪 Runtime Instantiation Verification</span>
            <span class="badge">🎨 PEP 8 Ruff Formatting</span>
            <span class="badge">🧠 Explainable Decision Log</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 6. Preset Selector & Layout Columns
# -----------------------------------------------------------------------------
col_preset, col_clear = st.columns([3, 1])
with col_preset:
    selected_preset = st.selectbox(
        "Choose a Preset JSON Payload:",
        options=["-- Select a Preset to Load --"] + list(PRESETS.keys()),
        index=0,
    )
with col_clear:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    if st.button("Clear Input Area", use_container_width=True):
        st.session_state.json_input_val = ""
        st.session_state.last_result = None
        st.session_state.compare_result = None
        st.rerun()

col_left, col_right = st.columns([1, 1], gap="medium")

# -----------------------------------------------------------------------------
# 7. Left Column: JSON Input
# -----------------------------------------------------------------------------
with col_left:
    st.subheader("📥 Input JSON")

    # Update input when preset changes
    if selected_preset != "-- Select a Preset to Load --":
        preset_data = PRESETS[selected_preset]
        initial_val = preset_data if isinstance(preset_data, str) else json.dumps(preset_data, indent=2)
        st.session_state.json_input_val = initial_val

    json_input = st.text_area(
        "Paste JSON payload here:",
        value=st.session_state.json_input_val,
        height=380,
        placeholder='{\n  "id": 1,\n  "name": "Sample"\n}',
    )
    st.session_state.json_input_val = json_input

    # Multi-sample inputs (FR-13)
    additional_samples: list[str] = []
    if multi_sample_mode:
        st.markdown("#### 🧩 Additional Samples (for nullability & optional field inference)")
        sample_tab1, sample_tab2 = st.tabs(["Sample #2", "Sample #3"])
        with sample_tab1:
            s2 = st.text_area("Sample #2 JSON:", height=140, placeholder='{\n  "user_id": "...",\n  "optional_key": "exists here"\n}')
            if s2.strip():
                additional_samples.append(s2)
        with sample_tab2:
            s3 = st.text_area("Sample #3 JSON:", height=140, placeholder='{\n  "user_id": "...",\n  "extra_flag": true\n}')
            if s3.strip():
                additional_samples.append(s3)

    convert_clicked = st.button("🚀 Generate Python Models", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# 8. Conversion Execution (Plan-Act-Observe-Repair Loop)
# -----------------------------------------------------------------------------
if convert_clicked:
    if not json_input.strip():
        st.error("Please provide a valid JSON payload in the input box.")
    else:
        with st.spinner("🤖 Agent inspecting JSON, planning hierarchy, generating code & testing instantiation..."):
            t_start = time.perf_counter()
            converter = AgentConverter(max_repair_attempts=max_retries)
            generator_options = {
                "frozen": is_frozen,
                "slots": is_slots,
                "kw_only": is_kw_only,
            }

            if format_choice == "Compare Both (Side-by-Side)":
                res_pydantic = converter.convert(
                    raw_json=json_input,
                    output_format=OutputFormat.PYDANTIC,
                    root_name=root_class_name,
                    detect_formats=detect_formats,
                    additional_samples=additional_samples if additional_samples else None,
                    generator_options=generator_options,
                )
                res_dataclass = converter.convert(
                    raw_json=json_input,
                    output_format=OutputFormat.DATACLASS,
                    root_name=root_class_name,
                    detect_formats=detect_formats,
                    additional_samples=additional_samples if additional_samples else None,
                    generator_options=generator_options,
                )
                st.session_state.last_result = res_pydantic
                st.session_state.compare_result = res_dataclass
            else:
                out_fmt = OutputFormat.PYDANTIC if format_choice == "Pydantic v2" else OutputFormat.DATACLASS
                result = converter.convert(
                    raw_json=json_input,
                    output_format=out_fmt,
                    root_name=root_class_name,
                    detect_formats=detect_formats,
                    additional_samples=additional_samples if additional_samples else None,
                    generator_options=generator_options,
                )
                st.session_state.last_result = result
                st.session_state.compare_result = None

            st.session_state.execution_time = time.perf_counter() - t_start

# -----------------------------------------------------------------------------
# 9. Right Column: Output, Validation Badge, and Decision Log
# -----------------------------------------------------------------------------
with col_right:
    st.subheader("🐍 Generated Python Code")

    res: Optional[ConversionResult] = st.session_state.last_result

    if res is None:
        st.info("Paste your JSON payload on the left and click **'Generate Python Models'** to convert.")
    else:
        # Validation Status Card
        if res.status == "validated":
            if res.repair_attempts == 0:
                st.markdown(
                    f'<div class="status-card-pass">✅ <b>Validated:</b> Models compiled and successfully instantiated with your payload on first attempt! ({st.session_state.execution_time:.3f}s)</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="status-card-repair">✨ <b>Validated via Self-Repair:</b> Passed compilation and runtime instantiation after {res.repair_attempts} repair attempt(s)! ({st.session_state.execution_time:.3f}s)</div>',
                    unsafe_allow_html=True,
                )
        elif res.status == "unvalidated":
            st.markdown(
                f'<div class="status-card-fail">⚠️ <b>Unvalidated:</b> Best-effort code generated, but payload verification encountered warnings after {res.repair_attempts} repair attempt(s).</div>',
                unsafe_allow_html=True,
            )
        elif res.status == "syntax_error":
            st.markdown(
                '<div class="status-card-fail">❌ <b>JSON Syntax Error:</b> Input text is not valid JSON. See syntax error details below.</div>',
                unsafe_allow_html=True,
            )
            st.code(res.error_message or "Unknown syntax error", language="text")

        # Code Display & Downloads
        if res.code:
            compare_res: Optional[ConversionResult] = st.session_state.compare_result

            if compare_res is not None:
                # Comparison Tabs
                tab_pydantic, tab_dataclass = st.tabs(["⚡ Pydantic v2 Model", "📦 Python Dataclass"])
                with tab_pydantic:
                    st.download_button(
                        label="💾 Download Pydantic (.py)",
                        data=res.code,
                        file_name=f"{root_class_name.lower()}_pydantic.py",
                        mime="text/x-python",
                        key="dl_pydantic",
                    )
                    st.code(res.code, language="python")

                with tab_dataclass:
                    st.download_button(
                        label="💾 Download Dataclass (.py)",
                        data=compare_res.code,
                        file_name=f"{root_class_name.lower()}_dataclass.py",
                        mime="text/x-python",
                        key="dl_dataclass",
                    )
                    st.code(compare_res.code, language="python")
            else:
                # Single Format Display
                filename = f"{root_class_name.lower()}_models.py"
                col_b1, col_b2 = st.columns([1, 1])
                with col_b1:
                    st.download_button(
                        label=f"💾 Download {filename}",
                        data=res.code,
                        file_name=filename,
                        mime="text/x-python",
                        use_container_width=True,
                    )
                with col_b2:
                    st.caption("💡 Use the built-in copy icon in the top-right of the code box to copy.")

                st.code(res.code, language="python")

            # Decision Log Expander (FR-15)
            with st.expander("🧠 Agent Decision Log & Explainability", expanded=True):
                if not res.decision_log:
                    st.write("No special decisions needed for this payload.")
                else:
                    for entry in res.decision_log:
                        cat = entry.category.lower()
                        if "naming" in cat:
                            css_cls = "log-item-naming"
                            icon = "🏷️"
                        elif "repair" in cat:
                            css_cls = "log-item-repair"
                            icon = "🛠️"
                        elif "null" in cat:
                            css_cls = "log-item-null"
                            icon = "❓"
                        elif "format" in cat:
                            css_cls = "log-item-type"
                            icon = "📅"
                        else:
                            css_cls = "log-item-general"
                            icon = "📐"

                        st.markdown(
                            f'<div class="{css_cls}"><b>{icon} [{entry.category.upper()}]</b> {entry.message}</div>',
                            unsafe_allow_html=True,
                        )

            # Ambiguities & Clarifications Expander (FR-16)
            if res.clarifying_questions:
                with st.expander("❓ Detected Ambiguities & Clarifying Points", expanded=True):
                    for q in res.clarifying_questions:
                        st.warning(f"**{q.question}**")
                        st.write("Options considered by agent:")
                        for opt in q.options:
                            st.markdown(f"- `{opt}`")

            # Parser & Validator Warnings Expander
            if res.warnings:
                with st.expander("⚠️ Parser & Validator Warnings", expanded=False):
                    for w in res.warnings:
                        st.info(w)
