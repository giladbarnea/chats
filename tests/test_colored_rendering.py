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
from pathlib import Path

import pytest
from rich.console import Console

import chats.console as console_mod
from chats.commands.parse import cmd_parse
from chats.commands.search import cmd_search
from chats.model import ConversationFlags, SearchOutputMode
from chats.theme import APP_THEME


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
    # diff.remove (#e06c75) and diff.add (#98c379) reach the output.
    assert "38;2;224;108;117" in styled, f"Expected red removed-line color. Got:\n{styled}"
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


def test_role_colors_are_preserved(tmp_path, monkeypatch):
    """Each message type keeps its hue: assistant violet, user blue."""
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

    assert "38;2;124;58;237" in styled, (
        f"Expected assistant violet (#7c3aed) on its panel. Got:\n{styled}"
    )
    assert "38;2;59;130;246" in styled, (
        f"Expected user blue (#3b82f6) on its panel. Got:\n{styled}"
    )


def test_colored_search_banner_leads_with_title(tmp_path, monkeypatch):
    """A colored search hit is framed by a banner showing the custom title + short id."""
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
    assert "88888888" in out, f"Expected the short id restated. Got:\n{out}"


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
    "chats.utils",
    "chats.search_query",
    "chats.parsing",
    "chats.murmurs",
    "chats.commands.rename",
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
