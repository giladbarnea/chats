from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .model import PROVIDERS, Provider
from .parsing import (
    _discover_session_file_rows,
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
        rows = [
            (
                session_file,
                native_provider
                or get_jsonl_session_adapter(session_file).name,
                stat_mtime,
            )
            for session_file, native_provider, stat_mtime in _discover_session_file_rows(
                include_sidechains=include_sidechains
            )
        ]
        return cls._from_rows(rows)

    @classmethod
    def from_files(cls, files: Sequence[Path]) -> SessionPool:
        """Build a pool from a known supported-session sequence."""
        return cls._from_rows([
            (
                session_file,
                get_jsonl_session_adapter(session_file).name,
                _safe_stat_mtime(session_file),
            )
            for session_file in files
        ])

    @classmethod
    def _from_rows(
        cls,
        rows: Sequence[tuple[Path, Provider, float]],
    ) -> SessionPool:
        """Build every pool projection from ordered provider and stat rows."""
        provider_groups: dict[Provider, list[Path]] = {
            provider: [] for provider in PROVIDERS
        }
        by_stem: dict[str, Path] = {}
        by_filename: dict[str, Path] = {}

        for session_file, provider, _stat_mtime in rows:
            provider_groups[provider].append(session_file)
            by_stem[session_file.stem] = session_file
            by_filename[session_file.name] = session_file

        return cls(
            files=tuple(session_file for session_file, _provider, _mtime in rows),
            by_provider={
                provider: tuple(provider_groups[provider]) for provider in PROVIDERS
            },
            by_stem=by_stem,
            by_filename=by_filename,
            stat_mtime_sorted=tuple(
                session_file
                for session_file, _provider, _mtime in sorted(
                    rows,
                    key=lambda row: row[2],
                )
            ),
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
