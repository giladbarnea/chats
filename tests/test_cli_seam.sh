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
assert_contains "$OUTPUT" "<${USER_MESSAGE_TAG}"

# Test 2: Slice argument ordering - slice after flags
echo "Test 2: Slice after flags..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE" --color=never "1" 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "<${USER_MESSAGE_TAG}"

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

echo "✅ CLI seam tests passed"
