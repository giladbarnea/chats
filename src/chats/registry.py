from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class ContentBlockInfo(NamedTuple):
    """Configuration for an XML content block type."""

    xml_tag: str
    header: str | None  # None for inner blocks (thinking, tools)


class ContentBlockType(Enum):
    """All XML content block types the system outputs."""

    # Message wrappers (outer)
    USER_MESSAGE = ContentBlockInfo("user-message", "## User")
    USER_COMMAND_INPUT = ContentBlockInfo(
        "user-command-input", "## User Command Input"
    )
    USER_COMMAND_OUTPUT = ContentBlockInfo(
        "user-command-output", "## User Command Output"
    )
    RECAP = ContentBlockInfo("recap", "## Recap")
    COMPACTION = ContentBlockInfo("compaction", "## Compaction")
    ASSISTANT_RESPONSE = ContentBlockInfo("assistant-response", "## Assistant")
    AGENT = ContentBlockInfo("agent", "## Agent")
    CUSTOM = ContentBlockInfo("custom", "## Custom")
    SESSION_RENAME = ContentBlockInfo("session-rename", "## Renamed Session")

    # Content blocks (inner)
    THINKING = ContentBlockInfo("thinking", None)
    TOOL_INPUT = ContentBlockInfo("tool-input", None)
    TOOL_OUTPUT = ContentBlockInfo("tool-output", None)
    SUBAGENT_TASK = ContentBlockInfo("subagent-task", None)


class ToolSchema(NamedTuple):
    """How to format a specific tool's input for XML output."""

    attr_keys: list[str]  # Keys to extract as XML attributes
    content_key: str | None  # Key for content body (None = no content)
    content_lang: str | None  # Language for code fence (None = no fence)


# Tool-specific formatting schemas. Adding a new tool = adding an entry here.
TOOL_SCHEMAS: dict[str, ToolSchema] = {
    "Bash": ToolSchema(
        ["workdir", "yield_time_ms", "max_output_tokens"],
        "command",
        "sh",
    ),
    "Read": ToolSchema(["file_path"], None, None),
    "Glob": ToolSchema(["pattern", "path"], None, None),
    "Grep": ToolSchema(["pattern", "path", "glob", "type", "output_mode"], None, None),
    "Write": ToolSchema(["file_path"], "content", None),
    "Edit": ToolSchema(
        ["file_path"], None, None
    ),  # old_string/new_string handled separately
    "Skill": ToolSchema(["skill", "location", "args"], None, None),
    "Task": ToolSchema(["subagent_type", "model"], "prompt", None),
    "WebFetch": ToolSchema(["url"], "prompt", None),
    "WebSearch": ToolSchema(["query"], None, None),
    "Patch": ToolSchema([], "input", "diff"),
    "TaskNotification": ToolSchema(
        ["tool_use_id", "status", "summary"],
        "result",
        None,
    ),
    "AdditionalContext": ToolSchema(["hook_name"], "content", None),
}


# Provider-native tool names mapped to shared canonical tool names.
TOOL_NAME_ALIASES: dict[str, dict[str, str]] = {
    "pi": {
        "bash": "Bash",
        "read": "Read",
        "write": "Write",
        "edit": "Edit",
        "grep": "Grep",
        "glob": "Glob",
        "task": "Task",
        "webfetch": "WebFetch",
        "websearch": "WebSearch",
    },
    "codex": {
        "apply_patch": "Patch",
        "exec_command": "Bash",
    },
    "antigravitycli": {
        "run_command": "Bash",
        "view_file": "Read",
        "write_to_file": "Write",
        "replace_file_content": "Edit",
        "grep_search": "Grep",
        "search_web": "WebSearch",
        "read_url_content": "WebFetch",
    },
}


# Provider-native input keys mapped to canonical schema keys after name aliasing.
TOOL_INPUT_KEY_ALIASES: dict[str, dict[str, dict[str, str]]] = {
    "claude": {
        "Read": {
            "path": "file_path",
        },
    },
    "codex": {
        "Bash": {
            "cmd": "command",
        },
    },
    "antigravitycli": {
        "Bash": {
            "Command": "command",
            "WorkingDirectory": "workdir",
            "WaitMsBeforeAsync": "yield_time_ms",
        },
        "Read": {
            "AbsolutePath": "file_path",
        },
        "Write": {
            "AbsolutePath": "file_path",
            "Content": "content",
        },
        "Edit": {
            "AbsolutePath": "file_path",
            "OldString": "old_string",
            "NewString": "new_string",
        },
        "Grep": {
            "Pattern": "pattern",
            "Path": "path",
            "IncludePattern": "glob",
        },
        "WebSearch": {
            "Query": "query",
        },
        "WebFetch": {
            "Url": "url",
            "URL": "url",
            "Prompt": "prompt",
        },
    },
}


def normalize_tool_name(provider: str, name: str | None) -> str:
    """Map a provider-native tool name to the canonical shared tool name."""
    if not name:
        return "Unknown"

    aliases = TOOL_NAME_ALIASES.get(provider, {})
    return aliases.get(name.lower(), name)


def normalize_tool_input_keys(
    provider: str,
    tool_name: str,
    input_data: dict,
) -> dict:
    """Map provider-native input keys to canonical schema keys for a tool."""
    aliases = TOOL_INPUT_KEY_ALIASES.get(provider, {}).get(tool_name, {})
    if not aliases:
        return input_data

    return {aliases.get(key, key): value for key, value in input_data.items()}
