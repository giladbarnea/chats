#!/usr/bin/env zsh -i
source tests/lib.sh

echo "Running Rich whitespace tests..."
DATA_FILE="tests/data/1e446a9f-08fd-43ac-be72-8ce337d01dcd.jsonl"

# Litmus test: decolored --color=always output should position text identically to --color=never.
# We check the invariant that no heading is followed by a double blank line, in both paths.

check_no_double_blank_after_headings() {
    local label="$1" output="$2"
    # Find each "# User" or "# Assistant" and check the two lines after it
    local lineno=0
    local prev_line="" prev_prev_line=""
    local heading_line=0
    while IFS= read -r line; do
        lineno=$((lineno + 1))
        if [[ "$prev_prev_line" == "# User"* || "$prev_prev_line" == "# Assistant"* ]]; then
            # prev_prev_line was heading, prev_line should be blank, current line should NOT be blank
            if [[ -z "$prev_line" && -z "$line" ]]; then
                echo "❌ [$label] Double blank line after heading '${prev_prev_line}' at line $((lineno - 2))"
                echo "DEBUG: lines $((lineno-2))-$((lineno)):"
                echo "  $((lineno-2)): |${prev_prev_line}|"
                echo "  $((lineno-1)): |${prev_line}|"
                echo "  $((lineno)):   |${line}|"
                exit 1
            fi
        fi
        prev_prev_line="$prev_line"
        prev_line="$line"
    done <<< "$output"
}

# --- color=always (Rich) tests ---
rich=$($CC_CMD --color=always --short --no-metadata "$DATA_FILE" 2>/dev/null | decolor)

check_no_double_blank_after_headings "color=always" "$rich"
echo "  ✓ [color=always] No extra blank line after headings"

if [[ "$rich" == *$'\n\n</user-message'* ]]; then
    echo "❌ [color=always] Empty line before </user-message>"
    exit 1
fi
if [[ "$rich" == *$'\n\n</assistant-response'* ]]; then
    echo "❌ [color=always] Empty line before </assistant-response>"
    exit 1
fi
echo "  ✓ [color=always] No extra blank line before closing tags"

if [[ "$rich" == *$'\n <'* ]]; then
    echo "❌ [color=always] Opening tag has leading whitespace"
    exit 1
fi
echo "  ✓ [color=always] No leading whitespace on tags"

# --- color=always --all (Rich with thinking/tools) ---
rich_all=$($CC_CMD --color=always --all --short --no-metadata "$DATA_FILE" 2>/dev/null | decolor)

check_no_double_blank_after_headings "color=always --all" "$rich_all"
echo "  ✓ [color=always --all] No extra blank line after headings"

# --- color=never (plain XML) tests ---
plain=$($CC_CMD --color=never --short --no-metadata "$DATA_FILE" 2>/dev/null)

check_no_double_blank_after_headings "color=never" "$plain"
echo "  ✓ [color=never] No extra blank line after headings"

# --- color=never --all (plain XML with thinking/tools) ---
plain_all=$($CC_CMD --color=never --all --short --no-metadata "$DATA_FILE" 2>/dev/null)

check_no_double_blank_after_headings "color=never --all" "$plain_all"
echo "  ✓ [color=never --all] No extra blank line after headings"

echo "✅ Rich whitespace tests passed"
