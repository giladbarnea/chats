#!/usr/bin/env zsh
source tests/lib.sh

USER_MESSAGE_TAG="${SUPPORTED_MESSAGE_TAGS[user-message]:?'user-message' not in SUPPORTED_MESSAGE_TAGS}"

echo "Running raw/no-metadata tests..."

DATA_FILE_SYNTHETIC=$(claude_fixture tests/data/synthetic_flags.jsonl)

# =============================================================================
# Test 1: --no-metadata suppresses YAML frontmatter in parse mode
# =============================================================================
echo "Test 1: parse --no-metadata (xml)..."
OUTPUT=$($CC_CMD --color never --no-metadata "$DATA_FILE_SYNTHETIC" ":3" 2>/dev/null)
assert_success
assert_contains "$OUTPUT" "<${USER_MESSAGE_TAG}"
assert_not_contains "$OUTPUT" "session_id:"
echo "  ✓ --no-metadata suppresses frontmatter"

# =============================================================================
# Test 2: -f raw outputs only content for a single message
# =============================================================================
echo "Test 2: parse -f raw (single message)..."
OUTPUT_SINGLE=$($CC_CMD --color never -f raw "$DATA_FILE_SYNTHETIC" "1" 2>/dev/null)
assert_success
if [[ "$OUTPUT_SINGLE" != "Hi" ]]; then
  echo "❌ Expected raw single-message output to be exactly: Hi"
  echo "Got: $OUTPUT_SINGLE"
  exit 1
fi
assert_not_contains "$OUTPUT_SINGLE" "## User"
assert_not_contains "$OUTPUT_SINGLE" "<${USER_MESSAGE_TAG}"
assert_not_contains "$OUTPUT_SINGLE" "---"
echo "  ✓ raw single-message output is just content"

# =============================================================================
# Test 3: -r/--raw is an alias for -f raw and implies --no-metadata
# =============================================================================
echo "Test 3: parse -r alias (single + multi)..."
OUTPUT_ALIAS_SINGLE=$($CC_CMD --color never -r "$DATA_FILE_SYNTHETIC" "1" 2>/dev/null)
assert_success
if [[ "$OUTPUT_ALIAS_SINGLE" != "Hi" ]]; then
  echo "❌ Expected -r single-message output to be exactly: Hi"
  echo "Got: $OUTPUT_ALIAS_SINGLE"
  exit 1
fi

OUTPUT_ALIAS_MULTI=$($CC_CMD --color never -r "$DATA_FILE_SYNTHETIC" ":3" 2>/dev/null)
assert_success
assert_contains "$OUTPUT_ALIAS_MULTI" "## User"
assert_contains "$OUTPUT_ALIAS_MULTI" "Hi"
assert_contains "$OUTPUT_ALIAS_MULTI" "---"
assert_contains "$OUTPUT_ALIAS_MULTI" "## Assistant"
assert_contains "$OUTPUT_ALIAS_MULTI" "Hello!"
assert_not_contains "$OUTPUT_ALIAS_MULTI" "session_id:"
assert_not_contains "$OUTPUT_ALIAS_MULTI" "<${USER_MESSAGE_TAG}"
echo "  ✓ -r works and implies --no-metadata"

# =============================================================================
# Test 4: search --no-metadata suppresses YAML frontmatter
# =============================================================================
echo "Test 4: search --no-metadata..."

TEMP_HOME=$(mktemp -d)
TEMP_PROJECTS="$TEMP_HOME/.claude/projects/test-project"
mkdir -p "$TEMP_PROJECTS"

cat > "$TEMP_PROJECTS/search-no-meta.jsonl" << 'EOF'
{"type":"user","message":{"role":"user","content":"needle"},"timestamp":"2025-11-23T09:29:08.354Z","cwd":"/tmp/test"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"haystack"}]},"timestamp":"2025-11-23T09:29:14.958Z"}
EOF

OUTPUT_SEARCH=$(HOME="$TEMP_HOME" $CC_CMD search --color never --no-metadata "needle" 2>&1)
assert_success
assert_contains "$OUTPUT_SEARCH" "<${USER_MESSAGE_TAG}"
assert_not_contains "$OUTPUT_SEARCH" "session_id:"
echo "  ✓ search --no-metadata suppresses frontmatter"

# =============================================================================
# Test 5: search -r outputs just content for a single visible message
# =============================================================================
echo "Test 5: search -r (single visible message)..."
OUTPUT_SEARCH_RAW_SINGLE=$(HOME="$TEMP_HOME" $CC_CMD search --color always --paging --raw "haystack" 2>&1)
assert_success
if [[ "$OUTPUT_SEARCH_RAW_SINGLE" != "haystack" ]]; then
  echo "❌ Expected raw search single-message output to be exactly: haystack"
  echo "Got: $OUTPUT_SEARCH_RAW_SINGLE"
  exit 1
fi
assert_not_contains "$OUTPUT_SEARCH_RAW_SINGLE" "session_id:"
assert_not_contains "$OUTPUT_SEARCH_RAW_SINGLE" "Session search-no-meta"
echo "  ✓ search -r single-message output is just content"

# =============================================================================
# Test 6: search -r --full uses setext session headings and one HR between sessions
# =============================================================================
echo "Test 6: search -r --full (session markdown)..."
cat > "$TEMP_PROJECTS/raw-full-one.jsonl" << 'EOF'
{"type":"user","message":{"role":"user","content":"context without token"},"timestamp":"2025-11-23T09:29:08.354Z","cwd":"/tmp/test"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"needle from assistant"}]},"timestamp":"2025-11-23T09:29:14.958Z"}
EOF

cat > "$TEMP_PROJECTS/raw-full-two.jsonl" << 'EOF'
{"type":"user","message":{"role":"user","content":"needle from second session"},"timestamp":"2025-11-23T09:29:18.000Z","cwd":"/tmp/test"}
EOF

OUTPUT_SEARCH_RAW_FULL=$(HOME="$TEMP_HOME" $CC_CMD search --color always --paging --raw --full "needle" 2>&1)
assert_success
assert_contains "$OUTPUT_SEARCH_RAW_FULL" $'Session raw-full-two\n===================='
assert_contains "$OUTPUT_SEARCH_RAW_FULL" $'Session raw-full-one\n===================='
assert_contains "$OUTPUT_SEARCH_RAW_FULL" "context without token"
assert_contains "$OUTPUT_SEARCH_RAW_FULL" "## Assistant"
assert_contains "$OUTPUT_SEARCH_RAW_FULL" "needle from assistant"
assert_contains "$OUTPUT_SEARCH_RAW_FULL" $'needle from second session\n\n---\n\nSession raw-full-one\n===================='
assert_not_contains "$OUTPUT_SEARCH_RAW_FULL" "session_id:"
echo "  ✓ search -r --full uses session markdown boundaries"

rm -rf "$TEMP_HOME"
echo "✅ Raw/no-metadata tests passed"
