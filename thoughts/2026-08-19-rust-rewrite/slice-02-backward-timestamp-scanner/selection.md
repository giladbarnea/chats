---
date: 2026-08-19
title: Slice two selection
---

# Slice two selection

Slice two replaces the backward last-timestamp scanner with Rust.

The scanner is the largest narrow runtime cost in the current command paths. On 4,851 main-session files, one warm Python pass took 832 to 847 ms. A process-cold pass took 1,198 to 1,445 ms. File discovery took about 112 ms. Rebuilding `SessionPool` took 91 to 98 ms warm. The scanner dominates both alternatives and directly affects the failing date-filtered search.

The root cause is algorithmic. One Pi session has a 3,752,303-byte final line. The Python chunk loop repeatedly copies and splits its growing buffer. That file alone took 773.5 ms and caused 67% of the full scan cost. A linear Python prototype took 178.5 ms for the pool. A standalone linear Rust prototype took 137 ms warm and 148 ms on its first pass.

The clean end-to-end baseline also supports this choice. `ch search . -ma 4h --list` took 2,443 ms against its 1,750 ms budget. Profiles attribute 1,292 ms of a 2,861 ms search run to last-timestamp calls. They attribute 1,108 ms of a 1,924 ms recent-index run to the same scanner.

The stable boundary already exists. `get_jsonl_last_timestamp(Path) -> datetime | None` owns local datetime conversion and filesystem fallback. Rust can replace only its raw backward file scan without changing callers, CLI behavior, filtering, ordering, or output.

Slice One measured only a 120 to 220 ms Rust gain in an earlier prototype. That result prevents acceptance by assumption. Differential parity and repeated cold and warm end-to-end measurements will decide whether this slice lands.

The forward timestamp scan ranks below this slice because `--mafter` does not call it across the pool. The cwd scan affects only directory filters. Provider session parsing is broader and remains Python.

This slice does not move first-timestamp scanning, datetime parsing, file discovery, session-pool construction, date filters, sorting, or command orchestration to Rust.
