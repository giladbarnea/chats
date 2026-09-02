---
date: 2026-08-28
author: context-curator
task: B4 — generated adversarial session content, driven under a pty at generated widths
status: built, calibrated, clean
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
---

# Generated session content fuzz

## What exists now

Landed at `tests/data/search-content-fuzz/`, the location `contract-owner` approved — beside their corpus, never inside it, because a regeneration of theirs is a correctness event while a regeneration of this one is routine.

| File | What it is |
| --- | --- |
| `SEED.json` | Committed seed. Nine adversarial shapes, each carrying the evidence for why it exists. Four widths: 52, 72, 111, 137 — none of them 80, none of them the pinned corpus default of 96. |
| `build_home.py` | Deterministic builder. Expands the seed into 169 sessions. Same seed, same bytes, verified by two independent builds compared with `diff -r`. |
| `fuzz_harness.py` | Pty driver, two-axis calibration gate, and invariant observer. Refuses to observe anything until both axes pass. |

No wall-clock input anywhere. Session timestamps are fixed absolute values, so this corpus cannot rot on a clock the way the age-coloured fixtures did.

### The nine shapes

| Shape | Sessions | Why it exists |
| --- | ---: | --- |
| `casefold-shrink` | 54 | Ligatures and `ŉ` shrink 3 bytes to 2 when lowercased |
| `wide-and-ambiguous` | 36 | CJK, kana, emoji, Hebrew — two columns per character |
| `casefold-risk-scalars` | 20 | The 20 Python 3.14 scalars whose casefold reaches ASCII |
| `empty-optionals` | 16 | Legacy drops empty metadata fields; the prior branch renders them |
| `casefold-expand` | 12 | `İ` grows 2 bytes to 3 — the branch's only blocker |
| `json-escape-forms` | 9 | Raw, `\/`, and `\uXXXX` in both hex cases, plus chunk-boundary padding |
| `leading-whitespace-controls` | 9 | U+001C–001F, U+0085, U+00A0, U+2028, U+3000, U+200B |
| `layout-edges` | 7 | Content landing at, side of, and beyond the wrap column |
| `carriage-returns` | 6 | LF, CRLF, and lone CR, so the product side is pinned too |

`contract-owner` de-duplicated three of these against work already on disk. Their single pinned instances catch the shape; these generated families catch the boundary.

## Result

**No invariant violations.** All 169 sessions render correctly through `main`'s Python at all four widths: every process exits 0, every visible line fits its terminal, and no output contains a replacement character.

That is a clean bill for the oracle over exactly the content classes that broke the prior native implementation.

## The near-miss, which is the more useful half

The first run reported a finding at every width: two lines exceeding the terminal by exactly one column. 52 to 53, 72 to 73, 111 to 112, 137 to 138. A consistent off-by-one across four independent widths reads like a real wrapping bug, and it would have been a confident, specific, entirely false report.

The cause was U+200B ZERO WIDTH SPACE in my own width measure. I zeroed combining characters but not format characters, so a zero-width space counted as one column. The product was right; the instrument was wrong.

**Two things about this are worth carrying.**

First, the mandated byte-payload calibration passed cleanly before this run and could never have caught it. That calibration grades whether the capture path can *see a difference between two payloads*. It cannot grade whether a derived measurement over a rendered line is correct, which is exactly what `search-firstmate` flagged when they said the width axis is not gradeable by byte payload. The gap was real and I fell into it inside an hour.

Second — and this is the part that revises the standing lesson — **`session-core` caught their two traps because the numbers were implausible. Mine was perfectly plausible.** A consistent single-column overflow at four widths is what a genuine off-by-one looks like. Nothing about the number would have prompted a second look. The only thing that caught it was auditing the offending lines character by character before reporting, and that has to be a rule rather than a habit.

## The width-axis calibration this produced

`fuzz_harness.py calibrate` now grades two axes, and `observe` refuses to run unless both pass.

The byte axis is `reviewer-profiler`'s tool, imported rather than reimplemented, driven through this harness's real pty capture path. All 8 dimensions visible, including both carriage-return traps.

The width axis is new and grades **both directions**, because a width instrument fails in two ways and only one is obvious:

- **Sensitivity** — a line planted wider than the terminal must be seen.
- **Specificity** — a line of zero-width, double-width, and combining characters that exactly fills the terminal must *not* be flagged. This is the direction that bit, and the direction a one-sided calibration would have missed.

Plus two live-subject checks: the product rendered at 52 and at 137 columns must stay within its terminal. Those cannot be done on a payload; they need a real process under a real pty.

## All five output modes (extension, 2026-08-28)

The observer now drives every public output mode: matches, list, full, ID-only, and raw. Twenty runs — five modes across four widths — **no invariant violations.**

The extension was not quite the one-line change I called it, for a reason worth recording. **The width invariant does not apply to every mode.** Raw mode emits stored content verbatim rather than wrapping it, and this corpus deliberately contains a session with a 131,070-character line. Asserting a wrap rule there would have manufactured a finding on a mode that is behaving correctly — the same false-positive class as the zero-width-space near-miss, one level up. So `OUTPUT_MODES` carries a `wraps` flag per mode, and exit status and UTF-8 validity are checked everywhere while the width check applies only where wrapping is the contract.

Importing `reviewer-profiler`'s calibration rather than copying it paid off here too: their probe set grew from 8 dimensions to 14 between my two runs, and this harness inherited all 14 with no change. It passes all of them.

## Limits

1. **Invariants, not a differential.** With no native route on `main`, this checks properties that must hold rather than comparing two implementations. The differential half activates when native search lands; the corpus and the harness are the durable part.
2. **ONLCR.** Pty capture turns `\n` into `\r\n`. Both sides of any future comparison must come from the same channel kind, and captures carry a channel label so a mismatch is caught rather than debugged.
3. **Determinism is verified, portability is not.** Two builds on this machine are byte-identical. Nothing has run this on another machine or filesystem.

## NFC versus NFD: the product diverges (2026-08-28)

Oracle revision: `8cb4c5f`.

`session-core` raised Unicode normalization form as their top candidate, and `reviewer-profiler` asked for a corpus answer — a probe proves a harness can *see* the difference; only a corpus says whether the product diverges.

**It diverges.** Title elision in list mode is normalization-sensitive.

Method: the same visible string built twice, NFC and NFD, rendered through the oracle at 52 and 72 columns, with both **outputs** normalized to NFC before comparison. Normalizing the output is what makes this a behaviour test rather than an input-encoding test.

Same visible text, same width, same session id, at 52 columns:

```
NFC:  café résumé naïvecafé résumé naïvecafé résumé naï…
NFD:  café résumé naïvecafé résumé naïvecafé r…
```

NFD truncates roughly nine visible characters early and wastes the columns. Cause: elision counts code points, and NFD spends two code points on each accented character that NFC spends one on.

Reproduced on 3 of 4 subjects across both widths — 6 divergences. The fourth subject was Hebrew, whose NFC and NFD forms are identical, so it correctly reported no difference rather than a false one.

**A confound was caught and removed.** The first run derived session ids from the form name, so NFC and NFD sessions had different ids and their list rows could differ for a trivial reason. Re-running with the id held constant reproduced the divergence, so the finding survived the check. This is the aggregate rule applied to my own result: six divergences meant nothing until the instances were read.

**For the rewrite:** a native implementation must either reproduce this exactly, or the team decides to fix it deliberately. It cannot be left to chance, and nothing currently pins it.
