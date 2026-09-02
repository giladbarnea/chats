"""The recorded cases where `ch search` deliberately differs from `ch-legacy`.

**One authority, imported by all three suites.** `test_deliberate_divergences.py` asserts
what each difference *is*; `test_search_command_contract.py` and
`test_legacy_selection_frozen.py` read these lists to know which cases they must not
assert byte-parity on. **A second copy of any of them is the defect this module exists to
prevent** — the launcher guard was fixed in one of two files that held it, and 21 errors
followed.

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

**The same warning ruling is reached by a third case through a different corpus**, so it
gets its own name here rather than a second list somewhere else. See
`SELECTION_WARNING_DIVERGENCES`.

**Removing an id from here restores byte-parity on it in the suite that reads it
automatically, and makes its entry in the divergence suite fail as an inert allowance.**
Both directions are covered, so no list here can quietly stop meaning anything.
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
#: The shape of that difference, so a suite can assert what it *is* rather than only that
#: it exists. `ch-legacy`'s stderr is exactly this prefix, the port's own bytes, and this
#: echoed source line. **Here rather than in a suite** because the frozen selection gate
#: needs the same two constants and outlives the live suite that first held them.
WARNING_PREFIX = b"{SEARCH_QUERY_SOURCE}:96: "
WARNING_SOURCE_ECHO = b"  regex = re.compile(pattern, flags)\n"

#: The same warning ruling, reached through `query_pattern_corpus.DEFECT_PATTERNS` instead
#: of the contract manifests. **A separate name, not an addition to `DELIBERATE`:** these
#: are pattern keys rather than manifest case ids, and
#: `test_the_set_of_deliberate_divergences_is_exact` compares `DELIBERATE` against what the
#: two manifests actually produce — a foreign id there would read as an allowance pointing
#: at nothing and fail that assertion.
SELECTION_WARNING_DIVERGENCES = ("posix_class_future_warning",)

DELIBERATE = frozenset(FENCE_DIVERGENCES + WARNING_DIVERGENCES)
