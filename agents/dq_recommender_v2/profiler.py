"""
agents/dq_recommender_v2/profiler.py

SQL-based column profiler for the dq_recommender_v2 agent.

Runs via the Databricks Statement Execution API (SQL Warehouse) — no PySpark
required. Compatible with the Databricks Apps environment.

Output columns per row:
    table_name, column_name, documented_datatype, inferred_datatype,
    distinct_count, pct_distinct, non_distinct_count, pct_non_distinct,
    null_count, pct_null, minimum_value, maximum_value

Audit columns (any column starting with "aud_") are skipped automatically.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUDIT_PREFIX      = "aud_"
COLUMN_BATCH_SIZE = 20
STATEMENT_TIMEOUT = "0s"
POLL_INTERVAL     = 1.0
POLL_DEADLINE     = 180


# ---------------------------------------------------------------------------
# Semantic type inference
# ---------------------------------------------------------------------------

def _infer_semantic_type(col_name: str, documented_dtype: str) -> str:
    name  = col_name.lower()
    dtype = documented_dtype.lower()

    if "timestamp" in dtype:
        return "Timestamp"
    if "date" in dtype:
        return "Date"
    if "boolean" in dtype or "bool" in dtype:
        return "Boolean"
    if any(t in dtype for t in ("int", "bigint", "smallint", "tinyint",
                                 "long", "short", "byte")):
        return "Integer"
    if any(t in dtype for t in ("double", "float", "decimal", "numeric",
                                 "real")):
        return "Float"
    if "string" in dtype or "varchar" in dtype or "char" in dtype:
        if "email" in name:
            return "Email"
        if "phone" in name or "mobile" in name or "tel" in name:
            return "Phone"
        if "url" in name or "link" in name or "href" in name:
            return "URL"
        if "uuid" in name or "guid" in name:
            return "UUID"
        if "postal" in name or "zip" in name or "postcode" in name:
            return "PostalCode"
        if "ip" == name or "ip_address" in name:
            return "IP"
        if "country_code" in name:
            return "CountryCode"
        if name.endswith("_id") or name == "id":
            return "ID"
        if name.endswith("_code") or name.endswith("_type"):
            return "Code"
        return "String"
    return documented_dtype


# ---------------------------------------------------------------------------
# Statement Execution API helpers
# ---------------------------------------------------------------------------

def _run_sql(sql: str, warehouse_id: str) -> List[List[Any]]:
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.sql import StatementState

        ws   = WorkspaceClient()
        stmt = ws.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout=STATEMENT_TIMEOUT,
        )

        deadline = time.time() + POLL_DEADLINE
        while stmt.status.state in (StatementState.PENDING,
                                     StatementState.RUNNING):
            if time.time() > deadline:
                raise TimeoutError(
                    f"Statement timed out after {POLL_DEADLINE}s"
                )
            time.sleep(POLL_INTERVAL)
            stmt = ws.statement_execution.get_statement(stmt.statement_id)

        if stmt.status.state != StatementState.SUCCEEDED:
            err = (stmt.status.error.message
                   if stmt.status.error else "Unknown error")
            raise RuntimeError(f"Statement failed: {err}")

        return stmt.result.data_array or []

    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        raise


def _scalar(sql: str, warehouse_id: str) -> Any:
    rows = _run_sql(sql, warehouse_id)
    return rows[0][0] if rows else None


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

def _get_columns(
    table_ref: str,
    warehouse_id: str,
) -> List[Dict[str, str]]:
    # Parse catalog, schema, table from fully qualified name
    parts = table_ref.split(".")
    if len(parts) == 3:
        catalog, schema, table = parts
    elif len(parts) == 2:
        catalog, schema, table = None, parts[0], parts[1]
    else:
        catalog, schema, table = None, None, parts[0]

    if catalog:
        sql = f"""
            SELECT column_name, data_type
            FROM {catalog}.information_schema.columns
            WHERE table_schema = '{schema}'
              AND table_name   = '{table}'
            ORDER BY ordinal_position
        """
    else:
        sql = f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = '{schema}'
              AND table_name   = '{table}'
            ORDER BY ordinal_position
        """

    rows = _run_sql(sql, warehouse_id)
    cols = []
    for row in rows:
        col_name  = str(row[0]).strip() if row[0] else ""
        col_dtype = str(row[1]).strip() if row[1] else ""
        if not col_name:
            continue
        if col_name.lower().startswith(AUDIT_PREFIX):
            logger.info(f"  Skipping audit column: {col_name}")
            continue
        cols.append({"name": col_name, "data_type": col_dtype})
    return cols


# ---------------------------------------------------------------------------
# Core profiling — batched SQL
# ---------------------------------------------------------------------------

