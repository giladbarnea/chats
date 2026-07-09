from __future__ import annotations

from rich.theme import Theme

# One Atom Dark palette, borrowed from ~/.pi/agent/themes/one-atom-dark-full.json.
# The single source of hues for message role colors (see formatting._ROLE_HUE) and
# message-body styling, so colors stay coherent and well-separated rather than
# drifting into ad-hoc near-duplicates. These are light pastels on a dark terminal;
# chips drawn over them use INK (dark text) for contrast.
BLUE = "#71b9f4"
CYAN = "#62bac6"
GREEN = "#98c379"
YELLOW = "#eac786"
RED = "#e27881"
MAGENTA = "#c88bda"
BRIGHT_CYAN = "#78c4ce"
ADDITIONAL_CONTEXT = "#fc9867"
GRAY = "#c9ccd3"
INK = "#1d1f23"


APP_THEME = Theme(
    {
        "dim": "rgb(80,80,80)",
        "markdown.code": "#EE7F4B on #3C3C3C",
        # Search list view (`ch search -l`). Two intentional colors: one teal
        # accent (directory + id head + row tick) and a cool-gray neutral ramp
        # tinted toward the accent. Recency rides the ramp's lightness only.
        "search.tick": "#5cc8a8",
        "search.title": "bold #e6e8eb",
        "search.title.fallback": "italic #9aa0a6",
        "search.dir": "#5cc8a8",
        "search.sep": "#4a4e54",
        "search.count": "bold #c3c7cd",
        "search.label": "#7e8389",
        "search.id.head": "#4f9e86",
        "search.id.tail": "#646a70",
        "search.header": "#7e8389",
        "search.empty": "#878c92",
        # Dim metadata trailing a message's role badge (short id, index, model),
        # and the amber pop used to highlight matched query terms in bodies.
        "message.meta": "#646a70",
        "search.match": "bold #14181d on #e6b450",
        # Tool blocks: ⏺ call / ⎿ result markers + the left rail marking each
        # block's extent. Call bright, result dim, error red.
        "tool.call": f"bold {BRIGHT_CYAN}",
        "tool.additional_context": f"bold {ADDITIONAL_CONTEXT}",
        "tool.result": "#5f7e86",
        "tool.error": f"bold {RED}",
        # Edit-tool diff bodies.
        "diff.add": GREEN,
        "diff.remove": RED,
        "search.age.now": "#a9aeb4",
        "search.age.week": "#878c92",
        "search.age.month": "#6b7076",
        "search.age.old": "#565b61",
    }
)
