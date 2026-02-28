#!/usr/bin/env zsh -i
source tests/lib.sh

echo "Running flags tests (Synthetic Data)..."
DATA_FILE_SYNTHETIC="tests/data/synthetic_flags.jsonl"

count_message_tags() {
  printf '%s\n' "$1" | grep -E "^<(${PIPE_JOINED_MESSAGE_TAGS})" -c || true
}

assert_message_count() {
  local output="$1"
  local expected="$2"
  local count
  count=$(count_message_tags "$output")
  if [[ "$count" -ne "$expected" ]]; then
    echo "❌ Expected $expected messages, got $count"
    exit 1
  fi
}

# -T: Thinking
echo "Testing -T (Thinking)..."
OUTPUT_T=$($CC_CMD -T "$DATA_FILE_SYNTHETIC")
assert_success
assert_contains "$OUTPUT_T" "<thinking>"
assert_not_contains "$OUTPUT_T" "<tool-"

# -T: Slice parsing (index + range)
echo "Testing -T with index slice..."
OUTPUT_T_INDEX=$($CC_CMD "$DATA_FILE_SYNTHETIC" -T "1" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_T_INDEX" 1

echo "Testing -T with range slice..."
OUTPUT_T_RANGE=$($CC_CMD "$DATA_FILE_SYNTHETIC" -T "1:3" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_T_RANGE" 2

# -t: Tools
echo "Testing -t (Tools)..."
OUTPUT_t=$($CC_CMD -t "$DATA_FILE_SYNTHETIC")
assert_success
assert_contains "$OUTPUT_t" "<tool-"
assert_not_contains "$OUTPUT_t" "<thinking>"

# -t: Slice parsing (index + range)
echo "Testing -t with index slice..."
OUTPUT_t_INDEX=$($CC_CMD "$DATA_FILE_SYNTHETIC" -t "1" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_t_INDEX" 1

echo "Testing -t with range slice..."
OUTPUT_t_RANGE=$($CC_CMD "$DATA_FILE_SYNTHETIC" -t "1:3" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_t_RANGE" 2

# -t -T: Both
echo "Testing -t -T..."
OUTPUT_tT=$($CC_CMD -t -T "$DATA_FILE_SYNTHETIC")
assert_success
assert_contains "$OUTPUT_tT" "<tool-"
assert_contains "$OUTPUT_tT" "<thinking>"

# -A: All
echo "Testing -A (All)..."
OUTPUT_A=$($CC_CMD -A "$DATA_FILE_SYNTHETIC")
assert_success
assert_contains "$OUTPUT_A" "<tool-"
assert_contains "$OUTPUT_A" "<thinking>"

# -A: Slice parsing (index + range)
echo "Testing -A with index slice..."
OUTPUT_A_INDEX=$($CC_CMD "$DATA_FILE_SYNTHETIC" -A "1" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_A_INDEX" 1

echo "Testing -A with range slice..."
OUTPUT_A_RANGE=$($CC_CMD "$DATA_FILE_SYNTHETIC" -A "1:3" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_A_RANGE" 2

# -s: Shorten
echo "Testing -s (Shorten)..."
# Create a file with long content
echo '{"type":"user","message":{"role":"user","content":"This is a very long message that should definitely be shortened because it exceeds the default width limit of 40 characters by quite a margin."},"timestamp":"2025-11-23T09:29:08.354Z"}' > tests/data/long_message.jsonl

OUTPUT_S=$($CC_CMD -s tests/data/long_message.jsonl)
assert_success
# Should contain the placeholder
assert_contains "$OUTPUT_S" "[...]"
# Should NOT contain the full text (end of it)
assert_not_contains "$OUTPUT_S" "margin."

# -s: Slice parsing (index + range)
echo "Testing -s with index slice..."
OUTPUT_S_INDEX=$($CC_CMD "$DATA_FILE_SYNTHETIC" -s "1" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_S_INDEX" 1

echo "Testing -s with range slice..."
OUTPUT_S_RANGE=$($CC_CMD "$DATA_FILE_SYNTHETIC" -s "1:3" --color=never 2>/dev/null)
assert_success
assert_message_count "$OUTPUT_S_RANGE" 2

# Cleanup
rm tests/data/long_message.jsonl

# -o: Output to file
echo "Testing -o (Output to file)..."
OUT_FILE="test_output.xml"
rm -f "$OUT_FILE"
$CC_CMD -o "$OUT_FILE" "$DATA_FILE_SIMPLE"
assert_success
assert_file_exists "$OUT_FILE"

# Check file content
CONTENT=$(cat "$OUT_FILE")
if [[ -z "$CONTENT" ]]; then
  echo "❌ Output file is empty"
  exit 1
fi

# Check NO colors in file
assert_no_colors "$CONTENT"

rm "$OUT_FILE"

# -o: Slice parsing (index + range)
echo "Testing -o with index slice..."
OUT_FILE="test_output_slice.xml"
rm -f "$OUT_FILE"
$CC_CMD -o "$OUT_FILE" "$DATA_FILE_SYNTHETIC" "1" --color=never 2>/dev/null
assert_success
assert_file_exists "$OUT_FILE"
CONTENT=$(cat "$OUT_FILE")
assert_message_count "$CONTENT" 1
rm "$OUT_FILE"

echo "Testing -o with range slice..."
OUT_FILE="test_output_slice.xml"
rm -f "$OUT_FILE"
$CC_CMD -o "$OUT_FILE" "$DATA_FILE_SYNTHETIC" "1:3" --color=never 2>/dev/null
assert_success
assert_file_exists "$OUT_FILE"
CONTENT=$(cat "$OUT_FILE")
assert_message_count "$CONTENT" 2
rm "$OUT_FILE"

echo "✅ Flags tests passed"
