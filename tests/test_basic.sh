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
EXPECTED_USER_MSGS=$(jq 'select(.type=="user" and .message?.role=="user" and (.isMeta != true)) | select(
  if (.message.content | type) == "string" then
    (.message.content | length > 0)
    and (.message.content | test("^\\s*<local-command-stdout>.*</local-command-stdout>\\s*$"; "s") | not)
    and (.message.content | split("\n") | all(test("^[ \t]*<command-[a-z0-9-]+>.*</command-[a-z0-9-]+>[ \t]*$"; "s"))) | not
  else
    (.message.content | map(select(.type=="text" and (.text | length > 0))) | length > 0)
  end
)' "$DATA_FILE_SIMPLE" | jq -s length)

# Count rendered user-origin wrappers in output (anchor to start of line to avoid matching content)
ACTUAL_USER_TAGS=$(count_user_origin_tags "$OUTPUT")

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
proc = subprocess.Popen(['uv', 'run', 'ch', '$DATA_FILE_SIMPLE'],
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
OUTPUT_STDIN=$(cat "$DATA_FILE_STDIN" | $CC_CMD)
assert_success
# Same checks
ACTUAL_USER_TAGS_STDIN=$(count_user_origin_tags "$OUTPUT_STDIN")
if [[ "$ACTUAL_USER_TAGS_STDIN" -ne "$EXPECTED_USER_MSGS" ]]; then
  echo "❌ Stdin: Expected $EXPECTED_USER_MSGS user messages, got $ACTUAL_USER_TAGS_STDIN"
  exit 1
fi
assert_not_contains "$OUTPUT_STDIN" "<thinking>"
assert_not_contains "$OUTPUT_STDIN" "<tool-"


# 3. Naive piped to cat (should have NO colors)
echo "Testing piped output (no colors)..."
METADATA_FILE=$(mktemp)
OUTPUT_PIPED=$($CC_CMD "$DATA_FILE_SIMPLE" 2>"$METADATA_FILE" | cat)
assert_success
assert_no_colors "$OUTPUT_PIPED"
assert_not_contains "$OUTPUT_PIPED" "session_id:"

METADATA=$(<"$METADATA_FILE")
rm "$METADATA_FILE"
assert_contains "$METADATA" "session_id:"
assert_not_contains "$METADATA" "<${USER_MESSAGE_TAG}"

echo "✅ Basic tests passed"
