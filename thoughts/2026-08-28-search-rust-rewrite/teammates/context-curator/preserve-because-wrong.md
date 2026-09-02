---
date: 2026-08-28
author: context-curator
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
question: Which behaviours must be preserved *because* they are wrong?
verdict: Eight, across six mechanisms, plus a ninth added by search-firstmate as an attributed addendum. Every one would be silently improved by a competent port.
---

# Preserve-because-wrong: the invisible divergence surface

## Why this class is the dangerous one

A native implementation that gets something *worse* fails a review. A native implementation that gets something **better** passes every gate we have, because the output looks correct and no reviewer flags an improvement. The divergence is real, silent, and invisible in exactly the direction our contract cannot see.

Two instances were already found by accident — code-point elision, and the age-colour signal. This is the systematic sweep for the rest.

Method: read the Python for places where the implementation is naive in a way a careful reimplementer would instinctively correct, then probe each against the oracle. All five below are confirmed by execution, not by reading.

---

## 1. `collapse_home` matches a string prefix, not a path boundary

`src/chats/utils.py`. Confirmed:

| Input | Renders as | Correct |
| --- | --- | --- |
| `/Users/giladbarnea/dev/chats` | `~/dev/chats` | yes |
| `/Users/giladbarneaX/dev/chats` | `~X/dev/chats` | **no** |
| `/Users/giladbarnea-backup/x` | `~-backup/x` | **no** |

Any sibling directory whose name starts with the home directory's name gets a mangled display path. A native implementation comparing path components — the obvious way to write it — produces the correct full path and diverges on every such directory.

**Reaches:** `commands/search.py:208` and `:290`, so both the list row and the panel title. Also `commands/rm.py`, outside our scope but the same function.

## 2. The age label and the age colour disagree by one bucket

`humanize_age` and `age_style` carry **separate, unaligned** thresholds. Confirmed against the oracle:

| Age | Token shown | Colour used |
| ---: | --- | --- |
| 3 days | `3d` | `search.age.week` |
| 5 days | `5d` | `search.age.week` |
| 10 days | `1w` | `search.age.month` |
| 20 days | `2w` | `search.age.month` |
| 45 days | `1mo` | `search.age.old` |
| 200 days | `6mo` | `search.age.old` |

The colour is consistently one bucket older than the label. A row reading `3d` is painted with the week colour; a row reading `2w` is painted with the month colour.

A native implementation driving both from one table — the obvious simplification, and the one any reviewer would ask for — changes the colour of **every coloured result row** in the product.

**This is the single highest-risk item on the list**, because `contract-owner`'s comparator is currently blind in exactly this dimension. It normalizes the age SGR away, so this can regress with no gate firing and no reviewer objecting.

**Reaches:** `commands/search.py:198/223` and `:268/283` — list row and panel title.

## 3. `elide_to_width` counts code points, so wide text overflows its own budget

The function's contract says columns; its implementation counts code points. Confirmed:

| Text | Budget | Result | Actual columns |
| --- | ---: | --- | ---: |
| `hello world` | 8 | `hello w…` | 8 |
| `你好你好你好你好` | 8 | `你好你好你好你好` | **16** |
| `cafécafécafé` | 8 | `cafécaf…` | 8 |

For double-width text the function returns the string **unchanged** and overshoots its budget by 2×, because eight characters is not eight columns. A native implementation measuring display width elides to four characters and fits.

**Corrected 2026-08-28 by `views-and-colour`, who rendered it instead of trusting this document.** The overshoot is real at the function and **never reaches the screen**. Every chrome line is wrapped in `Text(no_wrap=True, overflow="ellipsis")`, so Rich clips again — in **cells** — and two truncations counting different units stack:

```
console width 40, headline "你好"×30
  after elide_to_width : 38 code points / 75 cells
  on screen            : 21 code points / 40 cells   '…你好你好你 …'
```

Reproduced independently. Rich cannot split a double-width character, so it pads with a space and appends its own ellipsis.

**The divergence is still real, and still belongs on this list — but it is not the one this entry originally predicted.** A port that "fixes" the counter to cells produces a *short* line where the product produces a full-width line with a pad space. Both diverge; the shapes differ.

**So a gate must pin the composed bytes, not the function's return value.** A fixture written from this entry's original wording would look for 16 columns of overflow, never find it in either implementation, and pass a wrong port.

