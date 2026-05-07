# DQ Recommender V2 — Governance Rules

## CRITICAL — SQL Must Use Real Table Names
- Every SQL statement MUST use the exact fully qualified table name from the metadata.
- NEVER write `{table}`, `<table>`, `{column}`, `<column_name>`, or ANY placeholder.
- SQL must be immediately runnable with no substitution needed.
- SQL must return 0 when the rule passes, a positive integer when it fails.

## CRITICAL — Severity
- Every rule MUST have severity set to WARNING.
- Never use any other severity value under any circumstance.

## CRITICAL — Data Source
- Use the data_source value provided in the user context if present.
- If it is absent or blank, default the data_source field to 'system'.

## CRITICAL — Audit Columns
- Never generate any DQ rule for columns whose name starts with "aud_".
- These are system audit columns. Skip them entirely regardless of their data type
  or statistics.

## Rule Generation Logic

### Null
- Recommend a Null check on every non-nullable column and every primary/foreign
  key column.
- When pct_null is available: generate only when pct_null is 0 or column is
  defined as non-nullable.
- Correct SQL: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name IS NULL`

### Uniqueness
- Recommend a Uniqueness check on every business key and primary key column.
- When pct_distinct is available: generate when pct_distinct is at or near 100%.
- Do NOT recommend Uniqueness on foreign key columns — they are many-to-one
  by design.
- Correct SQL: `SELECT COUNT(*) - COUNT(DISTINCT column_name) FROM catalog.schema.table`

### Range
- Recommend a Range check on numeric columns where min and max values suggest
  bounded valid ranges.
- When minimum_value and maximum_value are available from profiling: use them
  directly as bounds.
- When only schema is available: infer bounds from column name and data type.
- Do NOT recommend Range on string or timestamp columns.
- Correct SQL: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name < <min> OR column_name > <max>`

### Format_Check
- Recommend a Format_Check on columns where values are expected to follow a
  pattern: dates, emails, phone numbers, postal codes, codes, IDs, and similar.
- When inferred_datatype is available: use it to select the appropriate regex.
- When only schema is available: infer from column name and documented_datatype.
- Always generate a regex-based SQL test regardless of the underlying data type.
- Correct SQL: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name NOT RLIKE '<regex>'`

### LoV (List of Values)
- Recommend a LoV check only when BOTH of the following are true:
  - distinct_count is low in absolute terms, AND
  - pct_distinct is low relative to total rows.
- Use judgment on the combination of both signals — do not apply a fixed threshold.
- When only schema is available: only generate LoV for columns where the name
  strongly implies a fixed set (status, type, category, flag, etc.).
- Correct SQL: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name NOT IN ('<val1>','<val2>',...)`

### Referential_Integrity
- Recommend a Referential_Integrity check only when the referenced table is
  present in the loaded metadata.
- Infer FK relationships from <name>_id column naming patterns.
- Do NOT generate a Referential_Integrity check if the reference table is not
  available in the metadata.
- Correct SQL: `SELECT COUNT(*) FROM catalog.schema.table t WHERE t.fk_col NOT IN (SELECT pk_col FROM catalog.schema.ref_table)`

## Anti-Patterns — Never Do These
- NEVER use {table}, <table>, {column}, <column_name>, or any placeholder in SQL.
- NEVER generate any rule for a column whose name starts with "aud_".
- Do NOT recommend Uniqueness on foreign key columns.
- Do NOT recommend Range on string or timestamp columns.
- Do NOT generate Referential_Integrity if the reference table is not in metadata.
- Do NOT generate LoV unless both distinct_count and pct_distinct signals are low.
- Do NOT use any severity value other than WARNING.
- Do NOT use the data_source field from the metadata — always take it from user
  context, or default to 'system'.
