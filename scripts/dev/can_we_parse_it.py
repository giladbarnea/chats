#!/usr/bin/env python3.12
"""
Iterative message model discovery for Claude conversation files.
Accepts a JSON string from stdin and attempts to parse it into a dataclass. Prints if fails.
Usage:
for i in {0..$(jq length /path/to/messages.jsonl)}; do
  python3 scripts/dev/truncate_json_strings.py /path/to/messages.jsonl | jq -s ".[$i]" | python3.12 scripts/dev/can_we_parse_it.py || break
done
"""

import json
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class SnapshotData:
    messageId: str
    trackedFileBackups: dict[str, Any]
    timestamp: str


@dataclass
class FileHistorySnapshot:
    type: str
    messageId: str
    snapshot: SnapshotData
    isSnapshotUpdate: bool

    def __post_init__(self):
        # From JSON, snapshot is always a dict. Convert to dataclass.
        self.snapshot = SnapshotData(**self.snapshot)


@dataclass
class HookProgressData:
    type: str  # "hook_progress"
    hookEvent: str
    hookName: str
    command: str


@dataclass
class BashProgressData:
    type: str  # "bash_progress"
    output: str
    fullOutput: str
    elapsedTimeSeconds: int
    totalLines: int


@dataclass
class ProgressMessage:
    type: str  # "progress"
    data: dict[str, Any]  # Can be different progress data types
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str
    toolUseID: str
    timestamp: str
    uuid: str
    parentToolUseID: str | None = None
    slug: str | None = None

    def __post_init__(self):
        # Parse data based on its type field
        data_type = self.data.get("type")
        if data_type == "hook_progress":
            self.data = HookProgressData(**self.data)
        elif data_type == "bash_progress":
            self.data = BashProgressData(**self.data)
        raise ValueError(f"Unknown progress type: {data_type}")


@dataclass
class MessageContent:
    role: str  # "user" or "assistant"
    content: str | list  # Can be string or list


@dataclass
class ThinkingMetadata:
    maxThinkingTokens: int


@dataclass
class UsageInfo:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation: dict[str, int] | None = None
    service_tier: str | None = None


@dataclass
class AssistantMessageContent:
    model: str
    id: str
    type: str  # "message"
    role: str  # "assistant"
    content: list  # List of content blocks
    stop_reason: str | None
    stop_sequence: str | None
    usage: UsageInfo

    def __post_init__(self):
        # From JSON, usage is always a dict. Convert to dataclass.
        self.usage = UsageInfo(**self.usage)


@dataclass
class BashToolUseResult:
    stdout: str
    stderr: str
    interrupted: bool
    isImage: bool


@dataclass
class GrepToolUseResult:
    mode: str
    filenames: list
    numFiles: int


@dataclass
class FileToolUseResult:
    type: str
    file: str


@dataclass
class UserMessage:
    """Base user message - handles all fields without toolUseResult"""

    type: str  # "user"
    message: MessageContent
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str
    uuid: str
    timestamp: str
    # Optional fields
    slug: str | None = None
    thinkingMetadata: ThinkingMetadata | None = None
    todos: list | None = None
    permissionMode: str | None = None

    def __post_init__(self):
        # From JSON, message is always a dict. Convert to dataclass.
        self.message = MessageContent(**self.message)
        # thinkingMetadata is optional but if present, it's a dict.
        if self.thinkingMetadata:
            self.thinkingMetadata = ThinkingMetadata(**self.thinkingMetadata)


@dataclass
class UserMessageWithBashResult(UserMessage):
    """User message with Bash tool result"""

    toolUseResult: BashToolUseResult | None = None
    sourceToolAssistantUUID: str | None = None

    def __post_init__(self):
        super().__post_init__()
        # toolUseResult is optional but if present, it's a dict.
        if self.toolUseResult:
            self.toolUseResult = BashToolUseResult(**self.toolUseResult)


@dataclass
class UserMessageWithGrepResult(UserMessage):
    """User message with Grep tool result"""

    toolUseResult: GrepToolUseResult | None = None
    sourceToolAssistantUUID: str | None = None

    def __post_init__(self):
        super().__post_init__()
        if self.toolUseResult:
            self.toolUseResult = GrepToolUseResult(**self.toolUseResult)


@dataclass
class UserMessageWithFileResult(UserMessage):
    """User message with File tool result"""

    toolUseResult: FileToolUseResult | None = None
    sourceToolAssistantUUID: str | None = None

    def __post_init__(self):
        super().__post_init__()
        if self.toolUseResult:
            self.toolUseResult = FileToolUseResult(**self.toolUseResult)


@dataclass
class AssistantMessage:
    type: str  # "assistant"
    message: AssistantMessageContent
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str
    requestId: str
    uuid: str
    timestamp: str
    slug: str | None = None

    def __post_init__(self):
        # From JSON, message is always a dict. Convert to dataclass.
        self.message = AssistantMessageContent(**self.message)


@dataclass
class SystemMessage:
    type: str  # "system"
    subtype: str  # e.g., "turn_duration"
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str
    slug: str
    durationMs: int
    timestamp: str
    uuid: str
    isMeta: bool


@dataclass
class CustomTitle:
    type: str  # "custom-title"
    customTitle: str
    sessionId: str


# Registry of all models to try
# Order matters: try more specific variants before base classes
MODELS = [
    FileHistorySnapshot,
    ProgressMessage,
    UserMessageWithBashResult,
    UserMessageWithGrepResult,
    UserMessageWithFileResult,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    CustomTitle,
]


def main(data: dict) -> None:
    success = False
    for model_cls in MODELS:
        try:
            model_cls(**data)
            success = True
            break
        except Exception:
            pass  # Silent failure, keep trying

    if not success:
        print(f"⚠️  NO MODEL MATCHED for data.type: {data.get('type', 'UNKNOWN')}")
        print(f"Keys: {list(data.keys())}")
        print("Each key's type:")
        for k, v in data.items():
            print(f"  {k}: {type(v).__name__}")
        sys.exit(1)


if __name__ == "__main__":
    data = json.loads(sys.stdin.read())
    main(data)
