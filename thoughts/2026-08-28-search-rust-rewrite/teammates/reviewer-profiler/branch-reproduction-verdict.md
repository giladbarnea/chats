# Branch reproduction verdict — `wip/cycle-02-native-default-pause-20260821` @ `0ffde41`

**Verdict: the implementation is real and substantially does what its records claim. Its
no-Python proof does not. Reconciling this branch beats building fresh.**

Measured 2026-08-28 in a detached worktree at
`/private/tmp/.../scratchpad/eval-0ffde41`. The shared checkout was never switched, never
mutated, and the user's global `ch` install was never touched.

## What I measured, and what I did not

Measured: the release build, both Rust test modes, the contract suite through the checkout
launcher, the root cause of every failure it produced, an independent no-Python proof, and an
interleaved native-versus-Python timing check on today's live pool.

Not measured: the real-uv-tool-install half of the contract suite, the wheel-identity test, the
eight-gate performance battery, and the two accepted behavior deviations (the 2-million-step
regex budget and the malformed-interval literal fallback). The branch's own suite does not
observe those two either, so nothing here confirms or denies them.

## The build

Clean. `cargo build --release --no-default-features --bin ch` finished in 16 s with **zero
warnings**. The resulting binary links only `libiconv`, `CoreFoundation` and `libSystem`, and
has **zero undefined `Py_` symbols**.

`cargo test` matches the record exactly: **54 passed** with `--no-default-features`, **58
passed** with default features, plus one doctest each, no warnings in either mode.

## The contract suite

173 manifest cases. Through the checkout launcher: **9 failures**, and every one is explained.

Two are artifacts of my method, not findings. `test_built_wheel_and_both_installs_own_identical_native_search_route`
and `test_unscoped_commands_stay_on_the_python_legacy_route` both loop over
`BOTH_INSTALLED_LAUNCHERS`, which includes the user's global `~/.local/bin/ch`. That binary is
built from `main`, so the comparison is meaningless here. I did not install the branch globally,
because that would have overwritten a working tool outside the shared checkout.

Seven are fixture rot. All seven are colored or pager cases, and all seven differ from their
expected bytes **in exactly one place**: the SGR color of the session-age token.

    expected  38;2;135;140;146   = #878c92 = search.age.week
    actual    38;2;107;112;118   = #6b7076 = search.age.month

The harness normalizes the age *text* — its own comment says `1d` decaying to `2d` "would rot
the green layer" — but it does not normalize the color that encodes the age *bucket*. The
fixture sessions carry a fixed content timestamp of `2026-08-20`. When the fixtures were
characterized on 24–25 August they were under seven days old and rendered in the "week" bucket.
Today they are eight days old and correctly render in the "month" bucket.

I proved this rather than argued it. Neutralizing the bucket color on both sides makes **all
seven pass byte for byte**:

    differ only in the age bucket : 7/7
    genuinely divergent           : 0

So the implementation is right and the fixture is stale. This is compatible with
`context-curator`'s correction that the age-formatter deviation does not exist — this is a
harness defect, not a formatter defect.

**What that buys the mission.** Those seven cases are Rich panels, hue cycling across four
hits, an 80-column narrow layout, highlight painting, and real `less` pager streaming. They
reproduce byte for byte. Colored presentation — the largest unpriced item on this mission —
is done on this branch, and it holds up.

### Correction: terminal width is not covered by that result

`session-core` qualified this and they are right. The contract harness sets `COLUMNS`
explicitly for every case, and the narrow case sets it to 80. The branch's width helper reads
`COLUMNS` only and otherwise returns 80; Rich piped into a subprocess also reports 80. So every
colored case I ran was measured with the width pinned, at the one value where a
"follows the terminal" implementation and an "always 80" implementation produce identical
bytes.

My result therefore establishes colored parity **when `COLUMNS` is set**, and says nothing
about width resolution. Under zsh, which sets `COLUMNS` without exporting it, the branch would
render at 80 columns on every real terminal. That is the same defect class `main` already paid
for twice: `a51f32c` fixed it with `ioctl TIOCGWINSZ` across fds 0/1/2, and before that a
hard-coded 44-column element passed every colored test because all of them pinned one width.

Everything else in this section stands — panels, hue cycling, highlight painting and pager
streaming are real results. Width alone was tested at exactly one value, and that value is the
shared fallback. Any colored parity claim must drive both binaries under a pty at two widths,
neither of them 80.

## The no-Python proof does not hold

