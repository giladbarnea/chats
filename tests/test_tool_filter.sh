#!/usr/bin/env zsh
source tests/lib.sh

TEST_DATA="tests/data/tool_filter_data.jsonl"

# Create synthetic data with two different tools
echo '{"type":"user","message":{"role":"user","content":"Run some tools"},"timestamp":"2025-01-01T12:00:00Z"}' > "$TEST_DATA"
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_bash","name":"Bash","input":{"command":"ls"}},{"type":"tool_use","id":"toolu_read","name":"Read","input":{"file_path":"test.txt"}}]},"timestamp":"2025-01-01T12:00:01Z"}' >> "$TEST_DATA"
echo '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"file1"},{"type":"tool_result","tool_use_id":"toolu_read","content":"content"}]},"timestamp":"2025-01-01T12:00:02Z"}' >> "$TEST_DATA"

echo "Testing Tool Filtering CLI..."

# 1. Filter Include "Bash"
echo "Testing -t Bash..."
OUTPUT=$($CC_CMD -t Bash "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_not_contains "$OUTPUT" 'name="Read"'
# Result check (Bash result should be visible, Read result should be hidden)
# The output format for results is <tool-output ...>content</tool-output>
# We can check for the content "file1" (Bash) and "content" (Read)
assert_contains "$OUTPUT" "file1"
assert_not_contains "$OUTPUT" "content"

# 2. Filter Exclude "!Bash" (should show Read)
echo "Testing -t !Bash..."
OUTPUT=$($CC_CMD -t \!Bash "$TEST_DATA")
assert_success
assert_not_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" 'name="Read"'
assert_not_contains "$OUTPUT" "file1"
assert_contains "$OUTPUT" "content"

# 3. Standard -t (Show all)
echo "Testing -t (All)..."
OUTPUT=$($CC_CMD -t "$TEST_DATA")
assert_success
assert_contains "$OUTPUT" 'name="Bash"'
assert_contains "$OUTPUT" 'name="Read"'

# Cleanup
rm "$TEST_DATA"

echo "✅ Tool filter CLI tests passed"
