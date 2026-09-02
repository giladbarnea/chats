#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = []
# ///
"""Does the product diverge on Unicode normalization form?

`session-core` raised NFC versus NFD as their top candidate: elision slices code
points, so the same *visible* string has a different code-point count depending
on normalization form, and a truncating renderer can cut it in a different place.

A probe in a calibration suite proves a harness can *see* that difference. It
cannot say whether the product actually diverges. That needs a corpus.

Method: build the same visible content twice, once NFC and once NFD, render both
through the oracle at narrow widths where elision bites, then normalize both
*outputs* to NFC before comparing. Normalizing the output is what makes this a
test of behaviour rather than a test of input encoding — if the renders still
differ after that, the product treated the two forms differently.

Usage:
    uv run nfc_nfd_probe.py
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unicodedata
from pathlib import Path

HARNESS = Path(__file__).parent / "fuzz_harness.py"
SCRATCH = Path(
    "/private/tmp/claude-501/-Users-giladbarnea-dev-chats"
    "/34993643-8a40-408e-be63-a5ecaf66fe03/scratchpad/nfcnfd"
)

# Strings whose NFC and NFD forms differ in code-point count but not in visible
# width. Long enough that a narrow terminal must elide them.
SUBJECTS = [
    "café résumé naïve" * 4,
    "ÀÉÎÕÜ àéîõü" * 6,
    "Ǎǎ Ǒǒ Ǔǔ ǗǙǛ" * 5,
    "מִבְחָן עִבְרִי" * 5,
]


def load_harness():
    spec = importlib.util.spec_from_file_location("fuzz_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fuzz_harness"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_session(home: Path, name: str, title: str, needle: str) -> None:
    directory = home / ".claude" / "projects" / "nfcnfd"
    directory.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha256(name.encode()).hexdigest()
    session = f"{digest[:8]}-{digest[8:12]}-4000-8000-{digest[12:24]}"
    entries = [
        {"type": "summary", "summary": title, "leafUuid": f"leaf-{name}"},
        {
            "type": "user",
            "uuid": "u-0001",
            "timestamp": "2026-08-20T10:00:00Z",
            "message": {"role": "user", "content": f"{title} {needle}"},
            "cwd": "/tmp/search-content-fuzz",
        },
    ]
    (directory / f"{session}.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    harness = load_harness()
    needle = "needle"
    findings: list[str] = []

    print(f"{'subject':>7}  {'form':>4}  {'code points':>11}  {'width':>5}  result")
    for index, subject in enumerate(SUBJECTS):
        nfc = unicodedata.normalize("NFC", subject)
        nfd = unicodedata.normalize("NFD", subject)
        if nfc == nfd:
            print(f"{index:>7}  skip  (forms identical for this subject)")
            continue

        for width in (52, 72):
            renders: dict[str, bytes] = {}
            for form, text in (("NFC", nfc), ("NFD", nfd)):
                home = SCRATCH / f"{index}-{form}-{width}" / "home"
                if home.exists():
                    shutil.rmtree(home)
                home.mkdir(parents=True)
                write_session(home, f"s{index}{form}", text, needle)
                output, status = harness.run_under_pty(
                    [
                        str(harness.LEGACY), "search", needle,
                        "-l", "--color", "always", "--no-paging",
                    ],
                    columns=width,
                    home=home,
                )
                if status != 0:
                    findings.append(f"subject {index} {form} w{width}: exit {status}")
                # Normalize the OUTPUT, so only behavioural differences survive.
                renders[form] = unicodedata.normalize(
                    "NFC", output.decode("utf-8", "replace")
                ).encode("utf-8")

            same = renders["NFC"] == renders["NFD"]
            print(
                f"{index:>7}  both  {len(nfc):>5}/{len(nfd):<5}  {width:>5}  "
                f"{'identical' if same else 'DIVERGES'}"
            )
            if not same:
                findings.append(
                    f"subject {index} at width {width}: renders differ after "
                    f"output normalization"
                )

    print()
    if not findings:
        print("no divergence: the oracle renders both normalization forms alike")
        return 0
    print(f"findings: {len(findings)}")
    for finding in findings:
        print(f"  - {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
