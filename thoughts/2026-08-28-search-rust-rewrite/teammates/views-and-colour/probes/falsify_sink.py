#!/usr/bin/env -S uv run
"""Falsify the coloured list sink's gate: mutate the projection, require a catch.

The row rendering is gated separately over 43,680 lines. What the sink adds is the
projection from a `SearchHit` onto the row, and these are the ways it can be wrong
while every earlier gate stays green.

Usage: falsify_sink.py   (run from the repository root)
"""

import subprocess
import sys
from pathlib import Path

SRC = Path("rust/search_views.rs")
FILTER = "search_views::sink_tests"

MUTATIONS = [
    ("S1 headline read directly, losing the falsy fallback",
     "        let (headline, headline_is_fallback) = hit.headline();",
     '        let (headline, headline_is_fallback) = match hit.last_custom_title.as_deref() {\n'
     '            Some(title) => (title, false),\n'
     '            None => ("(untitled session)", true),\n'
     '        };'),
    ("S2 match count drops summaries and custom titles",
     "            match_count: hit.match_count(),",
     "            match_count: hit.match_indices.len(),"),
    ("S3 provider column always shown",
     "            show_provider: self.output.show_provider,",
     "            show_provider: true,"),
    ("S4 provider column never shown",
     "            show_provider: self.output.show_provider,",
     "            show_provider: false,"),
    ("S5 absent age painted as zero rather than unknown",
     "            age_seconds: hit.age_seconds(self.output.now),",
     "            age_seconds: Some(hit.age_seconds(self.output.now).unwrap_or(0.0)),"),
    ("S6 summary emitted even when nothing was found",
     "        (self.found > 0).then(|| {",
     "        (true).then(|| {"),
]


def main() -> None:
    blind = []
    original = SRC.read_text()
    for label, old, new in MUTATIONS:
        if old not in original:
            print(f"  {label:<52} ANCHOR MISSING - result meaningless")
            blind.append(label)
            continue
        try:
            SRC.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                ["cargo", "test", "--no-default-features", "--lib", FILTER],
                capture_output=True, text=True)
        finally:
            SRC.write_text(original)
        blob = result.stdout + result.stderr
        if "error[" in blob:
            print(f"  {label:<52} DID NOT COMPILE - result meaningless")
            blind.append(label)
        elif result.returncode != 0:
            detail = [l.strip() for l in blob.splitlines() if "differ from Python" in l]
            print(f"  {label:<52} caught  {detail[0] if detail else '(assertion)'}")
        else:
            print(f"  {label:<52} NOT CAUGHT")
            blind.append(label)
    if blind:
        print(f"\nFAILED  {len(blind)} mutation(s) not caught or not applied")
        raise SystemExit(1)
    print(f"\nPASS    all {len(MUTATIONS)} mutations caught")


if __name__ == "__main__":
    main()