This is the one thing in the records that is not true, and it is worth more than the rest.

The acceptance record proves "no Python" by running each journey under `DYLD_PRINT_LIBRARIES=1`
and reporting "842 dyld libraries, 0 python entries" for all three. I reproduced that number,
and then ran the control the record never ran:

| command | expectation | dyld lines | python lines |
| --- | --- | ---: | ---: |
| `ch info --help` | **must** use Python | 842 | **0** |
| `ch search ...` | must not | 842 | 0 |
| `ch-legacy info --help` | must use Python | **0** | 0 |

`ch info` stays on the Python legacy route by design on this branch — and it produces the
identical "842 libraries, 0 python" signature that the record cites as proof of nativeness.
Invoking the Python launcher directly produces no trace at all.

The mechanism is `exec`. `run_legacy` replaces the process image, and macOS purges `DYLD_*`
from the environment of a hardened-runtime binary, which the Homebrew interpreter is. The trace
therefore captures the `ch` binary's own libraries and nothing after the handoff. **842 is just
the size of `ch`'s own library set.** The proof cannot distinguish a native route from a Python
one, and the failing tripwire test is the control that reveals it.

Nothing here suggests the branch actually uses Python for search. It means its evidence for
that claim is empty, and the same empty check is applied to all 173 cases.

### The proof that does discriminate

Copy `ch` alone into an empty directory with no `ch-legacy` sibling, strip `PATH`, and run:

    ch search "needle five" --no-paging --no-metadata   -> renders real hits
    ch search "needle" -ll                              -> lists five session ids
    ch info --help                                      -> Error: Cannot start the private ch legacy entry

Search works with no interpreter and no sibling reachable; `info` fails exactly as it must.
That is a discriminating proof, and the branch passes it. I recommend it replaces the loader
trace outright.

## Performance

Interleaved in one window on today's live pool (392 Claude + 1208 Codex files, 2.86 GB), branch
launcher against `main`'s installed launcher, three measured repetitions after a prime, medians:

| shape | native | Python | speedup |
| --- | ---: | ---: | ---: |
| search help | 6.5 ms | 226.6 ms | 35× |
| recent broad list | 291.8 ms | 1023.8 ms | 3.5× |
| broad literal miss, id-only | 2221.9 ms | 4887.3 ms | 2.2× |
| selective literal, id-only | 2504.7 ms | 14927.5 ms | 6.0× |

Same direction and same order as the recorded gates. The absolute numbers are not comparable to
theirs and I make no claim that they are: their window recorded 5,043 files and 6.9 GB, today's
pool is 1,600 files and 2.86 GB. Interleaving is what makes this pair trustworthy — both
launchers saw byte-identical corpora because they ran seconds apart.

The control is the Python route, verified rather than assumed: `main`'s `ch` serves only
`parse` natively and execs `ch-legacy` for search, and the 226 ms floor on `search --help`
is interpreter startup. This is not the trap that cost the prior team a battery, where a
control checkout's `ch` turned out to be a native launcher.

On the date-filtered row specifically, `search-runtime` found a live fork between
`python_extension.rs` (Python's four-byte JSON whitespace set) and `inventory.rs` (Rust's full
Unicode whitespace property), which can send the two routes to different timestamps for the
same file. I checked whether that corrupts the comparison: both launchers return the **same 36
session ids**, with an empty set difference. So this row compares equal work. That is a
statement about this corpus only — no file in it begins a line with U+00A0 — and it is not
evidence that the fork is harmless.

## Memory

Peak resident set on a broad selective scan (`search needle -ll`), same window:

| route | peak RSS |
| --- | ---: |
| native | 653 MB |
| Python | 1,920 MB |

The native route holds roughly a third of the memory. Read this as a floor rather than a
guarantee: `search-runtime` found that the same extraction replaced a streaming read with
`read_to_string`, giving up the scanner's bounded-memory property, and a known Pi session
carries a 3.75 MB final line. This corpus contains one small Pi session, so the measurement
above does not exercise that path at all.

## Two harness defects worth carrying forward regardless of what we do with the branch

1. **The age-bucket fixture rot.** Any byte-exact colored fixture rots the moment a pinned
   session crosses 1, 7 or 30 days of age. Normalize the bucket color as well as the age text,
   or pin the clock.
2. **The vacuous loader trace.** Replace it with the sibling-removal proof. As written it passes
   for a route that is entirely Python.

Both are inherited by the current mission if we adopt this contract suite as-is.
