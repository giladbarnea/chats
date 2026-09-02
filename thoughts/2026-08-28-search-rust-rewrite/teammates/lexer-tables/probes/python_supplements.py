#!/usr/bin/env -S uv run
"""The authored half of Python's corpus, generated rather than written out.

**Python's string surface is combinatorial and no real corpus covers it.**
`PythonLexer` declares one rule per prefix per quote style — `rf`, `f`, `rb`, `r`,
`u`, `b` and bare, times `\"\"\"`, `'''`, `"` and `'` — and then a *state* per
combination, several of them built by `combined()` and named `_tmp_N`. That is 435
rules over 49 states, where TypeScript has 94 over 6 and bash 189 over 9.

Real fenced Python reaches under half of it, so the rest is one small literal per
combination, each carrying the escapes, the `%` and `{}` format forms and the quote
characters those states' own rules are about. **They are recorded and compared
exactly as the harvested blocks are**, by the same Pygments driver; generating them
only means the set is complete by construction rather than by inspection.
"""

from __future__ import annotations

PREFIXES = ["rf", "FR", "f", "rb", "BR", "r", "u", "", "b"]
QUOTES = ['"""', "'''", '"', "'"]

ESCAPES = r"\n \x41 \101 \N{BULLET} \u00e9 \U0001F600 \\ "
FORMATS = "%s %(name)-10.3f {name} {obj.attr} {items[0]!r} {value:>10.2f} {{ }} %"


def string_cases() -> list[tuple[str, str]]:
    """One terminated and one unterminated literal per prefix and quote style.

    The unterminated half is not padding: a fenced block often ends inside a
    string, and the state's end-of-input path is a different rule from its closing
    quote.

    >>> len(string_cases()) == 2 * len(PREFIXES) * len(QUOTES)
    True
    """
    cases: list[tuple[str, str]] = []
    for prefix in PREFIXES:
        for quote in QUOTES:
            delimiter = quote[0]
            other = '"' if delimiter == "'" else "'"
            body = f"text and more {ESCAPES}{FORMATS} {other} "
            if len(quote) == 3:
                body += "\nsecond line\n"
            kind = "double" if delimiter == '"' else "single"
            name = f"string-{prefix or 'bare'}-{len(quote)}-{kind}"
            cases.append((name, f"value = {prefix}{quote}{body}{quote}\n"))
            cases.append((f"{name}-open", f"value = {prefix}{quote}{body}\n"))
    return cases


def fstring_expression_cases() -> list[tuple[str, str]]:
    """The replacement field's own expression state, which is Python's `expr` again.

    `expr-inside-fstring` and its `-inner` sibling are 87 of the 435 rules, and a
    real f-string almost never carries more than a name in the braces.
    """
    inner = (
        "0x1F 0b101 0o17 1.5e3 9j "
        "None True False Ellipsis NotImplemented self cls "
        "ArithmeticError repr(x) obj.__add__ obj.__class__ "
        "await thing if cond else other "
        "lambda: 1 "
        "[x async for x in items] "
        "'nested' \"also nested\" "
        "@ decorated "
    )
    return [
        ("fstring-expression", f"line = f\"{{ {inner} }}\"\n"),
        ("fstring-expression-single", f"line = f'{{ {inner} }}'\n"),
        ("fstring-expression-triple", f'line = f"""{{ {inner} }}"""\n'),
        (
            "fstring-nested-strings",
            'line = f"{ rb\'raw bytes\' } { u\'\'\'triple\'\'\' } { b"bytes" }"\n',
        ),
        (
            "fstring-conversions",
            'line = f"{value!r} {value!s} {value!a} {value:>{width}.2f} {{literal}}"\n',
        ),
        ("fstring-raw-escape", 'line = rf"a\\d+ {value} \\N{BULLET}"\n'),
        ("fstring-comment-like", 'line = f"# not a comment {value} % not a format"\n'),
        # Every string prefix again, this time **inside** a replacement field: the
        # f-string expression state carries its own copy of all of them.
        (
            "fstring-expression-prefixed-strings",
            'line = f"""{ rf"raw" } { FR\'\'\'triple\'\'\' } { f"inner" } { f\'\'\'ftriple\'\'\' }'
            ' { rb"bytes" } { BR\'\'\'rawbytes\'\'\' } { u"uni" } { U\'\'\'utriple\'\'\' }'
            ' { b"by" } { b\'\'\'bytriple\'\'\' } { "plain" } { \'single\' }"""\n',
        ),
        (
            "fstring-expression-operators",
            'line = f"{ a in b and c is not d or not e }" + f"{ 1e5 } { 2E-3j } { @deco } { @ }"\n',
        ),
        # `{`, `(` and `[` inside a field open a *second* expression state, which is
        # another whole copy of the same rules.
        (
            "fstring-expression-inner",
            'line = f"""{ ( rf"raw" , f\'\'\'t\'\'\' , rb"b" , u"u" , b"y" , \'s\' ) }'
            '{ [ 0x1F , 0b1, 0o7, 1.5e3, 9j, None, True, self, cls, Ellipsis ] }'
            '{ { ArithmeticError: repr, obj.__add__: obj.__class__ } }'
            '{ ( await x if y else z ) } { ( lambda: 1 ) } { ( x async for x in i ) }'
            '{ ( a in b and c is not d ) } { ( @deco ) } { ( a @ b ) }'
            '{ ( 1e5 ) } { ( 2E-3j ) } { ( # not a comment\n ) }"""\n',
        ),
    ]


