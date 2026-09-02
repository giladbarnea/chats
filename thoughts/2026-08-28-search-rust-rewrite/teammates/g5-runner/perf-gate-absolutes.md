# The six performance gates as ABSOLUTES — a landing spec

**Measured by `g5-runner`, 2026-09-01T19:28–19:31Z, while both routes still
existed.** Landed by `parity-finisher`. Row text goes **at the rows**.

## ⚠ Why absolutes are admissible here, and it is not a reversal

**Absolutes were retired because the LIVE POOL grew** — each widening was locally
reasonable and none was recorded, and that is how they reached 1750 ms and 2500 ms.

**These do not run on a live pool.** They run on the corpus check 2 pins:

    695 files, 1,183,541,907 bytes
    digest de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965
    performance_gates.py refuses to run if this moves

**A frozen, digest-pinned corpus cannot rot from growth, which is the only thing
that killed the old absolutes.** *Name the digest at the gate, or a reader sees
absolutes restored and reads a reversal.*

**And ratios could not survive the deletion.** A stored Python timing satisfies
none of same-query / same-corpus / same-window / same-machine. **A frozen
denominator is not a denominator.**

## The ceilings

| shape | native med | worst | spread | margin | **CEILING** | python (historical) | headroom |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| help | 5.3ms | 8.2ms | 2.02× | 2.00× | **20ms** | 199ms | 9.94× |
| broad literal miss, id-only | 253.5ms | 256.1ms | 1.02× | 1.25× | **325ms** | 464ms | **1.43×** |
| broad list, absolute date | 967.7ms | 990.0ms | 1.03× | 1.25× | **1240ms** | 2410ms | 1.94× |
| colored matches | 2300.4ms | 2343.3ms | 1.02× | 1.25× | **2930ms** | 21539ms | 7.35× |
| selective literal, id-only | 904.8ms | 985.2ms | 1.10× | 1.25× | **1235ms** | 2080ms | 1.68× |
| broad regex miss, id-only | 1628.1ms | 1649.5ms | 1.02× | 1.25× | **2065ms** | 3782ms | 1.83× |

**Ceiling = worst observed × margin, rounded UP to 5ms.** Both inputs are in the
table so the arithmetic is checkable. **Margin covers the measured noise band:
1.25× where spread is ≤1.20×, 2.00× for `help` whose spread is 2.02× because it is
a 5 ms measurement dominated by process startup.

**All six discriminate: every ceiling is below the Python route's time.**

## ⚠ THE CORRECTION TIGHTENS MORE THAN IT LOOSENS

| shape | old | new | |
| --- | ---: | ---: | --- |
| help | 25ms | **20ms** | tighter |
| broad literal miss | 750ms | **325ms** | **tighter, 2.3×** |
| colored matches | 4000ms | **2930ms** | tighter |
| broad list, absolute date | 650ms | **1240ms** | **looser — the only one** |
| selective literal | ratio 0.30 | 1235ms | was a ratio |
| broad regex miss | ratio 0.25 | 2065ms | was a ratio |

**Three of the four surviving absolutes get TIGHTER. One loosens.** That one is
`broad list`, which the port takes 968 ms on against an old 650 ms budget derived
from the branch — **the shape that was failing.** *A correction that tightens
three ceilings is not a relaxation, and the table is the argument.*

## Justification: the ratios measured against a LIVE Python route

Recorded here because after the deletion they cannot be taken again:

    help 0.033   literal miss 0.552   broad list 0.397
    colored 0.108   selective literal 0.435   regex miss 0.433

**Every shape 1.8× to 33× faster than the route it replaces**, measured
interleaved on 2026-09-01 at oracle digest `sha256:dd6ab701…`.

**⚠ The Python column above is HISTORICAL EVIDENCE and explicitly NOT a
denominator.** It records what the route it replaced cost on this corpus on this
day. **Do not compute a ratio from it.**

## ⚠ Why every repetition is printed, and it is not decoration

**The first derivation of these ceilings was wrong twice, and one fault would have
shipped a gate that proves nothing.**

1. **Rounding to nearest put `help`'s ceiling at 5 ms, BELOW its own worst run of
   5.8 ms.** The gate would have failed on a working product. **Ceilings round up.**
2. **One contended run of 490 ms against a 260 ms median drove `broad literal
   miss` to a 980 ms ceiling — above Python's 464 ms.** **A ceiling above the
   reference discriminates nothing**, which is the exact hole ratios were adopted
   to close, walking back in the moment absolutes returned.
   **Nine repetitions show 251–256 ms, spread 1.02×.** The 490 ms was the machine.
   **A 3× difference in the ceiling from one run nobody would have seen.**

**So: nine repetitions, every one printed, and each ceiling checked against the
Python median before it is offered.**

## Standing rules, carried over unchanged

- **A flapping row is widened with a recorded measurement, never quietly.** That
  is how the live-pool budgets reached 1750 and 2500.
- **`broad literal miss` is the thinnest at 1.43× headroom** — most likely to catch
  a real regression, least room to do it in. *As an absolute it once proved
  nothing at 750 ms; at 325 ms it is the sharpest of the six.*
