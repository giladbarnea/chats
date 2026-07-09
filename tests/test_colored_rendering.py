"""Characterization tests for the colored Rich rendering of parse and search.

These pin *observable output* through the public commands (`cmd_parse`,
`cmd_search`), never the internal renderers. A refactor is free to rename or
merge the panel/rail/tool helpers as long as what reaches the terminal is
preserved — these tests guard that, plus the colored-vs-plain split the redesign
depends on. The rest of the suite exercises the plain/data path but not the
colored render structure, which is what these cover.
"""

from __future__ import annotations

import doctest
import importlib
import json
import re
from pathlib import Path

import pytest
from rich.console import Console

import chats.console as console_mod
from chats.commands.parse import cmd_parse
from chats.commands.search import cmd_search
from chats.model import ConversationFlags, SearchOutputMode
from chats.theme import APP_THEME
from chats.tool_filter import ToolFilter


def _write_claude_session(home: Path, session_id: str, entries: list[dict]) -> str:
    path = home / ".claude" / "projects" / "proj" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return session_id


def _assistant(*, text: str | None = None, content: list | None = None,
               model: str = "claude-opus-4-8", ts: str = "2026-06-16T11:00:00Z") -> dict:
    body = content if content is not None else [{"type": "text", "text": text}]
    return {"type": "assistant", "timestamp": ts, "cwd": "/tmp/proj",
            "message": {"role": "assistant", "model": model, "content": body}}


def _user(content, ts: str = "2026-06-16T11:01:00Z") -> dict:
    return {"type": "user", "timestamp": ts, "cwd": "/tmp/proj",
            "message": {"role": "user", "content": content}}


def _render_colored(monkeypatch, func, *args, styles: bool = False,
                    width: int = 96, **kwargs) -> str:
    """Run a command against a recording truecolor console and return its output."""
    recorder = Console(theme=APP_THEME, width=width, force_terminal=True,
                       color_system="truecolor", record=True)
    monkeypatch.setattr(console_mod, "_console", recorder)
    try:
        func(*args, **kwargs)
    except SystemExit:
        pass
    return recorder.export_text(styles=styles)


def test_colored_parse_is_tag_free(tmp_path, monkeypatch):
    """The colored parse view renders message bodies without XML wrapper tags."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "11111111-aaaa-bbbb-cccc-000000000001",
        [_assistant(text="Hello world.")],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False), sid, None, None,
        output_format="xml", emit_metadata=False,
    )

    assert "Hello world." in out, f"Expected message text in colored parse. Got:\n{out}"
    assert "<assistant-response" not in out, (
        f"Colored parse must drop the XML wrapper tag. Got:\n{out}"
    )
    assert "</assistant-response>" not in out, (
        f"Colored parse must drop the closing wrapper tag. Got:\n{out}"
    )


def test_colored_parse_panel_title_includes_message_date(tmp_path, monkeypatch):
    """The colored parse panel title includes the message date in human form."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "11111111-aaaa-bbbb-cccc-000000000003",
        [_assistant(text="Dated reply.", ts="2026-06-21T09:00:00Z")],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False), sid, None, None,
        output_format="xml", emit_metadata=False,
    )

    assert "Assistant" in out, f"Expected the assistant title. Got:\n{out}"
    assert "#1" in out, f"Expected the message index in the title. Got:\n{out}"
    assert "opus-4-8" in out, f"Expected the model in the title. Got:\n{out}"
    assert "June 21st" in out, f"Expected the human message date in the title. Got:\n{out}"


