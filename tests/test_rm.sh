#!/usr/bin/env zsh
#
# Minimal CLI seam tests for rm command.
# Verifies shell->Python interface works.
# Logic tests are in test_rm.py
#
source tests/lib.sh

echo "Running rm CLI seam tests..."

# Setup: Create temp directory structure mimicking ~/.claude/
TEMP_HOME=$(mktemp -d)
TEMP_CLAUDE="$TEMP_HOME/.claude"
TEMP_PROJECTS="$TEMP_CLAUDE/projects/test-project"
mkdir -p "$TEMP_PROJECTS"
trap "rm -rf $TEMP_HOME" EXIT

# Helper: create a test session
create_test_session() {
  local session_id="$1"
  cat > "$TEMP_PROJECTS/${session_id}.jsonl" << EOF
{"type":"summary","summary":"Test session ${session_id}","leafUuid":"leaf-${session_id}"}
{"type":"user","message":{"role":"user","content":"Hello"},"sessionId":"${session_id}"}
EOF
}

# =============================================================================
# Test 1: Basic invocation (rm subcommand works)
# =============================================================================
echo "Test 1: Basic rm invocation..."
create_test_session "test1-session"
OUTPUT=$(echo "y" | HOME="$TEMP_HOME" $CC_CMD rm "$TEMP_PROJECTS/test1-session.jsonl" 2>&1)
assert_success
echo "$OUTPUT" | grep -q "Removed session"
if [[ -f "$TEMP_PROJECTS/test1-session.jsonl" ]]; then
  echo "❌ File should have been removed"
  exit 1
fi
echo "  ✓ Test 1 passed"

# =============================================================================
# Test 2: Dry run mode (--dry-run / -n)
# =============================================================================
echo "Test 2: Dry run mode..."
create_test_session "test2-session"
OUTPUT=$(HOME="$TEMP_HOME" $CC_CMD rm -n "$TEMP_PROJECTS/test2-session.jsonl" 2>&1)
assert_success
echo "$OUTPUT" | grep -q "Dry run"
if [[ ! -f "$TEMP_PROJECTS/test2-session.jsonl" ]]; then
  echo "❌ File should NOT have been removed in dry run"
  exit 1
fi
echo "  ✓ Test 2 passed"

# =============================================================================
# Test 3: Exit code on error (nonexistent session)
# =============================================================================
echo "Test 3: Exit code on error..."
HOME="$TEMP_HOME" $CC_CMD rm "nonexistent-session-uuid" 2>/dev/null
if [[ $? -eq 0 ]]; then
  echo "❌ Expected non-zero exit for nonexistent session"
  exit 1
fi
echo "  ✓ Test 3 passed"

# =============================================================================
# Test 4: Output contains session ID
# =============================================================================
echo "Test 4: Output contains session ID..."
create_test_session "test4-session"
OUTPUT=$(echo "y" | HOME="$TEMP_HOME" $CC_CMD rm "$TEMP_PROJECTS/test4-session.jsonl" 2>&1)
assert_success
assert_contains "$OUTPUT" "test4-session"
echo "  ✓ Test 4 passed"

# =============================================================================
# Test 5: Resolve by UUID
# =============================================================================
echo "Test 5: Resolve by UUID..."
create_test_session "test5-session-uuid"
OUTPUT=$(echo "y" | HOME="$TEMP_HOME" $CC_CMD rm "test5-session-uuid" 2>&1)
assert_success
echo "$OUTPUT" | grep -q "Removed session"
if [[ -f "$TEMP_PROJECTS/test5-session-uuid.jsonl" ]]; then
  echo "❌ File should have been removed"
  exit 1
fi
echo "  ✓ Test 5 passed"

echo "✅ Rm CLI seam tests passed"
