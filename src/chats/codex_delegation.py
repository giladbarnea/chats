"""Codex delegation provenance beyond ordinary subagent headers."""

from collections.abc import Iterable

from .herdr_launches import verified_herdr_forks


def delegated_parent(header: dict) -> str | None:
    """Read a spawner, not an ordinary fork's context source.

    >>> delegated_parent({"parent_thread_id": "parent"})
    'parent'
    >>> delegated_parent({"thread_source": "agent_forked_thread", "forked_from_id": "parent"})
    'parent'
    >>> delegated_parent({"thread_source": "user", "forked_from_id": "parent"}) is None
    True
    """
    if header.get("thread_source") == "agent_forked_thread":
        return header.get("forked_from_id")
    return header.get("parent_thread_id")


def verified_cli_forks(entries: Iterable[dict], writer: str) -> list[tuple[str, str]]:
    """Join successful Herdr execution events owned by this thread, not inherited events.

    >>> verified_cli_forks([], "parent")
    []
    """
    commands: list[tuple[str, str]] = []
    for entry in entries:
        payload = entry.get("payload", {})
        if entry.get("type") != "event_msg" or payload.get("thread_id") != writer:
            continue
        item = payload.get("item", {})
        if payload.get("type") != "item_completed" or item.get("type") != "CommandExecution":
            continue
        if item.get("status") != "completed" or item.get("exit_code") != 0:
            continue
        command = item.get("command", [])
        if command:
            commands.append((command[-1], item.get("aggregated_output", "")))
    return verified_herdr_forks(commands, "codex")
