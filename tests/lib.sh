#!/usr/bin/env zsh
setopt EXTENDED_GLOB

# Define data files relative to the test script location (assuming running from repo root)
# So tests/data/... is correct.
DATA_FILE_SIMPLE="tests/data/a6f25fb8-e7a8-4411-b378-ad0f20e552d1.jsonl"
DATA_FILE_COMPLEX="tests/data/91410674-da33-4697-b5a8-f334edbc5554.jsonl"

cc_cmd() {
  uv run ch "$@"
}
CC_CMD="cc_cmd"

py_cmd() {
  uv run python "$@"
}
PY_CMD="py_cmd"

# For tests that need the actual command array (like pty.spawn)
CC_CMD_BASE=("uv" "run" "ch")

# Supported message tags (centralized source of truth)
declare -A SUPPORTED_MESSAGE_TAGS=(
  [user-message]=user-message
  [user-command-input]=user-command-input
  [user-command-output]=user-command-output
  [assistant-response]=assistant-response
  [agent]=agent
  [session-rename]=session-rename
)

_SUPPORTED_TAG_VALUES=(${(@v)SUPPORTED_MESSAGE_TAGS})
PIPE_JOINED_MESSAGE_TAGS="${(j:|:)_SUPPORTED_TAG_VALUES}"
unset _SUPPORTED_TAG_VALUES

USER_ORIGIN_MESSAGE_TAGS=(
  "${SUPPORTED_MESSAGE_TAGS[user-message]}"
  "${SUPPORTED_MESSAGE_TAGS[user-command-input]}"
  "${SUPPORTED_MESSAGE_TAGS[user-command-output]}"
)
PIPE_JOINED_USER_ORIGIN_MESSAGE_TAGS="${(j:|:)USER_ORIGIN_MESSAGE_TAGS}"
unset USER_ORIGIN_MESSAGE_TAGS

# Assert no error
assert_success() {
  if [[ $? -ne 0 ]]; then
    echo "❌ Command failed with exit code $?"
    exit 1
  fi
}

# Assert file exists
assert_file_exists() {
  if [[ ! -f "$1" ]]; then
    echo "❌ File $1 does not exist"
    exit 1
  fi
}

# Assert output contains string
assert_contains() {
  if [[ "$1" != *"$2"* ]]; then
    echo "❌ Output does not contain expected string: '$2'"
    exit 1
  fi
}

# Assert output DOES NOT contain string
assert_not_contains() {
  if [[ "$1" == *"$2"* ]]; then
    echo "❌ Output contains forbidden string: '$2'"
    exit 1
  fi
}

# Check for ANSI color codes using Zsh pattern matching
assert_has_colors() {
  if [[ "$1" != *$'\x1b'* ]]; then
    echo "❌ Output expected to have colors, but none found"
    exit 1
  fi
}

assert_no_colors() {
  if [[ "$1" == *$'\x1b'* ]]; then
    echo "❌ Output expected to have NO colors, but some found"
    echo "DEBUG: Output hex dump:"
    echo "$1" | head -n 5 | od -c
    exit 1
  fi
}

decolor() {
  local text="${1:-$(<&0)}"
  text=${text//$'\e'\[(<0-9>##;#)##m/}
  print -r -- "$text"
}

count_user_origin_tags() {
  printf '%s\n' "$1" | grep -E "^<(${PIPE_JOINED_USER_ORIGIN_MESSAGE_TAGS})" -c || true
}