This is the same mechanism as the NFC/NFD finding, seen from the other side: there it truncated too early, here it truncates not at all.

**Reaches:** four call sites in `commands/search.py` — headline and directory, in both the list and panel views — plus `formatting.py:152` for tool-header key arguments. **This is several case pairs, not one.**

## 4. `truncate_middle` counts code points, so shortening is normalization-sensitive

Same counter, different surface. Confirmed at the default 500-character limit:

| Input | Visible characters surviving |
| --- | ---: |
| 400 visible chars, NFC | 400 (untouched, under the limit) |
| 400 visible chars, NFD | **253** |

Identical visible content, and NFD loses 37% of it. This is the mechanism `session-core` predicted from reading the source before any corpus existed.

**Confirmed end-to-end 2026-08-28**, after `views-and-colour` asked whether the same second-truncation applies here. It does not — `truncate_middle` guards **thinking blocks** (`model.py:303, 365`), which are not wrapped in an overflow-clipping `Text`. Rendered through `ch <session> -T --short`:

| Input | Visible characters in **rendered output** |
| --- | ---: |
| 400 visible chars, NFC | 400 |
| 400 visible chars, NFD | **247** |

So unlike item 3, this divergence reaches the screen unmodified and a gate on the composed output will see it. The rendered figure is 247 rather than the 253 measured at the function boundary; the ellipsis placeholder accounts for the difference.

**Reaches:** `model.py:303` and `:365` directly, and `shorten_data` at `model.py:218/220/290/323/353/386` — the whole tool-payload shortening path. So this surfaces in every `--short` mode, not just titles.

Note the codebase is already internally inconsistent here: Pi `responsePreview` truncation uses **UTF-16 code units**, a third counting unit. Any port that unifies them changes behaviour.

## 5. `humanize_age` uses 30-day months and 365-day years

`_AGE_UNITS` defines a month as exactly 30 days and a year as exactly 365. Twelve months is therefore 360 days, so ages between 360 and 365 days render as `12mo` before jumping to `1y`, and no calendar month is 30 days in the general case.

Lowest severity of the five — it is approximate rather than incoherent — but a native implementation reaching for real calendar arithmetic diverges on every age past a month. Listed for completeness; I would pin it with the same case pair as item 2 rather than separately.

---

## What I recommend

Items 1 through 4 need pinned case pairs before any porting starts. Item 2 needs one **first**, because it is the only one on this list that our current instruments cannot see.

The general shape for `contract-owner`: each pair is one input that exercises the naive behaviour and one expectation carrying the *wrong* answer, with a comment saying it is wrong on purpose. Without that comment the next person to read the fixture will fix it.

## Confidence and limits

- All five are confirmed by running the oracle at `8cb4c5f` with `src/chats` clean, not by reading.
- **All eight items are now confirmed against composed output, not the function boundary.** That distinction corrected two of them, so the rest were re-rendered rather than trusted. Evidence per item below.

## Composed-output confirmation (2026-08-28)

Item 3 was corrected by `views-and-colour` when they rendered it; item 4 by me. The remaining six were re-rendered afterwards on the same principle.

| Item | Composed evidence |
| --- | --- |
| 1 `collapse_home` | A session whose cwd is a sibling of `$HOME` renders `directory: ~X/dev`. The mangled path reaches the screen. |
| 2 age label vs colour | Real coloured list rows: `2d` and `4d` painted `search.age.week`; `1w` and `2w` painted `search.age.month`. **The colour is one band older than the label at every age**, on screen. |
| 5 30-day months | Same render path as item 2, same rows. |
| 6 lowercase ISO `z` | Two sessions, identical content timestamps, file mtime forced to 2027-03-03. Uppercase `Z` renders `modified: "2026-08-20 13:00"`; lowercase `z` renders `modified: "2027-03-03 03:00"`. **A seven-month difference in rendered metadata** — much more visible than "falls back to mtime" implied. |
| 7 DST fold | Sessions at `22:30Z` and `23:30Z` on 2026-10-24 both render `modified: "2026-10-25 01:30"`. Identical output for instants an hour apart. |
| 8 trailing space | Rendered from the start: one trailing space on the last line removed, two preserved, one on a non-last line preserved. |

