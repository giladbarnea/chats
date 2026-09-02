"""The recorded cases where `ch search` deliberately differs from `ch-legacy`.

**One authority, imported by both suites.** `test_deliberate_divergences.py` asserts what
each difference *is*; `test_search_command_contract.py` reads this list to know which
cases it must not assert byte-parity on. **A second copy of this list is the defect it
exists to prevent** — the launcher guard was fixed in one of two files that held it, and
21 errors followed.

**Two classes, both ruled.**

**Four fence rows carry a language the seven-family list does not cover.** L247 closed
that list at seven; `render-fence-web` carries `css`, `html` and `javascript`, and
`render-fence-data` carries `diff`, `json` and `markdown`. The promoted halves —
`render-fence-shell` and `render-fence-python` — are byte-identical at both widths, which
is what proves the divergence is the language list and not the renderer.

**Two warning rows want CPython's `warnings` decoration.** Reproducing it means emitting
a path to `search_query.py:96` and echoing a line of Python the cutover deletes — the
fabricated-traceback pattern this project already removed once. Ruled against
reproduction explicitly.

**Removing an id from here restores byte-parity on it in the contract suite
automatically, and makes its entry in the divergence suite fail as an inert allowance.**
Both directions are covered, so the list cannot quietly stop meaning anything.
"""

from __future__ import annotations

FENCE_DIVERGENCES = (
    "render-fence-web-96",
    "render-fence-web-140",
    "render-fence-data-96",
    "render-fence-data-60",
)
#: The control. These carry `shell`, `python` and `json`, all promoted, and they must be
#: byte-identical — including their colours.
FENCE_CONTROLS = (
    "render-fence-shell-96",
    "render-fence-shell-60",
    "render-fence-python-96",
    "render-fence-python-60",
)
WARNING_DIVERGENCES = ("fb-posix-class-warning", "fb-posix-class-bare-warning")

DELIBERATE = frozenset(FENCE_DIVERGENCES + WARNING_DIVERGENCES)
