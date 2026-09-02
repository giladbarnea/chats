# Branch `0ffde41` search modules vs. the search-runtime map

Requested by `search-firstmate`: read the branch's search modules against my map
and say where its boundaries differ and which split I would defend after seeing
both.

Read via `git show 0ffde41:<path>`. The shared checkout was never switched.
I have re-run none of it; reproduction is `reviewer-profiler`'s job and I did
not duplicate it.

---

## Bottom line

**I would defend the branch's split over mine, with one correction.** Its
decomposition is better than my proposal in the one place that matters most,
and my four-module lift is largely redundant against it. The correction is real
though: the branch's lift is incomplete and left two authorities for the same
behavior, which is exactly the failure my map's shared line-walk primitive
prevents.

Separately, my colored-path escalation is **probably superseded by evidence**.
See section 4.

---

## 1. Module boundaries side by side

| My proposal | Branch | Verdict |
| --- | --- | --- |
| `paths.rs` + `inventory.rs` + `jsonl_scan.rs` | `inventory.rs`, 572 lines | Branch merged my three into one. At that size the merge is right and my split was speculative. **Branch.** |
| `candidate_gate.rs` | `scanner.rs`, 731 lines | Same boundary, better contents: a per-query reusable `LogicalJsonStringGate` that compiles matchers once, and a fused single-sweep UTF-8 / JSON-escape guard. Both are ahead of what `main` has. **Branch.** |
| `search/cli.rs` | `search.rs`, 1057 lines, plus `search_help_consts.rs` | Same boundary. Branch also carries a faithful port of `parse_tool_spec`, which my map left implicit. **Branch.** |
| `search/plan.rs` + `hit.rs` + `raw.rs` + `stream.rs` | `search_engine.rs`, 1271 lines | Branch merged my four. 1271 lines is large but coherent, and I will not defend an unwritten four-way split against a working one. **Branch.** |
| `search/filters.rs` | `SearchPoolFilter` inside `search.rs` | Immaterial. **Branch.** |
| `search/render.rs` (mine) | `search_views.rs`, 594 lines (search) + `session_render.rs`, 3749 lines (session-core) | **The branch is right and my map was wrong here.** See below. |

### The seam my map got wrong

I put result modes and highlight integration together in one `render.rs` under
my ownership. That would have pulled message-body rendering — Markdown, code
fences, syntax highlighting, tool bodies — into search-runtime's scope, where it
does not belong.

The branch draws it correctly: `session_render.rs` owns rendering a message to
styled lines and belongs to session-core; `search_views.rs` owns only the
search-specific chrome — list rows, the panel frame, highlight painting, and the
pager. 594 lines against 3749 is the right ratio for that seam.

This is the boundary I would adopt, and I would not have arrived at it from my
map alone.

---

## 2. The correction: the branch's lift is incomplete

`rust/python_extension.rs` on the branch is 483 lines, down from 1399 on `main`.
Inventory, classification and the scanners did move out. But
`find_last_jsonl_timestamp_impl` and `scan_resolution_facets_impl` **stayed in
the wrapper file with their own bodies**, while `inventory.rs` separately grew
`pub fn last_timestamp` and `pub fn resolution_facets` for the native side.

So the crate now carries two independent implementations of the same behavior,
and they already differ:

1. **Last timestamp.** Both do a backward chunked scan. The wrapper trims lines
   with `trim_python_byte_whitespace`, which is Python's exact byte set
   (`\t \n \v \f \r` and space). `inventory::timestamp_from_bytes` uses Rust
   `str::trim`, which trims the Unicode whitespace set. Different inputs can
   decode differently.
2. **Resolution facets.** The wrapper streams 4096-byte chunks and handles `\r`,
   `\r\n`, and `\n` separately. `inventory::resolution_facets` reads the whole
   file with `read_to_string` and iterates decoded entries. Different memory
   profile and different line splitting.

Neither divergence is necessarily observable today. Both are the shape of bug
that surfaces later, and both violate the first mate's standing ruling of one
authority and no fork.

