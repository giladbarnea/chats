#!/usr/bin/env python3
"""Sessions and command shapes this contract adds on top of the cycle-02 shapes.

Every session here exists because a named defect had no fixture shaped like it.
The expectations are not written here: the oracle supplies them. Adding the
shape is the whole contribution, because a shape absent from the corpus is a
shape no parity proof can see.
"""

from __future__ import annotations

CWD = "/tmp/search-contract"
BASE_TIMESTAMP = "2026-08-20T13:00:00.000Z"
# Clear of every inherited mtime, whose maximum is 1800006000.0. An exact
# collision there made two fixture files tie on the ordering key, and the tie
# is broken by `read_dir` order, which is not stable across directory
# instances. `generate_fixtures.py` now refuses to build a corpus with a tie.
EXTRA_MTIME_BASE = 1800010000.0


def _claude_user(text: str, *, timestamp: str = BASE_TIMESTAMP) -> dict:
    return {
        "type": "user",
        "timestamp": timestamp,
        "cwd": CWD,
        "message": {"role": "user", "content": text},
    }


def _claude_assistant(text: str, *, timestamp: str = BASE_TIMESTAMP) -> dict:
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "cwd": CWD,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


SHELL_FENCE = """Renderfence shell sample:

```bash
cat <<'EOF' > /tmp/render.txt
inner $NOT_EXPANDED line
EOF
echo "done" && ls -la | grep -v '^d'
```
"""

PYTHON_FENCE = """Renderfence python sample:

```python
def build(name: str, count: int = 3) -> str:
    return f"{name!r} x {count} -> {' '.join(str(i) for i in range(count))}"
```
"""

WEB_FENCE = """Renderfence web sample:

```javascript
const render = (items) => items.map((item) => `<li>${item.name}</li>`).join("");
```

```html
<section class="panel"><h1 id="title">Heading</h1><!-- note --></section>
```

```css
.panel > h1#title { color: #5cc8a8; margin: 0 auto; content: "x"; }
```
"""

DATA_FENCE = """Renderfence data sample:

```json
{"name": "value", "nested": [1, 2.5, true, null], "escaped": "a\\"b"}
```

```diff
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
-removed line
+added line
 context line
```

```markdown
# Heading

- **bold** item with `code`
- [link](https://example.invalid)
```
"""

LONG_LINE = (
    "Renderwrap "
    + " ".join(f"segment{index:03d}" for index in range(60))
    + " end-of-long-line"
)

WIDE_GLYPHS = (
    "Renderwide CJK 中文字符串测试 and kana カタカナひらがな and emoji 🎯🚀👩‍👩‍👧‍👦 "
    "then ASCII tail"
)

# `has_inner_opening_tag` tests for `<tag` followed by `>` or a literal space,
# per line. Python's grammar admits the whole `\s` class in the attribute
# separator and, under MULTILINE, lets an opening tag continue onto the next
# line. The disagreement runs both ways, so all five shapes are needed:
# over-eager, under-eager, under-eager across lines, and the two that agree.
INCOMPLETE_TAGS = (
    "Renderescape over: <thinking is my hobby and not a tag\n"
    'Renderescape undertab: <thinking\tname="x">\n'
    'Renderescape underline: <thinking\nname="x">\n'
    'Renderescape agree-attr: <thinking name="x">\n'
    "Renderescape agree-bare: <thinking>real tag body</thinking>\n"
    "Renderescape plain: a < b and c > d"
)

# `re.IGNORECASE` folds single codepoints with a fixes table; `casefold()` does
# not agree with it. Today's Python search only avoids the divergence behind an
# `.isascii()` guard, so a native engine that drops the guard moves search truth
# with nothing to show for it.
CASEFOLD_TEXT = (
    "Renderfold sharp ß and ss pair\n"
    "Renderfold dotted İ and i pair\n"
    "Renderfold long ſ and s pair\n"
    "Renderfold kelvin K and k pair"
)

# The literal fallback must stay case-insensitive by default: an unbalanced
# paren is an ordinary shell-quoting accident, not an edge case.
LITERAL_PAREN_TEXT = "Renderparen calls foo( with an unbalanced paren"

