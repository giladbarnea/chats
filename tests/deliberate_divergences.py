"""The recorded cases where `ch search` deliberately differs from `ch-legacy`.

**One authority, imported by both surviving suites.** `test_search_command_contract.py`
and `test_legacy_selection_frozen.py` read these lists to know which cases they must not
assert byte-parity on, and the selection gate asserts each difference's *shape* from the
constants here. **A second copy of any of them is the defect this module exists to
prevent** — the launcher guard was fixed in one of two files that held it, and 21 errors
followed.

⚠ **WHAT THIS FILE STOPPED BEING ABLE TO SAY, 2026-09-02.**
`test_deliberate_divergences.py` held `test_the_set_of_deliberate_divergences_is_exact`,
which ran every recorded case through **both** routes and asserted that the set of
differences was exactly `DELIBERATE` — so a seventh divergence appearing was a failure
and a case quietly agreeing was a failure. **It ran `ch-legacy search` and died with the
Python search authority.** *The set was the assertion, and the set is what cannot be
re-derived.*

**What survives is per-case and one-directional:** each named id must still differ from
its **stored** bytes, and each difference must still have its recorded shape. **Nothing
now watches the cases that are not named here.** A new divergence in an unnamed case is
caught only where a stored baseline covers it, and **no gate can any longer prove that
these lists are complete.**

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

**The selection recording carries three classes of its own**, so they get names here
rather than a second list somewhere else: the same warning ruling reached through a
different corpus, a warning the port drops entirely, and a message `ch-legacy` mangles
through Rich markup. See the three tuples below the contract ones.

**Removing an id from here restores byte-parity on it in the suite that reads it
automatically, and an id that stops diverging fails there as an inert allowance.** Both
directions are covered, so no list here can quietly stop meaning anything **about the
cases it names**.
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

# ── The selection recording's three divergence classes ──────────────────────────────
#
# Keys into `tests/data/legacy-selection-baseline/legacy-selection-baseline.json`, read by
# `test_legacy_selection_frozen.py`. **Separate names, not additions to `DELIBERATE`:**
# these are recording keys rather than manifest case ids, and
# `test_the_set_of_deliberate_divergences_is_exact` compares `DELIBERATE` against what the
# two manifests actually produce — a foreign id there reads as an allowance pointing at
# nothing and fails that assertion.
#
# **All three were measured on 2026-09-02 by running all 60 generated rows against the
# live route and comparing stderr, which that gate does not do.** 7 of 60 differ. The
# split below is by *what* differs, not by which marker the row carries.

#: The `WARNING_DIVERGENCES` ruling above, reached through the selection recording.
#: `posix_class_future_warning` is a `DEFECT_PATTERNS` key; the other two are generated
#: patterns that produce the same POSIX-nested-set warning.
SELECTION_WARNING_DIVERGENCES = (
    "posix_class_future_warning",
    "generated-17",
    "generated-58",
)

#: ⚠ **The port being WORSE, and NOT covered by `WARNING_DIVERGENCES`.** For `[a&&b]`
#: `ch-legacy` warns `Possible set intersection at position 2` and **the port emits nothing
#: at all** — the whole warning absent, where that ruling allows only the missing
#: decoration around a warning the port does emit. **Recorded here so it cannot drift, with
#: a named follow-up to emit the warning.** Ruled 2026-09-02: record now, do not fix in the
#: deletion slice. *Not perishable — what CPython's `re` warns on is knowable from CPython,
#: not from `ch-legacy`, so the fix outlives the deletion.*
MISSING_WARNING_DIVERGENCES = ("generated-51",)

#: **The port being BETTER.** `console.print_hint` renders the no-results message through
#: Rich console markup, so a bracket expression that parses as a style tag is **deleted
#: from the user's own pattern inside a diagnostic about that pattern**: `ch-legacy` prints
#: `No sessions match "+".` for `[z-a]+`. `[-a]` and `[123]` survive because they do not
#: parse as tags, which is why `generated-32` keeps one bracket group and loses the other.
#: **Reproducing it means mangling the pattern on purpose** — the same family as the
#: fabricated traceback this project already removed: a defect the port naturally avoids.
#: Ruled against reproduction 2026-09-02.
MARKUP_DIVERGENCES = ("generated-15", "generated-32", "generated-42", "generated-59")

DELIBERATE = frozenset(FENCE_DIVERGENCES + WARNING_DIVERGENCES)
