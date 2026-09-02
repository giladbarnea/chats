# Pool ordering gate

`session_pool::SessionPool` against `chats.session_pool.SessionPool` on the live pool
of 5,036 sessions.

| projection | result |
| --- | --- |
| `files` (discovery order) | identical, both sidechain modes |
| `by_provider` counts | identical (claude 347/276, pi 3481, codex 1208) |
| `scan_order` (newest-first) | **0 of 5,036 positions differ** |

## The trap: the corpus mutates while you measure it

A first comparison showed 10 differing positions and looked like an ordering defect.
It was not. The Python and native captures ran minutes apart, and **the session pool
contains the team's own live sessions** — the ten files involved were exactly the ones
being written at the time, including this session's own transcript.

Two checks settled it:

1. Python run back-to-back against itself: 0 differences. So Python is deterministic.
2. Captures taken in the same second, in both orders: 0 differences, and 0 again after
   excluding the 300 files whose mtime moved during the window.

**Consequence for every engine gate that runs over the live pool.** The corpus is not
stable, and the instability is concentrated in exactly the newest files — which is where
a newest-first scan looks first. Any differential over it must either freeze a copy or
capture both sides in the same instant. A diff taken minutes apart will show a handful
of top-of-list differences that look precisely like an ordering defect.

This is the fourth instrument-not-code failure on this slice. The others: a pty capture
leaving a stray carriage return, a shell loop reporting false build failures, and a
mutation run whose crash poisoned the next baseline.
