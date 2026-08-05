#!/usr/bin/env zsh -i
source tests/lib.sh

AGENT_TAG="${SUPPORTED_MESSAGE_TAGS[agent]:?'agent' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running agents tests..."
DATA_FILE=$(claude_fixture tests/data/synthetic_agents.jsonl)

# =============================================================================
# Test 1 (positive): -a flag shows agent messages with correct structure
# =============================================================================
echo "Test 1: -a shows agent messages..."
OUTPUT=$($CC_CMD -a "$DATA_FILE" --color=never 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "<${AGENT_TAG}"
assert_contains "$OUTPUT" "## Agent"
assert_contains "$OUTPUT" 'agent_id="agent-abc-123"'
assert_contains "$OUTPUT" 'model="sonnet-4-5-20250929"'
assert_contains "$OUTPUT" "Agent research complete: found 3 relevant files."
echo "  ✓ -a flag shows agent messages with correct tag, header, and attributes"

# =============================================================================
# Test 2 (positive): -A (all) includes agent messages
# =============================================================================
echo "Test 2: -A includes agent messages..."
OUTPUT=$($CC_CMD -A "$DATA_FILE" --color=never 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "<${AGENT_TAG}"
assert_contains "$OUTPUT" "Agent research complete: found 3 relevant files."
echo "  ✓ -A includes agent messages"

# =============================================================================
# Test 3 (negative): bare parse and parse -t do NOT output agent messages
# =============================================================================
echo "Test 3a: bare parse does not show agent messages..."
OUTPUT=$($CC_CMD "$DATA_FILE" --color=never 2>/dev/null)
assert_success
assert_not_contains "$OUTPUT" "<${AGENT_TAG}"
assert_not_contains "$OUTPUT" "Agent research complete"
echo "  ✓ bare parse does not show agents"

echo "Test 3b: -t does not show agent messages..."
OUTPUT=$($CC_CMD -t "$DATA_FILE" --color=never 2>/dev/null)
assert_success
assert_not_contains "$OUTPUT" "<${AGENT_TAG}"
assert_not_contains "$OUTPUT" "Agent research complete"
echo "  ✓ -t does not show agents"

echo "✅ Agents tests passed"