def test_colored_parse_leads_with_session_title(tmp_path, monkeypatch):
    """The colored parse view opens with a white session title, not dim YAML.

    The title precedes the first message panel and carries the session name (when
    one exists), the session id, and the created/modified dates — replacing the
    YAML frontmatter the plain (piping) path still emits.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_id = "44444444-aaaa-bbbb-cccc-000000000001"
    _write_claude_session(
        home, session_id,
        [
            {"type": "custom-title", "customTitle": "My Parsed Title",
             "sessionId": session_id},
            _assistant(text="Body.", ts="2026-06-21T09:00:00Z"),
        ],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False), session_id, None, None,
        output_format="xml", emit_metadata=True, width=120,
    )

    assert "My Parsed Title" in out, f"Expected the session name in the title. Got:\n{out}"
    assert session_id in out, f"Expected the session id in the title. Got:\n{out}"
    assert "/tmp/proj" in out, f"Expected the session cwd in the title. Got:\n{out}"
    assert "created" in out and "modified" in out, (
        f"Expected the created/modified dates in the title. Got:\n{out}"
    )
    assert out.index("My Parsed Title") < out.index("Assistant"), (
        f"Expected the title to precede the first message panel. Got:\n{out}"
    )
    assert "history_path" not in out and "provider:" not in out, (
        f"Expected the rich view to drop the YAML frontmatter. Got:\n{out}"
    )


def test_colored_parse_title_without_custom_title_leads_with_id(tmp_path, monkeypatch):
    """With no session name, the title headlines the session id."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_id = "55555555-aaaa-bbbb-cccc-000000000001"
    _write_claude_session(
        home, session_id,
        [_assistant(text="Body.", ts="2026-06-21T09:00:00Z")],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False), session_id, None, None,
        output_format="xml", emit_metadata=True, width=120,
    )

    assert session_id in out, f"Expected the session id in the title. Got:\n{out}"
    assert out.index(session_id) < out.index("Assistant"), (
        f"Expected the id title to precede the first message panel. Got:\n{out}"
    )


def test_colored_parse_title_rides_inside_pager(tmp_path, monkeypatch):
    """With paging on (the interactive default), the title shares the pager buffer.

    Paging defaults to the color value, so `ch parse <id>` in a terminal pages
    through `less`, which takes the alternate screen. A title printed before the
    pager would flash on the main screen and vanish; it must be rendered inside
    the same paged buffer as the panels to actually sit above the conversation.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_id = "66666666-aaaa-bbbb-cccc-000000000001"
    _write_claude_session(
        home, session_id,
        [
            {"type": "custom-title", "customTitle": "Paged Title",
             "sessionId": session_id},
            _assistant(text="Body.", ts="2026-06-21T09:00:00Z"),
        ],
    )

    paged: list[str] = []
    monkeypatch.setattr(
        console_mod.UnicodeSafePager, "show",
        lambda self, content: paged.append(content),
    )
    recorder = Console(theme=APP_THEME, width=120, force_terminal=True,
                       color_system="truecolor")
    monkeypatch.setattr(console_mod, "_console", recorder)

    cmd_parse(
        ConversationFlags(color="always", paging=True), session_id, None, None,
        output_format="xml", emit_metadata=True,
    )

    assert paged, "Expected the colored view to be paged when paging is on."
    content = "".join(paged)
    assert "Paged Title" in content, (
        "The title must be inside the paged buffer (visible above the panels), not "
        f"printed before the pager takes the alternate screen. Paged content:\n{content}"
    )
    assert "Assistant" in content, (
        f"The message panels should also be in the paged buffer. Got:\n{content}"
    )


def test_plain_parse_keeps_xml_tags(tmp_path, monkeypatch, capsys):
    """The plain (--color never) parse view keeps tags: the form meant for piping."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "11111111-aaaa-bbbb-cccc-000000000002",
        [_assistant(
            content=[
                {"type": "text", "text": "Running it."},
                {"type": "tool_use", "id": "toolu_01", "name": "Bash",
                 "input": {"command": "echo hi"}},
            ]
        )],
    )

    try:
        cmd_parse(
            ConversationFlags(color="never", paging=False, show_tools=True),
            sid, None, None, output_format="xml", emit_metadata=False,
        )
    except SystemExit:
        pass
    out = capsys.readouterr().out

    assert "<assistant-response" in out, (
        f"Plain xml must keep the wrapper tag (machine/LLM-piping form). Got:\n{out}"
    )
    assert "<tool-input" in out, (
        f"Plain xml must keep the tool tag. Got:\n{out}"
    )


