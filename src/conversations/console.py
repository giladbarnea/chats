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
