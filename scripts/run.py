#!/usr/bin/env python3
"""Generate SQL migration files by diffing two database schema states."""

import re
import sys
from pathlib import Path


def parse_schema(sql: str) -> dict[str, dict[str, str]]:
    """Parse CREATE TABLE statements into a dict of tables -> columns."""
    tables = {}
    # Find all CREATE TABLE blocks
    pattern = re.compile(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);',
        re.DOTALL | re.IGNORECASE
    )
    for match in pattern.finditer(sql):
        table_name = match.group(1)
        body = match.group(2)
        columns = {}
        for line in body.split(","):
            line = line.strip()
            if not line:
                continue
            # Skip constraints that aren't column definitions
            upper = line.upper()
            if any(upper.startswith(kw) for kw in ["PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT"]):
                continue
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_def = " ".join(parts[1:])
                columns[col_name] = col_def
        tables[table_name] = columns
    return tables


def diff_schemas(old: dict, new: dict) -> dict:
    """Compare two schema dicts and return differences."""
    changes = {
        "added_tables": {},
        "removed_tables": {},
        "added_columns": {},
        "removed_columns": {},
    }

    # Find added and removed tables
    for table in new:
        if table not in old:
            changes["added_tables"][table] = new[table]
    for table in old:
        if table not in new:
            changes["removed_tables"][table] = old[table]

    # Find added and removed columns in existing tables
    for table in new:
        if table in old:
            for col in new[table]:
                if col not in old[table]:
                    changes["added_columns"].setdefault(table, {})[col] = new[table][col]
            for col in old[table]:
                if col not in new[table]:
                    changes["removed_columns"].setdefault(table, {})[col] = old[table][col]

    return changes


def generate_migration(changes: dict, dialect: str) -> str:
    """Generate up and down SQL from schema diff."""
    up_lines = ["-- Up"]
    down_lines = ["-- Down"]

    has_changes = False

    # Added tables
    for table, columns in changes["added_tables"].items():
        has_changes = True
        cols = ",\n    ".join(f"{name} {defn}" for name, defn in columns.items())
        up_lines.append(f"CREATE TABLE {table} (\n    {cols}\n);")
        down_lines.append(f"DROP TABLE IF EXISTS {table};")

    # Removed tables
    for table, columns in changes["removed_tables"].items():
        has_changes = True
        cols = ",\n    ".join(f"{name} {defn}" for name, defn in columns.items())
        up_lines.append(f"DROP TABLE IF EXISTS {table};")
        down_lines.append(f"CREATE TABLE {table} (\n    {cols}\n);")

    # Added columns
    for table, columns in changes["added_columns"].items():
        has_changes = True
        for col, defn in columns.items():
            up_lines.append(f"ALTER TABLE {table} ADD COLUMN {col} {defn};")
            if dialect == "sqlite":
                # SQLite doesn't support DROP COLUMN in older versions
                down_lines.append(f"-- SQLite: ALTER TABLE {table} DROP COLUMN {col}; (requires SQLite 3.35+)")
            else:
                down_lines.append(f"ALTER TABLE {table} DROP COLUMN {col};")

    # Removed columns
    for table, columns in changes["removed_columns"].items():
        has_changes = True
        for col, defn in columns.items():
            if dialect == "sqlite":
                up_lines.append(f"-- SQLite: ALTER TABLE {table} DROP COLUMN {col}; (requires SQLite 3.35+)")
            else:
                up_lines.append(f"ALTER TABLE {table} DROP COLUMN {col};")
            down_lines.append(f"ALTER TABLE {table} ADD COLUMN {col} {defn};")

    if not has_changes:
        return "-- No changes detected\n"

    return "\n".join(up_lines) + "\n\n" + "\n".join(down_lines) + "\n"


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("Usage: run.py [OPTIONS] <old-schema.sql> <new-schema.sql>")
        print()
        print("Generate SQL migration by diffing two schema files.")
        print()
        print("Options:")
        print("  --dialect DIALECT  SQL dialect: sqlite, postgresql (default: sqlite)")
        print("  --dry-run          Show changes without generating migration")
        print("  --output PATH      Write migration to file")
        print("  -h, --help         Show this help")
        sys.exit(0)

    dialect = "sqlite"
    dry_run = False
    output_path = None
    files = []

    i = 0
    while i < len(args):
        if args[i] == "--dialect" and i + 1 < len(args):
            dialect = args[i + 1]; i += 2
        elif args[i] == "--dry-run":
            dry_run = True; i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]; i += 2
        else:
            files.append(args[i]); i += 1

    if len(files) < 2:
        print("Error: two schema files required (old and new).", file=sys.stderr)
        sys.exit(1)

    old_path = Path(files[0])
    new_path = Path(files[1])

    if not old_path.exists():
        print(f"Error: file not found: {files[0]}", file=sys.stderr)
        sys.exit(1)
    if not new_path.exists():
        print(f"Error: file not found: {files[1]}", file=sys.stderr)
        sys.exit(1)

    old_schema = parse_schema(old_path.read_text())
    new_schema = parse_schema(new_path.read_text())
    changes = diff_schemas(old_schema, new_schema)

    has_changes = any(v for v in changes.values())

    if not has_changes:
        print("No changes detected between schemas.")
        sys.exit(0)

    if dry_run:
        print("=== DRY RUN ===")
        print()
        if changes["added_tables"]:
            print(f"Tables to add: {', '.join(changes['added_tables'].keys())}")
        if changes["removed_tables"]:
            print(f"Tables to remove: {', '.join(changes['removed_tables'].keys())}")
        if changes["added_columns"]:
            for table, cols in changes["added_columns"].items():
                print(f"Columns to add in {table}: {', '.join(cols.keys())}")
        if changes["removed_columns"]:
            for table, cols in changes["removed_columns"].items():
                print(f"Columns to remove from {table}: {', '.join(cols.keys())}")
        sys.exit(0)

    migration = generate_migration(changes, dialect)

    if output_path:
        Path(output_path).write_text(migration)
        print(f"Migration written to {output_path}", file=sys.stderr)
    else:
        print(migration, end="")


if __name__ == "__main__":
    main()
