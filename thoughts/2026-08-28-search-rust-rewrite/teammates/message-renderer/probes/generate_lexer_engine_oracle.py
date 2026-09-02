#!/usr/bin/env -S uv run
"""Gate the lexer driver against Pygments' own, mechanism by mechanism.

**One table, two consumers.** The table is defined here as data, used to build a
real `RegexLexer` **and** recorded for the Rust driver to rebuild. Neither side
holds a second copy, so the comparison is of the two drivers rather than of two
transcriptions.

Every mechanism the five promoted families use is exercised: a plain token,
`bygroups` over several groups including an empty one and a `None` slot,
`using(this)` with and without a starting stack, `default`, a push of one state, a
push of two, a tuple `#pop`, an integer `#pop:1`, `#push`, and both no-match
paths — **the newline that resets the stack to `root` and emits `Whitespace`, and
the character that emits `Error` and advances one.**
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pygments.lexer import RegexLexer, bygroups, default, using, this
from pygments.token import Token

# The table, as data. `action` is either {"token": path}, {"bygroups": [...]} or
# null (a `default`). A bygroups slot is null, {"token": path} or
# {"using_self": [stack…]}. `transition` is null, a list of state words, or an
# integer pop depth.
TABLE = {
    "root": [
        {"pattern": r"\s+", "action": {"token": "Token.Text.Whitespace"}, "transition": None},
        {"pattern": r"#.*?$", "action": {"token": "Token.Comment"}, "transition": None},
        # bygroups with three groups, the middle one able to match empty.
        {
            "pattern": r"(let)(\s*)(\w+)",
            "action": {"bygroups": [
                {"token": "Token.Keyword"},
                {"token": "Token.Text.Whitespace"},
                {"token": "Token.Name.Variable"},
            ]},
            "transition": None,
        },
        # A `None` slot: the group's text is dropped entirely.
        {
            "pattern": r"(drop)(\w+)",
            "action": {"bygroups": [{"token": "Token.Keyword"}, None]},
            "transition": None,
        },
        # `using(this)` over a group, with and without a starting stack.
        {
            "pattern": r"(re)\[(.*?)\]",
            "action": {"bygroups": [
                {"token": "Token.Keyword"},
                {"using_self": ["root"]},
            ]},
            "transition": None,
        },
        {
            "pattern": r"(st)\{(.*?)\}",
            "action": {"bygroups": [
                {"token": "Token.Keyword"},
                {"using_self": ["root", "instring"]},
            ]},
            "transition": None,
        },
        {"pattern": r'"', "action": {"token": "Token.Literal.String"}, "transition": ["instring"]},
        # A tuple push of two states at once.
        {"pattern": r"<<", "action": {"token": "Token.Operator"}, "transition": ["outer", "inner"]},
        # Pushes the state whose only rule is a `default`, which matches empty and
        # pops straight back out — the shape `default(...)` compiles to.
        {"pattern": r"@", "action": {"token": "Token.Punctuation"}, "transition": ["defaulted"]},
        {"pattern": r"\w+", "action": {"token": "Token.Name"}, "transition": None},
        {"pattern": r"[(),;]", "action": {"token": "Token.Punctuation"}, "transition": None},
    ],
    "instring": [
        # Excludes the newline on purpose: a string that cannot span lines is what
        # makes the newline **unmatched** inside this state, which is the only way to
        # reach the driver's reset-to-root fallback from a non-root state.
        {"pattern": r'[^"\\\n]+', "action": {"token": "Token.Literal.String"}, "transition": None},
        {"pattern": r'\\.', "action": {"token": "Token.Literal.String.Escape"}, "transition": None},
        # An integer pop.
        {"pattern": r'"', "action": {"token": "Token.Literal.String"}, "transition": 1},
    ],
    "outer": [
        {"pattern": r">>", "action": {"token": "Token.Operator"}, "transition": ["#pop"]},
        {"pattern": r"\w+", "action": {"token": "Token.Name.Class"}, "transition": None},
        {"pattern": r"\s+", "action": {"token": "Token.Text.Whitespace"}, "transition": None},
    ],
    "inner": [
        # `#push`, which duplicates the top of the stack.
        {"pattern": r"\+", "action": {"token": "Token.Operator"}, "transition": ["#push"]},
        {"pattern": r"-", "action": {"token": "Token.Operator"}, "transition": ["#pop"]},
        {"pattern": r"\w+", "action": {"token": "Token.Name.Function"}, "transition": None},
        {"pattern": r"\s+", "action": {"token": "Token.Text.Whitespace"}, "transition": None},
    ],
    "defaulted": [
        {"pattern": r"", "action": None, "transition": 1},
    ],
}

INPUTS = [
    "let x = 1",
    "let  y",
    # An **empty** token slot in `bygroups`: `\s*` matches nothing between `let` and
    # `x`. Python emits a token slot only `if data`, and nothing had reached that.
    "letx",
    "let z\n# a comment\nname",
    'a "string with \\" escape" b',
    # Reaches the DOTALL distinction: `.*?` inside `re[…]` must **not** cross the
    # newline, because `RegexLexer.flags` defaults to MULTILINE alone. Compiled with
    # search's flags this lexes as one group spanning both lines.
    're[a\nb] tail',
    '"open\nname',
    '"unterminated at end of input',
    "dropthis keep",
    "re[let q] tail",
    "st{inside a string} tail",
    "<< Klass fn + more - >> after",
    "@ afterdefault",
    "unmatched ~ character",
    "trailing ~\nnext line",
    "",
    "\n\n",
    "   ",
    "re[] empty group",
]


def token_of(path: str):
    node = Token
    for part in path.split(".")[1:]:
        node = getattr(node, part)
    return node


def build_lexer():
    tokens = {}
    for state, rules in TABLE.items():
        built = []
        for rule in rules:
            action = rule["action"]
            if action is None:
                resolved = None
            elif "token" in action:
                resolved = token_of(action["token"])
            else:
                slots = []
                for slot in action["bygroups"]:
                    if slot is None:
                        slots.append(None)
                    elif "token" in slot:
                        slots.append(token_of(slot["token"]))
                    else:
                        # **`state=`, not `stack=`.** `using` pops `state` and
                        # turns it into the starting stack; anything else in
                        # `kwargs` is forwarded to the lexer's constructor and the
                        # re-entry then starts from `root` regardless. Passing
                        # `stack=` here silently lexed from `root` and the gate
                        # caught it on its first run.
                        stack = tuple(slot["using_self"])
                        slots.append(using(this) if stack == ("root",) else using(this, state=stack))
                resolved = bygroups(*slots)
            target = rule["transition"]
            new_state = tuple(target) if isinstance(target, list) else target
            if isinstance(new_state, tuple) and len(new_state) == 1:
                new_state = new_state[0]
            if isinstance(target, int):
                new_state = f"#pop:{target}" if target != 1 else "#pop"
            if action is None and rule["pattern"] == "":
                built.append(default(new_state))
                continue
            # A rule that does not change state is a **two**-tuple. Pygments asserts
            # on a three-tuple whose third element is `None`.
            if new_state is None:
                built.append((rule["pattern"], resolved))
            else:
                built.append((rule["pattern"], resolved, new_state))
        tokens[state] = built

    return type("ProbeLexer", (RegexLexer,), {"name": "Probe", "tokens": tokens})()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    lexer = build_lexer()
    cases = []
    for text in INPUTS:
        stream = [
            [str(token), value]
            for _, token, value in lexer.get_tokens_unprocessed(text)
        ]
        cases.append({"text": text, "tokens": stream})

    import re as _re

    flags = type(lexer).flags
    Path(options.out).write_text(
        json.dumps(
            {
                "table": TABLE,
                # The lexer's own flags, recorded rather than assumed: a table
                # compiled under search's flags diverges only on multi-line input.
                "flags": {
                    "multiline": bool(flags & _re.MULTILINE),
                    "dotall": bool(flags & _re.DOTALL),
                    "ignorecase": bool(flags & _re.IGNORECASE),
                },
                "cases": cases,
            },
            ensure_ascii=False,
        )
    )
    print(f"{len(cases)} inputs, {sum(len(c['tokens']) for c in cases)} tokens -> {options.out}")


if __name__ == "__main__":
    main()
