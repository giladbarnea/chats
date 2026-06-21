#!/usr/bin/env python3
"""Off-main-branch marking for Claude transcripts (rewind branches + compaction eras)."""

from pathlib import Path

from rich.console import Console

from chats import ConversationFlags, parse_jsonl
from chats.formatting import build_message_panels, format_to_xml
from chats.theme import APP_THEME

FIXTURE = Path(__file__).parent / "data" / "claude-branches-compaction.jsonl"
LEAF_ABOVE_TIP = Path(__file__).parent / "data" / "claude-branch-leaf-above-tip.jsonl"
ROOT_REWIND = Path(__file__).parent / "data" / "claude-branch-root-rewind.jsonl"
COMPACTED_ROOT_REWIND = (
    Path(__file__).parent / "data" / "claude-branch-compacted-root-rewind.jsonl"
)


def _parse(show_branches: bool = True):
    flags = ConversationFlags(color="never", show_branches=show_branches)
    return parse_jsonl(FIXTURE.read_text(), flags, source_path=FIXTURE)


def _by_text(messages, needle):
    matches = [m for m in messages if needle in (m.text or "")]
    assert len(matches) == 1, (
        f"Expected exactly one message containing {needle!r}, got {len(matches)}."
    )
    return matches[0]


def test_rewind_abandoned_branch_marked_off_main_branch():
    """The abandoned rewind branch is off-main even though it is DEEPER than the kept
    branch — proving resolution anchors on the active leaf, not subtree depth."""
    messages = _parse()
    abandoned1 = _by_text(messages, "era0: ABANDONED rewind branch, message 1")
    abandoned2 = _by_text(messages, "era0: ABANDONED rewind branch, message 2")
    kept = _by_text(messages, "era0: KEPT current branch message")
    pre_branch = _by_text(messages, "era0: first user message")

    assert abandoned1.off_main_branch is True, (
        "The deeper-but-abandoned rewind branch must be off the main branch."
    )
    assert abandoned2.off_main_branch is True, (
        "Every message on the abandoned branch must be off the main branch."
    )
    assert kept.off_main_branch is False, (
        "The kept branch (the active last-prompt leaf) must stay on the main branch."
    )
    assert pre_branch.off_main_branch is False, (
        "Messages before the branch point must stay on the main branch."
    )


def test_compaction_does_not_throw_off_branch_resolution():
    """A /compact boundary is not a fork: the summary and each era's main thread stay
    on-branch, while each era's abandoned rewind is still marked off."""
    messages = _parse()
    summary = _by_text(messages, "Summary of the era-0 conversation")
    era0_kept = _by_text(messages, "era0: KEPT current branch message")
    era1_kept = _by_text(messages, "era1: KEPT current branch")
    era1_abandoned = _by_text(messages, "era1: ABANDONED rewind branch")

    assert summary.off_main_branch is False, (
        "The compaction summary is an era seam on the main branch, not an abandoned branch."
    )
    assert era0_kept.off_main_branch is False, (
        "Era-0's main thread must not be marked off just because the final leaf is in era-1."
    )
    assert era1_kept.off_main_branch is False, (
        "Era-1's active branch stays on the main branch."
    )
    assert era1_abandoned.off_main_branch is True, (
        "Rewind detection must still work in the post-compaction era."
    )


def test_branch_ids_group_messages_on_the_same_detour():
    """Messages on one detour share a branch id; distinct detours differ; main has none."""
    messages = _parse()
    abandoned1 = _by_text(messages, "era0: ABANDONED rewind branch, message 1")
    abandoned2 = _by_text(messages, "era0: ABANDONED rewind branch, message 2")
    era1_abandoned = _by_text(messages, "era1: ABANDONED rewind branch")
    kept = _by_text(messages, "era0: KEPT current branch message")

    assert abandoned1.branch_id is not None, (
        "An abandoned-branch message must carry a branch id."
    )
    assert abandoned1.branch_id == abandoned2.branch_id, (
        f"Messages on one detour must share a branch id. "
        f"Got {abandoned1.branch_id!r} vs {abandoned2.branch_id!r}."
    )
    assert era1_abandoned.branch_id != abandoned1.branch_id, (
        "Distinct detours must get distinct branch ids."
    )
    assert kept.branch_id is None, "Main-thread messages must have no branch id."


def test_offbranch_messages_render_branch_attribute_in_xml():
    """Off-branch wrappers carry a `branch` attribute; main-thread wrappers do not."""
    flags = ConversationFlags(color="never", show_branches=True)
    messages = parse_jsonl(FIXTURE.read_text(), flags, source_path=FIXTURE)
    output = format_to_xml(messages, flags, {})

    wrappers = [line for line in output.splitlines() if ' i="' in line]
    assert any('branch="1"' in w for w in wrappers), (
        "Expected the first detour's wrappers to be tagged branch=\"1\". "
        f"Wrappers:\n" + "\n".join(wrappers)
    )
    main_wrappers = [w for w in wrappers if ' i="1"' in w]
    assert main_wrappers and all("branch=" not in w for w in main_wrappers), (
        f"The first (main-thread) message wrapper must not carry a branch attr. "
        f"Got: {main_wrappers}"
    )


