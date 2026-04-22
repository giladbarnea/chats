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

is_role_heading() {
    local line="$1"
    echo "$line" | grep -Eq '^[[:space:]]*#?[[:space:]]*(User|Assistant)[[:space:]]*$'
}

assert_no_double_blank_after_headings() {
    local label="$1" output="$2"
    local lineno=0
    local prev_line="" prev_prev_line=""

    while IFS= read -r line; do
        lineno=$((lineno + 1))
        if is_role_heading "$prev_prev_line"; then
            if [[ -z "$prev_line" && -z "$line" ]]; then
                echo "❌ [$label] Two blank lines after heading at line $((lineno - 2))"
                echo "  $((lineno-2)): |${prev_prev_line}|"
                echo "  $((lineno-1)): |${prev_line}|"
                echo "  $((lineno)):   |${line}|"
                exit 1
            fi
        fi
        prev_prev_line="$prev_line"
        prev_line="$line"
    done <<< "$output"
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
assert_contains "$output" "<tool-output"
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
assert_contains "$output" "User"
assert_contains "$output" "Assistant"
assert_not_contains "$output" "## User"
assert_not_contains "$output" "## Assistant"
echo "  ✓ Rich output contains headers"

# Test 5b: Rich headings use badge style (no heavy box drawing chars)
echo "Testing Rich headings use badge style..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
if echo "$output" | grep -qF "━"; then
    echo "❌ Heavy box drawing char found — expected badge-style headings, not full-width panel"
    exit 1
fi
echo "  ✓ Rich headings use badge style (no box chars)"

# Test 6: Rich output contains separators
echo "Testing Rich output contains separators..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "---"
echo "  ✓ Rich output contains separators"

# Test 7: Rich output whitespace matches plain output structure
# Regression test for: extra blank lines, leading spaces on tags, trailing blank lines before closing tags
echo "Testing Rich output whitespace structure matches plain..."
DATA_FILE_MOCK="tests/data/1e446a9f-08fd-43ac-be72-8ce337d01dcd.jsonl"
plain=$($CC_CMD --color=never --short --no-metadata "$DATA_FILE_MOCK" 2>/dev/null)
rich=$($CC_CMD --color=always --short --no-metadata "$DATA_FILE_MOCK" 2>/dev/null | decolor)

assert_no_double_blank_after_headings "rich" "$rich"

# Bug 2: No empty line between message content and closing tag
# In plain: "content\n</tag>". Rich should not have "content\n\n</tag>".
if [[ "$rich" == *$'\n\n</user-message'* ]]; then
    echo "❌ Bug 2: Empty line before </user-message> closing tag in Rich output"
    exit 1
fi
if [[ "$rich" == *$'\n\n</assistant-response'* ]]; then
    echo "❌ Bug 2: Empty line before </assistant-response> closing tag in Rich output"
    exit 1
fi

echo "  ✓ Rich output whitespace structure matches plain"

echo "✅ Structured rendering tests passed"
