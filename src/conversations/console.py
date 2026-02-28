from __future__ import annotations

from rich.console import Console

# Module-level console instance for consistent formatting
_console: Console | None = None
_error_console: Console | None = None


def init_module_console(*, force_color: bool | None = None) -> Console:
    global _console
    # Note: if color is acting funny, explore with/instead force_interactive
    _console = Console(force_terminal=force_color) if force_color else Console()
    return _console


def get_console() -> Console:
    """Get the console instance, initializing if needed."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def print_error(*print_args) -> None:
    """Print error message to stderr in red."""
    global _error_console
    if _error_console is None:
        _error_console = Console(stderr=True)
    _error_console.print(*print_args, style="red")

