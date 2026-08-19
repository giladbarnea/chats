#!/usr/bin/env bash
# Local development environment setup.
# Safe to re-run — never overwrites existing state.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh

set -euo pipefail

ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m⊘\033[0m %s (already done)\n' "$1"; }

# ── 1. Python environment ────────────────────────────────────────────────────

if [[ ! -d .venv ]]; then
  uv venv
  uv sync --dev --reinstall-package chats
  ok "venv created and dependencies installed"
else
  uv sync --dev --reinstall-package chats
  ok "dependencies and native extension synced"
fi

# ── 2. pre-commit hooks ──────────────────────────────────────────────────────

if [[ -f .git/hooks/pre-commit ]] && grep -q 'pre-commit' .git/hooks/pre-commit 2>/dev/null; then
  skip "pre-commit hooks"
else
  uv run pre-commit install
  ok "pre-commit hooks installed"
fi

echo ""
echo "  Setup complete."
git config --local core.hooksPath "$(git rev-parse --show-toplevel)/.githooks"
