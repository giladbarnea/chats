#!/usr/bin/env -S uv run
"""Record Pygments' token stream over real fenced blocks of one family.

The gate this feeds compares **two drivers over one table**: Pygments runs its own
`_tokens`, and `syntax_lexer` runs the table `generate_lexer_tables.py` projected
from that same `_tokens`. Neither side holds a reading of the other.

**The corpus is real fenced content**, harvested from session files, plus as few
authored snippets as it takes to reach the rules real content never does. Both
halves are recorded the same way and compared the same way; the split exists only
so the adequacy report can say which rules only an authored case reaches.

Every case also carries the rules Pygments matched while lexing it, recorded by
wrapping each matcher in `_tokens`. That is what makes "every declared rule is
reached" checkable rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import python_supplements
from generate_lexer_tables import LEXER_OPTIONS
from harvest_family_corpus import fences, preprocess
from pygments.lexers import get_lexer_by_name
from pygments.token import _TokenType

# **TSX includes TypeScript's whole `root` twice more** — once as `expression`, the
# JSX attribute container, and once as `interp-inside`. Each copy is its own rule, so
# the same repertoire has to be lexed inside each container. Neither may contain a
# `}`, which closes both.
TSX_BODY = (
    "abstract implements private protected public readonly "
    "enum interface override declare type string boolean number "
    "module Foo.Bar name: string @Deco "
    # Every one of these has to be **mid-line**: at a line start the `^(?=\s|/|<!--)`
    # lookahead fires first and `slashstartsregex`'s own copies match instead.
    "ident /* block */ ident <!-- legacy ident // line\n"
    "0b1010n 0o755 0xFF00n 42n 1.5e3 "
    # `/` last would be read as the start of a regex literal by the state the
    # operator before it pushes — and with no closing slash the whole rest of the
    # body becomes one `badregex` run of `Error`. It needs an operand on each side.
    "... => ++ -- ~ ??= ? : << >>> == != ** || && + - * % & | ^ one / two "
    "( [ ; , ) ] . "
    "typeof instanceof in void delete new constructor from as "
    "for while return var let const function class "
    "byte synchronized volatile goto "
    "true false null NaN Infinity undefined Array Math RangeError "
    "fn() { identifier \"double\" 'single' `template` #privateField "
)


# Every shape the shared bash body carries, for embedding in each container
# state — `curly`, `paren`, `math` and `backticks` each re-include the same
# rules, and each copy is its own rule that the corpus has to reach.
BASH_CONTAINER_BODY = (
    "if for done alias echo declare "  # keywords and builtins
    "# a comment\n"
    "a\\b "  # an escape
    "name+=1 "  # an assignment
    "[ = ] "  # operators
    "<<< "
    "<<EOT\nheredoc body\nEOT\n"
    "x && y || z "
    "$\"locale\" "
    "\"has $var inside\" "
    "$'a\\tb' "
    "'plain' "
    "; & | "
    "42 plaintext < "
)


# Rules that no real block reached, each with a case written to reach it. Real
# content is the corpus; these exist because an ungated rule is ungated whatever
# the reason, and there is no reviewer left to notice a table half-proved.
SUPPLEMENTS = {
    # Generated, because the surface is combinatorial. See the module.
    "python": python_supplements.cases(),
    "sql": [
        ("nested-block-comment", "SELECT 1 /* outer /* inner */ still outer */ FROM t\n"),
        ("comment-with-stars-and-slashes", "/* a * b / c ** d // e */\nSELECT 1\n"),
        ("line-comment-at-end", "SELECT 1 -- trailing with no newline"),
        (
            "quotes-and-operators",
            "SELECT 'it''s', \"quoted \"\"name\"\"\", a+b*c/d<e>f=g~h!i@j#k%l^m&n|o`p?q-r\n",
        ),
        ("types-and-keywords", "CREATE TABLE t (a BIGINT, b VARCHAR, c BOOLEAN, d NUMERIC)\n"),
        ("lowercase-keywords", "select * from users where id = 1 order by name;\n"),
    ],
    "markdown": [
        ("setext-heading", "A heading\n=========\n\nbody\n"),
        ("setext-subheading", "A heading\n---------\n\nbody\n"),
        # **The transcribed callback rule.** It is the one action in the whole
        # generator that is not projected from `_tokens`, so it is the one that most
        # needs real cases.
        ("fence-tagged", "text\n\n```python\nvalue = 1\n```\n\nafter\n"),
        ("fence-tagged-with-extra", "```python title=example\nvalue = 1\n```\n"),
        # A trailing space with no extra word: `whitespace` matches, `extra` is
        # empty, and the callback emits an empty `Text` where `bygroups` emits
        # nothing. This is the case the elision exists for.
        ("fence-tagged-trailing-space", "```python \nvalue = 1\n```\n"),
        ("fence-tagged-indented", "  ```js\nconst a = 1\n  ```\n"),
        ("fence-tagged-unknown-language", "```nosuchlanguage\nbody\n```\n"),
        ("fence-untagged", "```\nplain fenced text\n```\n"),
        ("escape", "a \\* not emphasis \\_ nor this \\\\ backslash\n"),
        ("strong-underscore", "some __bold__ text and a__b\n"),
        ("emphasis-underscore", "some _italic_ text and a_b\n"),
        ("strikethrough", "some ~~gone~~ text\n"),
        ("mention-and-tag", "cc @someone and #topic and @org/team\n"),
        ("reference-link", "see [the text][the-ref] and [empty][]\n"),
        ("link-definition", "  [the-ref]: https://example.com/page\n"),
        ("inline-shapes", "**strong** *emph* `code` [link](https://x) ![img](y)\n"),
    ],

    # JavaScript is TypeScript's parent, so the same shapes reach it — minus the
    # TypeScript-only rules, which do not exist here at all.
    "javascript": [
        ("shebang", "#!/usr/bin/env node\nconst x = 1\n"),
        ("html-comment-inline", "tag <!-- legacy comment\nconst after = 1\n"),
        ("html-comment-at-line-start", "<!-- legacy comment\nconst after = 1\n"),
        ("block-comment-inline", "value /* a block comment\n   over two lines */ next\n"),
        (
            "numeric-literals",
            "const bits = 0b1010n\nconst octal = 0o755\nconst old = 0755\n"
            "const hex = 0xFF00n\nconst big = 42n\n",
        ),
        (
            "reserved-words",
            "abstract byte char double final float goto int long native package\n"
            "synchronized throws transient volatile\n",
        ),
        ("super-call", "class Child extends Base {\n    constructor() { super(a, b) }\n}\n"),
        ("private-field", "class Counter {\n    #count = 0\n    bump() { this.#count += 1 }\n}\n"),
        ("template-lone-dollar", "const price = `costs $ and ${amount} more`\n"),
        ("template-escape", "const escaped = `line\\nbreak and \\` quote`\n"),
        (
            "template-interpolation",
            "const report = `${typeof value} ${new Error('x')} ${a in b}`\n"
            "const flow = `${cond ? await run() : yield* gen()}`\n"
            "const decl = `${(function () { return class {} })()}`\n",
        ),
        (
            "template-interpolation-literals",
            "const mixed = `${0b11n} ${0o17} ${0x1F} ${9n} ${true} ${null} ${undefined}`\n"
            "const spread = `${[...items].map((x) => x)}`\n"
            "const inner = `${'single quoted'} ${\"double quoted\"} ${`nested`}`\n",
        ),
        (
            "template-interpolation-reserved",
            "const reserved = `${byte} ${synchronized} ${volatile} ${goto}`\n"
            "const words = `${constructor} ${from} ${as}`\n",
        ),
        (
            "template-interpolation-comments",
            "const commented = `${ /* block */ value // line\n}`\n"
            "const spanning = `${ x\n/* c */ }`\n"
            "const legacy = `${ x <!-- inside }`\n",
        ),
        (
            "template-interpolation-members",
            "const called = `${RangeError} ${super(a)} ${obj.#field} ${fn() {}}`\n",
        ),
        ("regex-literal", "const cleaned = raw.replace(/^\\s+/g, '')\n"),
        ("bad-regex", "const broken = /unterminated\n"),
    ],
    "tsx": [
        ("jsx-fragment", "const empty = <></>\n"),
        ("jsx-element", "const view = <div></div>\n"),
        ("jsx-dotted-element", "const nested = <Foo.Bar></Foo.Bar>\n"),
        ("jsx-closing-fragment-path", "const closing = <Foo.Bar>text</Foo.Bar>\n"),
        (
            "jsx-attributes",
            "const input = <input type=\"text\" value='x' disabled data.key={1} "
            "{...props} />\n",
        ),
        ("jsx-attribute-braces", "const spread = <div {...props} ></div>\n"),
        # The same repertoire three times: `root` has its own copy of every rule
        # `expression` and `interp-inside` also carry.
        ("root-body", TSX_BODY + "\n"),
        ("expression-body", "const wide = <div prop={ " + TSX_BODY + " } />\n"),
        ("interpolation-body", "const line = `${ " + TSX_BODY + " }`\n"),
        ("expression-jsx", "const inner = <div prop={ <span></span> } />\n"),
        ("expression-fragment", "const frag = <div prop={ <></> } />\n"),
        ("expression-closing-name", "const close = <div prop={ </Foo.Bar> } />\n"),
        # A newline inside a container, with a `/` after it, is the only way to the
        # line-start lookahead there.
        ("expression-line-start", "const spans = <div prop={ x\n/* c */ } />\n"),
        ("interpolation-line-start", "const spans = `${ x\n/* c */ }`\n"),
        ("interpolation-jsx", "const mixed = `${ <span></span> }`\n"),
        ("interpolation-fragment", "const frag = `${ <></> }`\n"),
        ("interpolation-closing-name", "const close = `${ </Foo.Bar> }`\n"),
        ("template-escape", "const escaped = `line\\nbreak and \\` quote`\n"),
        ("template-lone-dollar", "const price = `costs $ and ${amount} more`\n"),
        ("line-start-comment", "const x = 1\n/* block */\nconst y = 2\n"),
        ("shebang", "#!/usr/bin/env node\nconst x = 1\n"),
        ("html-comment-at-line-start", "<!-- legacy comment\nconst after = 1\n"),
        ("regex-literal", "const cleaned = raw.replace(/^\\s+/g, '')\n"),
        # `super(...)` is what the swap mutation moves. Without it in the corpus the
        # swap changes nothing and the gate cannot see the ordering it claims.
        ("super-call", "class Child extends Base {\n    constructor() { super(a, b) }\n}\n"),
        ("bad-regex", "const broken = /unterminated\n"),
    ],
    "bash": [
        ("shebang", "#!/usr/bin/env bash\necho started\n"),
        (
            "keywords-and-builtins",
            "if [ -n \"$name inside\" ]; then\n    echo hi\nelse\n    cd /tmp\nfi\n"
            "for item in a b; do declare -r value=1; done\n",
        ),
        ("escape-and-assignment", "path=/tmp\ncount+=1\necho a\\ b\n"),
        ("here-string-and-heredoc", "cat <<<\"$value inside\"\ncat <<EOF\nbody\nEOF\n"),
        ("operators-and-punctuation", "a && b || c ; d & e | f\nsort < input.txt\n"),
        ("numbers-and-plain-text", "sleep 5\nls -la /var/log\n"),
        (
            "quotes",
            "echo \"plain double\"\necho $\"localised\"\necho $'escaped\\tvalue'\n"
            "echo 'single quoted'\necho \"has $var inside\"\n",
        ),
        ("dollar-forms", "echo $HOME $1 $# $? $! $* $@ $- $$ $\n"),
        (
            "math",
            "echo $((1 + 2 * 3))\necho $((0x1F))\necho $((2#1010))\necho $((16#ff))\n"
            "echo $((10#))\necho $((n))\necho $(( $((1)) ))\n",
        ),
        ("math-body", "echo $(( " + BASH_CONTAINER_BODY + " ))\n"),
        ("paren-body", "echo $( " + BASH_CONTAINER_BODY + " )\n"),
        ("backticks-body", "echo ` " + BASH_CONTAINER_BODY + " `\n"),
        # Every container re-includes the `$`-forms, and each copy is its own rule.
        ("math-dollars", "echo $(( ` x ` ~ $var + $1 + $ + $(( 1 )) ))\n"),
        ("paren-dollars", "echo $( $var $1 $ $(( 1 )) $( inner ) ${ y } < )\n"),
        ("backticks-dollars", "echo ` $var $1 $ $(( 1 )) $( inner ) ${ y } `\n"),
        ("curly-dollars", "echo ${ $var $1 $ $(( 1 )) $( inner ) < \n"),
        # A backtick is one of the seven characters `curly`'s catch-all excludes, so
        # it is the only rule in that block a case can still reach.
        ("curly-backticks", "echo ${ ` date ` \n"),
        (
            "curly",
            "echo ${name}\necho ${#array}\necho ${value:-default}\necho ${var:1}\n"
            "echo ${outer${inner}\n",
        ),
        ("curly-body", "echo ${ " + BASH_CONTAINER_BODY + " \n"),
        ("string-state", "echo \"has $var and $(date) and $((1+2)) and ${x} inside\"\n"),
        ("nested-containers", "echo $( echo `date` $((1)) ${x} )\n"),
    ],
    "typescript": [
        ("shebang", "#!/usr/bin/env node\nconst x = 1\n"),
        ("module-declaration", "module Foo.Bar {\n    export const value = 1\n}\n"),
        ("decorator", "@Component({selector: 'app'})\nclass Widget {}\n"),
        # `<!--` and `/* */` reach their own rules only away from a line start: at
        # one, the lookahead rule pushes `slashstartsregex` and its copies match
        # first.
        ("html-comment-inline", "tag <!-- legacy comment\nconst after = 1\n"),
        ("html-comment-at-line-start", "<!-- legacy comment\nconst after = 1\n"),
        (
            "numeric-literals",
            "const bits = 0b1010n\nconst octal = 0o755\nconst old = 0755\n"
            "const hex = 0xFF00n\nconst big = 42n\n",
        ),
        (
            "block-comment-inline",
            "value /* a block comment\n   over two lines */ next\n",
        ),
        (
            "reserved-words",
            "abstract byte char double final float goto int long native package\n"
            "synchronized throws transient volatile\n",
        ),
        ("super-call", "class Child extends Base {\n    constructor() { super(a, b) }\n}\n"),
        ("private-field", "class Counter {\n    #count = 0\n    bump() { this.#count += 1 }\n}\n"),
        ("template-lone-dollar", "const price = `costs $ and ${amount} more`\n"),
        (
            "template-interpolation",
            "const line = `${declare} ${type} ${string} ${boolean} ${number}`\n",
        ),
        (
            "template-interpolation-keywords",
            "const report = `${typeof value} ${new Error('x')} ${a in b}`\n"
            "const flow = `${cond ? await run() : yield* gen()}`\n"
            "const decl = `${(function () { return class {} })()}`\n",
        ),
        (
            "template-interpolation-literals",
            "const mixed = `${0b11n} ${0o17} ${0x1F} ${9n} ${true} ${null} ${undefined}`\n"
            "const spread = `${[...items].map((x) => x)}`\n"
            "const inner = `${'single quoted'} ${`nested`}`\n",
        ),
        (
            "template-interpolation-typescript",
            "const shape = `${abstract} ${enum} ${module Foo.Bar } ${name: string}`\n"
            "const decorated = `${@Deco class {}}`\n",
        ),
        (
            "template-interpolation-comments",
            "const commented = `${ /* block */ value // line\n}`\n"
            "const spanning = `${ x\n/* c */ }`\n"
            "const legacy = `${ x <!-- inside }`\n",
        ),
        (
            # `byte` and the rest appear only in the reserved-word rule, which the
            # earlier keyword rules would otherwise shadow.
            "template-interpolation-reserved",
            "const reserved = `${byte} ${synchronized} ${volatile} ${goto}`\n",
        ),
        (
            # Reached by real content only by luck: it was in one harvest and gone
            # from the next, because the session directory is live.
            "template-interpolation-reserved-words",
            "const words = `${constructor} ${from} ${as}`\n",
        ),
        (
            "template-interpolation-members",
            "const called = `${RangeError} ${super(a)} ${obj.#field} ${fn() {}}`\n",
        ),
    ],
}




# A rule an earlier rule in the same state always matches first. The witness is
# text the unreached rule matches at position 0; the generator finds the earlier
# rule that matches it there, so the *claim* is checked rather than asserted.
SHADOWED = {
    "typescript": {
        "root[30]": "super(a, b)",
        "interp-inside[31]": "super(a, b)",
    },
    # **Bash re-includes one shared body into five states, and two of them open with
    # a catch-all that swallows most of it.** `curly` starts `\w+` then
    # `[^}:"\'`$\\]+`, so every included rule whose pattern starts with anything but
    # those seven characters is dead; `math` starts with its own operator, number and
    # identifier rules, which shadow the included keyword, builtin and punctuation
    # copies. Each witness is text the dead rule matches, and the generator finds the
    # earlier rule that takes it first.
    # Python's raw-string states include the general escape rule *and* a narrower
    # one for `\\\\`, `\\"` and a line continuation; the general one takes all three.
    # And `root`'s expression-keyword copy sits behind the statement-keyword rule
    # that already lists the same words.
    "python": {
        "root[44]": "await ",
        "_tmp_6[5]": "\\\\",
        "_tmp_7[5]": "\\\\",
        "_tmp_10[3]": "\\\\",
        "_tmp_11[3]": "\\\\",
        "_tmp_14[2]": "\\\\",
        "_tmp_15[2]": "\\\\",
        "expr-inside-fstring[24]": " ",
        "expr-inside-fstring-inner[23]": " ",
    },
    "javascript": {
        "root[23]": "super(a, b)",
        "interp-inside[24]": "super(a, b)",
    },
    "tsx": {
        "root[34]": "super(a, b)",
        "expression[36]": "super(a, b)",
        "interp-inside[35]": "super(a, b)",
    },
    "bash": {
        "curly[5]": "if ",
        "curly[6]": "echo ",
        "curly[8]": "#comment\n",
        "curly[10]": "name=1",
        "curly[11]": "[",
        "curly[12]": "<<<",
        "curly[13]": "<<EOF\nbody\nEOF",
        "curly[14]": "&&",
        "curly[20]": ";",
        "curly[21]": "&",
        "curly[22]": "|",
        "curly[23]": " ",
        "curly[24]": "42",
        "curly[25]": "plain",
        "curly[26]": "<",
        "math[7]": "if ",
        "math[8]": "echo ",
        "math[12]": "name=1",
        "math[14]": "<<<",
        "math[15]": "<<EOF\nbody\nEOF",
        "math[16]": "&&",
        "math[23]": "&",
        "math[24]": "|",
        "math[26]": "42",
        "math[28]": "<",
    },
}


def instrumented_lexer(alias: str):
    """A lexer whose every rule records itself when Pygments' driver matches it."""
    lexer = get_lexer_by_name(
        alias, stripnl=False, ensurenl=True, tabsize=4, **LEXER_OPTIONS.get(alias, {})
    )
    declared = [
        f"{state}[{index}]"
        for state, rules in lexer._tokens.items()
        for index in range(len(rules))
    ]
    per_case: set[str] = set()
    # `bygroups` emits a token slot only when the group's text is **non-empty**, and
    # emits a callable's whenever the group took part. The two conditions differ, so
    # a corpus that never matches an empty group cannot tell them apart.
    empty_groups: set[str] = set()
    instrumented = {}
    for state, rules in lexer._tokens.items():
        replaced = []
        for index, rule in enumerate(rules):
            grouped = rule[1] is not None and not isinstance(rule[1], _TokenType)

            def matcher(
                text,
                position,
                name=f"{state}[{index}]",
                inner=rule[0],
                grouped=grouped,
            ):
                found = inner(text, position)
                if found is not None:
                    per_case.add(name)
                    if grouped and "" in found.groups():
                        empty_groups.add(name)
                return found

            replaced.append((matcher, *rule[1:]))
        instrumented[state] = replaced
    lexer._tokens = instrumented
    return lexer, declared, per_case, empty_groups


