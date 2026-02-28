#!/usr/bin/env zsh
# takes a conversation jsonl either from stdin or by positional path, and prints it as-is with truncated strings (recursively).
jq 'walk(if type == "string" and length > 25 then .[:25] + "..." else . end)' "$@"
