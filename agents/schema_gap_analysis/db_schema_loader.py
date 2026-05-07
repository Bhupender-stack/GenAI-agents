
"""
db_schema_loader.py

Loads and normalizes schema metadata using Databricks SQL APIs.
NO PySpark is used (required for Databricks Apps compatibility).
"""

from databricks.sdk import WorkspaceClient

ws = WorkspaceClient()

# -----------------------------------------------------------------------------
# Datatype normalization (matches Excel schema)
# -----------------------------------------------------------------------------
def normalize_datatype(dt: str) -> str:
    if not dt:
        return ""

    dt = dt.lower()

    if "char" in dt or "string" in dt:
        return "varchar"
    if "timestamp" in dt or "date" in dt:
        return "datetime"
    if "decimal" in dt or "number" in dt or "numeric" in dt or "int" in dt:
        return "number"

    return dt


# -----------------------------------------------------------------------------
# Schema loader (SQL Warehouse)
# -----------------------------------------------------------------------------
def load_schema_from_db(
    catalog: str,
    schema: str,
    tables: list[str],
):
    """
    Returns list of dicts with keys:
      - table_name
      - column_name
      - data_type
      - column_definition
    (Exactly same structure as Excel schema input)
    """

    results = []

    for table in tables:
        query = f"""
            SELECT
                '{table}'        AS table_name,
                column_name     AS column_name,
                data_type       AS data_type,
                comment         AS column_definition,
                ordinal_position
            FROM {catalog}.information_schema.columns
            WHERE table_schema = '{schema}'
              AND table_name   = '{table}'
            ORDER BY ordinal_position
        """

        response = ws.sql.execute(
            warehouse_id=ws.config.warehouse_id,
            statement=query
        )

        for row in response.result.data_array:
            results.append(
                {
                    "table_name": row[0],
                    "column_name": row[1].strip(),
                    "data_type": normalize_datatype(row[2]),
                    "column_definition": row[3] or "",
                }
            )

    return results
