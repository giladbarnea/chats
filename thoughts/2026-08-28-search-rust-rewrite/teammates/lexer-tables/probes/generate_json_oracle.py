#!/usr/bin/env -S uv run
"""Record Pygments' JSON scanner over real fenced blocks — and which of its lines ran.

**JSON is the one family with no table.** `JsonLexer` is a hand-written character
scanner, so there is no `_tokens` to project into Rust and no rule set to demand the
corpus reaches. The port is of behaviour rather than of data, which is a weaker
starting position, so the gate compensates in the one way available:

**the reference's own executable lines stand in for a table's rules.** Every line of
`JsonLexer.get_tokens_unprocessed` that the corpus causes Pygments to execute is
recorded, and the Rust gate asserts the set is complete. A branch the corpus never
takes is exactly the ungated rule a table's adequacy test refuses to allow, one level
down.

Line numbers are recorded **relative to the function**, so a Pygments release that
moves the function in its file does not invalidate the fixture.
"""

from __future__ import annotations

import argparse
import dis
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harvest_family_corpus import fences, preprocess
from pygments.lexers import get_lexer_by_name
from pygments.lexers.data import JsonLexer

# Real JSON blocks are plentiful but tame: they carry keys, strings, numbers and
# punctuation, and nothing else. Every branch below the first three is authored.
SUPPLEMENTS: list[tuple[str, str]] = [
    ("object", '{"key": "value", "n": 1, "f": 1.5e-3, "t": true, "z": null}\n'),
    ("array", '[1, 2.0, "three", false, null]\n'),
    ("nested", '{"outer": {"inner": [{"deep": 1}]}}\n'),
    ("escapes", '{"a": "a \\" b \\\\ c \\/ d \\n e \\u00e9 f"}\n'),
    ("bad-unicode-escape", '{"a": "\\uZZZZ and \\u12 and \\q"}\n'),
    ("comment-single", '{\n  // a line comment\n  "a": 1\n}\n'),
    ("comment-multiline", '{\n  /* a block\n     comment */\n  "a": 1\n}\n'),
    ("comment-before-key", '{ /* c */ "a": 1, // c\n "b": 2 }\n'),
    ("comment-star-run", '{"a": 1} /** stars ** here **/\n'),
    ("comment-unterminated-single", '{"a": 1} // trailing with no newline'),
    ("comment-unterminated-multiline", '{"a": 1} /* never closed'),
    ("comment-opener-alone", '{"a": 1} / not a comment\n'),
    ("comment-opener-at-end", '{"a": 1} /'),
    ("unterminated-string", '{"a": "never closed\n'),
    ("trailing-number", '{"a": 1'),
    ("trailing-float", '{"a": 1.5'),
    ("trailing-constant", '{"a": tru'),
    ("trailing-whitespace", '{"a": 1} '),
    ("trailing-punctuation", '{"a": 1}'),
    ("no-validation", "--1-- and trustful and 1...eee\n"),
    ("errors", "{'single': `backtick` @ #}\n"),
    ("key-after-comment", '{ // c\n "a": 1 }\n'),
    # A comment or a space **between a string and its colon** is the only way the
    # queue holds anything but the string itself when the colon rewrites it.
    ("comment-between-key-and-colon", '{"a" /* c */ : 1, "b" // c\n : 2}\n'),
    ("space-between-key-and-colon", '{"a" : 1}\n'),
    ("bare-values", "true false null 1 2.5 \"s\"\n"),
    ("empty", ""),
    ("whitespace-only", " \t\r\n"),
]


def executable_lines(function) -> set[int]:
    """Every line of `function` that carries bytecode, relative to its first line."""
    code = function.__code__
    first = code.co_firstlineno
    return {
        line - first
        for _offset, line in dis.findlinestarts(code)
        # Offset 0 is the `def` itself, which a call event reports rather than a
        # line event, so it is never in the traced set.
        if line is not None and line != first
    }


