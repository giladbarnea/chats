# The 16 files, classified by whether the SUBJECT survives

**Built by `deletion-owner`, 2026-09-02, on `search-firstmate`'s ruling 1: classify by
whether the subject survives, not by whether the import breaks. Reported before acting.**

**Derived, not read.** `probes/classify_tests.py` walks every test function in the 16
files, takes the vanishing symbols from the three search-only modules' own ASTs, and
marks a test as reaching the authority when its own body or a module-level helper it
calls names one of them. **It walks the tree rather than the top level** — one file
nests its tests in a class and a top-level scan reported it as holding no tests at all.

**The ruling named two buckets. The measurement produced three, and the third changes
what is owed.**

---

## A — WHOLE FILE, the subject dies. Delete the file. No successor owed.

*These exercise Python search code. **Deleting a test for code that no longer exists is
not deleting a gate.***

| file | test functions | collected |
| --- | ---: | ---: |
| `test_search_orchestration.py` | 37 | **78** |
| `test_search_operators.py` | 22 | **22** |
| `test_search_cli_args.py` | 8 | **8** |
| `test_search_visibility.py` | 7 | **7** |
| `test_search_output_modes.py` | 6 | **6** |
| `test_session_scan.py` | 2 | **2** |
| `test_message_selection.py` | 1 | **1** |
| | | **124** |

`test_message_selection.py` is the one worth a sentence: its subject reads as *message
role selection*, which survives in parse. **Its vehicle is `SessionScan`, which does
not**, and role selection in parse is covered by `test_parse_visibility_flags.py`.

## B — MIXED, the file survives and only its search tests die. Surgical removal.

*Nothing is owed here either: the tests that go have subjects that go, and the ones that
stay never touched search.*

| file | tests that go | tests that stay |
| --- | ---: | ---: |
| `test_colored_rendering.py` | 3 | **27** |
| `test_provider_filter.py` | 10 | **4** |
| `test_search_case_sensitivity.py` | 5 | **1** |
| `test_provider_metadata.py` | 4 | **8** |
| `test_session_search_space.py` | 3 | **4** |
| `test_hook_additional_context.py` | 2 | **5** |
| `test_claude_agent_detection.py` | 1 | **9** |
| `test_metadata_timestamps.py` | 1 | **1** |
| | **29** | **59** |

**`test_colored_rendering.py` was flagged as the one to look at hardest, and the answer
is the opposite of the worry.** Its own docstring says it pins observable output through
`cmd_parse` **and** `cmd_search`. **27 of its 30 tests are the parse half and survive
untouched.** The three that go are `test_colored_search_banner_leads_with_title`,
`test_colored_search_labels_bash_result_match_as_bash` and
`test_colored_search_highlights_matched_term`. *A file whose name says which side it
grades would have been classified wrongly; the per-test measurement is what answered it.*

## C — ⚠ REPOINT, not freeze. The subject survives and Python was never its oracle.

**`test_native_ascii_candidate_scanner.py`, 18 functions, 59 collected.**

**This corrects the premise of the ruling it was given, and the correction is in the
product's favour.** It was described as grading the native scanner *against Python's*
`_file_contains_ascii`. **There is no Python implementation to grade against.** All three
imported names are marshalling wrappers over the PyO3 extension:

    _file_contains_ascii            → _native.file_contains_ascii            (os.fsencode)
    _file_contains_ascii_json_strings → _native.file_contains_ascii_json_strings
                                        (os.fsencode, and `except OSError: return True`)
    _files_contain_ascii_json_strings → _native.files_contain_ascii_json_strings
                                        (os.fsencode over a list)

**So `commands/search.py` is this file's ACCESS PATH, not its oracle.** The subject is
the Rust scanner, which the `ch` binary uses through the same `scanner` module.
**Decision 6 does not apply: there is no consultation to store, because nothing is being
consulted.** The successor is **a repoint to `chats._native`**, and
`_native` exports all three names today.

**⚠ One test in this file does lose its subject.**
`test_logical_json_candidate_file_errors_defer_to_semantic_reads` asserts the *wrapper's*
`except OSError: return True` policy, which is Python and goes.
`test_candidate_file_errors_propagate_as_os_errors` **survives the repoint** — the
un-caught error it asserts comes out of the native function itself.

---

## The totals

    A  delete the file          7 files    124 collected tests
    B  remove the search tests  8 files     29 of 88 tests go
    C  repoint to `_native`     1 file      59 collected tests KEPT
    ------------------------------------------------------------
       lost                                153 collected tests
       kept that a file-level rule would have lost              118

**A file-level deletion would have thrown away 118 working tests**, 59 of them the only
in-tree coverage of the native scanner through its Python boundary.

## What is NOT owed, stated because an absence reads as an omission

**No frozen successor is owed by any of the 16.** Bucket A's subjects are gone, bucket
B's survivors never touched search, and bucket C was never graded against Python.
**That is a measured answer, not a decision to skip the work** — the one file that
looked like decision 6 was measured and is not.

## Where the native coverage is thinnest, reported and not acted on

**`test_search_operators.py`'s 22 tests are the boolean `AND`/`OR`/`NOT` grammar**, and
they are the largest single semantic surface in bucket A. Their successor is the Rust
side plus whatever the 252-case contract corpus covers. **Nobody has measured how many
contract cases carry an operator**, and this seat did not either — it is parity work the
brief excludes. *Named so the thinnest point is on the record rather than assumed even.*
