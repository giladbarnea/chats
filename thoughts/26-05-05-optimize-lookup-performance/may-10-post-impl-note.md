session_id: session_id: e5b0d0ef-bce4-4793-978a-216622ddeb58

Considered. Here's the honest breakdown for `ccc search . -l -d .`, wall time ~1.45–1.70s:

| Stage | Cost | In scope? |
|---|---|---|
| `uv run` cold start | ~300ms | No |
| `SessionPool.discover` | ~400ms | No (out of scope per earlier decision) |
| 1300 non-matching streaming cwd probes | ~200ms | Already minimal |
| 179 matching files: full read + parse + regex render | ~700ms | Would need a wider refactor |

The non-matching pre-skip (the surgical edit) drove the original 4200ms down to ~750ms of actual work; everything else is fixed startup or work that genuinely needs to happen. The remaining ~700ms in the matching path is dominated by `_search_conversation_content` doing a full `SessionScan.from_content` + per-message render + regex on the rendered XML. For `--list` mode specifically, we're paying for full per-message rendering even though the output is just metadata — but we do need *some* parse to count matches and grab cwd/title/summaries.

**To go materially below 1000ms you'd need one of:**
- Skip eager rendering in `--list` mode (split `_search_conversation_content` into a "match count + facets only" fast path for `LIST` and a full one for `MATCHES`/`FULL`). Plausible, surgical-ish, but cross-cuts the search render path.
- Streaming-search per file (regex-match line-by-line and stop on first hit when the output mode only needs `--list`). Same idea, more invasive.
- Lighten `SessionPool.discover` — out of scope.

**My read:** at 1.45s wall with a 2-line surgical change, this is reasonable for now. The remaining wins live in a `--list`-aware fast path inside the search loop — which is a separate, meaningful refactor in its own right and worth its own session, not a tail to this one.

Want me to:

a) accept 2000ms budget and move on
b) tighten further with a `--list`-aware fast path (~30 lines, bounded scope)
