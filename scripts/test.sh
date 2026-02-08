#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=0
FAIL=0
TOTAL=0

pass() { ((PASS++)); ((TOTAL++)); echo "  PASS: $1"; }
fail() { ((FAIL++)); ((TOTAL++)); echo "  FAIL: $1 -- $2"; }

assert_exit_code() {
  local desc="$1" expected_code="$2"
  shift 2
  local actual_code=0
  "$@" >/dev/null 2>&1 || actual_code=$?
  if [ "$expected_code" -eq "$actual_code" ]; then pass "$desc"
  else fail "$desc" "expected exit $expected_code, got $actual_code"; fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if echo "$haystack" | grep -qF -- "$needle"; then pass "$desc"
  else fail "$desc" "output does not contain '$needle'"; fi
}

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Running tests for: db-migration-gen"
echo "================================"

# Create test schema files
cat > "$TMP_DIR/old.sql" << 'SQL1'
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id)
);
SQL1

cat > "$TMP_DIR/new.sql" << 'SQL2'
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    age INTEGER DEFAULT 0
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    user_id INTEGER REFERENCES users(id)
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    content TEXT NOT NULL
);
SQL2

echo ""
echo "Happy path:"

# Test: Detects added column
output=$(python3 "$SCRIPT_DIR/run.py" "$TMP_DIR/old.sql" "$TMP_DIR/new.sql" 2>&1)
assert_contains "detects added column age" "age" "$output"
assert_contains "detects added column body" "body" "$output"
assert_contains "detects new table comments" "comments" "$output"

# Test: Generates ALTER TABLE for added columns
assert_contains "generates ALTER TABLE" "ALTER TABLE" "$output"

# Test: Generates CREATE TABLE for new table
assert_contains "generates CREATE TABLE" "CREATE TABLE" "$output"

# Test: Down migration
assert_contains "includes down migration" "-- Down" "$output"

echo ""
echo "Edge cases:"

# Test: Identical schemas produce no changes
cat > "$TMP_DIR/same.sql" << 'SQLSAME'
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
SQLSAME
output=$(python3 "$SCRIPT_DIR/run.py" "$TMP_DIR/same.sql" "$TMP_DIR/same.sql" 2>&1)
assert_contains "identical schemas: no changes" "No changes" "$output"

# Test: Dry-run mode
output=$(python3 "$SCRIPT_DIR/run.py" --dry-run "$TMP_DIR/old.sql" "$TMP_DIR/new.sql" 2>&1)
assert_contains "dry-run shows changes" "DRY RUN" "$output"

# Test: SQLite dialect
output=$(python3 "$SCRIPT_DIR/run.py" --dialect sqlite "$TMP_DIR/old.sql" "$TMP_DIR/new.sql" 2>&1)
assert_contains "sqlite output includes ALTER" "ALTER TABLE" "$output"

echo ""
echo "Error cases:"

# Test: No arguments
assert_exit_code "fails with no args" 1 python3 "$SCRIPT_DIR/run.py"

# Test: Missing file
assert_exit_code "fails with missing file" 1 python3 "$SCRIPT_DIR/run.py" "$TMP_DIR/nonexistent.sql" "$TMP_DIR/new.sql"

# Test: Only one argument
assert_exit_code "fails with one arg" 1 python3 "$SCRIPT_DIR/run.py" "$TMP_DIR/old.sql"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[ "$FAIL" -eq 0 ] || exit 1
