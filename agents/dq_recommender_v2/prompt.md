## Task
{{task}}

## Table Metadata
```json
{{metadata}}
```

## User Context
{{context}}

## Instructions

1. Check whether profiling statistics are present in the metadata for each column.
   Profiling stats include fields such as: pct_null, null_count, distinct_count,
   pct_distinct, non_distinct_count, pct_non_distinct, minimum_value, maximum_value,
   inferred_datatype.
   If profiling stats are present, use them as the primary basis for rule generation.
   If only schema metadata is present (column name, documented_datatype, nullable),
   fall back to inferring rules from column names and data types alone.

2. Skip any column whose name starts with "aud_". Do not generate any rule for
   audit columns regardless of what other metadata is present.

3. Use the data_source value from the user context if provided.
   If it is absent or blank, set data_source to 'system' for all rules.

4. For each non-audit column, apply the following rule selection logic:

   Null:
   - Apply to every non-nullable column and every primary/foreign key column.
   - If pct_null is available: generate the rule when pct_null is 0 (confirmed
     no nulls) or when the column is non-nullable by definition.

   Uniqueness:
   - Apply to business keys and primary key columns only.
   - If pct_distinct is available: generate when pct_distinct is at or near 100%.
   - Never apply to foreign key columns.

   Range:
   - Apply to numeric columns where min and max values suggest bounded valid ranges.
   - If minimum_value and maximum_value are available from profiling: use them
     as the bounds. If only schema is available: infer from column name and type.
   - Do NOT apply to string or timestamp columns.

   Format_Check:
   - Apply to columns expected to follow a pattern: dates, emails, phone numbers,
     postal codes, IDs, codes, and similar.
   - Use inferred_datatype where available to select the appropriate regex.
   - If only schema is available: infer from column name and documented_datatype.
   - Always generate a regex-based SQL test regardless of data type.

   LoV:
   - Apply only when BOTH distinct_count is low in absolute terms AND pct_distinct
     is low relative to total rows. Use judgment on the combination of both signals.
   - If only schema is available: only generate LoV for columns where the name
     strongly implies a fixed set (e.g. status, type, category, flag columns).

   Referential_Integrity:
   - Apply only when the referenced table is present in the loaded metadata.
   - Infer FK relationships from <name>_id column naming patterns.
   - Do NOT generate if the reference table is not available.

5. Write fully executable SQL for each rule using the real fully qualified table
   name. SQL must return 0 on pass and a positive integer (failure count) on fail.

6. Set severity to WARNING for every rule without exception.

7. For the lov_values_comments field:
   - LoV check: list the inferred allowed values as: a,b,c,...
   - All other checks: include a very short note on what the rule is checking.

8. CRITICAL: Return ONLY valid JSON. Do not include markdown fences, explanations, comments, or   additional text.
