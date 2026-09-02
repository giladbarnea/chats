#!/usr/bin/env python3
"""Run every public `ch search` shape against the fixture corpus and record behavior."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRATCH = Path(__file__).parent
HOME = SCRATCH / "home"
CH = Path("/Users/giladbarnea/dev/chats/.venv/bin/ch")

SHAPES: list[tuple[str, list[str]]] = [
    # --- result modes ---
    ("matches-default", ["search", "needle"]),
    ("list", ["search", "-l", "needle"]),
    ("only-id", ["search", "-ll", "needle"]),
    ("full", ["search", "-f", "needle"]),
    ("raw", ["search", "-r", "needle"]),
    ("no-metadata", ["search", "--no-metadata", "needle"]),
    # --- ordering / whole pool ---
    ("dot-only-id", ["search", "-ll", "."]),
    ("dot-list", ["search", "-l", "."]),
    # --- boolean truth ---
    ("and-same-session", ["search", "-ll", "booleanalpha AND booleanbeta"]),
    ("and-cross-session", ["search", "-ll", "booleanalpha AND needle"]),
    ("or", ["search", "-ll", "booleanalpha OR needle"]),
    ("not", ["search", "-ll", "needle NOT summary"]),
    ("paren-group", ["search", "-ll", "(booleanalpha OR nomatchxyz) AND booleanbeta"]),
    ("quoted-term", ["search", "-ll", '"pi body" AND needle']),
    # --- malformed queries ---
    ("mix-not-and", ["search", "-ll", "a AND b NOT c"]),
    ("dangling-and", ["search", "-ll", "foo AND"]),
    ("unclosed-paren", ["search", "-ll", "(foo AND bar"]),
    ("empty-quoted", ["search", "-ll", '"" AND foo']),
    ("unexpected-term", ["search", "-ll", "foo AND bar baz"]),
    ("bare-operator-only", ["search", "-ll", "AND"]),
    ("unterminated-quote", ["search", "-ll", '"foo']),
    # --- regex vs literal fallback ---
    ("regex-dotstar", ["search", "-ll", "book.*alpha"]),
    ("regex-invalid-falls-back-literal", ["search", "-ll", "a.b*c"]),
    ("regex-invalid-syntax", ["search", "-ll", "foo["]),
    ("unicode-literal", ["search", "-ll", "ünïcodé"]),
    ("anchored", ["search", "-ll", "^plain alpha body$"]),
    # --- case sensitivity ---
    ("case-default", ["search", "-ll", "NEEDLE"]),
    ("case-sensitive", ["search", "-ll", "-s", "NEEDLE"]),
    ("case-insensitive-explicit", ["search", "-ll", "-i", "NEEDLE"]),
    ("case-both-flags", ["search", "-ll", "-s", "-i", "NEEDLE"]),
    # --- visibility-sensitive semantics ---
    ("thinking-hidden-by-default", ["search", "-ll", "thinkingonlyneedle"]),
    ("thinking-shown", ["search", "-ll", "-T", "thinkingonlyneedle"]),
    ("tool-hidden-by-default", ["search", "-ll", "toolonlyneedle"]),
    ("tool-shown", ["search", "-ll", "-t", "toolonlyneedle"]),
    ("tool-output-shown", ["search", "-ll", "-t", "tooloutputneedle"]),
    ("tool-filtered-out", ["search", "-ll", "-t", "!Bash", "toolonlyneedle"]),
    ("all-flag", ["search", "-ll", "-A", "thinkingonlyneedle"]),
    ("only-user", ["search", "-ll", "--only-user", "alpha assistant reply"]),
    ("only-assistant", ["search", "-ll", "--only-assistant", "plain alpha body"]),
    ("only-user-and-assistant", ["search", "-ll", "--only-user", "--only-assistant", "needle"]),
    ("only-user-overrides-tools", ["search", "-ll", "--only-user", "-t", "needle"]),
    # --- facets ---
    ("summary-facet", ["search", "-ll", "Alpha summary mentions"]),
    ("custom-title-facet", ["search", "-ll", "Titled needle session"]),
    # --- pool filters ---
    ("provider-claude", ["search", "-ll", "-p", "claude", "needle"]),
    ("provider-pi", ["search", "-ll", "-p", "pi", "needle"]),
    ("provider-codex", ["search", "-ll", "-p", "codex", "needle"]),
    ("provider-invalid", ["search", "-ll", "-p", "gemini", "needle"]),
    ("dir-filter", ["search", "-ll", "-d", "/tmp/ch-contract/alpha", "needle"]),
    ("dir-filter-nomatch", ["search", "-ll", "-d", "/tmp/ch-contract/nope", "needle"]),
    ("mafter-wide", ["search", "-ll", "-ma", "9999d", "needle"]),
    ("mafter-narrow", ["search", "-ll", "-ma", "1d", "needle"]),
    ("cafter-wide", ["search", "-ll", "-ca", "9999d", "needle"]),
    ("mafter-bad-date", ["search", "-ll", "-ma", "notadate", "needle"]),
    # --- no results / exits ---
    ("no-results", ["search", "-ll", "zzznomatchzzz"]),
    ("no-results-matches-mode", ["search", "zzznomatchzzz"]),
    ("no-results-with-filter", ["search", "-p", "claude", "zzznomatchzzz"]),
    # --- grammar errors and repairs ---
    ("missing-pattern", ["search"]),
    ("unknown-flag", ["search", "--bogus", "needle"]),
    ("short-swallows-pattern", ["search", "--short", "needle"]),
    ("short-with-spec", ["search", "--short=p=64", "-ll", "needle"]),
    ("short-bad-spec", ["search", "--short=7", "-ll", "needle"]),
    ("dash-s-is-case-not-short", ["search", "-s", "-ll", "needle"]),
    ("help", ["search", "--help"]),
    # --- color / paging ---
    ("color-always-list", ["search", "-l", "--color", "always", "needle"]),
    ("color-never-list", ["search", "-l", "--color", "never", "needle"]),
    ("only-id-color-always", ["search", "-ll", "--color", "always", "needle"]),
    ("paging-explicit-off", ["search", "--no-paging", "needle"]),
]


def run(args: list[str]) -> tuple[int, str, str]:
    environment = dict(os.environ)
    environment["HOME"] = str(HOME)
    environment["COLUMNS"] = "100"
    environment.pop("NO_COLOR", None)
    completed = subprocess.run(
        [str(CH), *args],
        env=environment,
        capture_output=True,
        text=True,
        cwd=str(SCRATCH),
    )
    return completed.returncode, completed.stdout, completed.stderr


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, args in SHAPES:
        if only and only not in name:
            continue
        code, out, err = run(args)
        print(f"\n{'=' * 78}\n### {name}: ch {' '.join(args)}\n--- exit={code}")
        if out:
            print(f"--- stdout ---\n{out.rstrip()}")
        if err:
            print(f"--- stderr ---\n{err.rstrip()}")


if __name__ == "__main__":
    main()
