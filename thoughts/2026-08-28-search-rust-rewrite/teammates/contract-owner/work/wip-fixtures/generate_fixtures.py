#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Generate the cycle-03 search-command contract fixtures.

Builds the static fixture home, runs every manifest case through the checkout
installed launcher (legacy search route), normalizes volatile paths, and writes
expected byte files plus MANIFEST.json and MTIMES.json under
tests/data/search-command-fixtures/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats-cycle02-ox")
CH = PROJECT_ROOT / ".venv/bin/ch"
FIXTURE_ROOT = PROJECT_ROOT / "tests/data/search-command-fixtures"
HOME_PARENT = Path("/tmp/ch03-gen")
HOME = HOME_PARENT / "home"
CWD = "/tmp/search-contract"

CASES: list[dict] = [
    # ---- help / usage ------------------------------------------------------
    {"id": "help-long", "arguments": ["--help"]},
    {"id": "help-short", "arguments": ["-h"]},
    # ---- strict argparse errors -------------------------------------------
    {"id": "err-unrecognized-flag", "arguments": ["needle", "--bogus-flag"]},
    {"id": "err-extra-positional", "arguments": ["needle", "extra"]},
    {"id": "err-missing-pattern", "arguments": []},
    {"id": "err-case-exclusive", "arguments": ["needle", "-s", "-i"]},
    {"id": "err-bad-color-choice", "arguments": ["needle", "--color", "bogus"]},
    {"id": "err-bad-thinking-value", "arguments": ["needle", "-T", "bogus"]},
    {"id": "err-bad-short-spec", "arguments": ["needle", "--short=bogusspec"]},
    {"id": "err-bad-provider-choice", "arguments": ["needle", "-p", "gpt"]},
    {"id": "err-thinking-swallowed-pattern", "arguments": ["-T", "needle"]},
    {
        "id": "err-tools-path-pattern-required",
        "arguments": ["-t", "{HOME}/.claude/projects/alpha/11111111-1111-4111-8111-111111111111.jsonl"],
    },
    # ---- pattern repair rules ---------------------------------------------
    {"id": "repair-short-detached", "arguments": ["--short", "needle five", "-ll"]},
    {"id": "repair-short-digits", "arguments": ["--short", "128", "needle five", "-ll"]},
    {"id": "repair-short-spec", "arguments": ["--short", "p=128", "needle five", "-ll"]},
    {"id": "only-id-forces-plain", "arguments": ["needle five", "-ll", "--color", "always", "--paging"]},
    {"id": "raw-forces-plain-nometa", "arguments": ["needle five", "-r", "--color", "always"], "color": True},
    # ---- boolean query grammar --------------------------------------------
    {"id": "bool-and-cross-message", "arguments": ["fox AND dog", "--no-metadata", "--color", "never"]},
    {"id": "bool-or", "arguments": ["red OR quick", "--no-metadata", "--color", "never"]},
    {"id": "bool-parens-precedence", "arguments": ["(red OR quick) AND fox", "--no-metadata", "--color", "never"]},
    {"id": "bool-not-only", "arguments": ["needle NOT alpha", "--no-metadata", "--color", "never"]},
    {"id": "err-not-leading", "arguments": ["NOT needle"]},
    {"id": "err-and-trailing", "arguments": ["needle AND"]},
    {"id": "err-or-leading", "arguments": ["OR needle"]},
    {"id": "err-mixed-not-and", "arguments": ["NOT needle AND fox"]},
    {"id": "err-not-parens", "arguments": ["needle NOT (fox)"]},
    {"id": "err-not-double-term", "arguments": ["needle NOT fox dog"]},
    {"id": "err-not-trailing", "arguments": ["needle NOT"]},
    {"id": "single-and-literal-icase", "arguments": ["AND", "--no-metadata", "--color", "never"]},
    {"id": "precedence-and-over-or", "arguments": ["needleone OR (fox AND dog)", "--no-metadata", "--color", "never"]},
    {"id": "quoted-without-operator-is-literal-quotes", "arguments": ['"Alpha needle one"', "--color", "never"]},
    {"id": "empty-quoted-no-operator", "arguments": ['""', "--color", "never"]},
    {"id": "apostrophe-midword", "arguments": ["don't panic", "-ll"]},
    {"id": "quoted-term-inside-operators", "arguments": ['"red fox" AND dog', "--no-metadata", "--color", "never"]},
    # ---- regex boundary: valid patterns ------------------------------------
    {"id": "rx-anchor-start", "arguments": ["^line2", "-ll"]},
    {"id": "rx-anchor-end", "arguments": ["end$", "-ll"]},
    {"id": "rx-digit-class", "arguments": ["foo\\d+", "-ll"]},
    {"id": "rx-upper-class", "arguments": ["[A-Z]+PITAL", "-ll"]},
    {"id": "rx-dotall", "arguments": ["one.*three", "-ll"]},
    {"id": "rx-multiline", "arguments": ["^two$", "-ll"]},
    {"id": "rx-word-boundary", "arguments": ["\\bMIDDLE\\b", "-ll"]},
    {"id": "rx-named-group-backref", "arguments": ["(?P<w>echo) (?P=w)", "-ll"]},
    {"id": "rx-lookahead", "arguments": ["foo(?=123)", "-ll"]},
    {"id": "rx-negative-lookahead", "arguments": ["foo(?!999)", "-ll"]},
    {"id": "rx-lookbehind", "arguments": ["(?<=start )MIDDLE", "-ll"]},
    {"id": "rx-group-alternation", "arguments": ["(red|quick)", "-ll"]},
    {"id": "rx-escaped-hyphen", "arguments": ["a\\-b", "-ll"]},
    {"id": "rx-tab-escape", "arguments": ["tab\\tend", "-ll"]},
    {"id": "rx-hex-escape", "arguments": ["caf\\u00e9", "-ll"]},
    {"id": "rx-octal-A", "arguments": ["C\\101PITAL", "-ll"]},
    {"id": "rx-named-unicode", "arguments": ["\\N{GREEK SMALL LETTER ALPHA}", "-ll"]},
    {"id": "rx-atomic-group", "arguments": ["(?>echo) echo", "-ll"]},
    {"id": "rx-possessive-quantifier", "arguments": ["a++g", "-ll"]},
    {"id": "rx-conditional-valid", "arguments": ["()(?(1)kettlexyz|zzz)", "-ll"]},
    {"id": "dv-z-anchor-absolute-end-miss", "arguments": ["end\\\\Z", "-ll"]},
    {"id": "dv-z-anchor-single-backslash-hit", "arguments": ["end\\Z", "-ll"]},
    {"id": "rx-inline-flag-scoped", "arguments": ["(?i:NEEDLE) one", "-ll"]},
    {"id": "rx-backref-icase", "arguments": ["(?P<w>ECHO) (?P=w)", "-ll"]},
    # ---- regex boundary: python-invalid -> literal fallback -----------------
    {"id": "fb-lookbehind-alt-syntax", "arguments": ["(?<x>a)", "-ll"]},
    {"id": "fb-unicode-prop", "arguments": ["\\p{L}", "-ll"]},
    {"id": "fb-braced-hex", "arguments": ["\\x{41} braced hex", "-ll"]},
    {"id": "fb-bad-range", "arguments": ["[z-a] range", "-ll"]},
    {"id": "fb-inverted-interval", "arguments": ["a{2,1} inverted", "-ll"]},
    {"id": "fb-digit-ref", "arguments": ["\\8 digit ref", "-ll"]},
    {"id": "fb-group-name-ref", "arguments": ["(?P=name) group ref", "-ll"]},
    {"id": "fb-conditional-invalid", "arguments": ["(?(1)x|y) conditional", "-ll"]},
    {"id": "fb-bad-escape-y", "arguments": ["\\y bad escape", "-ll"]},
    {"id": "fb-unmatched-paren", "arguments": ["open( paren", "-ll"]},
    {"id": "fb-bracket-mismatch", "arguments": ["bracket[mismatch", "-ll"]},
    {"id": "fb-posix-class-warning", "arguments": ["[[:alpha:]] class", "-ll"]},
    {"id": "fb-posix-class-bare-warning", "arguments": ["[[:alpha:]]", "-ll"]},
    # ---- regex divergence pins ----------------------------------------------
    {"id": "dv-empty-branch-all", "arguments": ["zznope|", "-ll"]},
    {"id": "dv-empty-branch-real", "arguments": ["fox|", "-ll"]},
    {"id": "dv-icase-dotted-i-hit", "arguments": ["istanbul dotted", "-ll"]},
    {"id": "dv-icase-dotted-i-pattern-hit", "arguments": ["İstanbul dotted", "-ll"]},
    {"id": "dv-icase-long-s", "arguments": ["steady long s", "-ll"]},
    {"id": "dv-icase-long-s-reverse", "arguments": ["ſteady long s", "-ll"]},
    {"id": "dv-icase-kelvin", "arguments": ["kelvin k sign", "-ll"]},
    {"id": "dv-sensitive-kelvin-explicit", "arguments": ["kelvin K sign", "-s", "-ll"]},
    {"id": "dv-sensitive-needle-miss", "arguments": ["needle five", "-s", "-ll"]},
    {"id": "role-only-assistant-hit", "arguments": ["response five", "--only-assistant", "-ll"]},
    # ---- candidate-gate equivalence ------------------------------------------
    {"id": "gate-uescaped-letter", "arguments": ["uescaped tab content needle", "-ll"]},
    {"id": "gate-escaped-slash", "arguments": ["slash a/b end", "-ll"]},
    {"id": "gate-quote-needle-serial", "arguments": ['say "hi"', "-ll"]},
    {"id": "gate-backslash-needle", "arguments": ["back\\\\slash", "-ll"]},
    {"id": "gate-control-char-needle", "arguments": ["plus\ttab café", "-ll"]},
    {"id": "gate-cafe-across-providers", "arguments": ["café", "-ll"]},
    {"id": "gate-false-candidate-rejected", "arguments": ["e9 accent", "-ll"]},
    {"id": "gate-decoded-e-acute", "arguments": ["only é accent", "-ll"]},
    {"id": "gate-pi-marker-hit", "arguments": ["pi-user-agents explicitly", "-ll"]},
    # ---- semantic confirmation: visibility -----------------------------------
    {"id": "vis-toolresult-hidden-default", "arguments": ["vistooloutput", "-ll"]},
    {"id": "vis-toolresult-shown-tools", "arguments": ["vistooloutput", "-t", "-ll"]},
    {"id": "vis-tooluse-hidden-default", "arguments": ["visbashcommand", "-ll"]},
    {"id": "vis-tooluse-shown-tools", "arguments": ["visbashcommand", "-t", "-ll"]},
    {"id": "vis-thinking-hidden-default", "arguments": ["vishushhush", "-ll"]},
    {"id": "vis-thinking-shown-flag", "arguments": ["vishushhush", "-T", "-ll"]},
    {"id": "vis-thinking-short", "arguments": ["vishushhush", "-T", "short", "-ll"]},
    {"id": "vis-plans-hidden-default", "arguments": ["visplansteps", "-ll"]},
    {"id": "vis-plans-shown-flag", "arguments": ["visplansteps", "--plans", "-ll"]},
    {"id": "vis-branch-hidden-default", "arguments": ["branchabandoned", "-ll"]},
    {"id": "vis-branch-shown-flag", "arguments": ["branchabandoned", "-b", "-ll"]},
    {"id": "vis-sidechain-hidden-default", "arguments": ["sidechainagentsecret", "-ll"]},
    {"id": "vis-sidechain-shown-agents", "arguments": ["sidechainagentsecret", "-a", "-ll"]},
    {"id": "vis-hook-context-hidden-default", "arguments": ["hookcontexttext", "-ll"]},
    {"id": "vis-hook-context-shown-tools", "arguments": ["hookcontexttext", "-t", "-ll"]},
    {"id": "vis-additionalcontext-marker-tools", "arguments": ["AdditionalContext", "-t", "-ll"]},
    {"id": "vis-additionalcontext-marker-default", "arguments": ["AdditionalContext", "-ll"]},
    {"id": "vis-thinking-marker-flag", "arguments": ["thinking", "-T", "-ll"]},
    {"id": "vis-tool-input-marker", "arguments": ["tool-input", "-t", "-ll"]},
    {"id": "vis-tool-output-marker", "arguments": ["tool-output", "-t", "-ll"]},
    {"id": "vis-exitplanmode-marker", "arguments": ["ExitPlanMode", "--plans", "-ll"]},
    {"id": "vis-fence-with-tools", "arguments": ["```", "-t", "-ll"]},
    {"id": "vis-fence-default", "arguments": ["```", "-ll"]},
    {"id": "vis-old-string-with-tools", "arguments": ["old_string:", "-t", "-ll"]},
    {"id": "vis-old-string-default", "arguments": ["old_string:", "-ll"]},
    {"id": "vis-rendered-tag-miss", "arguments": ["<user-message", "-ll"]},
    {"id": "vis-rendered-attr-default-miss", "arguments": ['="', "-ll"]},
    {"id": "vis-rendered-attr-tools-hit", "arguments": ['="', "-t", "-ll"]},
    # ---- semantic confirmation: facets, titles, summaries --------------------
    {"id": "facet-summary-match", "arguments": ["Alpha summary needle three", "-ll"]},
    {"id": "facet-custom-title-match", "arguments": ["Alpha Title", "-ll"]},
    {"id": "facet-pi-session-title", "arguments": ["Pi Current Title", "-ll"]},
    {"id": "facet-title-only-session", "arguments": ["TitleOnlySession name", "-ll"]},
    {"id": "facet-summary-only-session", "arguments": ["SummaryOnlySession digest", "-ll"]},
    {"id": "facet-empty-session-absent", "arguments": ["file-history-snapshot", "-ll"]},
    {"id": "pi-agent-record-needs-agents", "arguments": ["piagentsubagent", "-a", "-ll"]},
    {"id": "pi-agent-record-default-miss", "arguments": ["piagentsubagent", "-ll"]},
    {"id": "pi-user-agent-joined-visible-default", "arguments": ["piuseragentresponse", "-ll"]},
    {"id": "pi-arbitrary-custom-needs-all", "arguments": ["piarbitrarycustom", "-A", "-ll"]},
    {"id": "pi-arbitrary-custom-agents-miss", "arguments": ["piarbitrarycustom", "-a", "-ll"]},
    {"id": "codex-preamble-invisible", "arguments": ["preamblesecret", "-ll"]},
    {"id": "codex-preamble-invisible-all", "arguments": ["preamblesecret", "-A", "-ll"]},
    # ---- dot fast path --------------------------------------------------------
    {"id": "dot-only-id-full", "arguments": [".", "-ll"]},
    {"id": "dot-only-id-provider-codex", "arguments": [".", "-ll", "-p", "codex"]},
    {"id": "dot-only-id-dir-a", "arguments": [".", "-ll", "-d", "/tmp/search-contract/dir-a"]},
    {"id": "dot-not-special-as-regex", "arguments": ["needle.five", "-ll"]},
    # ---- pool filters -----------------------------------------------------------
    {"id": "filter-dir-match", "arguments": ["dirfilter", "-d", "/tmp/search-contract/dir-a", "-ll"]},
    {"id": "filter-dir-miss", "arguments": ["dirfilter", "-d", "/nonexistent/dir", "-ll"]},
    {"id": "filter-mafter-boundary", "arguments": ["dirfilter", "-ma", "2026-08-21", "-ll"]},
    {"id": "filter-mafter-inclusive", "arguments": ["dirfilter", "-ma", "2026-08-20", "-ll"]},
    {"id": "filter-cafter-old", "arguments": ["needle five", "-ca", "2020-01-01", "-ll"]},
    {"id": "filter-cafter-future", "arguments": ["needle five", "-ca", "2030-01-01", "-ll"]},
    {"id": "filter-provider-pi", "arguments": ["needle four", "-p", "pi", "-ll"]},
    # ---- shortening interaction --------------------------------------------------
    {"id": "shorten-elided-middle-miss", "arguments": ["middlenosecret", "-t", "--short=p=64", "-ll"]},
    {"id": "shorten-elided-middle-hit", "arguments": ["middlenosecret", "-t", "-ll"]},
    {"id": "shorten-tail-survives", "arguments": ["longtooloutput tail", "-t", "--short=p=64", "-ll"]},
    # ---- role filters --------------------------------------------------------------
    {"id": "role-only-user", "arguments": ["needle five", "--only-user", "-ll"]},
        {"id": "role-contradiction-warning", "arguments": ["needle five", "--only-assistant", "--thinking", "--color", "never"]},
    # ---- tool filter specs -----------------------------------------------------------
    {"id": "tools-filter-modifier", "arguments": ["longtooloutput", "-t", "Bash:i", "-ll"]},
    {"id": "tools-multi-name-spec-narrows", "arguments": ["longtooloutput", "-t", "Bash:bogusmod", "-ll"]},
    # ---- output modes ------------------------------------------------------------------
    {"id": "mode-matches-meta", "arguments": ["needle five", "--color", "never"]},
    {"id": "mode-matches-nometa", "arguments": ["needle five", "--no-metadata", "--color", "never"]},
    {"id": "mode-list-meta", "arguments": ["needle five", "-l", "--color", "never"]},
    {"id": "mode-list-nometa", "arguments": ["needle five", "-l", "--no-metadata", "--color", "never"]},
    {"id": "mode-full-meta", "arguments": ["needle five", "-f", "--color", "never"]},
    {"id": "mode-full-nometa", "arguments": ["needle five", "-f", "--no-metadata", "--color", "never"]},
    {"id": "mode-precedence-list-beats-full", "arguments": ["needle five", "-l", "-f", "--color", "never"]},
    {"id": "mode-precedence-id-beats-list", "arguments": ["needle five", "-ll", "-l"]},
    {"id": "raw-single-message-session", "arguments": ["sidechainagentsecret", "-a", "-r"]},
    {"id": "raw-multi-session", "arguments": ["needle five", "-r"]},
    {"id": "raw-full-breadth", "arguments": ["needle five", "-r", "-f"]},
    {"id": "nohit-matches-hint", "arguments": ["zznope", "--color", "never"]},
    {"id": "nohit-list-hint", "arguments": ["zznope", "-l", "--color", "never"]},
    {"id": "nohit-full-hint", "arguments": ["zznope", "-f", "--color", "never"]},
    {"id": "nohit-raw-hint", "arguments": ["zznope", "-r"]},
    {"id": "nohit-only-id-silent", "arguments": ["zznope", "-ll"]},
    {"id": "nohit-filtered-hint-suffix", "arguments": ["zznope", "-p", "pi", "--color", "never"]},
    {"id": "colored-list-fixed-width", "arguments": ["needle five", "-l", "--color", "always", "--no-paging"], "color": True},
    {"id": "colored-matches-panels", "arguments": ["needle five", "--color", "always", "--no-paging", "--no-metadata"], "color": True},
    {"id": "colored-full-panel", "arguments": ["needle five", "-f", "--color", "always", "--no-paging", "--no-metadata"], "color": True},
    {"id": "colored-hue-cycle-four-hits", "arguments": ["needle|dirfilter|tieorder", "--color", "always", "--no-paging", "--no-metadata"], "color": True},
    {"id": "colored-narrow-columns-80", "arguments": ["needle five", "--color", "always", "--no-paging", "--no-metadata"], "color": True, "columns": 80},
    {"id": "colored-highlight-painting", "arguments": ['"needle one" AND panic', "--color", "always", "--no-paging", "--no-metadata"], "color": True},
    {"id": "pager-engaged-real-less-piped", "arguments": ["needle five", "--color", "always", "--no-metadata"], "color": True},
]


