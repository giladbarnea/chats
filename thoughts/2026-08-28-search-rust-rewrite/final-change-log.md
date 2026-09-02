# `ch search` — native Rust rewrite: final change log

**2026-09-02. Complete.**

## Outcome

**`ch search` now runs entirely in the package's Rust executable.** It starts no
Python interpreter, imports no Python module, and has no fallback to one. The
Python implementation it replaced has been deleted.

**Everything the command did, it still does.** The proof is a byte-for-byte
comparison against the old route across 260 recorded command shapes, 82 frozen
reference outputs, 150 recorded pattern and width comparisons, and 36 whole
journeys — all captured while both routes existed, because they cannot be captured
now.

**It is faster on every shape measured — between 1.8× and 33×.** It uses about a
third of the memory when rendering results, and more when scanning very large
sessions. Both figures are below.

`ch-legacy` is unchanged and still serves default session parsing and every
unscoped command.

## Commits

| Commit | What it is |
| --- | --- |
| `67d6053` | The native cutover, captured. `ch search` begins routing to Rust here. |
| `e74f5a0` | Pre-deletion checkpoint, with the frozen gates green. |
| `ebd67ba` | **The deletion.** 7,611 lines removed across 36 files. |
| `4c921a7` | Two measurements retired that the deletion made meaningless. |

## Syntax highlighting: seven languages, and everything else renders plain

**Coloured: TypeScript, TSX, Bash/sh/zsh, Python, JavaScript, JSON, SQL.** Measured
over 25,940 real fenced code blocks, these seven carry **98.2% of every character
the old route painted**. The entire remaining tail is 1.8%, and no single language
in it reaches half a per cent.

**Every other language renders with complete geometry — background, padding, line
numbers, wrapping — and plain text inside.** It never truncates output and never
fails.

## Proof

Fifteen checks. **Thirteen green, two retired.**

| | |
| --- | --- |
| No Python in the binary | 0 undefined `Py_` symbols; links three system libraries |
| No Python at run time | Binary alone in an empty directory: search works, exit 0 |
| Output unchanged by the deletion | **Byte-identical to the pre-deletion run** |
| Full test suite | **1,963 passed, 3 skipped, 0 failed**, plus 13 of 13 shell suites |
| Recorded command shapes | 260 cases; 254 identical, 6 accepted differences |
| Frozen reference outputs | 82 stored, 0 drifted |
| Legacy journeys still working | **36 of 36 reproduce byte for byte** |
| Package and installed launcher | One executable, byte-identical to the one measured |
| Scope | 52 changed paths, none outside the rewrite |

**Two memory checks were retired rather than left failing.** They compared against
the Python route, which no longer exists — the comparison now measures interpreter
startup rather than search. Their own control detected this and reported the
measurement invalid.

## Speed and memory

**Time — every shape faster than the route it replaced:**

| | native | old route | |
| --- | ---: | ---: | ---: |
| `--help` | 5.4 ms | 190 ms | **33× faster** |
| coloured results | 2,390 ms | 21,539 ms | **9× faster** |
| broad list | 1,030 ms | 2,449 ms | **2.4× faster** |
| selective literal | 1,000 ms | 2,091 ms | **2.1× faster** |
| regex, no match | 1,739 ms | 3,819 ms | **2.2× faster** |
| literal, no match | 277 ms | 479 ms | **1.8× faster** |

**Memory — better where it costs most, worse on the largest sessions:**

**Rendering results uses about one-third of the old route's peak** — 276 MB against
892 MB on the largest session in the corpus.

**Scanning without rendering uses more, and the gap grows with session size** — up
to 3.39× on an 83 MB session, where the old route holds a flat 56 MB and the native
route reaches 192 MB. **In absolute terms both figures are small**, and 6 of 695
real sessions are large enough for this to apply. The cause is understood well
enough to name and is listed as a follow-up below.

## Accepted differences

**Six of the 260 recorded shapes differ on purpose.** Each is asserted *exactly* —
the tests fail if the difference changes, disappears, or is joined by a seventh.

**Four are code fences in unsupported languages.** Two fixtures carry `css`, `html`,
`diff` and `markdown`, which are outside the seven. The blocks render with full
geometry and plain text; the promoted languages in the same fixtures are
byte-identical, colours included.

**Two are a warning's provenance line.** Python's `warnings` module prints a source
path and the offending line of code before a regex `FutureWarning`. Reproducing that
would mean printing a path to a Python file this change deletes, so the native route
prints the warning text alone.

Three further differences were found in a wider recorded corpus and are accepted on
the same terms: the same missing warning decoration in three more cases; **the
native route printing the user's search pattern correctly where the old route
silently deleted part of it** (a bracket expression was being read as formatting
markup); and one missing warning, listed below as a follow-up.

## Known follow-ups

**1. `ch search '[a&&b]'` prints no warning.** The old route warned *"Possible set
intersection"*. The native route runs the search correctly but says nothing. What
CPython warns about is documented, so this is fixable without the deleted code.

**2. Scan memory grows per session where the old route's did not.** On id-only
scanning the old route's peak stayed flat at 56 MB regardless of session size; the
native route's grows with it. This is the cause behind the memory figure above and
is the starting point for reducing it.

**3. Evaluate Arborium and delete the custom highlighting.** The syntax engine,
seven language tables, generators and style tables are roughly 3,000 maintained
lines. A mature Rust alternative may replace them. The held-out corpora and gates
must survive any such change — they are how a replacement would be judged.

## One operational note

`target/debug` was removed to reclaim 2.9 GiB. The first `cargo` command rebuilds
it. `target/release/ch` is untouched and is the binary these measurements describe.
