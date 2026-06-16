from __future__ import annotations

import subprocess
import sys

from rich.console import Console
from rich.pager import Pager

from .theme import APP_THEME


class UnicodeSafePager(Pager):
    """Page Rich output via `less -r` so wide / ambiguous-width unicode survives.

    `less` under -R (--RAW-CONTROL-CHARS) keeps screen-width tracking active and
    mis-handles glyphs like ⏺, ⎿, and box drawing. Many shells (and Python's own
    pydoc.pager backend, which Rich's default SystemPager uses) configure -R. We
    bypass both by invoking `less` directly with -r on the command line, which
    overrides any conflicting raw-mode toggle inherited via the LESS env.
    """

    def show(self, content: str) -> None:
        try:
            proc = subprocess.Popen(
                ["less", "-r"],
                stdin=subprocess.PIPE,
                errors="backslashreplace",
            )
        except FileNotFoundError:
            sys.stdout.write(content)
            return
        assert proc.stdin is not None
        with proc.stdin as pipe:
            try:
                pipe.write(content)
            except (BrokenPipeError, KeyboardInterrupt):
                pass
        proc.wait()


class StreamingPager:
    """Page Rich output that is produced incrementally, chunk by chunk.

    Unlike `Console.pager()`, which buffers every byte and only spawns the pager
    on context exit, this spawns `less -r` up front and writes each chunk the
    moment it is ready, so search results appear as they are found instead of
    after the whole pool is scanned. The write path mirrors `UnicodeSafePager`,
    so quitting `less` early (SIGPIPE) is handled identically. Falls back to
    stdout when `less` is unavailable.
    """

    def __init__(self) -> None:
        self.closed = False
        try:
            self._proc: subprocess.Popen | None = subprocess.Popen(
                ["less", "-r"],
                stdin=subprocess.PIPE,
                errors="backslashreplace",
            )
        except FileNotFoundError:
            self._proc = None

    def write(self, chunk: str) -> None:
        """Write one already-rendered chunk to the pager, flushing immediately."""
        if self.closed or not chunk:
            return
        if self._proc is None:
            sys.stdout.write(chunk)
            return
        assert self._proc.stdin is not None
        try:
            self._proc.stdin.write(chunk)
            self._proc.stdin.flush()
        except (BrokenPipeError, KeyboardInterrupt):
            self.closed = True

    def close(self) -> None:
        """Close the pager's input and wait for the user to dismiss it."""
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
        except BrokenPipeError:
            pass
        self._proc.wait()


# Module-level console instance for consistent formatting
_console: Console | None = None
_error_console: Console | None = None
_warning_console: Console | None = None


def init_module_console(*, force_color: bool | None = None) -> Console:
    global _console
    # Note: if color is acting funny, explore with/instead force_interactive
    _console = (
        Console(force_terminal=force_color, theme=APP_THEME)
        if force_color
        else Console(theme=APP_THEME)
    )
    return _console


def get_console() -> Console:
    """Get the console instance, initializing if needed."""
    global _console
    if _console is None:
        _console = Console(theme=APP_THEME)
    return _console


def print_error(*print_args) -> None:
    """Print error message to stderr in red."""
    global _error_console
    if _error_console is None:
        _error_console = Console(stderr=True)
    _error_console.print(*print_args, style="red")


def print_warning(*print_args) -> None:
    """Print warning message to stderr in yellow."""
    global _warning_console
    if _warning_console is None:
        _warning_console = Console(stderr=True)
    _warning_console.print(*print_args, style="yellow")


_hint_console: Console | None = None


def print_hint(message: str) -> None:
    """Print a low-key informational message (e.g. no results) to stderr, dimmed."""
    global _hint_console
    if _hint_console is None:
        _hint_console = Console(stderr=True, theme=APP_THEME)
    _hint_console.print(message, style="search.empty")
