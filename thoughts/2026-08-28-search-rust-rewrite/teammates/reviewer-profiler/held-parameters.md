# What each of my gates parameterizes, and what it holds fixed

For `slice-reviewer`. A gate asks whether an implementation matches its oracle over a
parameterization. The question I cannot ask about my own gates is whether the parameterization
was the right one — so this is the input to that question: what each varies, and what it holds
fixed. **The held column is the answer to "what would this gate be blind to."**

Every held parameter listed here was found the expensive way, by something escaping through it.
The ones still unlisted are the ones that matter.

| gate | varies | holds fixed | known blind to |
| --- | --- | --- | --- |
| `performance_gates.py` | 6 command shapes, subject vs reference | corpus (`v1`), `COLUMNS=96`, `NO_COLOR=1`, warm cache, one machine | cold cache; any shape not in the six; concurrency |
| `freeze_references.py` | 4 widths, 9 ambient inputs × 2 settings × 2 conditions, 6 capability tiers, 4 stderr shapes | the fixture home, `TZ`, the query, one moment of the wall clock | any shape the fixture home cannot express — it held **zero non-ASCII characters** until I seeded one |
| `ambient_gate.py` | 9 env inputs × 2 settings, **both directions** | pty condition, `--color always`, width 80, **stdout** | everything only visible piped; everything on stderr |
| `ambient_gate_piped.py` | same 9 inputs | piped condition, colour default, **stdout** | everything only visible under a pty |
| `colored_width_gate.py` | 4 terminal widths | ambient environment, the query, one session set | content the fixtures cannot express; non-width layout inputs |
| `age_pairing_gate.py` | 7 `CH_NOW` instants → all 7 label units | the fixture ages, colour theme, width | a route that ignores `CH_NOW` — **guarded**, refuses below 5 units |
| `colour_capability_sweep.py` | 6 declared capability tiers | width 80, the query, stdout | tiers not declared through `TERM`/`COLORTERM` |
| `allocation_profile.py` | 5 payload sizes 8–96 MB | one session shape, one provider marker, absent-literal query | allocation behaviour on shapes other than an oversized final line |
| `economy_probe.py` | 3 economies, subject vs reference | corpus, one query per economy | the fourth economy (lazy short-circuiting) has no timing signature at all |
| `tool_visibility_oracle.py` | 1463 ordered spec lists × 5 tools | the tool alphabet I chose | a spec shape outside that alphabet |
| `calibrate_harness.py` | 14 mutation probes | the probe set itself | any dimension nobody thought to add — the objection is unanswerable by adding probes |

**Two held parameters common to all eleven, found by running this audit on `context-curator`'s
harness and turning it back on mine:**

- **`cwd`** — no gate sets it, so every subprocess inherits whatever directory I invoked from.
  It is not inert: `-d` resolves against cwd, and `pool_filter.passes_cwd` compares resolved
  paths. Held by accident in all eleven.
- **the `-d` filter is exercised on one branch only.** I first wrote here that no gate touches
  it; that was wrong within a minute of writing it — `economy_probe.py` passes
  `-d /nonexistent-directory` to measure filter-before-probe ordering. But that exercises the
  *no-match* branch: the filter excludes everything and the scan short-circuits. **Directory
  matching — a `-d` that resolves against cwd and selects real sessions — is exercised by no
  gate**, and that is the branch where `cwd` being inherited rather than set would bite.

## The six bounds, in the order I found them

1. **Inputs** — which variables are swept. Source reading proposed 7 ambient inputs; measurement
   confirmed 6, and 4 that Rich genuinely reads move nothing here.
2. **Conditions** — pty against pipe. The two see disjoint subsets; neither alone could have
   found more than three of five gaps.
3. **Categories** — `UNICODE_VERSION` is neither a colour input nor a width resolver. It decides
   how wide a *character* is, the layer between, and no sweep organised around those two
   categories reaches it however carefully it runs.
4. **Direction** — my sweeps asked "which inputs does the reference honour that the subject
   ignores". An input only the **subject** honours falls outside that by construction, and it is
   the worst class our gates face: the oracle does not vary along that axis at all, so **no
   comparison anywhere fails**. Now covered — both ambient sweeps report both directions, and
   the reverse list is empty against the branch. Falsified by swapping the roles: the four
   forward gaps move to the reverse list and the forward list empties.
5. **Streams** — `run_at_width` sent stderr to `DEVNULL`. Six gates inherited that and were
   structurally blind to a surface carrying a baseline divergence. **Nobody chose to hold it; it
   was a default in a helper.**

6. **Vocabulary** — the corpus cannot express the case. `session_render`'s body oracle was
   vacuously green because `flags_from` handled only `show_thinking`, so **no recorded case
   could ever set `show_tools`**. Not a thin corpus: an incapable one. Found by
   `lexer-tables` making the assertion fail on purpose.

   This is the same quantity as the reflow finding — *capacity in the corpus is not capacity in
   the cases a gate runs* — arriving one layer earlier. There the query selected only short
   bodies; here the fixture **generator** could not emit the flag at all. Both are invisible
   from the gate, and both are answered the same way: measure what the cases can express before
   trusting what they report.

**Streams is the one to look for**, and Direction and Vocabulary are the two that close
differently. A held parameter someone *chose* is usually documented. One *inherited from a
shared helper's default* is invisible in every downstream artifact, and the helper's own
docstring can be accurate the whole time. A held parameter someone chose is usually documented. A held
parameter inherited from a shared helper's default is invisible in every downstream artifact,
and the helper's own docstring can be entirely accurate the whole time.

## Two questions I would ask of my own gates and cannot

- **Is the parameterization derived or chosen?** Derived members can tell you they collapsed;
  chosen ones cannot. My tool-spec alphabet is chosen. My width-probe codepoints are derived,
  but only after two false negatives from choosing them.
- **Does the subject respond to each swept dimension?** A dimension is only swept if it moves the
  subject. `age_pairing_gate` guards this; the others do not, and a route ignoring an input looks
  identical to an input that does not matter.
