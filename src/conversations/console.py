from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

_GLOW_THEME = Theme({"markdown.code": "#EE7F4B on #3C3C3C"})

# Module-level console instance for consistent formatting
_console: Console | None = None
_error_console: Console | None = None
_warning_console: Console | None = None


def init_module_console(*, force_color: bool | None = None) -> Console:
    global _console
    # Note: if color is acting funny, explore with/instead force_interactive
    _console = Console(force_terminal=force_color, theme=_GLOW_THEME) if force_color else Console(theme=_GLOW_THEME)
    return _console


def get_console() -> Console:
    """Get the console instance, initializing if needed."""
    global _console
    if _console is None:
        _console = Console(theme=_GLOW_THEME)
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
