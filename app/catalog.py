"""
Data Engineering Agent Platform UI

Supports:
1. Legacy Schema Compare (manual – volume based)
2. Schema Gap Analysis
   - Manual mode (old schema_compare style – NO hard validation) ✅ UNCHANGED
   - Database mode (Catalog & Schema dropdowns, tables auto from object mapping)
"""

from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

# -----------------------------------------------------------------------------
# ✅ Add project ROOT to PYTHONPATH
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.orchestrator import Orchestrator

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Data Engineering Agent Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
if "orch" not in st.session_state:
    st.session_state.orch = Orchestrator(base_dir=PROJECT_ROOT)

orch: Orchestrator = st.session_state.orch

# -----------------------------------------------------------------------------
# Sidebar – Agent Catalog
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🤖 Agent Catalog")

    agents = orch.list_agents(enabled_only=True)
    agent_labels = {
        f"{a['icon']}  {a['display_name']}": a["id"]
        for a in agents
    }

    selected = st.radio("Select agent", list(agent_labels.keys()))
    agent_id = agent_labels[selected]
    agent_meta = next(a for a in agents if a["id"] == agent_id)

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.title("🏗️ Data Engineering Agent Platform")
st.subheader(agent_meta["display_name"])
st.caption(agent_meta.get("description", ""))

# =============================================================================
# ✅ LEGACY AGENT — Schema Compare (UNCHANGED)
# =============================================================================
if agent_id == "schema_compare":

    st.info("Uses Excel files already uploaded to Databricks Volume.", icon="ℹ️")

    if st.button("▶ Run Schema Compare", type="primary", use_container_width=True):

        metadata = {
            "base_path": "/Volumes/schema_compare_input/schema_gap_analysis/schema_compare"
        }

        with st.status("Running Schema Compare…", expanded=True):
            result = orch.run("schema_compare", metadata)

        if result.status == "success":
            st.download_button(
                "⬇️ Download Excel report",
                data=result.output["download"]["file_bytes"],
                file_name=result.output["download"]["file_name"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.error(result.error)

# =============================================================================
# ✅ NEW AGENT — Schema Gap Analysis
# =============================================================================
elif agent_id == "schema_gap_analysis":

    st.info(
        "Schema Gap Analysis supports both Manual (Excel) and Database inputs.\n"
        "Manual mode is unchanged. Database mode derives tables automatically from Object Mapping.",
        icon="ℹ️",
    )

    input_mode = st.radio(
        "Select Input Mode",
        ["Manual (Excel from Volume)", "Database (Schema & Tables)"],
        horizontal=True,
    )

    st.divider()

    # =========================================================================
    # ✅ MANUAL MODE – OLD STYLE (UNCHANGED ✅)
    # =========================================================================
    if input_mode == "Manual (Excel from Volume)":

        st.markdown("### Step 1 – SIMS1 Schema (Required)")
        sims1_schema_path = st.text_input(
            "SIMS1 Schema file path",
            value="/Volumes/schema_compare_input/schema_gap_analysis/schema_compare/SIMS1_SCHEMA.xlsx",
        )

        st.markdown("### Step 2 – SIMS2 Schema (Required)")
        sims2_schema_path = st.text_input(
            "SIMS2 Schema file path",
            value="/Volumes/schema_compare_input/schema_gap_analysis/schema_compare/SIMS2_SCHEMA.xlsx",
        )

        st.markdown("### Step 3 – Object Mapping (Required)")
        object_mapping_path = st.text_input(
            "Object Mapping file path",
            value="/Volumes/schema_compare_input/schema_gap_analysis/schema_compare/OBJECT_MAPPING.xlsx",
        )

        with st.expander("Optional: Sample Data"):
            sims1_sample_path = st.text_input(
                "SIMS1 Sample Data file path",
                value="/Volumes/schema_compare_input/schema_gap_analysis/schema_compare/SIMS1_SAMPLE_DATA.xlsx",
            )

            sims2_sample_path = st.text_input(
                "SIMS2 Sample Data file path",
                value="/Volumes/schema_compare_input/schema_gap_analysis/schema_compare/SIMS2_SAMPLE_DATA.xlsx",
            )

        st.divider()

        if st.button("▶ Run Schema Gap Analysis", type="primary", use_container_width=True):

            metadata = {
                "mode": "manual",
                "paths": {
                    "sims1_schema": sims1_schema_path,
                    "sims2_schema": sims2_schema_path,
                    "object_mapping": object_mapping_path,
                    "sims1_sample": sims1_sample_path,
                    "sims2_sample": sims2_sample_path,
                },
            }

            with st.status("Running Schema Gap Analysis…", expanded=True):
                result = orch.run(
                    agent_id="schema_gap_analysis",
                    metadata=metadata,
                    user_context="",
                )

            if result.status == "success":
                st.success("✅ Schema gap analysis completed")

                st.download_button(
                    "⬇️ Download Excel report",
                    data=result.output["download"]["file_bytes"],
                    file_name=result.output["download"]["file_name"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.error(result.error)

    # =========================================================================
    # ✅ DATABASE MODE – DROPDOWNS + AUTO TABLES FROM OBJECT MAPPING ✅
    # =========================================================================
    else:
        st.markdown("### SIMS1 Details")

        sims1_catalog = st.selectbox(
            "SIMS1 Catalog",
            options=[
                "schema_compare_input",
                "workspace",
                "samples"
            ],
            index=0,
        )

        sims1_schema = st.selectbox(
            "SIMS1 Schema",
            options=[
                "schema_gap_analysis",
                "default",
                "information_schema"
            ],
            index=0,
        )

        st.markdown("### SIMS2 Details")

        sims2_catalog = st.selectbox(
            "SIMS2 Catalog",
            options=[
                "schema_compare_input",
                "workspace",
                "samples"
            ],
            index=0,
        )

        sims2_schema = st.selectbox(
            "SIMS2 Schema",
            options=[
                "schema_gap_analysis",
                "default",
                "information_schema"
            ],
            index=0,
        )

        st.markdown("### Object Mapping")

        mapping_file = st.file_uploader(
            "Upload Object Mapping Excel (Tables auto‑derived from this file)",
            type=["xlsx"],
        )

        st.info(
            "✅ Tables will be selected automatically from Object Mapping.\n"
            "You do not need to manually choose tables.",
            icon="ℹ️",
        )

        st.divider()

        if st.button("▶ Run Schema Gap Analysis", type="primary", use_container_width=True):

            if not mapping_file:
                st.error("Object Mapping file is required")
            else:
                metadata = {
                    "mode": "database",
                    "sims1": {
                        "catalog": sims1_catalog,
                        "schema": sims1_schema,
                    },
                    "sims2": {
                        "catalog": sims2_catalog,
                        "schema": sims2_schema,
                    },
                    "object_mapping_file": mapping_file,
                }

                with st.status("Running Schema Gap Analysis…", expanded=True):
                    result = orch.run(
                        agent_id="schema_gap_analysis",
                        metadata=metadata,
                        user_context="",
                    )

                if result.status == "success":
                    st.success("✅ Schema gap analysis completed")

                    st.download_button(
                        "⬇️ Download Excel report",
                        data=result.output["download"]["file_bytes"],
                        file_name=result.output["download"]["file_name"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.error(result.error)

# =============================================================================
# Other agents
# =============================================================================
else:
    st.info("This agent uses the standard workflow.", icon="ℹ️")
