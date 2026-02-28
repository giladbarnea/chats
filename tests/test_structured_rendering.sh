#!/usr/bin/env zsh -i
source tests/lib.sh

USER_MESSAGE_TAG="${SUPPORTED_MESSAGE_TAGS[user-message]:?'user-message' not in SUPPORTED_MESSAGE_TAGS}"
ASSISTANT_RESPONSE_TAG="${SUPPORTED_MESSAGE_TAGS[assistant-response]:?'assistant-response' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running structured rendering tests..."
DATA_FILE_SYNTHETIC="tests/data/synthetic_flags.jsonl"
GOLDEN_FILE="tests/data/golden_xml_output.txt"

# Helper: strip ANSI codes
strip_ansi() {
    sed 's/\x1b\[[0-9;]*m//g'
}

# Test 1: XML output unchanged (regression prevention)
echo "Testing XML output unchanged (golden reference)..."
actual=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=never 2>/dev/null)
expected=$(cat "$GOLDEN_FILE")
if [[ "$actual" != "$expected" ]]; then
    echo "❌ XML output differs from golden reference"
    echo "=== EXPECTED ==="
    echo "$expected" | head -20
    echo "=== ACTUAL ==="
    echo "$actual" | head -20
    exit 1
fi
echo "  ✓ XML output matches golden reference"

# Test 2: Rich output contains thinking content
echo "Testing Rich output contains thinking..."
output=$($CC_CMD -T "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "<thinking>"
assert_contains "$output" "</thinking>"
assert_contains "$output" "I should reply hello"
echo "  ✓ Rich output contains thinking"

# Test 3: Rich output contains tool content
echo "Testing Rich output contains tools..."
output=$($CC_CMD -t "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "<tool-input"
assert_contains "$output" "</tool-input>"
assert_contains "$output" "<tool-output>"
assert_contains "$output" "</tool-output>"
assert_contains "$output" "result"
echo "  ✓ Rich output contains tools"

# Test 4: Rich/XML structural equivalence
echo "Testing Rich/XML tag count equivalence..."
xml_output=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=never 2>/dev/null)
rich_output=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)

for tag in "<${USER_MESSAGE_TAG}" "</${USER_MESSAGE_TAG}>" "<${ASSISTANT_RESPONSE_TAG}" "</${ASSISTANT_RESPONSE_TAG}>" \
           "<thinking>" "</thinking>" "<tool-input" "</tool-input>" "<tool-output>" "</tool-output>"; do
    xml_count=$(echo "$xml_output" | grep -c "$tag" || echo 0)
    rich_count=$(echo "$rich_output" | grep -c "$tag" || echo 0)
    if [[ "$xml_count" != "$rich_count" ]]; then
        echo "❌ Tag count mismatch for $tag: XML=$xml_count, Rich=$rich_count"
        exit 1
    fi
done
echo "  ✓ Rich/XML tag counts match"

# Test 5: Rich output contains headers
echo "Testing Rich output contains headers..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "# User"
assert_contains "$output" "# Assistant"
echo "  ✓ Rich output contains headers"

# Test 6: Rich output contains separators
echo "Testing Rich output contains separators..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "---"
echo "  ✓ Rich output contains separators"

echo "✅ Structured rendering tests passed"
