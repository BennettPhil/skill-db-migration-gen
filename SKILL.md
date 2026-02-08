---
name: db-migration-gen
description: Generate SQL migration files by diffing two database schema states with up/down migrations.
version: 0.1.0
license: Apache-2.0
---

# Database Migration Generator

## Purpose

Compares two SQL schema files (old and new) and generates migration SQL with both up and down statements. Detects added/removed tables and columns. Supports PostgreSQL and SQLite dialects.

## Contract

Behavioral guarantees (tested in `scripts/test.sh`):
- Detects added columns and generates ALTER TABLE ADD COLUMN
- Detects new tables and generates CREATE TABLE
- Generates DOWN migration to reverse changes
- Identical schemas produce "No changes" message
- Dry-run mode shows changes without writing files
- Supports `--dialect sqlite` and `--dialect postgresql`

## Inputs

- **Positional**: Two SQL schema files (old schema, new schema)
- **`--dialect`**: `sqlite` or `postgresql` (default: `sqlite`)
- **`--dry-run`**: Show changes without writing to file
- **`--output`**: Write migration to file instead of stdout

## Outputs

SQL migration with `-- Up` and `-- Down` sections.

## Error Handling

- Exit 1: Missing arguments, file not found
- Exit 0: Success (even with no changes)

## Testing

```bash
bash scripts/test.sh
```
