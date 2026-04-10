#!/usr/bin/env zsh -i
source tests/lib.sh

USER_MESSAGE_TAG="${SUPPORTED_MESSAGE_TAGS[user-message]:?'user-message' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running basic tests (Simple Data)..."

# 1. Naive file input
echo "Testing naive file input..."
OUTPUT=$($CC_CMD "$DATA_FILE_SIMPLE")
assert_success

# Positive shape check
# Count user messages in input using streaming jq with explicit if/else
# Use .message? to avoid errors on objects without message field
EXPECTED_USER_MSGS=$(jq 'select(.type=="user" and .message?.role=="user") | select(
  if (.message.content | type) == "string" then
    (.message.content | length > 0)
  else
    (.message.content | map(select(.type=="text" and (.text | length > 0))) | length > 0)
  end
)' "$DATA_FILE_SIMPLE" | jq -s length)

# Count tags in output (anchor to start of line to avoid matching content)
ACTUAL_USER_TAGS=$(echo "$OUTPUT" | grep -c "^<${USER_MESSAGE_TAG}")

if [[ "$ACTUAL_USER_TAGS" -ne "$EXPECTED_USER_MSGS" ]]; then
  echo "❌ Expected $EXPECTED_USER_MSGS user messages, got $ACTUAL_USER_TAGS"
  exit 1
fi

# No false positive objects (thinking/tools should be hidden by default)
assert_not_contains "$OUTPUT" "<thinking>"
assert_not_contains "$OUTPUT" "<tool-"

# Colors check
# Use Python subprocess with PTY (properly closes file descriptors to avoid hanging)
OUTPUT_TTY=$(TERM=xterm-256color $PY_CMD -c "
import subprocess, os, pty

master, slave = pty.openpty()
proc = subprocess.Popen(['uv', 'run', 'ccc', '$DATA_FILE_SIMPLE'],
                        stdout=slave, stderr=slave, stdin=subprocess.DEVNULL)
os.close(slave)
output = b''
while True:
    try:
        chunk = os.read(master, 1024)
        if not chunk:
            break
        output += chunk
    except OSError:
        break
proc.wait()
os.close(master)
print(output.decode('utf-8', errors='replace'), end='')
")
assert_has_colors "$OUTPUT_TTY"


# 2. Naive stdin input
echo "Testing naive stdin input..."
OUTPUT_STDIN=$(cat "$DATA_FILE_SIMPLE" | $CC_CMD)
assert_success
# Same checks
ACTUAL_USER_TAGS_STDIN=$(echo "$OUTPUT_STDIN" | grep -c "^<${USER_MESSAGE_TAG}")
if [[ "$ACTUAL_USER_TAGS_STDIN" -ne "$EXPECTED_USER_MSGS" ]]; then
  echo "❌ Stdin: Expected $EXPECTED_USER_MSGS user messages, got $ACTUAL_USER_TAGS_STDIN"
  exit 1
fi
assert_not_contains "$OUTPUT_STDIN" "<thinking>"
assert_not_contains "$OUTPUT_STDIN" "<tool-"


# 3. Naive piped to cat (should have NO colors)
echo "Testing piped output (no colors)..."
OUTPUT_PIPED=$($CC_CMD "$DATA_FILE_SIMPLE" | cat)
assert_success
assert_no_colors "$OUTPUT_PIPED"

echo "✅ Basic tests passed"
