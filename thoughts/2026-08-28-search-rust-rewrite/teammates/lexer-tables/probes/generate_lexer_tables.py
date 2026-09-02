#!/usr/bin/env -S uv run
"""Emit Pygments' own lexer tables as Rust, for the promoted families.

`RegexLexer._tokens` is the flat, already-expanded rule table: `include` and
`inherit` are resolved when the class is built, so a port copies the flat table and
the driver never sees either. This walks that table and writes it out as data for
`syntax_lexer`'s driver.

**The point of generating rather than transcribing** is that the Rust table is a
mechanical projection of the reference's own definition. The gate then compares two
*drivers* over one table rather than two readings of it, which is the same shape as
the engine's own gate.

Five traps, each of which has already produced a wrong answer on this desk:

1. **`_tokens` stores the compiled pattern's bound `match` method, not the
   pattern.** `getattr(rule[0], "pattern", ...)` returns
   `"<built-in method match ...>"`. The source is `rule[0].__self__.pattern`.
2. **`using()` honours only `state=`.** Anything else in `kwargs` goes to the
   lexer's *constructor* and the re-entry silently restarts from `root`, so a
   leftover `kwargs` is refused here rather than modelled.
3. **`using()` is never a rule's direct action** in these families, only a
   `bygroups` argument. A scan over rule actions finds none.
4. **A rule that does not change state is a two-tuple**, and an action is never
   `None` except through `default(...)`, which compiles to an **empty pattern**.
5. **Escaping.** `repr` plus a quote swap breaks on an apostrophe; JSON escaping
   breaks on a non-BMP character, which it writes as a surrogate pair Rust rejects.
   Only `\\` and `"` are escaped and everything else is written literally in UTF-8.
"""

from __future__ import annotations

import argparse
import inspect
import re
from pathlib import Path

from pygments.lexers import get_lexer_by_name
from pygments.token import _TokenType

# The promoted families, in the order painted characters put them. A family is
# either here with its gate or absent; there is no partly-promoted state.
FAMILIES = [
    # **`tsx` is a different lexer, not an alias.** `TsxLexer` adds the element,
    # attribute and fragment states — 161 rules against TypeScript's 94 — so it is
    # its own family with its own corpus and gate.
    ("typescript", "TypeScript"),
    ("tsx", "TSX"),
    ("python", "Python"),
    # `js`, `javascript` and `node`. `TypeScriptLexer` inherits this one.
    ("javascript", "JavaScript"),
    # The coverage set, in block order. `SqlLexer` declares IGNORECASE and nothing
    # else, which is the third `LexerFlags` field reaching a family for the first time.
    ("sql", "SQL"),
    # HELD: ("markdown", "Markdown") — its table, corpus and gate are written, but
    # they were built against `handlecodeblocks=False`, which was the *first* tail
    # ruling. **That ruling was retracted**: a nested fence in a language legacy
    # recognises must still be coloured, so the configuration is wrong and the work
    # waits for the replacement rule. The gate is
    # `teammates/lexer-tables/markdown-gate.rs.pending`.
    # `bash`, `sh`, `zsh`, `ksh` and `shell` are all this one lexer.
    ("bash", "Bash"),
]


# Options a family needs beyond the four every lexer gets.
#
# **`handlecodeblocks=False` is the captain's ruling expressed as a Pygments
# option.** With it on, markdown's fenced-code callback dispatches to *any* lexer by
# the fence's info string; with it off, the nested code is emitted as one `String`.
# The ruling is that a known-but-unported language renders plain, so the nested code
# renders plain — which is exactly this configuration, not an approximation of it.
LEXER_OPTIONS = {"markdown": {"handlecodeblocks": False}}

