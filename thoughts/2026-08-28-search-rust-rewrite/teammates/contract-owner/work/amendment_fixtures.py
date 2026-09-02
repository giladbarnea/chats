#!/usr/bin/env python3
"""Post-freeze shapes, in their own pool.

The main corpus is frozen. Adding session files to it would not be an amendment:
the session pool is an input to every broad-pattern case already frozen there, so
six new sessions move a fifth of the expectations. That is invalidation wearing
an amendment's clothes.

So these live in a second pool, additive by construction. Every case here is
self-contained against this pool and never reads the frozen one.

Several expectations here are wrong on purpose. Each says so at its definition.
Do not "fix" them: if a future change makes them right, the behaviour has moved
and these are the cases that are supposed to say so.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

CWD = "/tmp/search-amendment"
BASE_MTIME = 1800020000.0
BRANCH_FIXTURE_SOURCE = (
    Path(__file__).parent.parent.parent / "session-core" / "branch-fixtures"
)


def _claude_user(text: str, *, timestamp: str, uuid: str = "u1") -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "parentUuid": None,
        "timestamp": timestamp,
        "cwd": CWD,
        "message": {"role": "user", "content": text},
    }


# `_parse_iso_timestamp` converts to naive local time and drops the offset. Under
# `TZ=Asia/Jerusalem` these two instants — an hour apart in UTC — both land on
# `2026-10-25 01:30:00`, inside the autumn DST fold. Newest-first ordering and
# both date filters therefore cannot separate them for one hour every year.
#
# WRONG ON PURPOSE. A native implementation carrying aware UTC timestamps — the
# natural way to write it in Rust — orders these correctly and diverges. The
# shape never occurs naturally, so it has to be constructed; but its instants are
# absolute, so unlike an age band it is exactly what a fixture is for.
DST_FOLD_EARLY = "2026-10-24T22:30:00Z"
DST_FOLD_LATE = "2026-10-24T23:30:00Z"

# `parsing.py` accepts only an uppercase `Z`. A lowercase one returns None and
# the caller silently falls back to filesystem mtime, so the session sorts by a
# different clock, filters differently under `-ma` and `-ca`, and displays a
# different age.
#
# WRONG ON PURPOSE. ISO 8601 permits the lowercase form and `chrono` accepts it,
# so a port parses it, the session moves, and nothing errors anywhere.
LOWERCASE_Z_TIMESTAMP = "2026-08-20T10:00:00z"
# The identical instant with the accepted spelling. The pair is what makes the
# fallback observable: the two sessions carry the same in-band time and answer
# a date filter differently, which pins the behaviour without pinning a
# wall-clock value that would rot.
UPPERCASE_Z_TIMESTAMP = "2026-08-20T10:00:00Z"

# Both z-spelling sessions get a mtime in the PAST, unlike everything else in
# this pool. APFS lowers birthtime when an mtime is set earlier than it, and
# does not raise it when set later — so a future mtime leaves birthtime at
# "whenever this file was written", which is wall-clock and rots. A past mtime
# pins both, which is what makes the rendered `created:` and `modified:`
# stable enough to assert. The rendered date is the symptom item 6 is about;
# the None return is only the mechanism.
Z_PAIR_MTIME = 1704067260.0  # 2024-01-01 01:01 local

# Exactly one trailing space, on exactly the last line, is deleted. Two are
# preserved. One on a non-last line is preserved.
#
# WRONG ON PURPOSE, and asymmetric in both directions: a reimplementer who strips
# uniformly and one who preserves uniformly both change bytes.
TRAILING_ONE_LAST = "Renderspace body\nlast line has one trailing space "
TRAILING_TWO_LAST = "Renderspace body\nlast line has two trailing spaces  "
TRAILING_ONE_MIDDLE = "Renderspace middle line has one \nand a clean last line"

# `elide_to_width` counts code points. NFD spends two per accented character
# where NFC spends one, so the same visible title truncates about nine characters
# early in NFD.
#
# WRONG ON PURPOSE. A competent port reaches for display width, produces a
# *better* result, and diverges — the dangerous class, because the output looks
# correct and no reviewer flags it.
NFC_TITLE = unicodedata.normalize("NFC", "café résumé naïve" * 3)
NFD_TITLE = unicodedata.normalize("NFD", "café résumé naïve" * 3)
assert NFC_TITLE != NFD_TITLE and len(NFD_TITLE) > len(NFC_TITLE), (
    "Expected the two title forms to differ in code points while looking "
    "identical, which is the whole of what this pair tests."
)


def _titled(title: str, marker: str, timestamp: str) -> list[dict]:
    return [
        {"type": "custom-title", "customTitle": title},
        _claude_user(marker, timestamp=timestamp),
    ]


AMENDMENT_SESSIONS: dict[str, list[dict]] = {
    ".claude/projects/dst/c0000001-0000-4000-8000-000000000001.jsonl": [
        _claude_user("Renderdst early side of the fold", timestamp=DST_FOLD_EARLY)
    ],
    ".claude/projects/dst/c0000001-0000-4000-8000-000000000002.jsonl": [
        _claude_user("Renderdst late side of the fold", timestamp=DST_FOLD_LATE)
    ],
    ".claude/projects/zcase/c0000002-0000-4000-8000-000000000001.jsonl": [
        _claude_user("Renderzcase lowercase zulu suffix", timestamp=LOWERCASE_Z_TIMESTAMP)
    ],
    ".claude/projects/zcase/c0000002-0000-4000-8000-000000000002.jsonl": [
        _claude_user("Renderzcase uppercase zulu suffix", timestamp=UPPERCASE_Z_TIMESTAMP)
    ],
    ".claude/projects/space/c0000003-0000-4000-8000-000000000001.jsonl": [
        _claude_user(TRAILING_ONE_LAST, timestamp="2026-08-20T10:01:00.000Z")
    ],
    ".claude/projects/space/c0000003-0000-4000-8000-000000000002.jsonl": [
        _claude_user(TRAILING_TWO_LAST, timestamp="2026-08-20T10:02:00.000Z")
    ],
    ".claude/projects/space/c0000003-0000-4000-8000-000000000003.jsonl": [
        _claude_user(TRAILING_ONE_MIDDLE, timestamp="2026-08-20T10:03:00.000Z")
    ],
    ".claude/projects/norm/c0000004-0000-4000-8000-000000000001.jsonl": _titled(
        NFC_TITLE, "Rendernorm nfc subject", "2026-08-20T10:04:00.000Z"
    ),
    ".claude/projects/norm/c0000004-0000-4000-8000-000000000002.jsonl": _titled(
        NFD_TITLE, "Rendernorm nfd subject", "2026-08-20T10:05:00.000Z"
    ),
}

# `session-core` authored these, each asserting its structural precondition and
# the exact map `_resolve_branch_map` returns. Branch resolution is strictly
# intra-file, so searching them alone changes none of their maps.
BRANCH_FIXTURE_NAMES = (
    "truncated-head",
    "compaction-boundary",
    "rewind-to-first",
    "no-recorded-leaf",
    "combined-eras",
    "numbering-order",
)


AMENDMENT_CASES: list[dict] = [
    # ── DST fold: two instants an hour apart that the product cannot separate ──
    {"id": "dst-fold-order", "arguments": ["Renderdst", "-ll"], "columns": 96, "color": False},
    {"id": "dst-fold-metadata", "arguments": ["Renderdst", "-l"], "columns": 96, "color": False},
    {"id": "dst-fold-mafter-between", "arguments": ["Renderdst", "-ll", "-ma", "2026-10-25T01:00"], "columns": 96, "color": False},
    {"id": "dst-fold-cafter-between", "arguments": ["Renderdst", "-ll", "-ca", "2026-10-25T01:00"], "columns": 96, "color": False},
    # ── A lowercase `z` silently drops the session onto the filesystem clock ──
    # The seven-month error, as rendered bytes: identical in-band timestamps
    # and identical file mtimes, and the two spellings render different dates.
    {"id": "lowercase-z-rendered-dates", "arguments": ["Renderzcase", "-l"], "columns": 96, "color": False},
    {"id": "lowercase-z-ordering", "arguments": ["Renderzcase", "-ll"], "columns": 96, "color": False},
    {"id": "lowercase-z-mafter-splits-the-pair", "arguments": ["Renderzcase", "-ll", "-ma", "2026-08-21"], "columns": 96, "color": False},
    {"id": "lowercase-z-cafter-splits-the-pair", "arguments": ["Renderzcase", "-ll", "-ca", "2026-08-21"], "columns": 96, "color": False},
    # No `-f` case for this pair: rendering a lowercase-`z` timestamp raises an
    # uncaught ValueError from `model.py:34`, where `.replace("Z", "+00:00")`
    # misses the lowercase spelling. A traceback cannot be a golden — it bakes
    # machine paths, and the crash is ruled repaired rather than reproduced.
    # ── Trailing space, asymmetric in both directions ──
    {"id": "trailing-space-bodies", "arguments": ["Renderspace", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "trailing-space-raw", "arguments": ["Renderspace", "-f", "-r"], "columns": 96, "color": False},
    # ── Title elision counts code points, so NFD truncates early ──
    {"id": "normalization-title-elision-52", "arguments": ["Rendernorm", "-l", "--color", "always", "--no-paging"], "columns": 52, "color": True},
    # 72 columns pins nothing about normalization: neither form elides at that
    # width, so the two rows render identically. Kept deliberately — a width
    # where the implementations agree is a fact worth holding — but it is not
    # pulling discriminating weight, and someone would otherwise assume it is.
    {"id": "normalization-title-elision-72", "arguments": ["Rendernorm", "-l", "--color", "always", "--no-paging"], "columns": 72, "color": True},
    {"id": "normalization-title-panel-52", "arguments": ["Rendernorm", "--color", "always", "--no-paging", "--no-metadata"], "columns": 52, "color": True},
    # ── Branch resolution, at shapes real corpora carry at 1-2% prevalence ──
    # Markers are the fixtures' own text: `abandoned` appears only on off-main
    # branches, so the default and `-b` answers must differ; `branch off turn`
    # exists four times in `numbering-order`, where file order and traversal
    # order are deliberately reversed.
    {"id": "branch-abandoned-default", "arguments": ["abandoned", "-ll"], "columns": 96, "color": False},
    {"id": "branch-abandoned-with-flag", "arguments": ["-b", "abandoned", "-ll"], "columns": 96, "color": False},
    {"id": "branch-abandoned-bodies-default", "arguments": ["abandoned", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-abandoned-bodies-with-flag", "arguments": ["-b", "abandoned", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-kept-default", "arguments": ["kept", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-numbering-default", "arguments": ["branch off turn", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-numbering-with-flag", "arguments": ["-b", "branch off turn", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-compaction-bodies", "arguments": ["compaction", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-compaction-with-flag", "arguments": ["-b", "compaction", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-truncated-head", "arguments": ["trimmed transcript", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "branch-all-sessions", "arguments": [".", "-ll"], "columns": 96, "color": False},
    {"id": "branch-all-sessions-with-flag", "arguments": ["-b", ".", "-ll"], "columns": 96, "color": False},
]


# ── Codex sessions that are entirely injected scaffolding ────────────────────
#
# INVISIBLE ON PURPOSE. These sessions carry real prose and must NOT appear in
# `ch search .`. A port that shows them has broken visibility, not improved
# recall. Found by `reviewer-profiler` in a real 695-file corpus: the branch
# returned 563 ids where the Python product returns 560, and the three extra
# sessions were composed only of scaffolding Codex injects before anyone types.
#
# Nobody writes this fixture, because it is not an interesting case. Real usage
# produces it at roughly one percent — a directory is opened, AGENTS.md and the
# environment block are injected, and the turn is abandoned. Curated fixtures
# cover the cases someone thought of; this is one nobody would.
#
# The mechanism is the role, not the content: `_codex_entry_has_default_visible_text`
# handles `user` and `assistant` and returns False for everything else. The three
# shapes are separated because a port could get one right and the others wrong.
CODEX_DEVELOPER_PERMISSIONS = (
    "<permissions instructions>\nThe assistant may read files in the workspace "
    "and must ask before writing outside it.\n</permissions instructions>"
)
CODEX_AGENTS_PREAMBLE = (
    "# AGENTS.md instructions for /tmp/search-amendment\n\n"
    "Prefer small commits. Run the test suite before pushing."
)
CODEX_ENVIRONMENT_CONTEXT = (
    "<environment_context><cwd>/tmp/search-amendment</cwd>"
    "<shell>zsh</shell></environment_context>"
)
# A developer-role message whose content is unmistakably real prose. This is the
# negative control for the role rule: a port that filters by content pattern
# rather than by role passes the three above and fails this one.
CODEX_TURN_ABORTED = (
    "<turn_aborted>The previous turn was interrupted before the assistant "
    "replied. No work was completed and nothing was written to disk.</turn_aborted>"
)


def _codex_session(session_id: str, entries: list[tuple[str, str]]) -> list[dict]:
    return [
        {"type": "session_meta", "payload": {"id": session_id, "cwd": CWD}},
        *(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": text}],
                },
            }
            for role, text in entries
        ),
    ]


PREAMBLE_ONLY_SESSIONS: dict[str, list[dict]] = {
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-00-00-d0000001-0000-4000-8000-000000000001.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000001", [("developer", CODEX_DEVELOPER_PERMISSIONS)]),
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-01-00-d0000001-0000-4000-8000-000000000002.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000002", [("user", CODEX_AGENTS_PREAMBLE)]),
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-02-00-d0000001-0000-4000-8000-000000000003.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000003", [("user", CODEX_ENVIRONMENT_CONTEXT)]),
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-03-00-d0000001-0000-4000-8000-000000000004.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000004", [("developer", CODEX_TURN_ABORTED)]),
    # All three together, the shape the real sessions actually had.
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-04-00-d0000001-0000-4000-8000-000000000005.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000005", [
            ("developer", CODEX_DEVELOPER_PERMISSIONS),
            ("user", CODEX_AGENTS_PREAMBLE),
            ("user", CODEX_ENVIRONMENT_CONTEXT),
        ]),
    # The control that makes the four above mean something: one visible message
    # in the same provider and pool, which must appear.
    ".codex/sessions/2026/08/20/rollout-2026-08-20T12-05-00-d0000001-0000-4000-8000-000000000006.jsonl":
        _codex_session("d0000001-0000-4000-8000-000000000006", [
            ("developer", CODEX_DEVELOPER_PERMISSIONS),
            ("user", CODEX_AGENTS_PREAMBLE),
            ("assistant", "Renderpreamble visible assistant reply"),
        ]),
}
AMENDMENT_SESSIONS.update(PREAMBLE_ONLY_SESSIONS)

AMENDMENT_CASES.extend([
    {"id": "preamble-only-invisible-to-dot", "arguments": [".", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-only-invisible-to-dot-all", "arguments": ["-A", ".", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-developer-role-search", "arguments": ["permissions instructions", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-agents-md-search", "arguments": ["AGENTS.md instructions", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-environment-context-search", "arguments": ["environment_context", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-turn-aborted-search", "arguments": ["previous turn was interrupted", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-visible-sibling-search", "arguments": ["Renderpreamble", "-ll"], "columns": 96, "color": False},
    {"id": "preamble-visible-sibling-body", "arguments": ["Renderpreamble", "-f", "--no-metadata"], "columns": 96, "color": False},
])


# Sessions whose stat mtime is overridden rather than taken from the pool
# sequence. Keyed by the same relative path.
MTIME_OVERRIDES: dict[str, float] = {
    ".claude/projects/zcase/c0000002-0000-4000-8000-000000000001.jsonl": Z_PAIR_MTIME,
    ".claude/projects/zcase/c0000002-0000-4000-8000-000000000002.jsonl": Z_PAIR_MTIME + 1,
}
