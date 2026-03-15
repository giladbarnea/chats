#!/usr/bin/env zsh -i
source tests/lib.sh

echo "Running Rich whitespace tests..."
DATA_FILE="tests/data/1e446a9f-08fd-43ac-be72-8ce337d01dcd.jsonl"

rich=$($CC_CMD --color=always --short --no-metadata "$DATA_FILE" 2>/dev/null | decolor)

# Bug 1: Only one blank line between heading and content (not two)
if [[ "$rich" == *$'# User\n\n\n'* ]]; then
    echo "❌ Bug 1: Two blank lines between '# User' heading and content"
    exit 1
fi
if [[ "$rich" == *$'# Assistant\n\n\n'* ]]; then
    echo "❌ Bug 1: Two blank lines between '# Assistant' heading and content"
    exit 1
fi
echo "  ✓ No extra blank line after headings"

# Bug 2: No empty line between message content and closing tag
if [[ "$rich" == *$'\n\n</user-message'* ]]; then
    echo "❌ Bug 2: Empty line before </user-message>"
    exit 1
fi
if [[ "$rich" == *$'\n\n</assistant-response'* ]]; then
    echo "❌ Bug 2: Empty line before </assistant-response>"
    exit 1
fi
echo "  ✓ No extra blank line before closing tags"

# Bug 3: Opening tags must not have leading whitespace
if [[ "$rich" == *$'\n <'* ]]; then
    echo "❌ Bug 3: Opening tag has leading whitespace"
    echo "DEBUG:"
    echo "$rich" | grep -n '^ <'
    exit 1
fi
echo "  ✓ No leading whitespace on tags"

echo "✅ Rich whitespace tests passed"
