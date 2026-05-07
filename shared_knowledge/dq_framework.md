# Data Quality Framework

## DQ Check Types and Dimensions

| Check Type             | Dimension                  | Applies To                        |
|------------------------|----------------------------|-----------------------------------|
| Null                   | Completeness               | Non-nullable columns, PK/FK cols  |
| Uniqueness             | Uniqueness / Entity Integrity | Business keys, primary keys    |
| Range                  | Validity                   | Numeric columns with bounded values |
| Format_Check           | Validity                   | Dates, text patterns, numeric formats |
| LoV                    | Validity                   | Low-cardinality categorical columns |
| Referential_Integrity  | Completeness               | FK columns with reference table available |

## Rule Generation Logic

### Null
- Apply to every non-nullable column and every primary/foreign key column.
- SQL pattern: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name IS NULL`
- Returns 0 on pass (no nulls), positive count on fail.

### Uniqueness
- Apply to business keys and primary keys only.
- Do NOT apply to foreign key columns — they are many-to-one by design.
- SQL pattern: `SELECT COUNT(*) - COUNT(DISTINCT column_name) FROM catalog.schema.table`
- Returns 0 on pass (no duplicates), positive count on fail.

### Range
- Apply to numeric columns where metadata suggests bounded valid values.
- Infer min and max bounds from available profiling stats (Minimum Value, Maximum Value).
- Do NOT apply to string or timestamp columns.
- SQL pattern: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name < <min> OR column_name > <max>`
- Returns 0 on pass, count of out-of-range values on fail.

### Format_Check
- Apply to columns expected to follow a pattern: dates, emails, phone numbers, postal codes, etc.
- Always use a regex-based SQL test regardless of data type.
- Infer the expected regex from column name, data type, and available Patterns or sample values.
- SQL pattern: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name NOT RLIKE '<regex>'`
- Returns 0 on pass, count of non-conforming values on fail.

### LoV (List of Values)
- Apply only when BOTH #Distinct is low in absolute terms AND %Distinct is low relative to row count.
- Use judgment on the combination of both signals — not a fixed threshold.
- Infer allowed values from Top_Values or sample values in profiling stats.
- SQL pattern: `SELECT COUNT(*) FROM catalog.schema.table WHERE column_name NOT IN ('val1','val2','val3')`
- Returns 0 on pass, count of values outside the allowed list on fail.

### Referential_Integrity
- Apply only when the referenced table is present in the loaded metadata.
- Infer FK relationships from <name>_id column naming patterns.
- SQL pattern: `SELECT COUNT(*) FROM catalog.schema.table t WHERE t.fk_col NOT IN (SELECT pk_col FROM catalog.schema.ref_table)`
- Returns 0 on pass, count of unmatched FK values on fail.

## Severity
- All rules use severity: WARNING.
- No blocking or critical severity levels are used.

## SQL Standards
- Always use fully qualified table names: catalog.schema.table_name.
- Never use placeholders such as {table}, <table>, {column}, or <column_name>.
- All SQL must be immediately executable with no substitution required.
- All SQL must return a single integer: 0 = pass, positive integer = failure count.

## Output Fields
- data_source: inferred from metadata, defaults to 'system' if not determinable.
- table_name: exact table name from metadata.
- attribute_name: column name, or null for table-level rules.
- check_type: one of the six types listed above.
- severity: always WARNING.
- dimension: Validity, Completeness, or Uniqueness.
- sql: fully executable SQL using real table name.
- lov_values_comments: for LoV checks — list allowed values as a,b,c,...
                        for all other checks — a very short note on what is being checked.
