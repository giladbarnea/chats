from __future__ import annotations

from rich.console import Console

from chats.theme import APP_THEME


def test_dim_style_uses_explicit_rgb_fallback() -> None:
    style = Console(theme=APP_THEME).get_style("dim")

    assert style.color is not None
    assert style.color.triplet is not None
    assert style.color.triplet.red == 80
    assert style.color.triplet.green == 80
    assert style.color.triplet.blue == 80