# 14 characters, not 40. `(a+)+b` over 40 `a`s does not terminate in CPython
# inside ten seconds, so no expectation can be derived from it and no golden can
# own it. The pathological case is characterized in the contract as a product
# behavior with a ruling of its own; this run is long enough to exercise the
# backtracking path and short enough to have an answer.
BACKTRACK_TEXT = "Renderbacktrack " + "a" * 14 + " tail"

# Real transcripts carry carriage returns constantly: every `git` progress line
# and every Windows-authored file. A harness that captures with `text=True`
# rewrites `\r\n` and lone `\r` to `\n`, so it agrees where the two
# implementations differ and differs where they agree. This corpus captures
# bytes, and this session makes the product side of that visible.
CARRIAGE_RETURN_TEXT = (
    "Rendercr progress follows\r\n"
    "Receiving objects:  47% (470/1000)\r"
    "Receiving objects: 100% (1000/1000)\r\n"
    "Rendercr done"
)

# `truncate_middle` measures code points, not bytes, and splits grapheme
# clusters freely. A Rust port that slices bytes panics on a non-boundary index
# — the good failure, but only if a fixture reaches it — and one that "improves"
# this to graphemes or display width diverges silently. One sample per script,
# each 16 code points wide but a different byte width.
SHORT_SCRIPT_SAMPLES = {
    "latin": "abcdefghijklmnop",
    "hebrew": "אבגדהוזחטיכלמנסע",
    "cjk": "中文字符串測試樣本內容包含十六",
    "astral": "𝔘𝔫𝔦𝔠𝔬𝔡𝔢𝔗𝔢𝔵𝔱𝔖𝔞𝔪𝔭𝔩",
    "zwj": "👩‍👩‍👧‍👦👨‍👨‍👦‍👦x",
    "combining": "éééééééééééééééé",
}

# The passthrough test is `len(s) <= max_chars - len(placeholder)`, so a string
# shorter than the limit is still truncated and the output comes out longer than
# the input.
SHORT_PASSTHROUGH_SAMPLES = ("xxxxx", "xxxxxx", "xxxxxxxxxxx")

PI_USER_AGENT_CONTENT = (
    "<user_agent>\n"
    "<user_invocation>\n"
    "/agent renderagent task\n"
    "</user_invocation>\n"
    "<task>\n"
    "renderagent task\n"
    "</task>\n"
    "<response>\n"
    "renderagent response body\n"
    "</response>\n"
    "</user_agent>"
)


EXTRA_SESSIONS: dict[str, list[dict]] = {
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa01.jsonl": [
        _claude_assistant(SHELL_FENCE)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa02.jsonl": [
        _claude_assistant(PYTHON_FENCE)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa03.jsonl": [
        _claude_assistant(WEB_FENCE)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa04.jsonl": [
        _claude_assistant(DATA_FENCE)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa05.jsonl": [
        _claude_user(LONG_LINE)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa06.jsonl": [
        _claude_user(WIDE_GLYPHS)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa07.jsonl": [
        _claude_user(INCOMPLETE_TAGS)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa08.jsonl": [
        _claude_user(CASEFOLD_TEXT)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa09.jsonl": [
        _claude_user(LITERAL_PAREN_TEXT)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa10.jsonl": [
        _claude_user(BACKTRACK_TEXT)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa13.jsonl": [
        _claude_user(CARRIAGE_RETURN_TEXT)
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa14.jsonl": [
        _claude_user("Rendershort script samples follow"),
        *(
            _claude_assistant(f"{name} {sample}")
            for name, sample in SHORT_SCRIPT_SAMPLES.items()
        ),
    ],
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa15.jsonl": [
        _claude_user("Renderpass short samples follow"),
        *(_claude_assistant(sample) for sample in SHORT_PASSTHROUGH_SAMPLES),
    ],
    ".pi/agent/sessions/contract/2026-08-20T14-00-00-000Z_b1b1b1b1-1111-4111-8111-bbbbbbbbbb01.jsonl": [
        {"type": "session", "id": "b1b1b1b1-1111-4111-8111-bbbbbbbbbb01", "cwd": CWD},
        {
            "type": "custom_message",
            "customType": "pi-user-agents",
            "timestamp": BASE_TIMESTAMP,
            "details": {
                "agentId": "renderagent-1",
                "task": "renderagent task",
                "mainContextState": "joined",
                "content": PI_USER_AGENT_CONTENT,
            },
        },
    ],
}