def test_offbranch_panel_shows_fork_glyph_and_branch_id_in_color():
    """The colored per-message panel marks off-branch messages with ⑂ + the branch id."""
    flags = ConversationFlags(color="always", paging=False, show_branches=True)
    messages = parse_jsonl(FIXTURE.read_text(), flags, source_path=FIXTURE)
    console = Console(
        theme=APP_THEME, width=120, force_terminal=True,
        color_system="truecolor", record=True,
    )
    console.print(build_message_panels(messages, flags, {}))
    out = console.export_text()

    assert "⑂1" in out, (
        f"Expected the fork glyph with branch id (⑂1) on the first detour. Got:\n{out}"
    )
    assert "⑂2" in out, (
        f"Expected the second detour to be marked ⑂2. Got:\n{out}"
    )


def test_branches_hidden_by_default():
    """Without -b/--branches, abandoned-branch messages are excluded; the rest remains."""
    messages = _parse(show_branches=False)
    texts = [m.text or "" for m in messages]

    assert not any("ABANDONED" in text for text in texts), (
        f"Abandoned-branch messages must be hidden by default. Got:\n{texts}"
    )
    assert any("KEPT current branch message" in text for text in texts), (
        "Era-0 main-thread messages must remain in the default view."
    )
    assert any("Summary of the era-0 conversation" in text for text in texts), (
        "The compaction summary must remain in the default view."
    )
    assert all(m.branch_id is None for m in messages), (
        "No message in the default view should carry a branch id."
    )


def test_turns_below_the_recorded_leaf_stay_on_main_thread():
    """The reply (and further turns) below the last `last-prompt` leaf must not be hidden.

    The recorded leaf is where the most recent prompt attached; the assistant's answer
    lands below it. Resolution must follow the chosen branch down to its tip, not stop
    at the recorded leaf.
    """
    flags = ConversationFlags(color="never")  # default view: branches hidden
    messages = parse_jsonl(LEAF_ABOVE_TIP.read_text(), flags, source_path=LEAF_ABOVE_TIP)
    texts = [m.text or "" for m in messages]

    assert any("SECOND user message below the recorded leaf" in t for t in texts), (
        "The user turn below the recorded leaf must stay visible by default."
    )
    assert any("second assistant reply below the recorded leaf" in t for t in texts), (
        "The assistant reply below the recorded leaf must stay visible by default."
    )
    assert all(m.branch_id is None for m in messages), (
        "A purely linear thread has no abandoned branches to mark."
    )


def test_first_message_rewind_marks_abandoned_root_offbranch():
    """A rewind to the first message creates a second `parentUuid: null` user root; the
    abandoned attempt must be off-branch, not duplicated in the default view."""
    default = parse_jsonl(
        ROOT_REWIND.read_text(), ConversationFlags(color="never"), source_path=ROOT_REWIND
    )
    default_texts = [m.text or "" for m in default]
    assert any("KEPT real attempt" in t for t in default_texts), (
        "The kept (active-leaf) root must stay on the main branch."
    )
    assert not any("ABANDONED first attempt" in t for t in default_texts), (
        "The abandoned first-message attempt must be hidden by default, not duplicated."
    )

    with_branches = parse_jsonl(
        ROOT_REWIND.read_text(),
        ConversationFlags(color="never", show_branches=True),
        source_path=ROOT_REWIND,
    )
    abandoned = [m for m in with_branches if "ABANDONED first attempt" in (m.text or "")]
    assert abandoned and abandoned[0].branch_id is not None, (
        "With -b the abandoned attempt reappears and carries a branch id."
    )


def test_root_rewind_before_compaction_marks_abandoned_root_offbranch():
    """When the active leaf lives in a compaction era, a pre-compaction first-message
    rewind's abandoned root is still off-branch — resolved via the boundary's
    `logicalParentUuid`, which points at the real lineage."""
    messages = parse_jsonl(
        COMPACTED_ROOT_REWIND.read_text(),
        ConversationFlags(color="never"),
        source_path=COMPACTED_ROOT_REWIND,
    )
    texts = [m.text or "" for m in messages]
    assert any("REAL root attempt" in t for t in texts), "The real era-0 root must remain."
    assert any("post-compaction reply" in t for t in texts), "The post-compaction era must remain."
    assert not any("ABANDONED root attempt" in t for t in texts), (
        "The abandoned pre-compaction root must be hidden by default, not duplicated."
    )
