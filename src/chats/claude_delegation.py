"""Attribute delivered Claude agent results to their recorded dispatches."""

import re
from dataclasses import dataclass

from .model import Message
from .registry import ContentBlockType


@dataclass(frozen=True)
class AgentOrigins:
    calls: frozenset[str]
    tasks: frozenset[str]
    user_forks: frozenset[tuple[str, str]]


def agent_origins(entries: list[dict]) -> AgentOrigins:
    """Collect Agent call ids, returned child ids, and native user-fork launch receipts.

    >>> agent_origins([])
    AgentOrigins(calls=frozenset(), tasks=frozenset(), user_forks=frozenset())
    """
    calls = frozenset(
        block["id"]
        for entry in entries if entry.get("type") == "assistant"
        and isinstance(content := (entry.get("message") or {}).get("content"), list)
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use"
        and block.get("name") == "Agent" and block.get("id")
    )
    tasks = set()
    user_forks = set()
    pending = False
    for entry in entries:
        result = entry.get("toolUseResult")
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user" and isinstance(result, dict) and isinstance(content, list):
            linked = any(isinstance(block, dict) and block.get("type") == "tool_result"
                         and block.get("tool_use_id") in calls and not block.get("is_error") for block in content)
            if linked and result.get("agentId"):
                tasks.add(result["agentId"])
        if entry.get("type") != "system" or entry.get("subtype") != "local_command":
            continue
        command = entry.get("content", "")
        if "<command-name>" in command:
            pending = any(f"<command-name>{name}</command-name>" in command for name in ("/subtask", "/btw", "/fork"))
            continue
        match = re.fullmatch(r"<local-command-stdout>⑂ forked (.+) \(([0-9a-f]{4})\)</local-command-stdout>", command)
        if pending and match:
            user_forks.add((match[1], match[2]))
        pending = False
    return AgentOrigins(calls, frozenset(tasks), frozenset(user_forks))


def _field(body: str, name: str) -> str:
    """Read one native notification field without interpreting its result text as XML.

    >>> _field('<result>hello</result>', 'result')
    'hello'
    """
    _, opening, tail = body.partition(f"<{name}>")
    value, closing, _ = tail.partition(f"</{name}>")
    return value.strip() if opening and closing else ""


def notification_messages(entry: dict, origins: AgentOrigins) -> list[Message]:
    """Keep delivered agent reports with dispatch proof; shell tasks and pasted examples do not qualify.

    >>> notification_messages({}, agent_origins([]))
    []
    """
    content = (entry.get("message") or {}).get("content")
    if (entry.get("origin") or {}).get("kind") != "task-notification" or not isinstance(content, str):
        return []
    messages = []
    for match in re.finditer(r"<task-notification>(.*?)</task-notification>", content, re.DOTALL):
        body = match[1]
        task = _field(body, "task-id")
        slug, _, suffix = task.removeprefix("a").rpartition("-")
        proven = (_field(body, "tool-use-id") in origins.calls or task in origins.tasks
                  or (slug, suffix[-4:]) in origins.user_forks)
        text = _field(body, "result") or _field(body, "summary")
        if proven and task and text:
            messages.append(Message(role="agent", agent_id=task, text=text,
                                    timestamp=entry.get("timestamp"), status=_field(body, "status") or None,
                                    wrapper_type=ContentBlockType.AGENT))
    return messages
