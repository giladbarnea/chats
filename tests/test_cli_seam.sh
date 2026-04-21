#!/usr/bin/env zsh
#
# Minimal CLI seam tests - verifies shell->Python interface works.
# Logic tests are in test_slice_notation.py
#
source tests/lib.sh

USER_MESSAGE_TAG="${SUPPORTED_MESSAGE_TAGS[user-message]:?'user-message' not in SUPPORTED_MESSAGE_TAGS}"
ASSISTANT_RESPONSE_TAG="${SUPPORTED_MESSAGE_TAGS[assistant-response]:?'assistant-response' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running CLI seam tests..."

# Test 1: Basic invocation with file and slice
echo "Test 1: Basic invocation (file + slice)..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" "1" --color=never 2>/dev/null)
assert_success
if ! printf '%s\n' "$OUTPUT" | grep -Eq "^<(${PIPE_JOINED_USER_ORIGIN_MESSAGE_TAGS})"; then
  echo "❌ Expected first sliced message to render as a user-origin wrapper"
  exit 1
fi

# Test 2: Slice argument ordering - slice after flags
echo "Test 2: Slice after flags..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" --color=never "1" 2>/dev/null)
assert_success
if ! printf '%s\n' "$OUTPUT" | grep -Eq "^<(${PIPE_JOINED_USER_ORIGIN_MESSAGE_TAGS})"; then
  echo "❌ Expected first sliced message to render as a user-origin wrapper"
  exit 1
fi

# Test 3: Negative slice with -- separator
echo "Test 3: Negative slice with -- separator..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" -- "-1" --color=never 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "<${ASSISTANT_RESPONSE_TAG}"

# Test 4: Error exit code for invalid input
echo "Test 4: Error exit code for index 0..."
$CC_CMD "$DATA_FILE_SIMPLE" "0" --color=never 2>/dev/null
if [[ $? -eq 0 ]]; then
  echo "❌ Expected non-zero exit for invalid index 0"
  exit 1
fi

# Test 5: JSON format output
echo "Test 5: JSON format output..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" "1" --color=never -f json 2>/dev/null)
assert_success
assert_contains "$OUTPUT" '"role":'

# Test 6: Negative session index resolves as input, not slice
echo "Test 6: Negative session index input..."
TEMP_HOME=$(mktemp -d)
TEMP_PROJECTS="$TEMP_HOME/.claude/projects/test-project"
mkdir -p "$TEMP_PROJECTS"
cp tests/data/rename_fixtures/projects/test-project/*.jsonl "$TEMP_PROJECTS"/

# Oldest -> newest main conversations
touch -t 202401010101 "$TEMP_PROJECTS/aaaa1111-with-summary.jsonl"
touch -t 202401010102 "$TEMP_PROJECTS/bbbb2222-without-summary.jsonl"
touch -t 202401010103 "$TEMP_PROJECTS/cccc3333-ambiguous-alpha.jsonl"
touch -t 202401010104 "$TEMP_PROJECTS/dddd4444-ambiguous-beta.jsonl"

# Newer agent file must not steal the recent-session selector
cat > "$TEMP_PROJECTS/agent-newest.jsonl" << 'EOF'
{"type":"user","sessionId":"dddd4444-ambiguous-beta","message":{"role":"user","content":"agent noise"}}
EOF
touch -t 202401010199 "$TEMP_PROJECTS/agent-newest.jsonl"

OUTPUT=$(HOME="$TEMP_HOME" $CC_CMD -1 --color=never 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "session_id: dddd4444-ambiguous-beta"

# Test 7: Bare -t must not steal the recent session selector
echo "Test 7: Negative session index after bare -t..."
OUTPUT=$(HOME="$TEMP_HOME" $CC_CMD -t -1 --color=never 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "session_id: dddd4444-ambiguous-beta"

rm -rf "$TEMP_HOME"

# Test 8: Multiple message selectors are ORed
echo "Test 8: Multiple message selectors..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" "1" "2" --color=never --no-metadata 2>/dev/null)
assert_success
if [[ "$(count_user_origin_tags "$OUTPUT")" != "2" ]]; then
  echo "❌ Expected two user-origin messages from selectors 1 and 2"
  exit 1
fi
assert_not_contains "$OUTPUT" "<${ASSISTANT_RESPONSE_TAG} i=\"3\""

# Test 9: Range and negative selectors are ORed
echo "Test 9: Range and negative message selectors..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" "1:3" "-1" --color=never --no-metadata 2>/dev/null)
assert_success
MATCHED_TAG_COUNT=$(printf '%s\n' "$OUTPUT" | grep -E "^<(${PIPE_JOINED_MESSAGE_TAGS})" -c || true)
if [[ "$MATCHED_TAG_COUNT" != "3" ]]; then
  echo "❌ Expected three messages from selectors 1:3 and -1"
  exit 1
fi
assert_contains "$OUTPUT" "<${ASSISTANT_RESPONSE_TAG} i=\"3\""

echo "✅ CLI seam tests passed"
