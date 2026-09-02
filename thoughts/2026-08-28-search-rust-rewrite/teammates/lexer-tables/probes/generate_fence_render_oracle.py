#!/usr/bin/env -S uv run
"""Record what Rich renders for a fenced block in a **promoted** language.

The token-stream gate proves the table; this proves the block. Between them the
claim is end to end: the same fence tag a message carries, through the product's
own `Markdown`, at five widths, compared as styled runs rather than as SGR bytes.

**Two things it does not re-derive.** The recording machinery is imported from
`message-renderer`'s markdown oracle rather than copied, so the two corpora are
recorded by one function. And the real blocks come from the *token* oracle already
on disk, so this fixture regenerates identically from a checkout — which the
markdown oracle's own sampled half does not, because that half re-reads the live
session directory every time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "message-renderer" / "probes")
)

from generate_markdown_oracle import WIDTHS, render

# Geometry and colour together: every one of these reaches the promoted table, so a
# difference here is a difference in the *rendered* block rather than in the stream.
CURATED = {
 "typescript": [
    ("ts-plain", "typescript", "const answer: number = 42\nexport default answer\n"),
    ("ts-tag-ts", "ts", "function add(a: number, b: number) {\n    return a + b\n}\n"),
    (
        "ts-template-literal",
        "typescript",
        "const greeting = `hello ${name}, you have ${count} items`\n",
    ),
    (
        "ts-comment-and-regex",
        "typescript",
        "// strip the prefix\nconst cleaned = raw.replace(/^\\s+/g, '')\n",
    ),
    (
        "ts-decorator-and-private-field",
        "typescript",
        "@Injectable()\nclass Store {\n    #items: string[] = []\n}\n",
    ),
    (
        "ts-long-line",
        "typescript",
        "const message = " + "'a string literal long enough to wrap at every width' + " * 3 + "''\n",
    ),
    ("ts-long-word", "typescript", "const x = '" + "y" * 130 + "'\n"),
    ("ts-tabs", "typescript", "class A {\n\tvalue = 1\n\t\tdeep = 2\n}\n"),
    (
        "ts-wide-characters",
        "typescript",
        "const label = '你好你好你好你好你好你好你好你好你好你好'\n",
    ),
    ("ts-unicode-identifier", "typescript", "const café = 1\nconst Ω = café * 2\n"),
    ("ts-empty", "typescript", ""),
    ("ts-trailing-blank-lines", "typescript", "const a = 1\n\n\n"),
    ("ts-leading-indent", "typescript", "    const indented = 1\n        const deeper = 2\n"),
    ("ts-tag-with-argument", "typescript title=example", "const tagged = true\n"),
    (
        "ts-unterminated-string",
        "typescript",
        "const broken = 'never closed\nconst after = 1\n",
    ),
 ],
 "tsx": [
    ("tsx-element", "tsx", "const view = <div className=\"row\">{items}</div>\n"),
    ("tsx-fragment", "tsx", "const list = <>\n    <Item key={id} />\n</>\n"),
    (
        "tsx-component",
        "tsx",
        "export function Row({ label }: Props) {\n"
        "    return <li title={label}>{label}</li>\n}\n",
    ),
    ("tsx-dotted-element", "tsx", "const nested = <Foo.Bar prop={1}></Foo.Bar>\n"),
    ("tsx-attribute-expression", "tsx", "const el = <input value={count + 1} disabled />\n"),
    ("tsx-spread", "tsx", "const el = <div {...props} data-id='x' />\n"),
    ("tsx-template-literal", "tsx", "const cls = `row ${active ? 'on' : 'off'}`\n"),
    ("tsx-comment", "tsx", "// a note\nconst a = 1 /* inline */\n"),
    (
        "tsx-long-line",
        "tsx",
        "const label = " + "'a string long enough to wrap at every width' + " * 3 + "''\n",
    ),
    ("tsx-long-word", "tsx", "const x = '" + "y" * 130 + "'\n"),
    ("tsx-tabs", "tsx", "const view = <div>\n\t<span />\n\t\t<b />\n</div>\n"),
    ("tsx-wide-characters", "tsx", "const label = <p>你好你好你好你好你好你好你好你好你好你好</p>\n"),
    ("tsx-empty", "tsx", ""),
    ("tsx-trailing-blank-lines", "tsx", "const a = 1\n\n\n"),
    ("tsx-unterminated-string", "tsx", "const broken = 'never closed\nconst after = 1\n"),
 ],
 "python": [
    ("py-plain", "python", "def add(a: int, b: int) -> int:\n    return a + b\n"),
    ("py-tag-py", "py", "import os\nprint(os.getcwd())\n"),
    ("py-tag-python3", "python3", "value = {'key': [1, 2, 3]}\n"),
    ("py-docstring", "python", '\'\'\'A module docstring.\n\nSecond paragraph.\n\'\'\'\n'),
    (
        "py-fstring",
        "python",
        'name = "world"\nprint(f"hello {name!r} {count:>10.2f} {{literal}}")\n',
    ),
    ("py-raw-and-bytes", "python", 'pattern = rb"\\d+"\ntext = u\'\'\'unicode\'\'\'\n'),
    ("py-decorator-and-class", "python", "@dataclass\nclass Widget(Base):\n    pass\n"),
    ("py-numbers", "python", "a = 1.5\nb = 0o755\nc = 0xFF_00\nd = 2E-3j\n"),
    ("py-comment", "python", "# what this does\nvalue = 1  # trailing\n"),
    ("py-match", "python", "match command:\n    case _:\n        pass\n"),
    (
        "py-long-line",
        "python",
        "message = " + "'a string literal long enough to wrap at every width' + " * 3 + "''\n",
    ),
    ("py-long-word", "python", "value = '" + "y" * 130 + "'\n"),
    ("py-tabs", "python", "if True:\n\tvalue = 1\n\t\tdeeper = 2\n"),
    ("py-wide-characters", "python", "label = '你好你好你好你好你好你好你好你好你好你好'\n"),
    ("py-empty", "python", ""),
    ("py-trailing-blank-lines", "python", "value = 1\n\n\n"),
    ("py-unterminated-string", "python", "broken = 'never closed\nafter = 1\n"),
 ],
 "javascript": [
    ("js-plain", "javascript", "const answer = 42\nexport default answer\n"),
    ("js-tag-js", "js", "function add(a, b) {\n    return a + b\n}\n"),
    ("js-tag-node", "node", "const fs = require('fs')\nfs.readFileSync('a.txt')\n"),
    ("js-template-literal", "javascript", "const greeting = `hello ${name}, ${count} items`\n"),
    ("js-comment-and-regex", "javascript", "// strip it\nconst c = raw.replace(/^\\s+/g, '')\n"),
    ("js-class", "javascript", "class Store {\n    #items = []\n    get size() { return 1 }\n}\n"),
    ("js-numbers", "javascript", "const a = 0b1010n\nconst b = 0o755\nconst c = 0xFF00n\n"),
    (
        "js-long-line",
        "javascript",
        "const message = " + "'a string long enough to wrap at every width' + " * 3 + "''\n",
    ),
    ("js-long-word", "javascript", "const x = '" + "y" * 130 + "'\n"),
    ("js-tabs", "javascript", "if (a) {\n\tb()\n\t\tc()\n}\n"),
    ("js-wide-characters", "javascript", "const label = '你好你好你好你好你好你好你好你好你好你好'\n"),
    ("js-empty", "javascript", ""),
    ("js-trailing-blank-lines", "javascript", "const a = 1\n\n\n"),
    ("js-unterminated-string", "javascript", "const broken = 'never closed\nconst after = 1\n"),
 ],
 "sql": [
    ("sq-select", "sql", "SELECT id, name FROM users WHERE id = 1 ORDER BY name;\n"),
    ("sq-lowercase", "sql", "select * from t where a <> 'b';\n"),
    ("sq-create", "sql", "CREATE TABLE t (\n    id BIGINT,\n    name VARCHAR(50)\n);\n"),
    ("sq-comments", "sql", "-- a note\n/* a block\n   comment */\nSELECT 1;\n"),
    ("sq-quotes", "sql", "SELECT 'it''s', \"quoted\" FROM t;\n"),
    (
        "sq-long-line",
        "sql",
        "SELECT " + "'a column name long enough to wrap at every width', " * 3 + "1;\n",
    ),
    ("sq-long-word", "sql", "SELECT '" + "y" * 130 + "';\n"),
    ("sq-tabs", "sql", "SELECT\n\tid,\n\t\tname\nFROM t;\n"),
    ("sq-wide-characters", "sql", "SELECT '你好你好你好你好你好你好你好你好你好你好';\n"),
    ("sq-empty", "sql", ""),
    ("sq-trailing-blank-lines", "sql", "SELECT 1;\n\n\n"),
    ("sq-unterminated-string", "sql", "SELECT 'never closed\nFROM t;\n"),
 ],
 "json": [
    ("js-object", "json", '{"name": "value", "count": 1, "ok": true, "none": null}\n'),
    ("js-array", "json", '[1, 2.5, "three", false, null]\n'),
    ("js-nested", "json", '{\n  "outer": {\n    "inner": [1, 2]\n  }\n}\n'),
    ("js-escapes", "json", '{"text": "a \\" b \\\\ c \\u00e9"}\n'),
    ("js-comments", "json", '{\n  // a note\n  "a": 1 /* inline */\n}\n'),
    ("js-tag-json-object", "json-object", '{"a": 1}\n'),
    ("js-no-validation", "json", "--1-- trustful 1...eee\n"),
    ("js-errors", "json", "{'single': `backtick`}\n"),
    (
        "js-long-line",
        "json",
        '{"message": "' + "a value long enough to wrap at every width " * 3 + '"}\n',
    ),
    ("js-long-word", "json", '{"a": "' + "y" * 130 + '"}\n'),
    ("js-tabs", "json", '{\n\t"a": 1,\n\t\t"b": 2\n}\n'),
    ("js-wide-characters", "json", '{"label": "你好你好你好你好你好你好你好你好你好你好"}\n'),
    ("js-empty", "json", ""),
    ("js-trailing-blank-lines", "json", '{"a": 1}\n\n\n'),
    ("js-unterminated-string", "json", '{"a": "never closed\n'),
 ],
 "bash": [
    ("sh-plain", "bash", "#!/usr/bin/env bash\nset -euo pipefail\necho \"done\"\n"),
    ("sh-tag-sh", "sh", "for name in a b c; do\n    echo \"$name\"\ndone\n"),
    ("sh-tag-zsh", "zsh", "alias ll='ls -la'\nexport PATH=\"$HOME/bin:$PATH\"\n"),
    ("sh-tag-shell", "shell", "cd /tmp && rm -f log.txt || exit 1\n"),
    (
        "sh-substitutions",
        "bash",
        "now=$(date +%s)\ncount=$((now % 60))\necho \"${count:-0} ${#name}\"\n",
    ),
    ("sh-backticks", "bash", "files=`ls -1`\necho $files\n"),
    ("sh-heredoc", "bash", "cat <<EOF\nline one\nline two\nEOF\n"),
    ("sh-here-string", "bash", "grep -q pattern <<<\"$haystack\"\n"),
    ("sh-comment", "bash", "# what this does\nls -la  # trailing\n"),
    (
        "sh-long-line",
        "bash",
        "echo " + "'a quoted word long enough to wrap at every width' " * 3 + "\n",
    ),
    ("sh-long-word", "bash", "echo " + "y" * 130 + "\n"),
    ("sh-tabs", "bash", "if true; then\n\techo one\n\t\techo two\nfi\n"),
    ("sh-wide-characters", "bash", "echo '你好你好你好你好你好你好你好你好你好你好'\n"),
    ("sh-empty", "bash", ""),
    ("sh-trailing-blank-lines", "bash", "echo a\n\n\n"),
    ("sh-unterminated-string", "bash", "echo \"never closed $x\n"),
 ],
}


def real_blocks(
    token_oracle: Path, tag: str, prefix: str, count: int, cap: int
) -> list[tuple[str, str, str]]:
    """Real TypeScript, taken from the token oracle rather than from the disk again."""
    payload = json.loads(token_oracle.read_text())
    chosen = []
    for case in payload["cases"]:
        if case["source"] != "harvested":
            continue
        text = case["text"]
        # A fence cannot carry its own delimiter, and a long block makes a failure
        # unreadable without adding a shape.
        if "```" in text or len(text) > cap:
            continue
        chosen.append((f"{prefix}-real-{len(chosen)}", tag, text))
        if len(chosen) >= count:
            break
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="typescript")
    parser.add_argument("--tag", default="typescript")
    parser.add_argument("--prefix", default="ts")
    parser.add_argument("--real", type=int, default=40)
    parser.add_argument("--cap", type=int, default=400)
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    token_oracle = Path(f"tests/data/lexer-tables/{options.family}-oracle.json")
    cases = CURATED[options.family] + real_blocks(
        token_oracle, options.tag, options.prefix, options.real, options.cap
    )
    records = []
    for identifier, tag, code in cases:
        markup = f"```{tag}\n{code}```"
        for width in WIDTHS:
            records.append(
                {
                    "id": identifier,
                    "width": width,
                    "markup": markup,
                    "lines": render(markup, width),
                }
            )

    from importlib.metadata import version

    Path(options.out).write_text(
        json.dumps(
            {
                "rich_version": version("rich"),
                "widths": list(WIDTHS),
                "curated": len(CURATED),
                "real": len(cases) - len(CURATED),
                "cases": records,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"{len(records)} records over {len(cases)} fenced cases -> {options.out}")


if __name__ == "__main__":
    main()
