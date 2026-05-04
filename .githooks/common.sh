#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SKILLS_SOURCE="$REPO_ROOT/.agents/skills"
SKILLS_TARGETS=(".claude" ".gemini" ".codex" ".pi/agent")

sync_skills() {
  [ -d "$SKILLS_SOURCE" ] || return 0

  for target in "${SKILLS_TARGETS[@]}"; do
    target_skills="$REPO_ROOT/$target/skills"
    mkdir -p "$target_skills"

    # Remove stale symlinks
    for link in "$target_skills"/*/; do
      [ -d "$link" ] || continue
      name="$(basename "$link")"
      [ -d "$SKILLS_SOURCE/$name" ] || rm -f "$target_skills/$name"
    done

    # Create or update symlinks
    for skill in "$SKILLS_SOURCE"/*/; do
      [ -d "$skill" ] || continue
      ln -sfn "$skill" "$target_skills/$(basename "$skill")"
    done
  done
}
