# db-migration-gen

Generate SQL migration files by comparing two database schema states.

## Quick Start

```bash
python3 scripts/run.py old_schema.sql new_schema.sql
```

## Testing

```bash
bash scripts/test.sh
```

Tests are the source of truth for behavior. All edge cases and error conditions are defined in the test suite.

## Prerequisites

- Python 3.10+
- No external dependencies