def record(lexer, per_case: set[str], text: str) -> dict:
    per_case.clear()
    stream = [[str(token), value] for token, value in lexer.get_tokens(text)]
    return {"text": text, "tokens": stream, "rules": sorted(per_case)}


def why_unreachable(alias: str, name: str, tokens: dict) -> str:
    """Why no input can reach a rule — mechanically, or refuse.

    A gate that lists a rule as unreachable without saying why is a gate that
    accepts an ungated rule with an excuse attached.
    """
    state, index = name[:-1].split("[")
    index = int(index)
    entered = {
        target
        for rules in tokens.values()
        for rule in rules
        for target in (rule[2] if isinstance(rule[2], tuple) else ())
        if target not in ("#pop", "#push")
    }
    if state != "root" and state not in entered:
        return f"no rule transitions into state `{state}`; it exists only for `include`"

    rules = tokens[state]
    pattern = rules[index][0].__self__.pattern
    # An identical pattern earlier in the state matches wherever this one would, so
    # this one never runs — whatever its action is. Both a duplicated rule and a
    # container's own delimiter re-included from a shared body land here.
    for earlier in range(index):
        if rules[earlier][0].__self__.pattern == pattern:
            return f"identical to {state}[{earlier}], which always matches first"

    if pattern.startswith(r"\A") and state != "root":
        return (
            r"`\A` matches only at position 0, which is always lexed in `root`; "
            "no `using(this)` in this table re-enters over a substring"
        )

    witness = SHADOWED.get(alias, {}).get(name)
    if witness is not None:
        if not re.compile(pattern, re.MULTILINE | re.DOTALL).match(witness):
            raise SystemExit(f"{name}: the witness {witness!r} does not reach this rule at all")
        for earlier in range(index):
            earlier_pattern = rules[earlier][0].__self__.pattern
            if re.compile(earlier_pattern, re.MULTILINE | re.DOTALL).match(witness):
                return (
                    f"{state}[{earlier}] matches every text this rule can start on — "
                    f"checked on {witness!r}"
                )
        raise SystemExit(f"{name}: no earlier rule in {state} matches {witness!r}")

    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", default="typescript")
    parser.add_argument("--tags", default="typescript,ts,tsx")
    parser.add_argument("--files", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--held-out",
        action="store_true",
        help=(
            "Real content only, from a different seed, with no authored cases and no "
            "coverage requirement. **Nothing is ever repaired against this corpus** — "
            "a failure here is a defect in the table or the driver."
        ),
    )
    options = parser.parse_args()

    lexer, declared, per_case, empty_groups = instrumented_lexer(options.alias)

    # The preprocessing is Rich's `_process_code` followed by `Lexer.get_tokens`'s
    # own, so the recorded text is exactly what the renderer will hand the driver.
    # This one is also the uninstrumented table the unreachability reasons read.
    plain = get_lexer_by_name(
        options.alias, stripnl=False, ensurenl=True, tabsize=4,
        **LEXER_OPTIONS.get(options.alias, {}),
    )
    tags = {tag.strip() for tag in options.tags.split(",")}
    seen: set[str] = set()
    cases = []
    for _, body in fences(options.files, options.seed, tags):
        text = preprocess(plain, body.rstrip())
        if text in seen:
            continue
        seen.add(text)
        entry = record(lexer, per_case, text)
        entry["source"] = "harvested"
        cases.append(entry)

    for name, snippet in [] if options.held_out else SUPPLEMENTS.get(options.alias, []):
        text = preprocess(plain, snippet.rstrip())
        entry = record(lexer, per_case, text)
        entry["source"] = f"authored:{name}"
        cases.append(entry)

    reached = {name for case in cases for name in case["rules"]}
    unreachable = (
        {}
        if options.held_out
        else {
            name: why_unreachable(options.alias, name, plain._tokens)
            for name in declared
            if name not in reached
        }
    )
    unexplained = [name for name, reason in unreachable.items() if not reason]
    if unexplained and not options.held_out:
        for name in unexplained:
            state, index = name[:-1].split("[")
            pattern = plain._tokens[state][int(index)][0].__self__.pattern
            print(f"  UNEXPLAINED {name}  {pattern[:120]!r}")
        raise SystemExit(
            f"{len(unexplained)} of {len(declared)} rules are never reached and "
            f"nothing explains why. Either the corpus needs cases that reach them, "
            f"or the reasons belong in this generator."
        )
    bygroups_rules = [
        f"{state}[{index}]"
        for state, rules in plain._tokens.items()
        for index, rule in enumerate(rules)
        if rule[1] is not None and not isinstance(rule[1], _TokenType)
    ]
    payload = {
        "lexer": lexer.name,
        # **Markdown's fenced-code callback emits an empty `Text` where `bygroups`
        # emits nothing**, when a fence's info string has trailing whitespace and no
        # extra word. Neither Rich's `Text.append_tokens` nor ours produces a segment
        # or a span for an empty token, so the *rendered* block is identical — which
        # the render gate proves end to end. The token comparison elides them on both
        # sides rather than pretending the streams are equal.
        "elide_empty_tokens": options.alias == "markdown",
        "declared_rules": declared,
        "bygroups_rules": bygroups_rules,
        "unreachable_rules": unreachable,
        "bygroups_rules_that_matched_an_empty_group": sorted(empty_groups),
        "cases": cases,
    }
    Path(options.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    characters = sum(len(case["text"]) for case in cases)
    tokens = sum(len(case["tokens"]) for case in cases)
    print(
        f"{len(cases)} cases, {characters} characters, {tokens} tokens, "
        f"{len(reached)} of {len(declared)} rules reached -> {options.out}"
    )
    print(f"{len(empty_groups)} bygroups rules matched an empty group")
    for name, reason in unreachable.items():
        print(f"  unreachable {name}: {reason}")


if __name__ == "__main__":
    main()
