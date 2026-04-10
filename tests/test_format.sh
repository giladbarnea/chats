#!/usr/bin/env zsh -i
source tests/lib.sh

USER_MESSAGE_TAG="${SUPPORTED_MESSAGE_TAGS[user-message]:?'user-message' not in SUPPORTED_MESSAGE_TAGS}"
ASSISTANT_RESPONSE_TAG="${SUPPORTED_MESSAGE_TAGS[assistant-response]:?'assistant-response' not in SUPPORTED_MESSAGE_TAGS}"
SESSION_RENAME_TAG="${SUPPORTED_MESSAGE_TAGS[session-rename]:?'session-rename' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running format tests (JSON output)..."

# Helper function to validate JSON
# Tries jq first, falls back to python if jq has issues
validate_json() {
  if ! printf '%s\n' "$1" | jq empty 2>/dev/null; then
    # jq failed, try python as fallback
    if printf '%s\n' "$1" | $PY_CMD -m json.tool >/dev/null 2>&1; then
      # Python validates OK, jq just has issues with some characters
      return 0
    else
      echo "❌ Invalid JSON output"
      exit 1
    fi
  fi
}

# Helper function to assert JSON is an array
assert_json_array() {
  local type=$(printf '%s\n' "$1" | jq -r 'type' 2>/dev/null || echo "error")
  if [[ "$type" != "array" ]]; then
    # Fallback to python check
    if printf '%s\n' "$1" | $PY_CMD -c "import json, sys; data=json.load(sys.stdin); sys.exit(0 if isinstance(data, list) else 1)" 2>/dev/null; then
      # Python confirms it's an array
      return 0
    fi
    echo "❌ Expected JSON array, got: $type"
    exit 1
  fi
}

# Helper function to count JSON array elements
json_array_length() {
  printf '%s\n' "$1" | jq 'length' 2>/dev/null || printf '%s\n' "$1" | $PY_CMD -c "import json, sys; print(len(json.load(sys.stdin)))"
}

# Helper function to get JSON array element field
json_get_field() {
  local json="$1"
  local index="$2"
  local field="$3"
  printf '%s\n' "$json" | jq -r ".[$index].$field" 2>/dev/null || printf '%s\n' "$json" | $PY_CMD -c "import json, sys; data=json.load(sys.stdin); print(data[$index]['$field'])"
}

# 1. Basic JSON output
echo "Testing -f json (basic)..."
# Capture output and filter metadata in one step
OUTPUT_JSON=$($CC_CMD -f json "$DATA_FILE_SIMPLE" 2>&1 | grep -v "^File:")
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "❌ Command failed with exit code $EXIT_CODE"
  echo "Output: $OUTPUT_JSON"
  exit 1
fi
validate_json "$OUTPUT_JSON"
assert_json_array "$OUTPUT_JSON"

# Check that output has expected structure
LENGTH=$(json_array_length "$OUTPUT_JSON")
if [[ $LENGTH -eq 0 ]]; then
  echo "❌ JSON output is empty array"
  exit 1
fi

# Check first message has required fields
FIRST_ROLE=$(json_get_field "$OUTPUT_JSON" 0 "role")
FIRST_CONTENT=$(json_get_field "$OUTPUT_JSON" 0 "content")

if [[ -z "$FIRST_ROLE" ]]; then
  echo "❌ First message missing 'role' field"
  exit 1
fi

if [[ -z "$FIRST_CONTENT" ]]; then
  echo "❌ First message missing 'content' field"
  exit 1
fi

# Role should be either 'user' or 'assistant'
if [[ "$FIRST_ROLE" != "user" && "$FIRST_ROLE" != "assistant" ]]; then
  echo "❌ Invalid role: $FIRST_ROLE (expected 'user' or 'assistant')"
  exit 1
fi


# 2. JSON output should have NO colors
echo "Testing JSON has no colors..."
assert_no_colors "$OUTPUT_JSON"


# 3. JSON with stdin
echo "Testing -f json with stdin..."
OUTPUT_JSON_STDIN=$(cat "$DATA_FILE_SIMPLE" | $CC_CMD -f json 2>&1 | grep -v "^File:")
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo "❌ Stdin test failed with exit code $EXIT_CODE"
  exit 1
fi
validate_json "$OUTPUT_JSON_STDIN"
assert_json_array "$OUTPUT_JSON_STDIN"


# 4. JSON output to file
echo "Testing -f json -o file..."
OUT_FILE="test_output.json"
rm -f "$OUT_FILE"
$CC_CMD -f json -o "$OUT_FILE" "$DATA_FILE_SIMPLE"
assert_success
assert_file_exists "$OUT_FILE"

# Validate file content is valid JSON
FILE_CONTENT=$(cat "$OUT_FILE")
validate_json "$FILE_CONTENT"
assert_json_array "$FILE_CONTENT"

# Check NO colors in file
assert_no_colors "$FILE_CONTENT"

rm "$OUT_FILE"


# 5. JSON with slice (1-based: ":3" means "up to but not including i=3")
echo "Testing -f json with slice..."
OUTPUT_JSON_SLICE=$($CC_CMD -f json "$DATA_FILE_SIMPLE" ":3" 2>&1 | grep -v "^File:")
if [[ $? -ne 0 ]]; then
  echo "❌ Slice test failed"
  exit 1
fi
validate_json "$OUTPUT_JSON_SLICE"
assert_json_array "$OUTPUT_JSON_SLICE"