def _profile_batch(
    table_ref:    str,
    columns:      List[Dict[str, str]],
    total_rows:   int,
    warehouse_id: str,
) -> List[Dict[str, Any]]:
    if not columns or total_rows == 0:
        return [
            {
                "column_name":         c["name"],
                "documented_datatype": c["data_type"],
                "inferred_datatype":   _infer_semantic_type(
                                           c["name"], c["data_type"]
                                       ),
                "distinct_count":      0,
                "pct_distinct":        0.0,
                "non_distinct_count":  0,
                "pct_non_distinct":    0.0,
                "null_count":          0,
                "pct_null":            0.0,
                "minimum_value":       None,
                "maximum_value":       None,
            }
            for c in columns
        ]

    agg_parts = []
    for c in columns:
        qname = f"`{c['name']}`"
        agg_parts += [
            f"COUNT(DISTINCT {qname})                           AS `{c['name']}__distinct`",
            f"SUM(CASE WHEN {qname} IS NULL THEN 1 ELSE 0 END) AS `{c['name']}__nulls`",
            f"MIN(CAST({qname} AS STRING))                      AS `{c['name']}__min`",
            f"MAX(CAST({qname} AS STRING))                      AS `{c['name']}__max`",
        ]

    sql  = f"SELECT {', '.join(agg_parts)} FROM {table_ref}"
    rows = _run_sql(sql, warehouse_id)
    row  = rows[0] if rows else []

    results = []
    for idx, c in enumerate(columns):
        base         = idx * 4
        distinct     = int(row[base]     or 0) if len(row) > base     else 0
        nulls        = int(row[base + 1] or 0) if len(row) > base + 1 else 0
        min_val      = row[base + 2]            if len(row) > base + 2 else None
        max_val      = row[base + 3]            if len(row) > base + 3 else None
        non_distinct = max(total_rows - distinct, 0)

        results.append({
            "column_name":         c["name"],
            "documented_datatype": c["data_type"],
            "inferred_datatype":   _infer_semantic_type(c["name"], c["data_type"]),
            "distinct_count":      distinct,
            "pct_distinct":        round(distinct / total_rows * 100, 4)
                                   if total_rows > 0 else 0.0,
            "non_distinct_count":  non_distinct,
            "pct_non_distinct":    round(non_distinct / total_rows * 100, 4)
                                   if total_rows > 0 else 0.0,
            "null_count":          nulls,
            "pct_null":            round(nulls / total_rows * 100, 4)
                                   if total_rows > 0 else 0.0,
            "minimum_value":       str(min_val) if min_val is not None else None,
            "maximum_value":       str(max_val) if max_val is not None else None,
        })

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_profiler(
    warehouse_id: str,
    table_refs:   List[str],
    sample_size:  int = 0,
) -> Dict[str, Any]:
    """
    Profile one or more Databricks tables via SQL Warehouse.

    Parameters
    ----------
    warehouse_id : Databricks SQL Warehouse ID
    table_refs   : list of fully qualified table names
    sample_size  : rows to sample per table (0 = full table)

    Returns
    -------
    dict with keys:
      "profiles" : list of per-table profile dicts
      "rows"     : flat list of per-column rows across all tables
      "summary"  : high-level run metadata
    """
    if not warehouse_id:
        raise ValueError(
            "A SQL Warehouse ID is required for profiling. "
            "Please enter one in the profiling options."
        )

    all_profiles: List[Dict[str, Any]] = []
    all_rows:     List[Dict[str, Any]] = []

    for table_ref in table_refs:
        logger.info(f"Profiling: {table_ref}")
        table_name = table_ref.split(".")[-1]

        try:
            # 1. Get columns (audit columns skipped inside)
            columns = _get_columns(table_ref, warehouse_id)
            if not columns:
                logger.warning(f"  No profileable columns in {table_ref}")
                all_profiles.append({
                    "table_name":      table_name,
                    "fully_qualified": table_ref,
                    "total_rows":      0,
                    "total_columns":   0,
                    "audit_skipped":   [],
                    "columns":         [],
                    "error":           "No profileable columns found.",
                })
                continue

            # 2. Get row count
            if sample_size > 0:
                count_sql = (
                    f"SELECT COUNT(*) FROM "
                    f"(SELECT * FROM {table_ref} LIMIT {sample_size})"
                )
            else:
                count_sql = f"SELECT COUNT(*) FROM {table_ref}"

            total_rows = int(_scalar(count_sql, warehouse_id) or 0)
            logger.info(f"  {total_rows:,} rows x {len(columns)} columns")

            # 3. Build reference (with sample if requested)
            profile_ref = (
                table_ref if sample_size == 0
                else f"(SELECT * FROM {table_ref} LIMIT {sample_size})"
            )

            # 4. Profile in batches
            column_rows: List[Dict[str, Any]] = []
            for i in range(0, len(columns), COLUMN_BATCH_SIZE):
                batch = columns[i : i + COLUMN_BATCH_SIZE]
                logger.info(
                    f"  Batch {i+1}-{i+len(batch)} of {len(columns)}"
                )
                batch_results = _profile_batch(
                    profile_ref, batch, total_rows, warehouse_id
                )
                for row in batch_results:
                    row["table_name"] = table_name
                    column_rows.append(row)
                    all_rows.append(row)

            # 5. Collect audit column names for display
            all_col_rows  = _run_sql(
                f"DESCRIBE TABLE {table_ref}", warehouse_id
            )
            audit_skipped = [
                str(r[0]) for r in all_col_rows
                if r[0]
                and str(r[0]).lower().startswith(AUDIT_PREFIX)
                and not str(r[0]).startswith("#")
            ]

            all_profiles.append({
                "table_name":      table_name,
                "fully_qualified": table_ref,
                "total_rows":      total_rows,
                "total_columns":   len(columns),
                "audit_skipped":   audit_skipped,
                "sampled":         sample_size > 0,
                "sample_size":     sample_size if sample_size > 0
                                   else total_rows,
                "columns":         column_rows,
            })
            logger.info(f"  Done: {table_ref}")

        except Exception as e:
            logger.error(f"Failed to profile {table_ref}: {e}")
            all_profiles.append({
                "table_name":      table_name,
                "fully_qualified": table_ref,
                "total_rows":      0,
                "total_columns":   0,
                "audit_skipped":   [],
                "columns":         [],
                "error":           str(e),
            })

    return {
        "profiles": all_profiles,
        "rows":     all_rows,
        "summary": {
            "tables_profiled": len(all_profiles),
            "total_columns":   len(all_rows),
            "profiled_at":     datetime.now().isoformat(timespec="seconds"),
        },
    }
