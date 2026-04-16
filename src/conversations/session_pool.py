from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from .model import Provider
from .parsing import (
    find_all_supported_session_files,
    get_jsonl_session_adapter,
    get_native_session_id,
)


def _safe_stat_mtime(session_file: Path) -> float:
    """Return filesystem mtime, falling back to the oldest sortable value."""
    try:
        return session_file.stat().st_mtime
    except OSError:
        return float("-inf")


@dataclass(frozen=True)
class SessionPool:
    """Unified supported-session inventory for one CLI invocation."""

    files: tuple[Path, ...]
    by_provider: dict[Provider, tuple[Path, ...]]
    by_stem: dict[str, Path]
    by_filename: dict[str, Path]
    stat_mtime_sorted: tuple[Path, ...]

    @classmethod
    def discover(cls, *, include_sidechains: bool = True) -> SessionPool:
        """Build a pool from the current supported-session universe."""
        return cls.from_files(
            find_all_supported_session_files(include_sidechains=include_sidechains)
        )

    @classmethod
    def from_files(cls, files: Sequence[Path]) -> SessionPool:
        """Build a pool from a known supported-session sequence."""
        normalized_files = tuple(files)
        provider_groups: dict[Provider, list[Path]] = {
            "claude": [],
            "pi": [],
            "codex": [],
        }
        by_stem: dict[str, Path] = {}
        by_filename: dict[str, Path] = {}

        for session_file in normalized_files:
            provider = get_jsonl_session_adapter(session_file).name
            provider_groups[provider].append(session_file)
            by_stem[session_file.stem] = session_file
            by_filename[session_file.name] = session_file

        return cls(
            files=normalized_files,
            by_provider={
                provider: tuple(provider_groups[provider])
                for provider in ("claude", "pi", "codex")
            },
            by_stem=by_stem,
            by_filename=by_filename,
            stat_mtime_sorted=tuple(sorted(normalized_files, key=_safe_stat_mtime)),
        )

    def resolve_exact_identifier(self, identifier: str) -> Path | None:
        """Resolve a single-token identifier from the unified pool."""
        if len(identifier.split()) != 1:
            return None

        if session_file := self.by_stem.get(identifier):
            return session_file

        if session_file := self.by_filename.get(identifier):
            return session_file

        for session_file in self.files:
            if identifier not in session_file.stem:
                continue
            if get_native_session_id(session_file) == identifier:
                return session_file

        for session_file in self.files:
            if get_native_session_id(session_file) == identifier:
                return session_file

        return None
