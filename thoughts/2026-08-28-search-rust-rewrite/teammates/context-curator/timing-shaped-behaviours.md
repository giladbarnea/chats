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
question: What else is a right behaviour whose absence looks identical?
verdict: Five, all sharing one mechanism. Time-boxed sweep; yield moderate and I recommend stopping.
---

# Timing-shaped behaviours

## The class

The preserve-because-wrong list is wrong behaviours that look right. This is the mirror: **right behaviours whose absence looks identical.** Remove one and the output is byte-for-byte the same, in the same order, with the same exit code. Only the clock and the I/O counters change.

No byte comparator can fail on any of these. Neither can an exit-code check, nor a corpus of any size.

Method, per the brief: bias toward behaviours some earlier effort introduced **deliberately**, because a deliberate performance behaviour has a reason, a measurement, and usually a test — which makes it findable. An accidental one does not. All five below are pinned by a test, a comment, or a recorded measurement.

## The five

### 1. Every streamed session ID is flushed individually

`commands/search.py:350` — `print(..., flush=True)`.

The entire deliverable of a measured scope on 2026-08-20. First ID of `ch search 'CLIENT_ID/CARD' -ca 2m -ll | cat` moved from **15.995 seconds to 0.38 seconds**, completion time unchanged. The whole gain was Python block-buffering three short lines into a pipe.

A port that buffers gives back 15.6 seconds of the product's most visible latency, byte-identically.

### 2. Date probing is lazy *and* short-circuits

`pool_filter.py:79–88`. The structure is load-bearing:

```python
if self.mafter_dt is not None:
    mtime = get_jsonl_last_timestamp(path)
    if mtime is None or mtime < self.mafter_dt:
        return False          # ← returns before any first-timestamp probe
if self.cafter_dt is not None:
    ctime = get_jsonl_first_timestamp(path)
```

Two separate economies. Each probe happens **only if its own filter is active**, and a failed `-ma` check returns **before** the `-ca` probe runs. So `-ma` alone never reads a first timestamp, and a file rejected by `-ma` is never opened a second time.

Pinned by `test_cmd_search_skips_first_timestamp_probe_when_only_mafter_is_active`, whose docstring states the intent: "`-ma` alone should never probe first-timestamp for files outside the window."

An implementation that probes both timestamps up front and then evaluates is **byte-identical** and doubles the pool-wide file I/O. Backward and forward scans over roughly 5,000 files is where the historical profiles put a full second.

### 3. Sidechains are excluded before the timestamp probe, not after

Pinned by `test_recent_index_excludes_sidechains_before_timestamp_probe`.

Pure ordering. Filter first, probe second. Reversing it produces identical results and probes every sidechain for nothing.

### 4. An early pager close stops later scanning

`console.py:53, 65, 74–75`. The pager carries a `closed` flag, set when a write raises `BrokenPipeError` or `KeyboardInterrupt`, and every subsequent `write` returns immediately.

Quitting `less` therefore stops the work behind it. A port that keeps scanning after the reader has gone produces identical output — none — while burning the remaining corpus. On a broad search that is seconds of CPU and gigabytes of reads after the user has already walked away.

### 5. Non-raw results stream per confirmed hit; raw buffers deliberately

Raw mode buffers all hits because its one-message output is a special case that needs the whole set. Every other mode emits each hit as it confirms.

A port that buffers uniformly — the simpler implementation — is byte-identical and converts every search from incremental to all-at-the-end. This is item 1's mechanism at the level of whole results rather than single IDs.

## What they share

Every one is **doing less work, in a specific order, with an early exit**. None is an algorithm choice; all are economies layered onto a correct implementation. That is why they are invisible: they were designed not to change the answer.

It also means they are systematically at risk in a rewrite. A native implementation is fast enough that the economies look unnecessary, and each one reads as complexity worth removing.

## Not included, and why

The 256-file candidate window and the 128 KiB read buffer are measured constants rather than behaviours. A port that picks different numbers is slower, not wrong, and the difference shows up on a stopwatch rather than needing one. They are already recorded elsewhere.

## Yield and recommendation

**Moderate, and I recommend stopping here.** Five behaviours, and the deliberate-behaviour bias worked exactly as predicted — every one was findable because someone left a test, a docstring, or a recorded measurement.

That same bias is the limit. **An accidental economy leaves no trace and this method cannot find it.** If the product has a hot path that happens to be lazy without anyone having noticed, nothing here would surface it, and nothing in our instrument set would either.

Closing that would need I/O-counting or timing assertions on the oracle rather than reading — a different and larger job. Given only one of the five (item 1) has a known cost large enough to be worth a dedicated test, I would take the timing assertion for that one and treat items 2 through 5 as documented properties an implementer must know rather than gates.

## Revised the same day, and one claim above withdrawn

I wrote that no instrument on either side could reach this class, and that a gate could be earned later if someone measured one of items 2 to 5 and found it expensive. `reviewer-profiler` built the instrument I said could not exist and measured three of the four.

- **Item 5, streaming — survives**, and the native side is better: first byte at 19 ms against 243 ms.
- **Item 3, filter-before-probe — survives**: a nothing-matching filter costs a tenth of unfiltered rather than a sixth.
- **Item 4, early close — does not survive.** The native route keeps scanning after the reader stops. Python exits in 237 ms against a 3,076 ms full scan; the native route exits in 1,062 against its own 1,048 ms full scan, which is no saving at all. Confirmed by a second path through `head -1`: native 1,494 and 1,627 ms, Python 298 and 488 ms. Total output is 20,831 bytes, inside a 64 KB pipe buffer, so this is not a back-pressure artefact.

**Item 4 therefore earns a gate.** It now has a measured cost *and* a demonstrated failure — a stronger case than item 1 had when I recommended gating that. Revised recommendation: **gate items 1 and 4.**

Item 2, lazy short-circuiting inside a probe, remains a reading job with no instrument.

**The correction that matters more than the revision:** my claim should have been that *our instruments at the time* could not see these, which is a statement about the toolkit. I wrote it as a property of the behaviours, and that framing would have discouraged anyone from trying. Three of four leave a timing signature.

## Time box

About twenty minutes, four tool calls, mostly against tests and `pool_filter.py`. I did not measure any of these five myself — items 1 is measured in the historical record, and 2 through 5 are confirmed as intentional by test or source, with their cost inferred rather than timed.
