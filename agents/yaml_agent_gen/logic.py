"""
logic.py
SIMS Mapping CSV → YAML generation logic

FINAL VERSION
- Order independent
- File-name independent
- Priority-based table detection (FIXED)
- Prevents merging of TANTOSHA / KIGYO / SHIKUGUN
- Exactly one YAML per table
- NaN-safe
"""

import pandas as pd
from collections import defaultdict


# ============================================================
# PUBLIC API (used by catalog.py)
# ============================================================
def generate_yaml_from_multiple_dfs(mapping_dfs):
    """
    mapping_dfs : list[pd.DataFrame]
    Returns:
        dict { table_name : yaml_text }
    """

    table_to_dfs = defaultdict(list)

    # Step 1: Detect table and group CSVs
    for df in mapping_dfs:
        table = _detect_table_type(df)
        table_to_dfs[table].append(df)

    # Step 2: Merge and generate YAML per table
    result = {}

    for table, dfs in table_to_dfs.items():
        merged_df = pd.concat(dfs, ignore_index=True)

        if table == "EMPLOYEE":
            result[table] = _generate_employee_yaml(merged_df)

        elif table == "ECOMMERCE_SALES":
            result[table] = _generate_ecommerce_yaml()

        elif table in (
            "PPA_M_PVS_OV_TANTOSHA_ALL",
            "PVS_OV_MEISHO_ALL",
            "PVS_OV_KIGYO_VC_ALL",
        ):
            result[table] = _generate_pvs_yaml(merged_df)

        elif table == "PVS_OV_SHIKUGUN_HIMOZUKE_ALL":
            result[table] = _generate_shikugun_yaml()

        else:
            raise ValueError(f"Unsupported table detected: {table}")

    return result


# ============================================================
# ✅ PRIORITY-BASED TABLE DETECTION (FINAL FIX)
# ============================================================
def _detect_table_type(df):
    sims2_vals = {
        str(v).upper()
        for v in df.get("sims2_column", [])
        if v and str(v).lower() != "nan"
    }

    # 1️⃣ EMPLOYEE
    if any("EMP" in v and "NAME" in v for v in sims2_vals):
        return "EMPLOYEE"

    # 2️⃣ ECOMMERCE
    if any("TOTAL_PRICE" in v for v in sims2_vals):
        return "ECOMMERCE_SALES"

    # 3️⃣ TANTOSHA (unique keyword)
    if any("TANTOSHA" in v for v in sims2_vals):
        return "PPA_M_PVS_OV_TANTOSHA_ALL"

    # 4️⃣ MEISHO (code / type based)
    if any(
        ("KUBUN" in v or "KBN" in v or "TYPE" in v)
        for v in sims2_vals
    ):
        return "PVS_OV_MEISHO_ALL"

    # 5️⃣ KIGYO VC (company based – FIXED)
    if any(
        ("KIGYO" in v or "COMPANY" in v or "CORP" in v)
        for v in sims2_vals
    ):
        return "PVS_OV_KIGYO_VC_ALL"

    # 6️⃣ SHIKUGUN (LAST fallback only)
    if "DELETE_FLAG" in sims2_vals:
        return "PVS_OV_SHIKUGUN_HIMOZUKE_ALL"

    raise ValueError(
        "Unable to auto-detect table from mapping.csv. "
        "Check sims2_column values."
    )


# ============================================================
# YAML GENERATORS (NaN-safe)
# ============================================================
def _generate_employee_yaml(df):
    lines = ["rules:", "  string:"]
    for _, r in df.iterrows():
        if r.get("rule_type") == "DERIVED":
            lines.append(f"    {r['sims2_column']}:")
            lines.append("      method: CONCAT")
            lines.append("      source_columns:")
            for c in str(r.get("sims1_column", "")).split(","):
                c = c.strip()
                if c:
                    lines.append(f"        - {c}")
            lines.append('      delimiter: " "')
    return "\n".join(lines)


def _generate_ecommerce_yaml():
    return """aggregations:
- aggregation_id: TOTAL_PRICE
  source_phase: phase1
  group_by:
  - CUSTOMER_ID
  metrics:
    TOTAL_PRICE:
      expression: "(UNITS_SOLD * UNIT_PRICE) - DISCOUNT_AMOUNT"
      function: SUM
"""


def _generate_pvs_yaml(df):
    lines = ["rules:", "  string:"]
    for _, r in df.iterrows():
        if r.get("rule_type") == "DERIVED":
            lines.append(f"    {r['sims2_column']}:")
            lines.append("      method: COALESCE")
            lines.append("      source_columns:")
            for c in str(r.get("sims1_column", "")).split(","):
                c = c.strip()
                if c:
                    lines.append(f"        - {c}")

    lines.extend([
        "  boolean:",
        "    IS_ACTIVE:",
        "      method: FLAG_TO_BOOLEAN",
        "      source_column: Del_FLG",
        '      true_value: "0"',
        '      false_value: "1"',
    ])
    return "\n".join(lines)


def _generate_shikugun_yaml():
    return """rules:
  string:
    DELETE_FLAG:
      method: CODE_MAP
      source_column: Del_FLG
      mapping:
        "0": ACTIVE
        "1": DELETED

  date:
    RECORD_CREATE_DATE:
      method: CURRENT_DATE
    RECORD_UPDATE_DATE:
      method: CURRENT_DATE

  string_defaults:
    RECORD_CREATE_USER:
      value_from: Sakuseisha_ID
    RECORD_UPDATE_USER:
      value_from: Koshinsha_ID
    RECORD_UPDATE_PROGRAM:
      value_from: KoshinProgram_ID
    APPROVAL_USER:
      value_from: Shinseisha_ID
"""
