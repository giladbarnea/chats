"""Compare the engine's `\\w` predicate and `tolower` against CPython, exhaustively.

The generated corpus cannot express these: `\\w` divergence needs the specific
codepoint, and the `tolower` truncation needs a multi-scalar lowering. Both sets
are finite, so enumerate instead of sampling.
"""

import json
import pathlib
import re
import sys

WORD = re.compile(r"\w")
FOLD = re.MULTILINE | re.DOTALL | re.IGNORECASE


def main() -> None:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text())

    engine_word = set()
    for low, high in data["word_ranges"]:
        engine_word.update(range(low, high + 1))

    # CPython's `\w` for str patterns is its own alphanumeric predicate plus "_".
    # Verified against re itself on a sample before trusting it for the sweep.
    for probe in (0x41, 0x5F, 0x660, 0x4E2D, 0x2D, 0x0BE6, 0x2160):
        character = chr(probe)
        assert bool(WORD.match(character)) == (character.isalnum() or character == "_"), (
            f"fast predicate disagrees with re at U+{probe:04X}"
        )

    only_engine, only_python = [], []
    for code in range(0x110000):
        character = chr(code)
        python_says = character.isalnum() or character == "_"
        engine_says = code in engine_word
        if python_says == engine_says:
            continue
        (only_engine if engine_says else only_python).append(code)

    print("== \\w predicate, all 1,114,112 codepoints ==")
    print(f"   engine matches, CPython does not: {len(only_engine)}")
    print(f"   CPython matches, engine does not: {len(only_python)}")
    for label, codes in (("engine-only", only_engine), ("python-only", only_python)):
        for code in codes[:12]:
            print(f"      {label}: U+{code:04X} {chr(code)!r}")
        if len(codes) > 12:
            print(f"      … and {len(codes) - 12} more")

    print("\n== multi-scalar lowerings the engine truncates ==")
    divergent = 0
    for entry in data["multi_scalar_lowerings"]:
        character = chr(entry["code"])
        kept = entry["engine_keeps"]
        # Does CPython's IGNORECASE treat the character and the kept scalar as
        # equal? If yes, truncation is harmless for this scalar.
        python_equal = bool(re.compile(re.escape(kept), FOLD).search(character)) and bool(
            re.compile(re.escape(character), FOLD).search(kept)
        )
        if not python_equal:
            divergent += 1
            print(
                f"   U+{entry['code']:04X} {character!r} lowers to {entry['full']!r}, "
                f"engine keeps {kept!r} — CPython does NOT equate them"
            )
    total = len(data["multi_scalar_lowerings"])
    print(f"   {total} scalars have multi-scalar lowerings; {divergent} diverge under IGNORECASE")


if __name__ == "__main__":
    main()