# A first line carrying `NaN` makes `detect_format` report "jsonl" while
# `decode_jsonl_entries` drops it, so the two JSON readers disagree about
# whether the session exists at all.
RAW_EXTRA_SESSIONS: dict[str, str] = {
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa11.jsonl": (
        '{"type":"user","timestamp":"2026-08-20T13:00:00.000Z","cwd":"'
        + CWD
        + '","message":{"role":"user","content":"Rendernan first line"},"score":NaN}\n'
        '{"type":"user","timestamp":"2026-08-20T13:01:00.000Z","cwd":"'
        + CWD
        + '","message":{"role":"user","content":"Rendernan second line"}}\n'
    ),
    # Python `str.strip()` removes U+001C through U+001F and Rust `.trim()` does
    # not, so one leading control character flips a whole file from `jsonl` to
    # `raw` in one implementation and not the other.
    ".claude/projects/render/a1a1a1a1-1111-4111-8111-aaaaaaaaaa12.jsonl": (
        "\x1c"
        + '{"type":"user","timestamp":"2026-08-20T13:00:00.000Z","cwd":"'
        + CWD
        + '","message":{"role":"user","content":"Renderctrl separator line"}}\n'
    ),
}


EXTRA_CASES: list[dict] = [
    # ── Colored rendering: hand-written tokenizers against real content ──
    {"id": "render-fence-shell-96", "arguments": ["Renderfence shell", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-fence-shell-60", "arguments": ["Renderfence shell", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 60, "color": True},
    {"id": "render-fence-python-96", "arguments": ["Renderfence python", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-fence-python-60", "arguments": ["Renderfence python", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 60, "color": True},
    {"id": "render-fence-web-96", "arguments": ["Renderfence web", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-fence-web-140", "arguments": ["Renderfence web", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 140, "color": True},
    {"id": "render-fence-data-96", "arguments": ["Renderfence data", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-fence-data-60", "arguments": ["Renderfence data", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 60, "color": True},
    {"id": "render-wrap-long-96", "arguments": ["Renderwrap", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-wrap-long-40", "arguments": ["Renderwrap", "--color", "always", "--no-paging", "--no-metadata"], "columns": 40, "color": True},
    {"id": "render-wide-glyphs-96", "arguments": ["Renderwide", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "render-wide-glyphs-40", "arguments": ["Renderwide", "--color", "always", "--no-paging", "--no-metadata"], "columns": 40, "color": True},
    {"id": "render-fence-shell-plain", "arguments": ["Renderfence shell", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "render-wide-glyphs-plain", "arguments": ["Renderwide", "-f", "--no-metadata"], "columns": 96, "color": False},
    # ── Renderer escaping of incomplete opening tags ──
    {"id": "escape-incomplete-tag-plain", "arguments": ["Renderescape", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "escape-incomplete-tag-colored", "arguments": ["Renderescape", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "escape-incomplete-tag-search", "arguments": ["<thinking is my hobby", "-ll"], "columns": 96, "color": False},
    {"id": "escape-complete-tag-search", "arguments": ["<thinking>", "-ll"], "columns": 96, "color": False},
    {"id": "escape-tab-separated-tag-search", "arguments": ["Renderescape undertab", "-ll"], "columns": 96, "color": False},
    {"id": "escape-newline-separated-tag-search", "arguments": ["Renderescape underline", "-ll"], "columns": 96, "color": False},
    {"id": "escape-escaped-entity-search", "arguments": ["&lt;thinking", "-ll"], "columns": 96, "color": False},
    # `truncate_middle` counts code points and cuts grapheme clusters. A byte-
    # slicing port panics here; a grapheme-aware "improvement" diverges quietly.
    {"id": "short-grapheme-16", "arguments": ["Rendershort", "-f", "--short=16", "--no-metadata"], "columns": 96, "color": False},
    {"id": "short-grapheme-16-colored", "arguments": ["Rendershort", "-f", "--short=16", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    {"id": "short-grapheme-8", "arguments": ["Rendershort", "-f", "--short=8", "--no-metadata"], "columns": 96, "color": False},
    {"id": "short-grapheme-progressive", "arguments": ["Rendershort", "-f", "--short=p=128", "--no-metadata"], "columns": 96, "color": False},
    # A string shorter than the limit is still truncated, and comes out longer.
    {"id": "short-passthrough-10", "arguments": ["Renderpass", "-f", "--short=10", "--no-metadata"], "columns": 96, "color": False},
    {"id": "short-passthrough-8", "arguments": ["Renderpass", "-f", "--short=8", "--no-metadata"], "columns": 96, "color": False},
    # Carriage returns inside content, which a `text=True` harness would erase.
    {"id": "carriage-return-id", "arguments": ["Rendercr", "-ll"], "columns": 96, "color": False},
    {"id": "carriage-return-body", "arguments": ["Rendercr", "-f", "--no-metadata"], "columns": 96, "color": False},
    {"id": "carriage-return-raw", "arguments": ["Rendercr", "-f", "-r"], "columns": 96, "color": False},
    {"id": "carriage-return-colored", "arguments": ["Rendercr", "-f", "--color", "always", "--no-paging", "--no-metadata"], "columns": 96, "color": True},
    # One leading U+001C flips a file between `jsonl` and `raw` for one reader.
    {"id": "control-prefixed-first-line-id", "arguments": ["Renderctrl", "-ll"], "columns": 96, "color": False},
    {"id": "control-prefixed-first-line-body", "arguments": ["Renderctrl", "-f", "--no-metadata"], "columns": 96, "color": False},
    # ── Case folding: re.IGNORECASE is not casefold() ──
    {"id": "casefold-sharp-s-vs-ss", "arguments": ["Renderfold sharp ss", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-sharp-s-literal", "arguments": ["Renderfold sharp ß", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-dotted-i", "arguments": ["renderfold dotted İ", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-long-s", "arguments": ["renderfold long ſ", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-kelvin-k", "arguments": ["renderfold kelvin k", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-kelvin-sign", "arguments": ["renderfold kelvin K", "-ll"], "columns": 96, "color": False},
    {"id": "casefold-kelvin-case-sensitive", "arguments": ["-s", "Renderfold kelvin K", "-ll"], "columns": 96, "color": False},
    # ── Literal fallback must stay case-insensitive ──
    {"id": "literal-fallback-unbalanced-paren", "arguments": ["Renderparen calls foo(", "-ll"], "columns": 96, "color": False},
    {"id": "literal-fallback-unbalanced-paren-lower", "arguments": ["renderparen calls foo(", "-ll"], "columns": 96, "color": False},
    {"id": "literal-fallback-unbalanced-paren-sensitive", "arguments": ["-s", "Renderparen calls foo(", "-ll"], "columns": 96, "color": False},
    {"id": "literal-fallback-unbalanced-bracket", "arguments": ["Renderparen calls foo[", "-ll"], "columns": 96, "color": False},
    # ── Backtracking: two heavy patterns in one process, not just the first ──
    {"id": "backtrack-nested-quantifier", "arguments": ["(a+)+b", "-ll"], "columns": 96, "color": False},
    {"id": "backtrack-alternation", "arguments": ["(a|aa)+c", "-ll"], "columns": 96, "color": False},
    {"id": "backtrack-pair-in-one-query", "arguments": ["(a+)+b OR (a|aa)+c", "-ll"], "columns": 96, "color": False},
    # ── Two JSON readers disagreeing about the first line ──
    {"id": "nan-first-line-visible", "arguments": ["Rendernan", "-ll"], "columns": 96, "color": False},
    {"id": "nan-first-line-body", "arguments": ["Rendernan", "-f", "--no-metadata"], "columns": 96, "color": False},
    # ── Pi user-agent envelope without a duration terminator ──
    {"id": "pi-user-agent-joined-default", "arguments": ["renderagent response", "-ll"], "columns": 96, "color": False},
    {"id": "pi-user-agent-joined-agents", "arguments": ["-a", "renderagent response", "-ll"], "columns": 96, "color": False},
    {"id": "pi-user-agent-joined-body", "arguments": ["-a", "renderagent response", "-f", "--no-metadata"], "columns": 96, "color": False},
    # ── Provider column when the candidate pool holds a single provider ──
    {"id": "provider-column-single-provider", "arguments": ["-p", "claude", "Renderfence", "-l", "--color", "always", "--no-paging"], "columns": 96, "color": True},
    {"id": "provider-column-multi-provider", "arguments": ["needle", "-l", "--color", "always", "--no-paging"], "columns": 96, "color": True},
]
