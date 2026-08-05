#!/usr/bin/env zsh -i
source tests/lib.sh

echo "Running structured rendering tests..."
DATA_FILE_SYNTHETIC=$(claude_fixture tests/data/synthetic_flags.jsonl)
GOLDEN_FILE="tests/data/golden_xml_output.txt"

# Helper: strip ANSI codes
strip_ansi() {
    sed 's/\x1b\[[0-9;]*m//g'
}

# Test 1: XML output unchanged (regression prevention)
echo "Testing XML output unchanged (golden reference)..."
actual=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=never 2>/dev/null)
expected=$(cat "$GOLDEN_FILE")
if [[ "$actual" != "$expected" ]]; then
    echo "❌ XML output differs from golden reference"
    echo "=== EXPECTED ==="
    echo "$expected" | head -20
    echo "=== ACTUAL ==="
    echo "$actual" | head -20
    exit 1
fi
echo "  ✓ XML output matches golden reference"

# Test 2: Rich thinking renders tag-free under a ✻ marker (not <thinking> tags).
# tests/test_colored_rendering.py pins the colored structure in detail; this is the
# CLI-seam check that the same tag-free shape reaches the terminal through `ch`.
echo "Testing Rich thinking renders tag-free..."
output=$($CC_CMD -T "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "✻ thinking"
assert_contains "$output" "I should reply hello"
assert_not_contains "$output" "<thinking>"
echo "  ✓ Rich thinking is tag-free (✻ marker)"

# Test 3: Rich tools render tag-free as ⏺ call / ⎿ result headers (not <tool-*> tags).
echo "Testing Rich tools render tag-free..."
output=$($CC_CMD -t "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "⏺"
assert_contains "$output" "⎿"
assert_contains "$output" "result"
assert_not_contains "$output" "<tool-input"
assert_not_contains "$output" "<tool-output"
echo "  ✓ Rich tools are tag-free (⏺/⎿ markers)"

# Test 4: colored and plain views diverge by design — colored is tag-free, while
# plain (--color=never) keeps the XML tags (the form meant for piping to tools/LLMs).
echo "Testing colored is tag-free while plain keeps tags..."
plain=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=never 2>/dev/null)
rich=$($CC_CMD -T -t "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$plain" "<thinking>"
assert_contains "$plain" "<tool-input"
assert_not_contains "$rich" "<thinking>"
assert_not_contains "$rich" "<tool-input"
echo "  ✓ colored tag-free, plain keeps tags"

# Test 5: Rich output contains headers
echo "Testing Rich output contains headers..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "User"
assert_contains "$output" "Assistant"
assert_not_contains "$output" "## User"
assert_not_contains "$output" "## Assistant"
echo "  ✓ Rich output contains headers"

# Test 5b: Rich headings use badge style (no heavy box drawing chars)
echo "Testing Rich headings use badge style..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
if echo "$output" | grep -qF "━"; then
    echo "❌ Heavy box drawing char found — expected badge-style headings, not full-width panel"
    exit 1
fi
echo "  ✓ Rich headings use badge style (no box chars)"

# Test 6: Rich output leads with a session title (id + created/modified), not YAML
echo "Testing Rich output leads with a session title..."
output=$($CC_CMD "$DATA_FILE_SYNTHETIC" --color=always 2>&1 | strip_ansi)
assert_contains "$output" "synthetic_flags"
assert_contains "$output" "created"
assert_contains "$output" "modified"
assert_not_contains "$output" "history_path"
echo "  ✓ Rich output leads with a session title"

echo "✅ Structured rendering tests passed"