def test_tool_call_and_result_markers(tmp_path, monkeypatch):
    """Tools render tag-free as ⏺ call / ⎿ result headers with a ▎ rail."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "22222222-aaaa-bbbb-cccc-000000000001",
        [
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0a", "name": "Bash",
                 "input": {"command": "echo hi"}},
            ]),
            _user([{"type": "tool_result", "tool_use_id": "toolu_0a",
                    "content": "hi"}]),
        ],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_tools=True),
        sid, None, None, output_format="xml", emit_metadata=False,
    )

    assert "⏺ Bash" in out, f"Expected ⏺ call header. Got:\n{out}"
    assert "⎿ Bash" in out, f"Expected ⎿ result header. Got:\n{out}"
    assert "▎" in out, f"Expected the left rail glyph. Got:\n{out}"
    assert "<tool-input" not in out and "<tool-output" not in out, (
        f"Tool blocks must be tag-free in colored output. Got:\n{out}"
    )


def test_additional_context_tool_has_dedicated_color(tmp_path, monkeypatch):
    """AdditionalContext renders in its own color, distinct from ordinary tools."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "22222222-aaaa-bbbb-cccc-000000000002",
        [
            {"type": "user", "uuid": "u1", "timestamp": "2026-06-16T11:00:00Z",
             "cwd": "/tmp/proj", "message": {"role": "user", "content": "go"}},
            {"type": "attachment", "uuid": "att1", "parentUuid": "u1",
             "timestamp": "2026-06-16T11:00:01Z", "cwd": "/tmp/proj",
             "attachment": {"type": "hook_additional_context",
                            "content": ["injected context body"],
                            "hookName": "UserPromptSubmit",
                            "toolUseID": "hook-123",
                            "hookEvent": "UserPromptSubmit"}},
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0a", "name": "Bash",
                 "input": {"command": "echo hi"}},
            ]),
        ],
    )

    styled = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_tools=True),
        sid, None, None, output_format="xml", emit_metadata=False, styles=True,
    )

    assert "AdditionalContext" in styled, (
        f"Expected the synthetic AdditionalContext tool to render. Got:\n{styled}"
    )
    assert "38;2;252;152;103" in styled, (
        f"Expected AdditionalContext to use Monokai orange (#fc9867). Got:\n{styled}"
    )
    assert "38;2;120;196;206" in styled, (
        f"Expected ordinary Bash tool calls to keep the existing cyan. Got:\n{styled}"
    )


def test_edit_renders_as_diff_not_old_new_blocks(tmp_path, monkeypatch):
    """Edit renders a colored diff, not labeled old_string:/new_string: blocks."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "33333333-aaaa-bbbb-cccc-000000000001",
        [_assistant(content=[
            {"type": "tool_use", "id": "toolu_0e", "name": "Edit",
             "input": {"file_path": "/tmp/a.css",
                       "old_string": "margin-left: 1em;",
                       "new_string": "margin-right: 1em;"}},
        ])],
    )

    plain = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_tools=True),
        sid, None, None, output_format="xml", emit_metadata=False,
    )
    styled = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_tools=True),
        sid, None, None, output_format="xml", emit_metadata=False, styles=True,
    )

    assert "old_string:" not in plain and "new_string:" not in plain, (
        f"Edit must not fall back to labeled string blocks. Got:\n{plain}"
    )
    assert "-margin-left: 1em;" in plain, f"Expected removed line. Got:\n{plain}"
    assert "+margin-right: 1em;" in plain, f"Expected added line. Got:\n{plain}"
    # diff.remove (#e27881) and diff.add (#98c379) reach the output.
    assert "38;2;226;120;129" in styled, f"Expected red removed-line color. Got:\n{styled}"
    assert "38;2;152;195;121" in styled, f"Expected green added-line color. Got:\n{styled}"


def test_read_output_highlighted_with_preserved_line_numbers(tmp_path, monkeypatch):
    """A Read result is highlighted by extension, keeping the input's line range."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    read_output = "    42\tdef compute():\n    43\t    return outcome"
    sid = _write_claude_session(
        home, "44444444-aaaa-bbbb-cccc-000000000001",
        [
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0r", "name": "Read",
                 "input": {"file_path": "/tmp/snippet.py"}},
            ]),
            _user([{"type": "tool_result", "tool_use_id": "toolu_0r",
                    "content": read_output}]),
        ],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_tools=True),
        sid, None, None, output_format="xml", emit_metadata=False,
    )

    assert "def compute():" in out, f"Expected file content. Got:\n{out}"
    assert "42" in out, (
        f"Expected the input's starting line number (42) preserved, not reset to 1. "
        f"Got:\n{out}"
    )
    assert "\t" not in out, (
        f"Expected the cat -n tab gutter to be stripped before highlighting. Got:\n{out}"
    )


