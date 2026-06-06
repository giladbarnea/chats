#!/usr/bin/env zsh -i
source tests/lib.sh

echo "Running color tests..."

# 1. --color always
echo "Testing --color always..."
# Even when piped, it should have colors
OUTPUT_ALWAYS=$((unset NO_COLOR; TERM=xterm-256color $CC_CMD --color always "$DATA_FILE_SIMPLE") | cat)
assert_success
assert_has_colors "$OUTPUT_ALWAYS"

# 2. --color never
echo "Testing --color never..."
# Use Python subprocess with PTY (properly closes file descriptors to avoid hanging)
OUTPUT_NEVER=$(TERM=xterm-256color $PY_CMD -c "
import subprocess, os, pty

master, slave = pty.openpty()
proc = subprocess.Popen(['uv', 'run', 'ch', '--color', 'never', '$DATA_FILE_SIMPLE'],
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
assert_success
assert_no_colors "$OUTPUT_NEVER"

echo "✅ Color tests passed"