def traced(lexer, text: str) -> tuple[list[list[str]], set[int]]:
    """The token stream, and the scanner's lines that ran while producing it."""
    code = JsonLexer.get_tokens_unprocessed.__code__
    first = code.co_firstlineno
    reached: set[int] = set()

    def local(frame, event, argument):
        if event == "line":
            reached.add(frame.f_lineno - first)
        return local

    def outer(frame, event, argument):
        if event == "call" and frame.f_code is code:
            return local
        return None

    previous = sys.gettrace()
    sys.settrace(outer)
    try:
        stream = [[str(token), value] for token, value in lexer.get_tokens(text)]
    finally:
        sys.settrace(previous)
    return stream, reached


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", default="json,json-object,jsonl,ndjson")
    parser.add_argument("--files", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--cap", type=int, default=4000)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--held-out",
        action="store_true",
        help=(
            "Real content only, from a different seed, with no authored cases and no "
            "line-coverage requirement. **Nothing is ever repaired against this "
            "corpus** — a failure here is a defect in the port."
        ),
    )
    options = parser.parse_args()

    lexer = get_lexer_by_name("json", stripnl=False, ensurenl=True, tabsize=4)
    declared = sorted(executable_lines(JsonLexer.get_tokens_unprocessed))

    tags = {tag.strip() for tag in options.tags.split(",")}
    seen: set[str] = set()
    cases = []
    reached: set[int] = set()
    for _, body in fences(options.files, options.seed, tags):
        text = preprocess(lexer, body.rstrip())
        if text in seen or len(text) > options.cap:
            continue
        seen.add(text)
        stream, lines = traced(lexer, text)
        reached |= lines
        cases.append({"text": text, "tokens": stream, "source": "harvested"})

    for name, snippet in [] if options.held_out else SUPPLEMENTS:
        # Preprocessed exactly like a harvested block, including the empty one:
        # `_process_code` turns an empty fence into a single newline.
        text = preprocess(lexer, snippet.rstrip())
        stream, lines = traced(lexer, text)
        reached |= lines
        cases.append({"text": text, "tokens": stream, "source": f"authored:{name}"})

    # **The final-flush branches for a number, a constant, punctuation, a `//`
    # comment and a lone `/` cannot run in this product**, and the reason is one line
    # of `Syntax`: the lexer is built with `ensurenl=True` and `_process_code`
    # appends a newline, so **the text always ends in one** — which closes every one
    # of those states before the loop ends. Only an unterminated string, an
    # unterminated `/* */` and trailing whitespace survive a newline.
    for case in cases if not options.held_out else []:
        if not case["text"].endswith("\n"):
            raise SystemExit(
                f"case {case['source']} does not end in a newline, so the reason the "
                f"unreachable final-flush branches are unreachable does not hold"
            )
    unreachable = {} if options.held_out else {
        str(line): (
            "a final-flush branch for a state a newline closes; `Syntax` builds the "
            "lexer with `ensurenl=True` and `_process_code` appends a newline, so the "
            "text always ends in one"
        )
        for line in declared
        if line not in reached
    }
    missing = sorted(int(line) for line in unreachable)
    if not options.held_out and missing != [215, 217, 219, 223, 225, 228, 229]:
        raise SystemExit(
            f"unreached scanner lines are offsets {missing}, not the seven "
            f"final-flush branches the newline explains. Add cases that reach the "
            f"new ones — an unexercised branch is this family's version of an "
            f"ungated rule."
        )

    Path(options.out).write_text(
        json.dumps(
            {
                "lexer": lexer.name,
                "scanner_lines": declared,
                "unreachable_lines": unreachable,
                "cases": cases,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    characters = sum(len(case["text"]) for case in cases)
    tokens = sum(len(case["tokens"]) for case in cases)
    print(
        f"{len(cases)} cases, {characters} characters, {tokens} tokens, "
        f"{len(reached)} of {len(declared)} scanner lines reached -> {options.out}"
    )


if __name__ == "__main__":
    main()