def _compact(text: str) -> str:
    """Drop all whitespace so word-wrap/line-folding can't split a marker token."""
    return re.sub(r"\s+", "", text)


def _long_marked(head: str, middle: str, tail: str) -> str:
    """A >4k string whose center marker is guaranteed cut by a 500-char shorten."""
    return f"{head}_" + ("A" * 2000) + f"_{middle}_" + ("Z" * 2000) + f"_{tail}"


def test_colored_read_output_is_shortened_with_tool_short(tmp_path, monkeypatch):
    """`-t:s` must shorten a Read result body in the colored view, not just plain.

    Regression: the colored renderer highlights a Read result from the raw
    `output_text` field, which was left un-shortened while only the fenced
    `content` string got truncated — so `--color=always` leaked the full file.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    read_output = _long_marked("READHEAD", "READMIDDLE", "READTAIL")
    sid = _write_claude_session(
        home, "bbbbbbbb-aaaa-bbbb-cccc-000000000001",
        [
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0r", "name": "Read",
                 "input": {"file_path": "/tmp/snippet.py"}},
            ]),
            _user([{"type": "tool_result", "tool_use_id": "toolu_0r",
                    "content": read_output}]),
        ],
    )

    out = _compact(_render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False,
                          show_tools=[ToolFilter(short=True)]),
        sid, None, None, output_format="xml", emit_metadata=False,
    ))

    assert "READHEAD" in out, f"Expected the preserved prefix marker. Got:\n{out}"
    assert "READTAIL" in out, f"Expected the preserved suffix marker. Got:\n{out}"
    assert "READMIDDLE" not in out, (
        "The colored Read output must be shortened (middle cut) under -t:s, "
        f"just like --color=never. Got:\n{out}"
    )


def test_colored_read_output_is_shortened_with_standalone_short(tmp_path, monkeypatch):
    """Standalone `--short` (with tools shown) shortens a Read result in color too."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    read_output = _long_marked("SREADHEAD", "SREADMIDDLE", "SREADTAIL")
    sid = _write_claude_session(
        home, "bbbbbbbb-aaaa-bbbb-cccc-000000000002",
        [
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0r", "name": "Read",
                 "input": {"file_path": "/tmp/snippet.py"}},
            ]),
            _user([{"type": "tool_result", "tool_use_id": "toolu_0r",
                    "content": read_output}]),
        ],
    )

    out = _compact(_render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False,
                          show_tools=True, shorten=True),
        sid, None, None, output_format="xml", emit_metadata=False,
    ))

    assert "SREADHEAD" in out and "SREADTAIL" in out, (
        f"Expected the preserved prefix/suffix markers. Got:\n{out}"
    )
    assert "SREADMIDDLE" not in out, (
        f"Standalone --short must shorten the colored Read output. Got:\n{out}"
    )


