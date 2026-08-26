# Review: native `ch parse` Rust rewrite (rust/model.rs, rust/codecs.rs, rust/main.rs + parse fixtures/tests)

Scope: standalone `ch parse` rewrite across ac6599cc..3078625 (b203317 pin contract, b2ce1fd move conversion native). Method: read all three Rust files in full, compared against the deleted Python twin (`xmlmd.py`, old `model.py`/`formatting.py`/`tools.py`/`commands/parse.py`) via a worktree oracle at ac6599cc, and ran byte-level parity probes against both implementations. Findings 1–5 were re-verified against a HEAD-built `.venv/bin/ch` after discovering the globally installed `ch` is a stale wip-cycle02 build (see finding 7); all reproduce identically on HEAD source.

## Confirmed parity bugs (native vs legacy Python, reachable from user input, unpinned by fixtures)

### 1. Empty-string optional fields are rendered instead of dropped (both directions)

Legacy guards every message metadata field with Python truthiness (`if self.branch_id:` in `get_wrapper_attrs`, `to_json_dict`, `_tool_use_to_json`). Native guards with `Option::is_some`. Input `{"branch": "", "status": "", "agent_id": "", "name": "", "model": ""}`:

- legacy XML: `<user-message i="1">`
- native XML: `<user-message i="1" branch="" status="">` / `<assistant-response ... agent_id="" name="" model="" custom_type="">`

Same divergence in the JSON direction (`branch`/`status` keys emitted vs omitted), verified against the oracle. Note the inconsistency: `render_tool_result_xml` *does* filter empty names (matching legacy), so this is an oversight on message-level fields, not a uniform policy. Affects: `branch`, `agent_id`, `subagent_type`, `name`, `model`, `custom_type`, `status`, `timestamp` (empty string errors first), `sourceToolUserId`, `inherited_context` is fine, tool-level `native_tool_call_id`.

Fix shape: filter empty strings where the Option is populated (`optional_string` or at attribute/key emission), matching Python truthiness.

### 2. Float overflow sentinel `"Infinity"` accepted as integer `original_index`

`original_index: 1e999` → legacy rejects ("Expected message 1.original_index to be an integer."); native renders `<user-message i="Infinity">`. Root cause chain: `canonicalize_json_numbers` renders overflow floats as the strings `Infinity`/`-Infinity`; `number_is_integer()` only scans for `.`/`e`/`E` characters, which `Infinity` lacks, so it passes the integer gate. Bonus damage: the emitted document fails native's own re-parse (`canonical_integer("Infinity")` errors) — self-breaking round-trip. Fix: make `number_is_integer` reject non-numeric sentinels (or track int-vs-float provenance instead of char-scanning).

### 3. `NaN` in unknown-tool embedded JSON body rejected; `Infinity` accepted

Legacy `json.loads` accepts bare `NaN`/`Infinity` constants and re-emits them. Native's `normalize_python_json_constants` rewrites `±Infinity → ±1e999999` for serde but omits `NaN`, so such bodies die with `Expecting value: line N column M`. Inconsistent half-measure inside one function — add the `NaN` case.

### 4. argparse long-option abbreviation implemented only for `--format`

`ch parse --h` and `--he`: legacy prints help, exit 0 (argparse prefix-matches to `--help`); native errors `unrecognized arguments: --h`, exit 2. Native hardcodes abbreviations for `--format` (`--f/--fo/--for/--form/--forma`) but not `--help`. Verified both sides.

## Lower-severity confirmed divergences

### 5. Lone surrogate escapes take a wrong, unpoliced path

JSON containing `\ud800`: validator accepts, serde rejects, `python_json_error`'s generic branch emits `unexpected end of hex escape` at a wrong position; legacy parses fine then fails later at stdout encoding with a UnicodeEncodeError traceback. This path also silently covers other validator/serde disagreements (e.g. nesting depth >128 hits serde's recursion limit that CPython doesn't have). Extreme edge, but it demonstrates the dual-parser design has no arbiter when the two disagree — the generic fallback branch can emit fabricated messages.

