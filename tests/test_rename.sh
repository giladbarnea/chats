#!/usr/bin/env zsh
#
# Minimal CLI seam tests for rename command.
# Verifies shell->Python interface works.
# Logic tests are in test_rename.py
#
source tests/lib.sh

echo "Running rename CLI seam tests..."

# Setup: Create temp directory structure mimicking ~/.claude/
TEMP_HOME=$(mktemp -d)
TEMP_CLAUDE="$TEMP_HOME/.claude"
TEMP_PROJECTS="$TEMP_CLAUDE/projects/test-project"
mkdir -p "$TEMP_PROJECTS"
trap "rm -rf $TEMP_HOME" EXIT

DATA_WITH_SUMMARY="tests/data/rename_with_summary.jsonl"

# Helper: copy fixture to temp projects dir and return path
setup_fixture() {
  local src="$1"
  local name="$2"
  local dest="$TEMP_PROJECTS/$name"
  cp "$src" "$dest"
  echo "$dest"
}

# =============================================================================
# Test 1: Basic invocation (rename subcommand works)
# =============================================================================
echo "Test 1: Basic rename invocation..."
FIXTURE=$(setup_fixture "$DATA_WITH_SUMMARY" "test1.jsonl")
HOME="$TEMP_HOME" $CC_CMD rename "$FIXTURE" "Test Name" 2>&1
assert_success
echo "  ✓ Test 1 passed"

# =============================================================================
# Test 2: Exit code on error (empty name)
# =============================================================================
echo "Test 2: Exit code on error..."
FIXTURE=$(setup_fixture "$DATA_WITH_SUMMARY" "test2.jsonl")
HOME="$TEMP_HOME" $CC_CMD rename "$FIXTURE" "" 2>/dev/null
if [[ $? -eq 0 ]]; then
  echo "❌ Expected non-zero exit for empty name"
  exit 1
fi
echo "  ✓ Test 2 passed"

# =============================================================================
# Test 3: Output contains confirmation
# =============================================================================
echo "Test 3: Output contains new name..."
FIXTURE=$(setup_fixture "$DATA_WITH_SUMMARY" "test3.jsonl")
OUTPUT=$(HOME="$TEMP_HOME" $CC_CMD rename "$FIXTURE" "Confirmed Name" 2>&1)
assert_success
assert_contains "$OUTPUT" "Confirmed Name"
echo "  ✓ Test 3 passed"

# =============================================================================
# Test 4: Dry run prints name without modifying file
# =============================================================================
echo "Test 4: Dry run prints name without modifying file..."
FIXTURE=$(setup_fixture "$DATA_WITH_SUMMARY" "test4.jsonl")
ORIGINAL_CONTENT=$(cat "$FIXTURE")
OUTPUT=$(HOME="$TEMP_HOME" $CC_CMD rename -n "$FIXTURE" "Preview Name" 2>&1)
assert_success
if [[ "$OUTPUT" != $'Preview Name' && "$OUTPUT" != $'Preview Name\n' ]]; then
  echo "❌ Dry run should print only the preview name"
  printf 'Got:\n%s\n' "$OUTPUT"
  exit 1
fi
CURRENT_CONTENT=$(cat "$FIXTURE")
if [[ "$CURRENT_CONTENT" != "$ORIGINAL_CONTENT" ]]; then
  echo "❌ Dry run modified the session file"
  exit 1
fi
assert_not_contains "$OUTPUT" "Renamed"
echo "  ✓ Test 4 passed"

echo "✅ Rename CLI seam tests passed"