def test_colored_read_output_is_shortened_with_scoped_spec(tmp_path, monkeypatch):
    """A scoped `-t Read:o:s` shortens the colored Read result it targets."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    read_output = _long_marked("XREADHEAD", "XREADMIDDLE", "XREADTAIL")
    sid = _write_claude_session(
        home, "bbbbbbbb-aaaa-bbbb-cccc-000000000003",
        [
            _assistant(content=[
                {"type": "tool_use", "id": "toolu_0r", "name": "Read",
                 "input": {"file_path": "/tmp/snippet.py"}},
            ]),
            _user([{"type": "tool_result", "tool_use_id": "toolu_0r",
                    "content": read_output}]),
        ],
    )

    out = _compact(_render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(
            color="always", paging=False,
            show_tools=[ToolFilter(name="Read", direction="output", short=True)],
        ),
        sid, None, None, output_format="xml", emit_metadata=False,
    ))

    assert "XREADHEAD" in out and "XREADTAIL" in out, (
        f"Expected the preserved prefix/suffix markers. Got:\n{out}"
    )
    assert "XREADMIDDLE" not in out, (
        f"`-t Read:o:s` must shorten the colored Read output. Got:\n{out}"
    )


def test_colored_edit_diff_is_shortened_with_tool_short(tmp_path, monkeypatch):
    """`-t:s` must shorten an Edit's diff in the colored view.

    The colored Edit renderer builds its diff from the raw `input_data`
    (old_string/new_string), which was left un-shortened alongside `content`.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    old_string = _long_marked("OLDHEAD", "OLDMIDDLE", "OLDTAIL")
    new_string = _long_marked("NEWHEAD", "NEWMIDDLE", "NEWTAIL")
    sid = _write_claude_session(
        home, "bbbbbbbb-aaaa-bbbb-cccc-000000000004",
        [_assistant(content=[
            {"type": "tool_use", "id": "toolu_0e", "name": "Edit",
             "input": {"file_path": "/tmp/a.py",
                       "old_string": old_string, "new_string": new_string}},
        ])],
    )

    out = _compact(_render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False,
                          show_tools=[ToolFilter(short=True)]),
        sid, None, None, output_format="xml", emit_metadata=False,
    ))

    assert "OLDHEAD" in out and "NEWHEAD" in out, (
        f"Expected the preserved diff prefixes. Got:\n{out}"
    )
    assert "OLDMIDDLE" not in out and "NEWMIDDLE" not in out, (
        "The colored Edit diff must be shortened (old/new middles cut) under -t:s. "
        f"Got:\n{out}"
    )


def test_colored_bash_body_stays_shortened(tmp_path, monkeypatch):
    """Control: Bash (generic content path) was and stays shortened in color."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    command = _long_marked("BASHHEAD", "BASHMIDDLE", "BASHTAIL")
    sid = _write_claude_session(
        home, "bbbbbbbb-aaaa-bbbb-cccc-000000000005",
        [_assistant(content=[
            {"type": "tool_use", "id": "toolu_0b", "name": "Bash",
             "input": {"command": command}},
        ])],
    )

    out = _compact(_render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False,
                          show_tools=[ToolFilter(short=True)]),
        sid, None, None, output_format="xml", emit_metadata=False,
    ))

    assert "BASHHEAD" in out and "BASHTAIL" in out, (
        f"Expected the preserved Bash markers. Got:\n{out}"
    )
    assert "BASHMIDDLE" not in out, (
        f"Bash content was already shortened in color and must stay so. Got:\n{out}"
    )


def test_thinking_is_detagged(tmp_path, monkeypatch):
    """Thinking renders under a ✻ marker, not <thinking> tags."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "66666666-aaaa-bbbb-cccc-000000000001",
        [_assistant(content=[
            {"type": "thinking", "thinking": "weighing the options"},
            {"type": "text", "text": "Here is the answer."},
        ])],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False, show_thinking=True),
        sid, None, None, output_format="xml", emit_metadata=False,
    )

    assert "✻ thinking" in out, f"Expected the ✻ thinking marker. Got:\n{out}"
    assert "weighing the options" in out, f"Expected thinking text. Got:\n{out}"
    assert "<thinking>" not in out, f"Thinking must be tag-free in color. Got:\n{out}"