ROOT_CASES: list[tuple[str, str]] = [
    (
        "module-docstring",
        "'''A module docstring.\n\nSecond paragraph.\n'''\nimport os\n",
    ),
    ("line-continuation", "total = 1 + \\\n    2\n"),
    ("soft-keywords", "match command:\n    case _:\n        pass\n"),
    ("soft-keyword-wildcard", "match value:\n    case  something _:\n        pass\n"),
    ("class-and-decorator", "@dataclass\nclass Widget(Base):\n    pass\n"),
    ("matrix-multiply", "product = left @ right\n"),
    (
        "numbers",
        "a = 1.5\nb = .5\nc = 2.\nd = 1_000.000_1\ne = 1e10\nf = 2E-3j\n"
        "g = 0o755\nh = 0b1010\ni = 0xFF_00\nj = 10j\n",
    ),
    (
        "expression-keywords",
        "value = [x async for x in items if x else None]\n"
        "lazy = lambda: (yield from other)\n"
        "awaited = await thing\n",
    ),
    (
        "magic-names",
        "class A:\n    def __init__(self):\n        self.__class__\n"
        "    def __add__(self, other):\n        return NotImplemented\n",
    ),
    (
        "builtins-and-exceptions",
        "raise ArithmeticError(repr(Ellipsis), cls, NotImplemented)\n",
    ),
    (
        "imports",
        "import os.path\nfrom . import sibling\nfrom None import nothing\n"
        "from a import (b, c)\n",
    ),
    (
        "expression-keywords-at-statement-level",
        "result = a if cond else b\nlazy = lambda: 0\ngen = (x for x in items)\n"
        "chosen = await thing\nrelayed = yield from source\n",
    ),
    (
        "magic-names-as-values",
        "handler = __add__\nwrapper = __enter__\nmeta = __class__\ndoc = __doc__\n",
    ),
    (
        "string-line-continuation",
        'value = "abc\\\ndef"\nother = \'ghi\\\njkl\'\n',
    ),
    (
        "function-and-class-names",
        "def handler(argument):\n    pass\n\nclass Handler:\n    pass\n",
    ),
]


def fstring_prefix_cases() -> list[tuple[str, str]]:
    """Every prefix and quote style again, inside a replacement field and inside a
    bracket within one.

    Those are two more whole copies of the string rules — `expr-inside-fstring` and
    `expr-inside-fstring-inner` — and nothing short of the same sweep reaches them.

    >>> len(fstring_prefix_cases()) == len(PREFIXES) * len(QUOTES)
    True
    """
    cases: list[tuple[str, str]] = []
    for prefix in PREFIXES:
        for quote in QUOTES:
            # A triple-double-quoted literal cannot sit inside a triple-double-quoted
            # f-string, so the outer quote is chosen against the inner one.
            outer = "'''" if quote == '"""' else '"""'
            literal = f"{prefix}{quote}inner{quote}"
            kind = "double" if quote[0] == '"' else "single"
            name = f"fstring-field-{prefix or 'bare'}-{len(quote)}-{kind}"
            body = f"{{ {literal} }} {{ ( {literal} ) }}"
            cases.append((name, f"line = f{outer}{body}{outer}\n"))
    return cases


CONTINUATION = "\\\n"

FSTRING_ODDITIES: list[tuple[str, str]] = [
    (
        # A backslash-newline inside an f-string body is its own rule in every one of
        # the `_tmp_N` states `combined()` built.
        "fstring-line-continuation",
        f'line = f"abc{CONTINUATION}def"\n'
        f"other = f'ghi{CONTINUATION}jkl'\n"
        f'triple = f"""mno{CONTINUATION}pqr"""\n'
        f"quad = f'''stu{CONTINUATION}vwx'''\n"
        f'raw = rf"abc{CONTINUATION}def"\n'
        f"rawsingle = rf'ghi{CONTINUATION}jkl'\n",
    ),
    (
        "fstring-field-punctuation",
        'line = f"{ a , b ; c : d }" + f"{ ( e , f ; g ) }"\n',
    ),
    (
        # A truncated `from` is the only way to the `fromimport` state's `default`:
        # every complete import pops at its `import` keyword first.
        "truncated-from",
        "from\n",
    ),
    (
        "fstring-field-spacing",
        'line = f"{\tvalue\t}" + f"{ (\tvalue\t) }"\n',
    ),
]


def cases() -> list[tuple[str, str]]:
    return (
        ROOT_CASES
        + fstring_expression_cases()
        + FSTRING_ODDITIES
        + fstring_prefix_cases()
        + string_cases()
    )
