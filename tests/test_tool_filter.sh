#!/usr/bin/env zsh
source tests/lib.sh

TEST_DATA="tests/data/tool_filter_data.jsonl"

# Create synthetic data: two tool_use + two tool_result (one is an error)
echo '{"type":"user","message":{"role":"user","content":"Run some tools"},"timestamp":"2025-01-01T12:00:00Z"}' > "$TEST_DATA"
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_bash","name":"Bash","input":{"command":"ls"}},{"type":"tool_use","id":"toolu_read","name":"Read","input":{"file_path":"test.txt"}}]},"timestamp":"2025-01-01T12:00:01Z"}' >> "$TEST_DATA"
echo '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"file1","is_error":true},{"type":"tool_result","tool_use_id":"toolu_read","content":"readcontent"}]},"timestamp":"2025-01-01T12:00:02Z"}' >> "$TEST_DATA"

echo "Testing Tool Filtering CLI..."

# =============================================================================
# Backward-compatible: existing syntax
# =============================================================================

# 1. Filter Include "Bash"
echo "Testing -t Bash..."
OUTPUT=$($CC_CMD -t Bash "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_not_contains "$OUTPUT" 'name="Read"'
assert_contains "$OUTPUT" "file1"
assert_not_contains "$OUTPUT" "readcontent"

# 2. Filter Exclude "!Bash" (should show Read)
echo "Testing -t '!Bash'..."
OUTPUT=$($CC_CMD -t \!Bash "$TEST_DATA")
assert_success
assert_not_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" 'name="Read"'
assert_not_contains "$OUTPUT" "file1"
assert_contains "$OUTPUT" "readcontent"

# 3. Standard -t (Show all)
echo "Testing -t (All)..."
OUTPUT=$($CC_CMD -t "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" 'name="Read"'

# =============================================================================
# New: direction modifiers
# =============================================================================

# 4. Direction: output only
echo "Testing -t o ..."
OUTPUT=$($CC_CMD -t o "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "tool-output"
assert_not_contains "$OUTPUT" "tool-input"

# 5. Direction: input only
echo "Testing -t i ..."
OUTPUT=$($CC_CMD -t i "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "tool-input"
assert_not_contains "$OUTPUT" "tool-output"

# 6. Name + direction: Bash inputs only
echo "Testing -t Bash:i ..."
OUTPUT=$($CC_CMD -t Bash:i "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" "tool-input"
assert_not_contains "$OUTPUT" "tool-output"
assert_not_contains "$OUTPUT" 'name="Read"'

# 7. Name + direction: Read outputs only
echo "Testing -t Read:o ..."
OUTPUT=$($CC_CMD -t Read:o "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "tool-output"
assert_contains "$OUTPUT" "readcontent"
assert_not_contains "$OUTPUT" "tool-input"
assert_not_contains "$OUTPUT" "file1"

# 8. Long form modifier
echo "Testing -t output (long form)..."
OUTPUT=$($CC_CMD -t output "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "tool-output"
assert_not_contains "$OUTPUT" "tool-input"

# =============================================================================
# New: order independence
# =============================================================================

# 9. Reversed order: i:Bash == Bash:i
echo "Testing -t i:Bash (reversed order)..."
OUTPUT=$($CC_CMD -t i:Bash "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" "tool-input"
assert_not_contains "$OUTPUT" "tool-output"
assert_not_contains "$OUTPUT" 'name="Read"'

# =============================================================================
# New: error filter
# =============================================================================

# 10. Error only
echo "Testing -t e ..."
OUTPUT=$($CC_CMD -t e "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "is_error"
assert_contains "$OUTPUT" "file1"
assert_not_contains "$OUTPUT" "readcontent"

# =============================================================================
# New: negation with modifiers
# =============================================================================

# 11. !Bash:o → everything except Bash output (Bash input + Read input + Read output)
echo "Testing -t '!Bash:o' ..."
OUTPUT=$($CC_CMD -t \!Bash:o "$TEST_DATA")
assert_success
# Should have Bash input (tool-input name="Bash")
assert_contains "$OUTPUT" 'name="Bash"'
# Should have Read input + output
assert_contains "$OUTPUT" 'name="Read"'
assert_contains "$OUTPUT" "readcontent"
# Should NOT have Bash output (file1 is in the Bash error result)
assert_not_contains "$OUTPUT" "file1"

# =============================================================================
# New: shortening modifier
# =============================================================================

# 12. -t s → all tools, shortened
echo "Testing -t s (shortened)..."
OUTPUT=$($CC_CMD -t s "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" "tool-input"
assert_contains "$OUTPUT" "tool-output"

# Cleanup
rm "$TEST_DATA"

echo "✅ Tool filter CLI tests passed"