**Item 6's composed form is worth pinning over its function-boundary form.** `_parse_iso_timestamp` returning `None` is the mechanism; a seven-month error in a rendered date is the symptom, and it is what a fixture should assert.

**Item 3 remains the only one whose composed form differs in kind from its function-boundary form.** For every other item the screen shows what the function does. For item 3 a second truncation intervenes, which is exactly why the distinction had to be checked rather than assumed.
- This sweep covered `utils.py` and `ordering.py` in full plus their call sites. It did **not** cover `parsing.py` (2,661 lines), `formatting.py` (830), or `session_scan.py`. The same class very likely exists there — provider normalization and rendering are where "obviously wrong, quietly load-bearing" lives — and that is the next place to look if the team wants more.

---

# 9. Two width resolvers that disagree inside one invocation

Found by `search-runtime` while building `terminal.rs`, not by either of my sweeps. Added here because this list is what a porter reads, and a behaviour of this class is worthless in a message thread.

**The behaviour.** The product resolves terminal width two different ways and they disagree in the same run.

- **argparse** reaches width through `shutil.get_terminal_size`, which is `int(COLUMNS)` inside a `try/except`. That accepts a leading `+`, surrounding whitespace, and fullwidth digits.
- **Rich** reaches it through `str.isdigit()` and then `int()`. That accepts none of them.

At `COLUMNS=+96`, `--help` wraps at **96** while Rich-rendered output wraps at **80** — same binary, same invocation. Verified end to end on the real launcher. They also disagree on `0` and on `' 96'`.

**Two resolvers is the correct port, and the single most tempting deletion in the grammar.** Unifying on argparse changes rendered output; unifying on Rich changes help. `terminal.rs` keeps both, each named for what it models, and `search-runtime` landed a test asserting they **disagree** on `+96` and `' 96'` — so a later unification fails with an explanation rather than a diff.

## Why neither sweep could have found this

Items 1 through 8 came from reading for **naive** implementations a porter would instinctively correct: a counter using the wrong unit, a prefix match where a boundary was meant, a threshold table that drifted from its neighbour.

**Item 9 has no naive implementation in it.** Two *correct* implementations of two *different* specifications share one process. `shutil.get_terminal_size` is right about what it models. `str.isdigit()` is right about what it models. The defect exists only in the composition, and nothing in either half signals it.

So the method that produced this list is structurally blind to this class, and running it harder would not have helped.

## The signature, which is the transferable part

**One user-facing option name, read by two libraries, where one parser is stricter than the other.**

That is checkable without knowing anything about width. Wherever the product exposes a single knob and two dependencies interpret it independently, the stricter parser silently defines a second behaviour for the same input.

# 10. `--color never` still emits colour on stderr

Read out of the source by `search-runtime`, who flagged it unverified when their probe returned empty stderr three times and stopped rather than debug a harness at 75% window. Measured six ways by `views-and-colour`, whose harness had been sending stderr to `DEVNULL`; inverted, it reproduced immediately. The reading needed no correction.

**The behaviour.** The colour choice reaches stdout's console and none of the stderr ones. Stderr colour is decided **solely by whether stderr is a tty**.

| stderr is | bare / `--color never` / `--color always` |
| --- | --- |
| a pty | 103 B, full truecolor — **all three identical** |
| a pipe | 38 B, no SGR — **all three identical** |

So `ch search nomatch --color never 2>/dev/tty` is coloured.

**Five renderings, not three (measured by `views-and-colour`, 2026-08-28).** I reported three tiers to them; they swept five, and the two I had collapsed are distinct. At 256-colour and 16-colour the match highlight is **downgraded, not absent** — still 58 SGR sequences, just not the truecolor form. That is the path `rust/color.rs` computes, and my grouping hid it by treating everything non-truecolor as one bucket.

| Tier | full highlight | bare bold | total SGR |
| --- | ---: | ---: | ---: |
| truecolor | 1 | 0 | 58 |
| eight-bit | 0 | 0 | 58 |
| standard | 0 | 0 | 58 |
| no-colour | 0 | 3 | 8 |
| dumb | 0 | 0 | 0 |

