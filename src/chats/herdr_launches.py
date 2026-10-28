"""Proven fork launches from successful Herdr command/result pairs."""

import json
from collections.abc import Iterable
from pathlib import PurePosixPath


def _herdr_action(command: str) -> tuple[str, str] | None:
    """Accept one plain Herdr invocation, optionally inside an exact zshi wrapper.

    >>> _herdr_action("zshi -c 'herdr agent get reviewer'")
    ('get', 'reviewer')
    >>> _herdr_action("herdr agent get reviewer; printf fake") is None
    True
    """
    command = command.strip()
    for quote in ("'", '"'):
        prefix = f"zshi -c {quote}"
        if command.startswith(prefix) and command.endswith(quote):
            command = command[len(prefix):-1]
            break
    if any(character in command for character in "'\"`;$&|<>\\(){}*?[]\n\r"):
        return None
    arguments = command.split()
    if len(arguments) < 4 or arguments[:2] != ["herdr", "agent"] or arguments[2] not in {"start", "get"}:
        return None
    return arguments[2], arguments[3]


def _fork_source(arguments: list[str], provider: str) -> str | None:
    """Read a context source from Herdr's canonical launch argv, never from shell prose.

    >>> _fork_source(["/usr/bin/codex", "fork", "parent", "--model", "model"], "codex")
    'parent'
    >>> _fork_source(["codex", "exec", "fork", "parent"], "codex")
    'parent'
    >>> _fork_source(["claude", "--fork-session", "--resume", "parent"], "claude")
    'parent'
    >>> _fork_source(["codex", "resume", "parent"], "codex") is None
    True
    """
    if not arguments or PurePosixPath(arguments[0]).name != provider:
        return None
    if provider == "claude":
        if "--fork-session" not in arguments:
            return None
        return next((value for flag, value in zip(arguments, arguments[1:]) if flag in {"--resume", "-r"} and not value.startswith("-")), None)
    command = arguments[1:]
    if command[:1] == ["exec"]:
        command = command[1:]
    if provider != "codex" or len(command) < 2 or command[0] != "fork" or command[1].startswith("-"):
        return None
    return command[1]


def verified_herdr_forks(commands: Iterable[tuple[str, str]], provider: str) -> list[tuple[str, str]]:
    """Join successful starts to exact terminal identities; return (child, context source).

    Callers supply only successful executed command/results owned by the launching
    session, then validate the returned IDs against child headers. Copied receipts,
    failed tools and arbitrary shell programs must not be supplied as proof.

    >>> verified_herdr_forks([], "codex")
    []
    """
    starts: dict[str, str] = {}
    launches: list[tuple[str, str]] = []
    for command, output in commands:
        action = _herdr_action(command)
        if not action:
            continue
        try:
            receipt = json.loads(output)
        except json.JSONDecodeError:
            continue
        if not isinstance(receipt, dict) or receipt.get("id") != f"cli:agent:{action[0]}":
            continue
        result = receipt.get("result", {})
        agent = result.get("agent", {})
        terminal = agent.get("terminal_id")
        if not terminal or action[1] not in {agent.get("name"), agent.get("pane_id"), terminal}:
            continue
        if result.get("type") == "agent_started" and action[0] == "start":
            starts.pop(terminal, None)
            source = _fork_source(result.get("argv", []), provider)
            starts.update({terminal: source} if source else {})
        identity = agent.get("agent_session", {})
        if result.get("type") not in {"agent_started", "agent_info"}:
            continue
        if identity.get("agent") != provider or identity.get("kind") != "id":
            continue
        child = identity.get("value")
        if child and terminal in starts:
            launches.append((child, starts.pop(terminal)))
    return launches