### 6. Fabricated BrokenPipe traceback bakes build-machine paths into shipped stderr

On `ch parse <big fixture> | head -c 100`, native prints a hardcoded fake Python traceback referencing `src/chats/cli.py:368`, `src/chats/commands/parse.py:146`, `resolve.py:405` — code deleted in this very range (`cmd_parse_json` is gone from HEAD; nothing at those paths/lines can ever produce this stack). Worse, the paths are baked via `env!("CARGO_MANIFEST_DIR")` at build time: builds print wherever they were compiled — observed `/Users/giladbarnea/dev/chats-cycle02-ox/src/...` (stale install) and `/Users/giladbarnea/dev/chats/src/...` (checkout build) on the same machine. This is weasel code emulating a ghost of pre-deletion behavior. Recommend honest EPIPE handling (silent exit or one-line native error); if byte-fidelity to some recorded oracle was required, that oracle no longer exists. Verified firing on both the installed and a HEAD-built binary.

## Test-suite finding

### 7. Contract suite is red today: installed-binary mismatch, not a launcher defect

`test_uncompleted_public_journeys_keep_exact_legacy_behavior` fails on this machine when run against `REAL_INSTALLED_CH` (`~/.local/bin/ch`): the stdout/stderr fixture assertions pass, but `assert b"python" in traced.stderr.lower()` finds zero dyld lines mentioning python. Attribution (corrected after peer pushback — my initial dyld-across-exec theory was wrong): `~/.local/bin/ch` is a stale wip-cycle02 build that differs from HEAD (see cli-router-commands' installed-binary-mismatch finding) and handles these journeys natively without exec'ing Python. Against a HEAD-built launcher (`.venv/bin/ch`) the trace shows Python across exec as expected, so the assertion itself is sound.

The review-worthy residue stands: the contract suite binds to PATH-installed binaries rather than freshly built checkout artifacts, so it can go red for reasons unrelated to HEAD (this failure) or stay silently green while validating stale bytes. Pinning these tests to a build-from-checkout artifact would remove the ambiguity. All other 59 tests pass.

## Non-findings worth recording (checked, clean)

- Float canonicalization: ryu output converted to Python repr rules matched byte-for-byte on every probed edge (1e16 boundary → `1e+16`, small values → `1e-05`, `-0.0`, `1e999`→`Infinity`, >u64 integers exact via BigInt).
- UTF-8 decode error messages match modern CPython exactly, including plural position ranges for truncated multibyte sequences and the shutil-style 80-col wrapping of error text.
- Tool schema table matches registry.py exactly (13 tools, attr/content keys, languages).
- Key-order parity handled correctly via serde_json `preserve_order`; `arbitrary_precision` handles big ints.
- Document-separator scanning, subagent-task text rules, header validation, `i` attribute parsing through Python `int()` semantics (underscores/plus/trim), outer-template bytes, empty-output suppression, exit codes (0/1/2), help text, unknown-argument errors, bad-separator junk-swallowing: all match the oracle.
- Tests are substantial, not hollow: 15-row × byte-exact dual-direction oracle corpus with stabilization assertions, matrix-completeness self-checks, pinned TZ/COLUMNS/NO_COLOR environment, wheel ownership proofs (Mach-O magic + RECORD hashes), dyld-based process-isolation proofs, plus hand-written behavioral cases (adjacency rule, ambiguous-input wrappers, provenance invisibility).

## Over-engineering observations (minor)

- The ~200-line hand-rolled `JsonValidator` coexists with `python_json_error`'s serde-error mapping — two systems for one job whose disagreement zone is exactly where finding #5 lives. Defensible for byte parity, but the fallback branch should fail loudly rather than fabricate positions.
- Small dead-defensive sprinkles: `FixedOffset::from_local_datetime(...).single().ok_or_else(invalid_isoformat)` (always Some for fixed offsets); `tool.content.clone().unwrap_or(Value::Null)` guarded by `has_content`.