**A candidate mechanism eliminated, not replaced.** I measured 632 bare-bold against 316 full highlights — exactly 2× — and said I would not guess why. They measured 3:1 on different content. The counts are not comparable across corpora, but **a ratio that is not stable is evidence against a fixed open/reopen pair per span**, which would predict 2× everywhere. Recorded as one hypothesis ruled out; no replacement adopted.

**Why it is preserve-because-wrong.** A native route that resolves the colour choice once and applies it to all four consoles — which is what anyone would write, and is arguably correct — suppresses stderr colour under `--color never` and diverges on every no-results search run in a terminal. The divergence is an *improvement*, which is the direction our comparators cannot see.

**Doubly hidden.** Most harnesses discard stderr; the ones that keep it usually redirect it to a file, where the behaviour vanishes because stderr stops being a tty. That is exactly how the first probe missed it.

## Two refinements from mapping the construction sites

I enumerated every `Console()` in the product. Seven sites, and two things follow that sharpen the item.

**The correct pattern already exists in-tree.** There is a *fourth* stderr console, `formatting.py:698`, and it **does** honour the flag — it is guarded by `if color:` and falls through to a plain `print` when the choice is falsy. So the codebase contains the right shape immediately beside the wrong one.

That makes unification *more* tempting rather than less: a porter can point at `formatting.py:698` as the house style and "bring the other three into line". The argument against is not that the pattern is unknown — it is that these three sites are load-bearing precisely by not following it.

**The three defective sites do not agree with each other either.** `print_error` and `print_warning` build `Console(stderr=True)` with **no theme**; `print_hint` builds `Console(stderr=True, theme=APP_THEME)`. So error and warning output is unthemed while hint output is themed — a second disagreement inside the set, on a different axis from the colour flag.

Four stderr consoles, three configurations, one of which is correct.

# 11. An empty string means "absent" to one code path and "present and invalid" to another

Found and measured by `search-runtime`. I reproduced all four invocations independently before recording them.

`SearchPoolFilter` carries `-d` and `-ma` as raw strings. An empty string means opposite things depending on which path reads it:

| Invocation | Output |
| --- | --- |
| `search -d "" zzz` | `No sessions match "zzz".` |
| `search zzz` (no filter at all) | `No sessions match "zzz".` — **identical** |
| `search -d /tmp/g zzz` | `No sessions match "zzz" with the current filters.` |
| `search -ma "" zzz` | `Error … Invalid date format: empty` |

For the no-results **wording**, an empty string is *absent* — the check is `not (provider or dir or mafter or cafter)`, truthiness rather than presence, so `-d ""` produces the unfiltered sentence. For the **date filter**, the same empty string is *present and invalid* and raises. Both readings are deliberate.

Second-order: the date error repeats once per candidate file, because a `cached_property` that raises caches nothing.

**Why it needs pinning.** The natural Rust port of that emptiness check is `is_none()`. That is correct for every input except an empty string, where it silently gives the **filtered** wording to a search that had no filter. A wrong sentence on a no-results message is about as unreviewed as output gets — no byte gate compares it unless someone recorded that exact argv, and `search-runtime` only recorded it because they were rehearsing a recipe.

Both readings are now pinned in tests beside the code with the measurements in the comment, so the next person reaching for `is_none()` gets a failure that explains itself.

## The class, widened — and my first version of it was too narrow

I wrote the signature as *one user-facing option name read by two libraries, where one parser is stricter than the other.* Items 9 and 10 fit it. **Item 11 does not**, and anyone hunting with my version walks straight past it: there is one struct, one language, no second library.

`search-runtime`'s general form is the right one:

> **One value consumed by two code paths that disagree about what counts as supplied.**

That subsumes all three. The disagreeing paths may sit in different libraries (item 9), in one module's separate construction sites (item 10), or **inside a single object** (item 11). The library boundary was incidental to the first two instances and I mistook it for the mechanism.

**Which also means my earlier negative result was wrong.** I reported that the hunt for a third instance was exhausted, on the grounds that product code reads only one environment variable directly and every `Console()` site was enumerated. Both facts hold. The conclusion did not, because I was searching for the wrong shape — item 11 was reachable the whole time and my search could not have found it.

The corrected search is not "find options read by two libraries". It is **find a value whose supplied-ness is decided more than once.**

Neither is reachable by the method that produced items 1 through 8. That method reads for implementations that look naive; here **every individual site is correct in isolation** and the defect lives in the set.