# Should have exactly 2 messages (i="1" and i="2")
SLICE_LENGTH=$(json_array_length "$OUTPUT_JSON_SLICE")
if [[ $SLICE_LENGTH -ne 2 ]]; then
  echo "❌ Expected 2 messages with slice :3, got $SLICE_LENGTH"
  exit 1
fi


# 6. JSON should NOT contain XML tags (as structural elements)
echo "Testing JSON doesn't contain XML tags as structure..."
# Check that JSON doesn't start lines with XML tags (which would indicate XML structure)
if printf '%s\n' "$OUTPUT_JSON" | grep -q "^<${USER_MESSAGE_TAG}"; then
  echo "❌ JSON output contains XML user-message tags"
  exit 1
fi
if printf '%s\n' "$OUTPUT_JSON" | grep -q "^<${ASSISTANT_RESPONSE_TAG}"; then
  echo "❌ JSON output contains XML assistant-response tags"
  exit 1
fi
# Check for XML-style headers (which appear in XML format but not JSON)
if printf '%s\n' "$OUTPUT_JSON" | grep -q "^# User$"; then
  echo "❌ JSON output contains XML-style user header"
  exit 1
fi
if printf '%s\n' "$OUTPUT_JSON" | grep -q "^# Assistant$"; then
  echo "❌ JSON output contains XML-style assistant header"
  exit 1
fi


# 7. Compare JSON vs XML message count
echo "Testing JSON vs XML message count..."
OUTPUT_XML=$($CC_CMD --color never "$DATA_FILE_SIMPLE" 2>&1 | grep -v "^File:")
if [[ $? -ne 0 ]]; then
  echo "❌ XML output failed"
  exit 1
fi

# Count user messages in XML
XML_USER_COUNT=$(printf '%s\n' "$OUTPUT_XML" | grep -c "^<${USER_MESSAGE_TAG}")
# Count user messages in JSON (use python for reliable counting)
JSON_USER_COUNT=$(printf '%s\n' "$OUTPUT_JSON" | $PY_CMD -c "import json, sys; data=json.load(sys.stdin); print(len([m for m in data if m.get('role')=='user']))")

if [[ $XML_USER_COUNT -ne $JSON_USER_COUNT ]]; then
  echo "❌ XML has $XML_USER_COUNT user messages, JSON has $JSON_USER_COUNT"
  exit 1
fi


# 8. JSON with --color flag (should be ignored for JSON)
echo "Testing JSON ignores --color flag..."
OUTPUT_JSON_COLOR=$($CC_CMD -f json --color always "$DATA_FILE_SIMPLE" 2>&1 | grep -v "^File:")
if [[ $? -ne 0 ]]; then
  echo "❌ Color flag test failed"
  exit 1
fi
validate_json "$OUTPUT_JSON_COLOR"
# Still should have no colors even with --color always
assert_no_colors "$OUTPUT_JSON_COLOR"


# 9. Test with complex data file (has assistant messages)
# 1-based: ":3" means up to but not including position 3 → positions 1,2 → 2 messages
echo "Testing JSON with assistant messages..."
OUTPUT_JSON_COMPLEX=$($CC_CMD -f json "$DATA_FILE_COMPLEX" ":3" 2>&1 | grep -v "^File:")
if [[ $? -ne 0 ]]; then
  echo "❌ Complex data test failed"
  exit 1
fi
validate_json "$OUTPUT_JSON_COMPLEX"
assert_json_array "$OUTPUT_JSON_COMPLEX"

# Verify slice count: ":3" should produce exactly 2 messages
COMPLEX_LENGTH=$(json_array_length "$OUTPUT_JSON_COMPLEX")
if [[ $COMPLEX_LENGTH -ne 2 ]]; then
  echo "❌ Expected 2 messages with slice :3, got $COMPLEX_LENGTH"
  exit 1
fi

# Check for both roles (use python for reliable counting)
HAS_USER=$(printf '%s\n' "$OUTPUT_JSON_COMPLEX" | $PY_CMD -c "import json, sys; data=json.load(sys.stdin); print(len([m for m in data if m.get('role')=='user']))")
HAS_ASSISTANT=$(printf '%s\n' "$OUTPUT_JSON_COMPLEX" | $PY_CMD -c "import json, sys; data=json.load(sys.stdin); print(len([m for m in data if m.get('role')=='assistant']))")

if [[ $HAS_USER -eq 0 ]]; then
  echo "❌ JSON output has no user messages"
  exit 1
fi

if [[ $HAS_ASSISTANT -eq 0 ]]; then
  echo "⚠️  Warning: No assistant messages found in test data"
fi


# 10. Test JSON format with piped output (should work the same)
echo "Testing JSON piped output..."
OUTPUT_JSON_PIPED=$($CC_CMD -f json "$DATA_FILE_SIMPLE" 2>&1 | grep -v "^File:" | cat)
if [[ $? -ne 0 ]]; then
  echo "❌ Piped output test failed"
  exit 1
fi
validate_json "$OUTPUT_JSON_PIPED"

# 11. Test custom-title renders as session-rename
echo "Testing custom-title parsing..."
OUTPUT_CUSTOM=$(cc_cmd "tests/data/custom_title.jsonl" --color never 2>/dev/null)
if ! echo "$OUTPUT_CUSTOM" | grep -q "<${SESSION_RENAME_TAG}"; then
  echo "❌ custom-title not rendered as session-rename"
  exit 1
fi
if ! echo "$OUTPUT_CUSTOM" | grep -q '# Renamed Session'; then
  echo "❌ session-rename missing header"
  exit 1
fi

echo "✅ Format tests passed"