def environment(color: bool, columns: int, home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "TZ": "Asia/Jerusalem",
        "COLUMNS": str(columns),
        "LINES": "40",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
    })
    if not color:
        env["NO_COLOR"] = "1"
    return env


def normalize(content: bytes, home: Path) -> bytes:
    """Normalize volatile bytes: paths, warning source roots, and the
    wall-clock relative age token that colored list rows and panel titles
    render from ``humanize_age`` (e.g. ``1d`` flipping to ``2d`` at the next
    UTC day boundary)."""
    normalized = (
        content.replace(str(home).encode(), b"{HOME}")
        .replace(str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}")
    )
    normalized = re.sub(
        rb"(\x1b\[[0-9;]*m)(\d{1,3}[smhdw]|\?)(\x1b\[0m)",
        rb"\g<1>{AGE}\g<3>",
        normalized,
    )
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def main() -> None:
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    source_home = Path(sys.argv[1])
    fixture_home = FIXTURE_ROOT / "home"
    shutil.copytree(source_home, fixture_home, symlinks=True)

    mtimes: dict[str, float] = {}
    for path in sorted(fixture_home.rglob("*")):
        if path.is_file():
            rel = path.relative_to(fixture_home).as_posix()
            stat = path.stat()
            mtimes[rel] = stat.st_mtime
            os.utime(path, (stat.st_mtime, stat.st_mtime))
    (FIXTURE_ROOT / "MTIMES.json").write_text(
        json.dumps(mtimes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    expected_dir = FIXTURE_ROOT / "expected"
    expected_dir.mkdir()
    manifest_cases: list[dict] = []
    for case in CASES:
        raw_arguments = [str(argument) for argument in case["arguments"]]
        arguments = [
            argument.replace("{HOME}", str(fixture_home))
            for argument in raw_arguments
        ]
        completed = subprocess.run(
            [str(CH), "search", *arguments],
            cwd=str(PROJECT_ROOT),
            env=environment(bool(case.get("color")), int(case.get("columns", 96)), fixture_home),
            input=b"",
            capture_output=True,
            check=False,
        )
        stdout_file = f"expected/{case['id']}.stdout"
        stderr_file = f"expected/{case['id']}.stderr"
        (expected_dir / f"{case['id']}.stdout").write_bytes(normalize(completed.stdout, fixture_home))
        (expected_dir / f"{case['id']}.stderr").write_bytes(normalize(completed.stderr, fixture_home))
        manifest_cases.append({
            "id": case["id"],
            "arguments": raw_arguments,
            "expected_stdout": stdout_file,
            "expected_stderr": stderr_file,
            "exit_status": completed.returncode,
            "color": bool(case.get("color")),
            "columns": int(case.get("columns", 96)),
        })
        print(f"{case['id']}: exit={completed.returncode} out={len(completed.stdout)} err={len(completed.stderr)}")

    (FIXTURE_ROOT / "MANIFEST.json").write_text(
        json.dumps({"cases": manifest_cases}, indent=2) + "\n", encoding="utf-8"
    )

    # Provenance: keep the deterministic builders beside the fixtures so the
    # contract never depends on /tmp volatility (review F6).
    this_script = Path(__file__).resolve()
    shutil.copyfile(this_script, FIXTURE_ROOT / "generate_fixtures.py")
    for builder_name in ("ch03-build-home.py", "build_home.py"):
        builder_candidate = this_script.parent / builder_name
        if builder_candidate.exists():
            shutil.copyfile(builder_candidate, FIXTURE_ROOT / "build_home.py")
            break
    print(f"\nwrote {len(manifest_cases)} cases to {FIXTURE_ROOT}")


if __name__ == "__main__":
    main()
