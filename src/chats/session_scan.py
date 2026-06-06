from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model import ConversationFlags, Message, Provider
from .parsing import (
    decode_jsonl_entries,
    detect_format,
    extract_cwd_from_entries,
    extract_latest_custom_title_from_entries,
    extract_summaries_from_entries,
    get_jsonl_session_adapter,
    parse_jsonl_entries,
    parse_raw_cli_transcript,
)


@dataclass(frozen=True)
class SessionScan:
    """One-pass per-file search facets and visible messages."""

    provider: Provider | None
    cwd: str | None
    summaries: tuple[str, ...]
    custom_title: str | None
    messages: tuple[Message, ...]

    @classmethod
    def from_file(cls, session_file: Path, flags: ConversationFlags) -> SessionScan:
        """Read and scan one session file once."""
        content = session_file.read_text(encoding="utf-8")
        return cls.from_content(content, flags, source_path=session_file)

    @classmethod
    def from_content(
        cls,
        content: str,
        flags: ConversationFlags,
        *,
        source_path: Path | None = None,
    ) -> SessionScan:
        """Scan content into search facets and visible messages."""
        if detect_format(content) != "jsonl":
            return cls(
                provider=None,
                cwd=None,
                summaries=(),
                custom_title=None,
                messages=tuple(parse_raw_cli_transcript(content, flags)),
            )

        entries = decode_jsonl_entries(content)
        provider = (
            get_jsonl_session_adapter(source_path).name
            if source_path is not None
            else None
        )
        return cls(
            provider=provider,
            cwd=extract_cwd_from_entries(entries),
            summaries=tuple(extract_summaries_from_entries(entries)),
            custom_title=extract_latest_custom_title_from_entries(entries),
            messages=tuple(
                parse_jsonl_entries(entries, flags, source_path=source_path)
            ),
        )
