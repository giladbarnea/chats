#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = []
# ///
"""Expand SEED.json into a generated adversarial session home plus a case list.

The corpus beside this one (`search-command-fixtures`) is characterized and
pinned: regenerating it is a correctness event. This corpus is generated and
regenerable: rebuilding it is routine. The two must not share a directory,
because confusing them is silent in the dangerous direction.

Deterministic. Same seed, same bytes. No wall-clock input anywhere — session
timestamps are fixed absolute values, so nothing here rots on a clock the way
an age-coloured fixture does.

Usage:
    uv run build_home.py <destination>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SEED_PATH = Path(__file__).parent / "SEED.json"

# Fixed. Never `datetime.now()` — a generated corpus that moves with the clock
# is the defect this project has already shipped twice.
BASE_TIMESTAMP = "2026-08-20T10:00:00Z"
PROJECT_CWD = "/tmp/search-content-fuzz"


def claude_summary(text: str, leaf: str) -> dict:
    return {"type": "summary", "summary": text, "leafUuid": leaf}


def claude_user(text: str, index: int, **extra: object) -> dict:
    entry = {
        "type": "user",
        "uuid": f"u-{index:04d}",
        "timestamp": BASE_TIMESTAMP,
        "message": {"role": "user", "content": text},
        "cwd": PROJECT_CWD,
    }
    entry.update(extra)
    return entry


def claude_assistant(text: str, index: int, **extra: object) -> dict:
    entry = {
        "type": "assistant",
        "uuid": f"a-{index:04d}",
        "timestamp": BASE_TIMESTAMP,
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": text}],
        },
    }
    entry.update(extra)
    return entry


def place(decoration: str, needle: str, placement: str) -> str:
    """Put the adversarial run before, around, or after the needle.

    Placement matters: a length-changing fold only shifts offsets for text that
    follows it, so `before` and `around` can abort where `after` renders fine.
    """
    if placement == "before":
        return f"{decoration} {needle} tail"
    if placement == "after":
        return f"head {needle} {decoration}"
    if placement == "around":
        return f"{decoration} {needle} {decoration}"
    if placement == "line-start":
        return f"{decoration}{{\"looks-like-json\": true}} {needle}"
    raise ValueError(f"unknown placement: {placement}")


def sessions_for_shape(shape: dict, needle: str) -> list[tuple[str, list[dict]]]:
    """Return (session_name, entries) pairs for one seed shape."""
    identifier = shape["id"]
    out: list[tuple[str, list[dict]]] = []

    if identifier in {
        "casefold-expand",
        "casefold-shrink",
        "casefold-risk-scalars",
        "wide-and-ambiguous",
        "leading-whitespace-controls",
    }:
        for character_index, character in enumerate(shape["characters"]):
            for repeat in shape["repeats"]:
                for placement in shape["placement"]:
                    body = place(character * repeat, needle, placement)
                    name = f"{identifier}-c{character_index}-r{repeat}-{placement}"
                    out.append((
                        name,
                        [
                            claude_summary(f"{name} summary {needle}", f"leaf-{name}"),
                            claude_user(body, 1),
                            claude_assistant(f"reply {needle} {character * repeat}", 2),
                        ],
                    ))

    elif identifier == "empty-optionals":
        for field in shape["fields"]:
            for value_index, value in enumerate(shape["values"]):
                name = f"{identifier}-{field}-v{value_index}"
                out.append((
                    name,
                    [
                        claude_user(f"{name} {needle}", 1),
                        claude_assistant(f"reply {needle}", 2, **{field: value}),
                    ],
                ))

    elif identifier == "json-escape-forms":
        # The needle's own characters, re-spelled. A gate that only looks for
        # raw bytes must still treat every one of these as a possible match.
        spellings = {
            "raw": lambda text: text,
            "short-escape": lambda text: text.replace("/", "\\/"),
            "upper-hex": lambda text: "".join(f"\\u{ord(c):04X}" for c in text),
            "lower-hex": lambda text: "".join(f"\\u{ord(c):04x}" for c in text),
            "mixed-hex": lambda text: "".join(
                (f"\\u{ord(c):04X}" if i % 2 else f"\\u{ord(c):04x}")
                for i, c in enumerate(text)
            ),
        }
        for form in shape["forms"]:
            name = f"{identifier}-{form}"
            # Written as a raw JSON line so the escape survives to disk exactly.
            out.append((name, [{"__raw_user_text__": spellings[form](needle)}]))
        for pad in shape["pad_to_boundaries"]:
            name = f"{identifier}-boundary-{pad}"
            out.append((
                name,
                [claude_user("x" * pad + f" {needle} tail", 1)],
            ))

    elif identifier == "layout-edges":
        for offset in shape["offsets"]:
            name = f"{identifier}-offset{offset:+d}"
            out.append((
                name,
                [claude_user(f"{{WIDTH{offset:+d}}} {needle}", 1)],
            ))
        for multiple in shape["unbroken_token_multiples"]:
            name = f"{identifier}-unbroken-x{multiple}"
            out.append((
                name,
                [claude_user(f"{{UNBROKEN x{multiple}}} {needle}", 1)],
            ))

    elif identifier == "carriage-returns":
        for separator_index, separator in enumerate(shape["separators"]):
            for repeat in shape["repeats"]:
                name = f"{identifier}-s{separator_index}-r{repeat}"
                body = (separator * repeat).join(
                    [f"first {needle}", "second line", "third line"]
                )
                out.append((name, [claude_user(body, 1)]))

    return out


def write_session(home: Path, name: str, entries: list[dict], needle: str) -> str:
    """Write one Claude session; return its relative path."""
    directory = home / ".claude" / "projects" / "fuzz"
    directory.mkdir(parents=True, exist_ok=True)
    # Stable synthetic uuid derived from the name. `hash()` is randomized per
    # process for str, so it cannot be used here: the seed's whole purpose is
    # that the same input yields the same bytes on every machine and run.
    import hashlib

    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    session_id = (
        f"{digest[:8]}-{digest[8:12]}-4000-8000-{digest[12:24]}"
    )
    path = directory / f"{session_id}.jsonl"

    lines: list[str] = []
    for entry in entries:
        if "__raw_user_text__" in entry:
            # Emit the escape spelling verbatim rather than letting json.dumps
            # re-encode it: the point of these cases is the on-disk bytes.
            text = entry["__raw_user_text__"]
            lines.append(
                '{"type":"user","uuid":"u-0001","timestamp":"%s",'
                '"message":{"role":"user","content":"%s"},"cwd":"%s"}'
                % (BASE_TIMESTAMP, text, PROJECT_CWD)
            )
        else:
            lines.append(json.dumps(entry, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(home))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    destination = Path(sys.argv[1])
    home = destination / "home"
    if home.exists():
        import shutil

        shutil.rmtree(home)
    home.mkdir(parents=True)

    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    needle = seed["needle"]

    cases: list[dict] = []
    for shape in seed["shapes"]:
        for name, entries in sessions_for_shape(shape, needle):
            relative = write_session(home, name, entries, needle)
            cases.append({
                "id": name,
                "shape": shape["id"],
                "session": relative,
                "why": shape["why"],
            })

    manifest = {
        "seed_version": seed["version"],
        "widths": seed["widths"],
        "needle": needle,
        "cases": cases,
    }
    (destination / "CASES.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"sessions: {len(cases)}")
    print(f"widths:   {seed['widths']}")
    print(f"home:     {home}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