**The fix is the primitive from my map, and it is small:** one chunked line walk
in `inventory.rs`, forward and backward, parameterized by a line handler. The
PyO3 wrapper passes a handler that calls Python; the native side passes a Rust
handler. The Python-whitespace trim becomes part of the shared walk so both
sides see identical lines. This is the piece of my map worth keeping.

My seam ruling stands unchanged and the branch does not contradict it: the
timestamp decoder is search-runtime's (a one-field date probe feeding date
filters and hit metadata), the resolution-facet decoder is session-core's (and
is not on the native search route at all).

---

## 3. Two facts that change mission planning

**3.1 The branch is a superset of this mission.** `rust/main.rs` at `0ffde41`
routes `parse` and `search` natively, routes `name`/`rm`/`catalog`/`info` to
`ch-legacy`, and falls through to `_native::session::run(&arguments)` — the
default session-parsing journey is native too. The charter says default session
parsing stays on `ch-legacy`. Adopting the branch whole changes this mission's
scope; adopting only its search half means keeping the `run_legacy` fallthrough.

**3.2 The branch deletes the differential oracle.** On the branch,
`src/chats/commands/search.py` is a five-line stub, and `search_query.py` and
`session_scan.py` are gone. `ch-legacy search` does not exist there.

That breaks the property the first mate accepted from my map as the G4 plan —
`ch-legacy search` staying live as an oracle through the cutover. It is
recoverable, not fatal: build `ch-legacy` from `9bf1e06` in one checkout and
`ch` from the branch worktree, and diff across the two. But it has to be planned
rather than assumed, and it means the branch's own fixture corpus is the only
parity evidence that lives in its tree.

If the branch is adopted, I would keep the Python search implementation until
after the byte harness is green, and delete it as a separate final step. That
costs nothing and preserves the oracle exactly when it is most needed.

---

## 4. My colored-path escalation is probably superseded

I raised the colored path as the mission's largest unpriced item, on the grounds
that it needs Rich's Markdown renderer and Pygments. The branch priced and paid
it, and the evidence says it did so faithfully rather than approximately.

`session_render.rs` contains a hand-written Markdown block/inline renderer and
per-language tokenizers for shell (with heredoc state), Python (with f-string
expansion), JavaScript, HTML, CSS, JSON, Markdown, and diff.

I expected a look-alike and probed the sharpest tell I could think of: Rich
renders `Markdown("---")` as a **dim ASCII hyphen run**, not a box-drawing rule.
I confirmed that against live Rich at width 96 — `\x1b[2m` + 96 `-` + `\x1b[0m`
+ `\n\n`. The branch emits exactly `Segment::styled("-".repeat(body_width), "2")`.
It matches. The `humanize_age` unit tests in `search_views.rs` likewise cite
byte-parity pins taken from the legacy function. This is a byte-faithful port.

So my R1 was right to raise and appears to be answered. What I would still hold:

- The byte harness the first mate mandated stays mandatory. It is what would
  catch the remaining risk, which is no longer "did they attempt Rich" but "does
  a hand-written Python or shell tokenizer agree with Pygments token for token
  on real corpus content."
- **Colored coverage is thin for the surface it guards.** The branch's search
  corpus is 173 cases; 8 are colored, at widths 80 and 96. Eight cases is not
  much for a 3749-line renderer. Credit where due: two widths means the earlier
  fixed-width lesson was applied, which is exactly what would otherwise let a
  width bug through green tests. If the branch is adopted, added colored contract
  cases are where I would spend contract effort first — fenced code in several
  languages, long wrapped lines, and CJK or emoji width.

---

## 5. What I would do next, if the reproduction holds

1. Adopt the branch's module boundaries as written.
2. Land the shared line-walk primitive to collapse the two duplicated scanners
   (section 2). Small, mechanical, and it closes a live fork.
3. Keep the Python search implementation until the byte harness is green; delete
   it as a separate final step (section 3.2).
4. Decide explicitly whether the native default-session journey is in or out of
   this mission's scope (section 3.1). That is the first mate's call, not mine.
5. Add colored contract cases before trusting the colored slice (section 4).

If the reproduction does not hold, my map stands as written, with the
`search_views` / `session_render` seam corrected per section 1.
