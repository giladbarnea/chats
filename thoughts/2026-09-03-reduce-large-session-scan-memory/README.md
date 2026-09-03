# Reduce large-session scan memory

**Priority: P1**

## Problem statement

Native `ch search` is faster than the former Python route, but id-only scanning retains memory proportional to session size.

The Python route stayed near **56 MB**. The Rust route reached **192 MB** on an 83 MB session, or **3.39×** Python memory.

This affects **6 of 695 measured sessions**. It did not block the Rust rewrite because the absolute use remained bounded. Full colored rendering also improved from **892 MB to 276 MB**.

## Reproduction

1. Use the fixed large-session corpus recorded in the G5 performance artifacts.
2. Run an id-only search that scans but does not render the large session.
3. Measure peak memory for the native route.
4. Compare several increasing session sizes.
5. Confirm that Python stays near 56 MB while Rust memory grows with input size.

Use the recorded G5 harness rather than creating a new benchmark. Preserve the source-digest-before-and-after rule so each measurement names its exact binary.

## Team-recorded fix vector

The team did **not** name a proven code fix.

It narrowed the cause to **per-session accumulation rather than fixed runtime overhead**. The next task should profile allocations across one large session and find which scan or confirmation buffers remain live together.

Start from the existing “flat 56 MB versus size-growing Rust” diagnostic. Do not start with allocator tuning or arbitrary streaming refactors.
