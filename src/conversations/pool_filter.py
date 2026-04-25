"""Shared session-pool narrowing filter used by `parse` and `search`.

A `PoolFilter` is a declarative bundle of options that narrow the supported-
session universe before resolution or search:

  - `provider`  — restrict to one of: claude, pi, codex
  - `dir`       — restrict to sessions whose cwd is under this directory
  - `mafter`    — only sessions modified after DATE
  - `cafter`    — only sessions created after DATE

Both subcommands share the same flag definitions via `add_pool_filter_args`
and resolve them through `PoolFilter.from_args`. The filter then exposes
small predicates the call sites compose into their own pipelines.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path

from .date_filters import parse_date_filter
from .model import ConversationMetadata, Provider
from .parsing import extract_cwd_from_jsonl
from .session_pool import SessionPool


@dataclass(frozen=True)
class PoolFilter:
    """Narrows the supported-session universe by provider, dir, and date."""

    provider: Provider | None = None
    dir: str | None = None
    mafter: str | None = None
    cafter: str | None = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "PoolFilter":
        return cls(
            provider=getattr(args, "provider", None),
            dir=getattr(args, "dir", None),
            mafter=getattr(args, "mafter", None),
            cafter=getattr(args, "cafter", None),
        )

    def is_empty(self) -> bool:
        return not (self.provider or self.dir or self.mafter or self.cafter)

    @cached_property
    def mafter_dt(self) -> datetime | None:
        return parse_date_filter(self.mafter)

    @cached_property
    def cafter_dt(self) -> datetime | None:
        return parse_date_filter(self.cafter)

    def candidate_files(self, pool: SessionPool) -> list[Path]:
        """Cheap pre-filter using only the pool's provider partition."""
        if self.provider is not None:
            return list(pool.by_provider[self.provider])
        return list(pool.files)

    def passes_metadata(self, meta: ConversationMetadata) -> bool:
        """Check loaded metadata against date filters."""
        if self.mafter_dt and (not meta.mtime or meta.mtime < self.mafter_dt):
            return False
        if self.cafter_dt and (not meta.ctime or meta.ctime < self.cafter_dt):
            return False
        return True

    def passes_cwd(self, cwd: str | None) -> bool:
        """Check a session's cwd against the dir filter."""
        if self.dir is None:
            return True
        if cwd is None:
            return False
        try:
            Path(cwd).resolve().relative_to(Path(self.dir).resolve())
            return True
        except ValueError:
            return False

    def needs_content_for_dir(self) -> bool:
        return self.dir is not None

    def passes_path_for_index(self, path: Path) -> bool:
        """Apply dir filter to a candidate path for index resolution.

        Reads the file content only when a dir filter is present.
        Date filters are applied separately via `passes_metadata`.
        """
        if not self.needs_content_for_dir():
            return True
        try:
            cwd = extract_cwd_from_jsonl(path.read_text(encoding="utf-8"))
        except OSError:
            return False
        return self.passes_cwd(cwd)

    def narrow_for_index(self, paths: Iterable[Path]) -> list[Path]:
        """Apply dir filter to an already metadata-filtered candidate list."""
        return [p for p in paths if self.passes_path_for_index(p)]


def add_pool_filter_args(
    parser: argparse.ArgumentParser,
    *,
    provider_help: str = "Restrict to sessions from a specific provider (claude, pi, codex)",
    dir_help: str = "Restrict to sessions whose cwd is under this directory",
    mafter_help: str = "Only sessions modified after DATE (e.g., 2024-12-15, 1d, 2w)",
    cafter_help: str = "Only sessions created after DATE",
) -> None:
    """Install the shared session-pool narrowing flags on a parser."""
    group = parser.add_argument_group("session pool filters")
    group.add_argument("-d", "--dir", type=str, default=None, help=dir_help)
    group.add_argument(
        "-ma", "--mafter", type=str, default=None, metavar="DATE", help=mafter_help
    )
    group.add_argument(
        "-ca", "--cafter", type=str, default=None, metavar="DATE", help=cafter_help
    )
    group.add_argument(
        "-p",
        "--provider",
        choices=["claude", "pi", "codex"],
        default=None,
        help=provider_help,
    )