# The one action in 957 rules that is **not** projected from `_tokens`.
#
# Markdown's fenced-code rule is a hand-written callback, so there is nothing to
# read. Under `handlecodeblocks=False` it emits its nine groups as fixed tokens, and
# that is transcribed here as an ordinary `bygroups`. **The entry carries its own
# premise** — the callback's name, the group count and every group name — and the
# generator refuses if any of them moved.
HAND_WRITTEN_ACTIONS = {
    ("markdown", "root", 9): {
        "callback": "_handle_codeblock",
        "groups": {
            "initial": 1, "lang": 2, "afterlang": 3, "whitespace": 4,
            "extra": 5, "newline": 6, "code": 7, "terminator": 9,
        },
        "group_count": 9,
        # By group number. `None` is a group the callback does not emit: `afterlang`
        # is a container for the two inside it, and 8 is the anonymous repeat inside
        # `code`.
        "slots": [
            "Token.Literal.String.Backtick",
            "Token.Literal.String.Backtick",
            None,
            "Token.Text.Whitespace",
            "Token.Text",
            "Token.Text.Whitespace",
            "Token.Literal.String",
            None,
            "Token.Literal.String.Backtick",
        ],
    },
}


def rust_string(value: str) -> str:
    """A Rust string literal for `value`, escaping only what Rust's syntax needs."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + "".join(
        character if character >= " " else f"\\u{{{ord(character):x}}}"
        for character in escaped
    ) + '"'


def pattern_of(rule) -> str:
    """The rule's regex source. **Not `rule[0].pattern`** — see trap 1."""
    return rule[0].__self__.pattern


def closure_variables(callback) -> dict:
    return inspect.getclosurevars(callback).nonlocals


def group_action(slot, where: str) -> str:
    """One `bygroups` slot, as Rust."""
    if slot is None:
        return "None"
    if isinstance(slot, _TokenType):
        return f"group_token({rust_string(str(slot))})"
    variables = closure_variables(slot)
    if "args" in variables:
        raise SystemExit(f"{where}: a nested bygroups is not modelled")
    # **`using(this)` leaves no `_other` in the closure.** Pygments branches on
    # `_other is this` when it builds the callback, and the `this` branch's body
    # never mentions `_other`, so it is not a free variable at all. **Presence means
    # a second lexer**, which the engine does not model; absence means `this`.
    if "_other" in variables:
        raise SystemExit(
            f"{where}: using() names {variables['_other']}, a second lexer, which the "
            f"driver does not model — it re-enters the same table only"
        )
    leftover = variables.get("kwargs") or {}
    if leftover:
        # Trap 2: these reach the lexer's constructor, and the re-entry then starts
        # from `root` whatever the author meant. Refusing beats reproducing a shape
        # nobody checked.
        raise SystemExit(f"{where}: using() carries {sorted(leftover)}, which is not `state=`")
    stack = variables.get("gt_kwargs", {}).get("stack", ("root",))
    states = ", ".join(rust_string(state) for state in stack)
    return f"group_using(&[{states}])"


def hand_written_action(alias: str, state: str, index: int, rule, where: str) -> str | None:
    """A transcribed action for a rule there is nothing to project, or `None`.

    Refuses rather than applies if the callback, the group count or any group name
    has moved, because the slot map is written against exactly those.
    """
    entry = HAND_WRITTEN_ACTIONS.get((alias, state, index))
    if entry is None:
        return None
    name = getattr(rule[1], "__name__", None)
    if name != entry["callback"]:
        raise SystemExit(f"{where}: expected the callback {entry['callback']}, found {name}")
    compiled = re.compile(pattern_of(rule), re.MULTILINE)
    if compiled.groups != entry["group_count"] or compiled.groupindex != entry["groups"]:
        raise SystemExit(
            f"{where}: the pattern's groups moved — {compiled.groups} groups, "
            f"{dict(compiled.groupindex)} — so the transcribed slot map does not apply"
        )
    slots = ", ".join(
        "None" if slot is None else f"group_token({rust_string(slot)})"
        for slot in entry["slots"]
    )
    return f"by_groups(vec![{slots}])"


def action_of(rule, where: str) -> str:
    action = rule[1]
    if action is None:
        # Trap 4: only `default(...)` produces this, and it compiles to an empty
        # pattern, so the two travel together.
        if pattern_of(rule) != "":
            raise SystemExit(f"{where}: a None action on a non-empty pattern")
        return "Action::Nothing"
    if isinstance(action, _TokenType):
        return f"token({rust_string(str(action))})"
    variables = closure_variables(action)
    if "args" not in variables:
        # Trap 3 in reverse: a `using()` used directly, or markdown's hand-written
        # `_handle_codeblock`. Neither is a table, so neither is silently dropped.
        raise SystemExit(f"{where}: a hand-written callback, which is not a table")
    slots = ", ".join(group_action(slot, where) for slot in variables["args"])
    return f"by_groups(vec![{slots}])"


