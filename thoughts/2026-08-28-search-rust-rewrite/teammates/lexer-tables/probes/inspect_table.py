#!/usr/bin/env -S uv run
"""What one Pygments RegexLexer's flat table actually contains.

Classifies every rule of `_tokens` so the generator is written against measured
shapes rather than assumed ones. **`_tokens` stores the compiled pattern's bound
`match` method**, so the pattern comes from `rule[0].__self__.pattern`.
"""
from __future__ import annotations

import argparse
import collections
import inspect
import re

from pygments.lexer import this
from pygments.lexers import get_lexer_by_name
from pygments.token import _TokenType


def closure(callback):
    return inspect.getclosurevars(callback).nonlocals


def classify(action):
    if action is None:
        return "default", None
    if isinstance(action, _TokenType):
        return "token", str(action)
    variables = closure(action)
    if "args" in variables:
        return "bygroups", variables["args"]
    return "other-callback", (action, variables)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("alias")
    options = parser.parse_args()

    lexer = get_lexer_by_name(options.alias, stripnl=False, ensurenl=True, tabsize=4)
    tokens = lexer._tokens
    print(f"lexer {lexer.name!r} class {type(lexer).__name__} states {len(tokens)}")
    print(f"flags {lexer.flags} = {re.RegexFlag(lexer.flags)!r}")

    kinds = collections.Counter()
    transitions = collections.Counter()
    slot_kinds = collections.Counter()
    features = collections.Counter()
    total = 0
    for state, rules in tokens.items():
        for rule in rules:
            total += 1
            pattern = rule[0].__self__.pattern
            # The pattern text plus the lexer's flags must reproduce the compiled
            # object, which is what catches reading the wrong source string. A
            # leading `(?i)` shows up in the compiled flags and nowhere else, and
            # `default(...)` compiles `re.compile('')` with no flags of its own.
            if pattern:
                assert re.compile(pattern, lexer.flags).flags == rule[0].__self__.flags, (
                    state, pattern, rule[0].__self__.flags)
            kind, payload = classify(rule[1])
            kinds[kind] += 1
            if kind == "bygroups":
                for slot in payload:
                    if slot is None:
                        slot_kinds["none"] += 1
                    elif isinstance(slot, _TokenType):
                        slot_kinds["token"] += 1
                    else:
                        variables = closure(slot)
                        other = variables.get("_other")
                        left = {k: v for k, v in variables.get("kwargs", {}).items()}
                        slot_kinds[
                            f"using(this={other is this}) gt={variables.get('gt_kwargs')} leftover={left}"
                        ] += 1
                slot_kinds[f"arity-{len(payload)}"] += 1
            if kind == "other-callback":
                print(f"  ⚠ callback in {state}: {payload[0]} vars={list(payload[1])}")
            target = rule[2]
            if target is None:
                transitions["stay"] += 1
            elif isinstance(target, int):
                transitions[f"pop:{-target}"] += 1
            elif isinstance(target, str):
                transitions[f"bare-str:{target}"] += 1
            else:
                transitions[f"push-{len(target)}"] += 1
                for entry in target:
                    if entry in ("#pop", "#push"):
                        transitions[f"tuple-{entry}"] += 1
            for name, probe in [
                ("lookahead", r"\(\?="), ("neg-lookahead", r"\(\?!"),
                ("lookbehind", r"\(\?<"), ("inline-flags", r"\(\?[aiLmsux]+\)"),
                ("scoped-flags", r"\(\?[aiLmsux]+:"), ("backref", r"\\[1-9]"),
                ("named-group", r"\(\?P<"), ("named-ref", r"\(\?P="),
                ("conditional", r"\(\?\("), ("atomic", r"\(\?>"),
                ("possessive", r"[*+?}]\+"), ("non-bmp", r"[\U00010000-\U0010FFFF]"),
            ]:
                if re.search(probe, pattern):
                    features[name] += 1
    print(f"\nrules {total}")
    print("actions      ", dict(kinds))
    print("transitions  ", dict(transitions))
    print("bygroup slots", dict(slot_kinds))
    print("features     ", dict(features))
    for state, rules in tokens.items():
        print(f"  state {state!r}: {len(rules)} rules")


if __name__ == "__main__":
    main()
