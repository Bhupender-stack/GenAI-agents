"""
catalog.py
Data Engineering Agent Platform
Mapping CSV → YAML Rule Conversion

FINAL VERSION
- Multi-file upload
- Order independent
- Merge-safe
- One YAML per detected table
- ZIP output
- Non-agentic
"""

import sys
from pathlib import Path
import io
import zipfile

import streamlit as st
import pandas as pd

# ------------------------------------------------------------------
# Ensure project root available in PYTHONPATH
# ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------------------------------------------------------------------
# Import final merge-safe logic
# ------------------------------------------------------------------
from agents.yaml_agent_gen.logic import generate_yaml_from_multiple_dfs


# ------------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Data Engineering Agent Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------------
st.sidebar.markdown("## 🤖 Agent Catalog")
chosen_id = st.sidebar.radio(
    "Select agent",
    ["sims_yaml_gen"],
    format_func=lambda _: "Mapping Transformation → YAML Rule Conversion",
)
st.sidebar.markdown("---")
st.sidebar.caption("Free (No LLM)")

# ------------------------------------------------------------------
# MAIN HEADER
# ------------------------------------------------------------------
st.title("🏗️ Data Engineering Agent Platform")

# ==============================================================
# YAML GENERATOR AGENT
# ==============================================================
if chosen_id == "sims_yaml_gen":

    st.subheader("📄 Mapping Transformation → YAML Rule Conversion")
    st.info(
        "Upload mapping.csv files in any order. "
        "The system will automatically detect table type, merge mappings "
        "per table, and generate one YAML per table in a single ZIP."
    )

    st.markdown("---")

    uploaded_files = st.file_uploader(
        "Upload mapping.csv files",
        type=["csv"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.warning("Upload one or more mapping.csv files to continue.")
        st.stop()

    st.success(f"✅ {len(uploaded_files)} file(s) uploaded")

    st.markdown("---")

    if st.button("🚀 Generate YAML (ZIP)"):

        mapping_dfs = []

        # Read all CSVs
        for file in uploaded_files:
            try:
                df = pd.read_csv(file)
                mapping_dfs.append(df)
            except Exception as e:
                st.error(f"❌ Failed to read {file.name}: {e}")
                st.stop()

        # Generate YAMLs
        try:
            table_to_yaml = generate_yaml_from_multiple_dfs(mapping_dfs)
        except Exception as e:
            st.error(f"❌ YAML generation failed: {e}")
            st.stop()

        if not table_to_yaml:
            st.error("❌ No YAML files generated.")
            st.stop()

        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for table, yaml_text in table_to_yaml.items():
                zip_file.writestr(f"{table}.yml", yaml_text)

        zip_buffer.seek(0)

        st.success(f"✅ YAML generated for {len(table_to_yaml)} table(s)")

        st.download_button(
            label="⬇️ Download YAML ZIP",
            data=zip_buffer,
            file_name="sims_yaml_output.zip",
            mime="application/zip",
        )

st.markdown("---")
st.caption(
    "Non‑LLM · Priority‑safe detection · Merge‑aware · Production‑ready"
)