def transition_of(rule, where: str) -> str:
    """`RegexLexerMeta` has already resolved `#pop:n` to a negative integer and a
    bare state name to a one-tuple, so only three shapes reach here."""
    target = rule[2]
    if target is None:
        return "Transition::Stay"
    if isinstance(target, int):
        if target >= 0:
            raise SystemExit(f"{where}: an integer transition {target} that is not a pop")
        return f"Transition::Pop({-target})"
    if isinstance(target, str):
        if target != "#push":
            raise SystemExit(f"{where}: a bare string transition {target!r}")
        return 'push(&["#push"])'
    states = ", ".join(rust_string(state) for state in target)
    return f"push(&[{states}])"


def emit_table(alias: str, display_name: str) -> tuple[str, str]:
    """One family's `LexerTable` builder, and how many rules it carries."""
    lexer = get_lexer_by_name(
        alias, stripnl=False, ensurenl=True, tabsize=4, **LEXER_OPTIONS.get(alias, {})
    )
    if lexer.name != display_name:
        raise SystemExit(f"{alias!r} resolves to {lexer.name!r}, not {display_name!r}")
    # `LexerFlags` carries exactly these three. VERBOSE would change what every
    # pattern means and the engine has no channel for it, so a family declaring one
    # refuses rather than being lexed under flags it does not have.
    carried = re.MULTILINE | re.DOTALL | re.IGNORECASE
    if lexer.flags & ~carried:
        raise SystemExit(
            f"{display_name} sets flags {re.RegexFlag(lexer.flags)!r}; `LexerFlags` "
            f"carries only MULTILINE, DOTALL and IGNORECASE"
        )

    states = []
    rule_count = 0
    for state, rules in lexer._tokens.items():
        emitted = []
        for index, rule in enumerate(rules):
            where = f"{display_name}/{state}[{index}]"
            pattern = pattern_of(rule)
            # The pattern text plus the lexer's flags must reproduce the compiled
            # object the table holds — a leading `(?s)` shows up in the compiled
            # flags and nowhere else, so this is what catches reading the wrong
            # source string.
            if pattern and re.compile(pattern, lexer.flags).flags != rule[0].__self__.flags:
                raise SystemExit(
                    f"{where}: {pattern[:60]!r} under {re.RegexFlag(lexer.flags)!r} does "
                    f"not reproduce the compiled flags {rule[0].__self__.flags}"
                )
            transcribed = hand_written_action(alias, state, index, rule, where)
            emitted.append(
                f"        rule({rust_string(pattern)},\n"
                f"             {transcribed or action_of(rule, where)},\n"
                f"             {transition_of(rule, where)}),"
            )
            rule_count += 1
        joined = "\n".join(emitted)
        states.append(
            f"    ({rust_string(state)}.to_string(), vec![\n{joined}\n    ]),"
        )
    body = "\n".join(states)
    identifier = display_name.lower().replace(" ", "_")
    flags = (
        f"LexerFlags {{ multiline: {str(bool(lexer.flags & re.MULTILINE)).lower()}, "
        f"dotall: {str(bool(lexer.flags & re.DOTALL)).lower()}, "
        f"ignorecase: {str(bool(lexer.flags & re.IGNORECASE)).lower()} }}"
    )
    builder = f'''
/// {display_name}'s table, exactly as `{type(lexer).__name__}._tokens` holds it:
/// {rule_count} rules over {len(lexer._tokens)} states, under
/// `{re.RegexFlag(lexer.flags)!r}`.
pub fn {identifier}_table() -> LexerTable {{
    LexerTable {{ name: {rust_string(display_name)}.to_string(), flags: {flags}, states: vec![
{body}
    ] }}
}}

/// Compiled once per process, on first use.
pub static {identifier.upper()}: LazyLexer = LazyLexer::new({identifier}_table);
'''
    return builder, identifier


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    from importlib.metadata import version

    builders = []
    identifiers = []
    for alias, display_name in FAMILIES:
        builder, identifier = emit_table(alias, display_name)
        builders.append(builder)
        identifiers.append((display_name, identifier))

    helpers = {
        "rule": """fn rule(pattern: &str, action: Action, transition: Transition) -> Rule {
    Rule { pattern: pattern.to_string(), action, transition }
}""",
        "token": """fn token(path: &str) -> Action {
    Action::Token(path.to_string())
}""",
        "by_groups": """fn by_groups(slots: Vec<Option<GroupAction>>) -> Action {
    Action::ByGroups(slots)
}""",
        "group_token": """fn group_token(path: &str) -> Option<GroupAction> {
    Some(GroupAction::Token(path.to_string()))
}""",
        "group_using": """fn group_using(stack: &[&str]) -> Option<GroupAction> {
    Some(GroupAction::UsingSelf(stack.iter().map(|state| state.to_string()).collect()))
}""",
        "push": """fn push(states: &[&str]) -> Transition {
    Transition::States(states.iter().map(|state| state.to_string()).collect())
}""",
    }
    body = "".join(builders)
    used = "\n\n".join(
        source for name, source in helpers.items() if f"{name}(" in body
    )
    # `CompiledLexer` and `LazyLexer` are the footer's, so they are always used;
    # the rest depend on which shapes the promoted families happen to carry, and an
    # unused import is a warning in a tree that builds at zero.
    imports = ", ".join(
        name
        for name in [
            "Action", "CompiledLexer", "GroupAction", "LazyLexer", "LexerFlags",
            "LexerTable", "Rule", "Transition",
        ]
        if name in ("CompiledLexer", "LazyLexer", "LexerFlags")
        or re.search(rf"\b{name}\b", body + used)
    )

    arms = "\n".join(
        f"        {rust_string(display_name)} => Some({identifier.upper()}.get()),"
        for display_name, identifier in identifiers
    )
    names = ", ".join(rust_string(display_name) for display_name, _ in identifiers)

    Path(options.out).write_text(
        f'''//! Pygments' own lexer tables for the promoted families, as data.
//!
//! Generated from Pygments {version("pygments")} by
//! `teammates/lexer-tables/probes/generate_lexer_tables.py`. Do not edit.
//!
//! `RegexLexer._tokens` is the flat table: `include` and `inherit` are expanded
//! when the class is built, so this is the reference's own rule list rather than a
//! reading of its source. [`crate::syntax_lexer`] is the driver that runs it.
//!
//! **A family appears here only with its gate.** `promoted_lexer` is the whole
//! interface: a display name that answers `None` renders with no lexer at all,
//! which is what a fence tag Pygments does not know already does.

use crate::syntax_lexer::{{{imports}}};

{used}
{body}
/// Every promoted family, by the display name [`crate::syntax_lexers::lexer_for_tag`]
/// returns for a fence tag.
pub const PROMOTED_LEXERS: &[&str] = &[{names}];

/// The compiled lexer for a display name, or `None` when the family is not promoted.
///
/// **A `None` here means the fence renders plain.** Ruled 2026-08-30: a language
/// Pygments knows and no table covers renders with complete fence geometry and plain
/// unstyled code, the same treatment as a tag Pygments does not know. `session_render`'s
/// fence arm maps such a language to `None` **before** `render_code_block` is called,
/// which is why that function's unpromoted branch is `unreachable!()` — the plain
/// render happens once, in one place.
///
/// The language named here must be one that is **not a promotion candidate**, or the
/// assertion turns into a failing test the moment the work succeeds.
///
/// ```
/// use _native::syntax_tables::promoted_lexer;
/// assert!(promoted_lexer("TypeScript").is_some());
/// assert!(promoted_lexer("CSS").is_none());
/// ```
pub fn promoted_lexer(display_name: &str) -> Option<&'static CompiledLexer> {{
    match display_name {{
{arms}
        _ => None,
    }}
}}
''',
        encoding="utf-8",
    )
    total = sum(builder.count("        rule(") for builder in builders)
    print(f"{len(identifiers)} families, {total} rules -> {options.out}")


if __name__ == "__main__":
    main()
