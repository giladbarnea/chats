#!/usr/bin/env zsh
source tests/lib.sh

echo "Running search only-id tests..."

TEMP_HOME=$(mktemp -d)
TEMP_PROJECTS="$TEMP_HOME/.claude/projects/test-project"
mkdir -p "$TEMP_PROJECTS"

cat > "$TEMP_PROJECTS/match-session.jsonl" << 'EOF'
{"type":"summary","summary":"Only-id search session","leafUuid":"leaf-match"}
{"type":"user","message":{"role":"user","content":"find needle"},"timestamp":"2025-01-01T00:00:00Z","cwd":"/tmp/only-id"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"response"}]}}
EOF

run_search() {
    HOME="$TEMP_HOME" $CC_CMD search "$@"
}

echo "Test 1: --only-id prints just the session id..."
OUTPUT=$(run_search --only-id "needle" 2>&1) || true
assert_success
if [[ "$OUTPUT" != "match-session" ]]; then
    echo "❌ Expected --only-id output to be exactly 'match-session'"
    echo "Got: $OUTPUT"
    exit 1
fi
assert_not_contains "$OUTPUT" "session_id:"
assert_not_contains "$OUTPUT" "history_path:"
echo "  ✓ --only-id prints just the session id"

echo "Test 2: -ll is accepted as shorthand..."
OUTPUT=$(run_search -ll "needle" 2>&1) || true
assert_success
if [[ "$OUTPUT" != "match-session" ]]; then
    echo "❌ Expected -ll output to be exactly 'match-session'"
    echo "Got: $OUTPUT"
    exit 1
fi
assert_not_contains "$OUTPUT" "session_id:"
assert_not_contains "$OUTPUT" "history_path:"
echo "  ✓ -ll prints just the session id"

rm -rf "$TEMP_HOME"

echo "✅ Search only-id tests passed"