def test_colored_text_preserves_attributed_xml_tags(tmp_path, monkeypatch):
    """Tag-like text with attributes survives the colored view, not stripped by Markdown.

    Message text is escaped before Markdown so XML/HTML-like tags render literally.
    A bare tag (<thinking>) was already escaped, but an attributed tag like
    <div class="box"> slipped past the guard and Markdown silently dropped it.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "aaaaaaaa-aaaa-bbbb-cccc-000000000001",
        [_assistant(text='Wrap it in <div class="box"> please.')],
    )

    out = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False), sid, None, None,
        output_format="xml", emit_metadata=False,
    )

    assert '<div class="box">' in out, (
        f"An attributed XML-like tag in message text must survive the colored view "
        f"(escaped, rendered literally), not be stripped by Markdown. Got:\n{out}"
    )


def test_role_colors_are_preserved(tmp_path, monkeypatch):
    """Each message type keeps its hue: assistant magenta, user blue."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "77777777-aaaa-bbbb-cccc-000000000001",
        [_assistant(text="reply"), _user("ask")],
    )

    styled = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False),
        sid, None, None, output_format="xml", emit_metadata=False, styles=True,
    )

    assert "38;2;200;139;218" in styled, (
        f"Expected assistant magenta (#c88bda) on its panel. Got:\n{styled}"
    )
    assert "38;2;113;185;244" in styled, (
        f"Expected user blue (#71b9f4) on its panel. Got:\n{styled}"
    )


def test_compaction_message_has_its_own_badge_and_hue(tmp_path, monkeypatch):
    """A compaction summary renders a 'Compaction' badge in its own amber hue."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    sid = _write_claude_session(
        home, "77777777-aaaa-bbbb-cccc-000000000002",
        [{"type": "user", "isCompactSummary": True, "timestamp": "2026-06-16T11:01:00Z",
          "cwd": "/tmp/proj",
          "message": {"role": "user", "content": "Summary of the prior conversation."}}],
    )

    styled = _render_colored(
        monkeypatch, cmd_parse,
        ConversationFlags(color="always", paging=False),
        sid, None, None, output_format="xml", emit_metadata=False, styles=True,
    )

    assert "Compaction" in styled, (
        f"Expected the compaction badge to read 'Compaction'. Got:\n{styled}"
    )
    assert "User" not in styled, (
        f"A compaction message must not be labeled 'User'. Got:\n{styled}"
    )
    assert "38;2;234;199;134" in styled, (
        f"Expected the compaction amber hue (#eac786) on its panel. Got:\n{styled}"
    )


def test_colored_search_banner_leads_with_title(tmp_path, monkeypatch):
    """A colored search hit is framed by a banner showing the custom title + full id."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_id = "88888888-aaaa-bbbb-cccc-000000000001"
    _write_claude_session(
        home, session_id,
        [
            {"type": "custom-title", "customTitle": "My Special Title",
             "sessionId": session_id},
            _assistant(text="the needle is in this message"),
        ],
    )

    out = _render_colored(
        monkeypatch, cmd_search, "needle",
        ConversationFlags(color="always", paging=False),
        output_mode=SearchOutputMode.FULL,
    )

    assert "My Special Title" in out, (
        f"Expected the banner to lead with the custom title, not the UUID. Got:\n{out}"
    )
    first_line = out.splitlines()[0]
    assert session_id in first_line, (
        f"Expected the search banner to restate the full session id. Got:\n{out}"
    )


def test_colored_search_highlights_matched_term(tmp_path, monkeypatch):
    """The matched term is highlighted (amber) in the rendered body."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_claude_session(
        home, "99999999-aaaa-bbbb-cccc-000000000001",
        [_assistant(text="the needle is in this message")],
    )

    styled = _render_colored(
        monkeypatch, cmd_search, "needle",
        ConversationFlags(color="always", paging=False),
        output_mode=SearchOutputMode.MATCHES, styles=True,
    )

    assert "needle" in styled, f"Expected the matched term in output. Got:\n{styled}"
    assert "48;2;230;180;80" in styled, (
        f"Expected the amber match-highlight background (#e6b450). Got:\n{styled}"
    )


@pytest.mark.parametrize("module_name", [
    "chats.model",
    "chats.utils",
    "chats.search_query",
    "chats.parsing",
    "chats.murmurs",
    "chats.commands.name",
    "chats.commands.resolve",
])
def test_module_doctests(module_name):
    """Run the dormant module doctests so the suite covers those pure functions."""
    module = importlib.import_module(module_name)
    results = doctest.testmod(module, verbose=False)
    assert results.attempted > 0, (
        f"Expected {module_name} to have doctests; found none."
    )
    assert results.failed == 0, (
        f"{module_name}: {results.failed} of {results.attempted} doctest(s) failed."
    )