**I hunted a third and did not find one.** Two axes, both exhausted:

- *Multiple `Console()` sites* — all seven enumerated above. The disagreements are items 9 and 10 and the theme split noted here.
- *Environment variables read at more than one place* — product code reads exactly **one** env var directly (`_NOW_OVERRIDE_VARIABLE`, the clock seam). Everything else, `COLUMNS` included, is read inside the dependencies. So the two-parser problem for `COLUMNS` exists entirely below the product, which is why item 9 was invisible to source reading of `src/chats` alone.

That second point is the useful negative: **this class cannot be found by reading product source, because the disagreeing parsers are in libraries the product does not call directly.** It is found by running the product two ways and comparing — which is how both instances were actually found.

---

# Second sweep: `parsing.py`, `formatting.py`, `session_scan.py`

Oracle `8cb4c5f`, `src/chats` clean (0 modified files, verified at measurement time).

Three more, all confirmed by execution. Two of them affect **ordering and filtering** rather than display, which makes them more dangerous than anything in the first sweep.

## 6. A lowercase ISO `z` is rejected, and the timestamp silently falls back to file mtime

`parsing.py:120` handles only uppercase `Z`:

| Input | Parsed |
| --- | --- |
| `2026-08-20T10:00:00Z` | `2026-08-20 13:00:00` |
| `2026-08-20T10:00:00z` | **`None`** |
| `2026-08-20T10:00:00+00:00` | `2026-08-20 13:00:00` |

ISO 8601 permits the lowercase form. On `None` the caller falls back to filesystem mtime, so such a session sorts by a different clock, filters differently under `-ma` and `-ca`, and shows a different age.

Rust's `chrono` accepts both cases. A port therefore parses the timestamp, and the session moves — with no error anywhere.

## 7. Naive local time collapses two distinct instants across a DST fold

`_parse_iso_timestamp` converts to **naive local** time and drops the offset. Inside a DST fold, two different instants become the same value. Measured under `TZ=Asia/Jerusalem`, which is this product's pinned zone and the user's own:

| Input (UTC) | Parsed (naive local) |
| --- | --- |
| `2026-10-24T22:30:00Z` | `2026-10-25 01:30:00` |
| `2026-10-24T23:30:00Z` | `2026-10-25 01:30:00` |

Two sessions an hour apart compare as **equal**: `a < b` is `False`. Newest-first ordering and both date filters are unreliable for one hour each year.

A native implementation carrying aware UTC timestamps — the natural way to write it in Rust — orders them correctly and diverges. Worse, this is the one item on either list whose divergence is *invisible in the fixture corpus*, because it only appears within a DST fold.

Related, lower severity: sub-second precision is truncated to microseconds, so `.123456789Z` becomes `.123456`. `chrono` keeps nanoseconds, so a port can order two events that Python sees as identical.

## 8. Exactly one trailing space, on exactly the last line, is deleted

`formatting.py:525`. Confirmed by rendering:

| Content | Rendered |
| --- | --- |
| last line ends with **one** space | space **removed** |
| last line ends with **two** spaces | both **preserved** |
| a **non-last** line ends with one space | space **preserved** |

The rule fires only for a single trailing space, and only on the final line. It is asymmetric in both directions. Any reimplementer will either strip trailing whitespace uniformly or preserve it, and both choices change output bytes.

The two-space case is presumably deliberate — it is a Markdown hard line break — but nothing says so, and the single-space rule reads like an accident that happens to be load-bearing.

## Yield assessment and the boundary of this sweep

Yield here is lower than the first sweep — three findings from about 3,500 lines against five from about 200. That is expected: these files are mostly deliberate provider rules, and a deliberate rule is not this class.

But findings 6 and 7 are worth more than their count, because they move which sessions match and in what order, rather than how a matched session looks.

**What this sweep covered:** timestamp parsing in full, trailing-whitespace handling, and a pattern sweep across all three files for boundary-insensitive string matching, counting-unit mismatches, case-folding choices, and silent exception fallbacks, with targeted reads at every interesting hit.

**What it did not cover:** the three provider adapters' normalization rules, read line by line. That is the bulk of `parsing.py`'s 2,661 lines. A defect of this class could hide there, but finding it needs differential execution against real provider payloads rather than pattern reading, which is a different and much larger job than this method.
