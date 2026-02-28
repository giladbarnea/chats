#!/usr/bin/env zsh
source tests/lib.sh

echo "Running search date filter tests..."

# Create temp directory structure mimicking ~/.claude/projects/
TEMP_HOME=$(mktemp -d)
TEMP_PROJECTS="$TEMP_HOME/.claude/projects/test-project"
mkdir -p "$TEMP_PROJECTS"

# Calculate dynamic timestamps
TIMESTAMP_OLD=$(date -u -v-30d +%Y-%m-%dT%H:%M:%S.000Z)
TIMESTAMP_RECENT=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)

# Create test conversation files with controlled timestamps
# File 1: "old" - modified 30 days ago
cat > "$TEMP_PROJECTS/old-conversation.jsonl" << EOF
{"type":"summary","summary":"Old conversation about testing","leafUuid":"leaf-old"}
{"type":"user","message":{"role":"user","content":"Hello old"},"timestamp":"$TIMESTAMP_OLD","cwd":"/tmp/test"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Old response"}]}}
EOF

# File 2: "recent" - modified today (default)
cat > "$TEMP_PROJECTS/recent-conversation.jsonl" << EOF
{"type":"summary","summary":"Recent conversation about features","leafUuid":"leaf-recent"}
{"type":"user","message":{"role":"user","content":"Hello recent"},"timestamp":"$TIMESTAMP_RECENT","cwd":"/tmp/test"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Recent response"}]}}
EOF

# Set modification times using touch -t (format: YYYYMMDDhhmm)
# Old file: 30 days ago
OLD_DATE=$(date -v-30d +%Y%m%d%H%M)
touch -t "$OLD_DATE" "$TEMP_PROJECTS/old-conversation.jsonl"

# Recent file: now (already is, but be explicit)
touch "$TEMP_PROJECTS/recent-conversation.jsonl"

# Helper to run parse.py with mocked home directory
run_search() {
    HOME="$TEMP_HOME" $CC_CMD search "$@"
}

# =============================================================================
# Test 1: --mafter filters by modification time
# =============================================================================
echo "Test 1: --mafter filters by modification time..."

# Search with --mafter=7d should only find recent file
OUTPUT=$(run_search --mafter=7d "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_not_contains "$OUTPUT" "old-conversation"
echo "  ✓ --mafter=7d includes recent, excludes old"

# Search with --mafter=60d should find both files
OUTPUT=$(run_search --mafter=60d "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_contains "$OUTPUT" "old-conversation"
echo "  ✓ --mafter=60d includes both"

# =============================================================================
# Test 2: --mafter with future date returns no matches (exit 1)
# =============================================================================
echo "Test 2: --mafter with future date returns exit 1..."

# Tomorrow's date
TOMORROW=$(date -v+1d +%Y-%m-%d)
run_search --mafter="$TOMORROW" "conversation" > /dev/null 2>&1
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 1 ]]; then
    echo "❌ Expected exit code 1 for no matches, got $EXIT_CODE"
    exit 1
fi
echo "  ✓ --mafter with future date returns exit 1"

# =============================================================================
# Test 3: --cafter filters by creation time
# =============================================================================
echo "Test 3: --cafter filters by creation time..."

# On macOS, touch -t changes BOTH mtime AND birthtime!
# So old-conversation has birthtime of 30 days ago (same as mtime)
# --cafter=7d should only find recent-conversation
OUTPUT=$(run_search --cafter=7d "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_not_contains "$OUTPUT" "old-conversation"
echo "  ✓ --cafter=7d finds only recent (old birthtime is 30d ago due to touch -t)"

# --cafter=60d should find both
OUTPUT=$(run_search --cafter=60d "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_contains "$OUTPUT" "old-conversation"
echo "  ✓ --cafter=60d finds both"

# =============================================================================
# Test 4: Combined --mafter + --cafter
# =============================================================================
echo "Test 4: Combined --mafter + --cafter..."

# Both filters applied: mafter=7d AND cafter=7d
# Should only find recent (old fails mafter)
OUTPUT=$(run_search --mafter=7d --cafter=7d "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_not_contains "$OUTPUT" "old-conversation"
echo "  ✓ --mafter + --cafter both applied"

# =============================================================================
# Test 5: Combined --mafter + -d (directory filter)
# =============================================================================
echo "Test 5: Combined --mafter + -d..."

# Create another conversation in a different "cwd"
cat > "$TEMP_PROJECTS/other-dir-conversation.jsonl" << EOF
{"type":"summary","summary":"Other dir conversation","leafUuid":"leaf-other"}
{"type":"user","message":{"role":"user","content":"Hello other"},"timestamp":"$TIMESTAMP_RECENT","cwd":"/other/path"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Other response"}]}}
EOF

# Search with both filters: recent + in /tmp/test
OUTPUT=$(run_search --mafter=7d -d /tmp/test "Hello" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_not_contains "$OUTPUT" "other-dir-conversation"
echo "  ✓ --mafter + -d both applied"

# =============================================================================
# Test 6: ISO date format works
# =============================================================================
echo "Test 6: ISO date format..."

# Use a date 15 days ago
DATE_15D_AGO=$(date -v-15d +%Y-%m-%d)
OUTPUT=$(run_search --mafter="$DATE_15D_AGO" "conversation" 2>&1) || true
assert_contains "$OUTPUT" "recent-conversation"
assert_not_contains "$OUTPUT" "old-conversation"
echo "  ✓ --mafter with ISO date works"

# =============================================================================
# Cleanup
# =============================================================================
rm -rf "$TEMP_HOME"

echo "✅ Search date filter tests passed"
