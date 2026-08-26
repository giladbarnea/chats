#!/usr/bin/env zsh
# Compare pre-rewrite Python argparse routing vs native `ch parse` on unpinned corners.

OLD_ROUTER="uv run python thoughts/2026-08-25-post-rust-rewrite-project-review/cli-router-commands/old_parse_router.py parse"
NATIVE=".venv/bin/ch parse"

run_case() {
  local desc="$1"; shift
  echo "=================================================================="
  echo "CASE: $desc  | args: $*"
  echo "--- OLD python argparse ---"
  eval "${OLD_ROUTER} $*" '>/tmp/old_out.txt' '2>/tmp/old_err.txt'
  print -P "%F{yellow}old exit: $?%f"
  echo "[stdout]"; cat /tmp/old_out.txt; echo "[stderr]"; cat /tmp/old_err.txt
  echo "--- NATIVE ch ---"
  eval "${NATIVE} $*" '>/tmp/new_out.txt' '2>/tmp/new_err.txt'
  print -P "%F{yellow}native exit: $?%f"
  echo "[stdout]"; cat /tmp/new_out.txt; echo "[stderr]"; cat /tmp/new_err.txt
}

run_case "help abbreviation --h" "--h"
run_case "help abbreviation --he" "--he"
run_case "-h short" "-h"
run_case "unknown long option" "--foo bar"
run_case "unknown short option" "-z file.json"
run_case "option as format value" "-f --help"
run_case "attached short value" "-fxml /dev/null"
run_case "equals short value" "-f=xml /dev/null"
run_case "negative-number-looking input" "-5"
run_case "double dash separator" "-- -weird-file.json"
run_case "format after positional" "/dev/null -f json"
