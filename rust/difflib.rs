//! CPython's `difflib.unified_diff`, vendored and corrected.
//!
//! **Provenance.** `difflib` 0.4.0 by Dima Kudosh, MIT licensed, from
//! <https://github.com/DimaKudosh/difflib>. Vendored rather than depended on because
//! it needs a correction, and a patched dependency that looks like an unpatched one is
//! the worst of both.
//!
//! **Why this exists.** `_edit_diff_renderable` renders an `Edit` tool call as a
//! coloured unified diff of `old_string` against `new_string`. Reproducing it means
//! reproducing `SequenceMatcher`, autojunk heuristic included. A hand port of
//! CPython's 687 lines was the alternative; this is about 300 and is exact.
//!
//! **What was left behind, because the product does not reach it:** `Differ`,
//! `get_close_matches`, `context_diff`, `format_range_context`, and `ratio`. Vendoring
//! them would mean gating them, and an ungated vendored function is a liability.
//!
//! ## The correction, and the number that decides it
//!
//! **`chain_second_seq`'s autojunk filter was inverted.** CPython adds every element
//! appearing in more than 1% of positions to `bpopular` and then **deletes** those
//! entries; the published crate **keeps exactly those and discards the rest**. So on
//! any sequence of 200 lines or more it matches against a handful of blank lines.
//!
//! **The real corpus cannot see it.** Almost no real `Edit` reaches the 200 lines
//! where autojunk engages, so a clean pass there proves almost nothing about the
//! heuristic most likely to be wrong. The corpus that decides is built from real file
//! bodies over 200 lines, where autojunk changes CPython's own answer a fifth of the
//! time. Re-derived on 2026-09-01 against the frozen corpora under
//! `tests/data/edit-diff/`:
//!
//! | | real `Edit` calls | long-body pairs |
//! | --- | --- | --- |
//! | as published | 2,998 / 3,000 — **99.93%** | 116 / 400 — **29.0%** |
//! | corrected | **3,000 / 3,000** | **400 / 400** |
//!
//! **These replace a set of figures whose instrument no longer existed.** The seat that
//! first measured this reported 99.93% and 28.0% for the published crate over corpora
//! of 2,814 and 900 — and left neither the corpora nor the probes behind. The numbers
//! above are an independent rebuild that lands within a point of them, which is
//! convergence rather than agreement, because nothing of the first measurement
//! survived to be copied. **A percentage whose instrument is gone is a claim, not a
//! measurement.**
//!
//! **The corrected side is 400 of 400 here where the lost measurement reported 99.67%
//! with a residue of 3.** Different corpora, so that is not the residue being fixed —
//! it is a corpus that does not contain it.
//!
//! Both corpora are gated by [`edit_diff_oracle_tests`], with the published behaviour
//! kept as a mutation the gate has to kill on one corpus and **watch survive** on the
//! other.
//!
//! **`find_longest_match`'s doubled extension pass is correct as written — do not
//! "fix" it.** CPython extends once over non-junk and once over junk; with
//! `isjunk=None` the junk set is empty, so its second pass extends over nothing and
//! the crate's repeated identical pass agrees. Implementing the two-phase form
//! faithfully was tried and made agreement **worse**, 99.67% to 92.56%.

use std::cmp::{max, min};
use std::collections::HashMap;
use std::fmt::Display;
use std::hash::Hash;

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd, Eq, Ord)]
pub struct Match {
    pub first_start: usize,
    pub second_start: usize,
    pub size: usize,
}

impl Match {
    fn new(first_start: usize, second_start: usize, size: usize) -> Match {
        Match { first_start, second_start, size }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Opcode {
    pub tag: &'static str,
    pub first_start: usize,
    pub first_end: usize,
    pub second_start: usize,
    pub second_end: usize,
}

impl Opcode {
    fn new(
        tag: &'static str,
        first_start: usize,
        first_end: usize,
        second_start: usize,
        second_end: usize,
    ) -> Opcode {
        Opcode { tag, first_start, first_end, second_start, second_end }
    }
}

pub trait Sequence: Eq + Hash {}
impl<T: Eq + Hash> Sequence for T {}

pub struct SequenceMatcher<'a, T: 'a + Sequence> {
    first_sequence: &'a [T],
    second_sequence: &'a [T],
    matching_blocks: Option<Vec<Match>>,
    opcodes: Option<Vec<Opcode>>,
    second_sequence_elements: HashMap<&'a T, Vec<usize>>,
    /// Run the published crate's inverted autojunk filter instead of CPython's.
    ///
    /// **A mutation the gate has to kill**, kept beside the code it mutates so the
    /// falsifier cannot drift away from the thing it falsifies.
    #[cfg(test)]
    inverted_autojunk: bool,
}

impl<'a, T: Sequence> SequenceMatcher<'a, T> {
    pub fn new(first_sequence: &'a [T], second_sequence: &'a [T]) -> SequenceMatcher<'a, T> {
        let mut matcher = SequenceMatcher {
            first_sequence,
            second_sequence,
            matching_blocks: None,
            opcodes: None,
            second_sequence_elements: HashMap::new(),
            #[cfg(test)]
            inverted_autojunk: false,
        };
        matcher.chain_second_seq();
        matcher
    }

    /// The published crate's behaviour, for the gate's mutation only.
    #[cfg(test)]
    pub fn with_inverted_autojunk(
        first_sequence: &'a [T],
        second_sequence: &'a [T],
    ) -> SequenceMatcher<'a, T> {
        let mut matcher = SequenceMatcher::new(first_sequence, second_sequence);
        matcher.inverted_autojunk = true;
        matcher.chain_second_seq();
        matcher
    }

    /// `SequenceMatcher.__chain_b`: index the second sequence, then purge the
    /// elements that are too popular to be worth matching against.
    ///
    /// **`isjunk` is always `None` here**, because `difflib.unified_diff` builds its
    /// matcher as `SequenceMatcher(None, a, b)`. The junk-purge half of CPython's
    /// method is therefore dead and is not reproduced; `autojunk` defaults to true and
    /// is.
    fn chain_second_seq(&mut self) {
        let second_sequence = self.second_sequence;
        let mut second_sequence_elements: HashMap<&'a T, Vec<usize>> = HashMap::new();
        for (index, item) in second_sequence.iter().enumerate() {
            second_sequence_elements.entry(item).or_default().push(index);
        }
        let length = second_sequence.len();
        if length >= 200 {
            // `ntest = n // 100 + 1`, in integers. The published crate floors an `f32`
            // division, which agrees here and stops agreeing above the mantissa.
            let test_length = length / 100 + 1;
            #[cfg(test)]
            let keep = |count: usize| {
                if self.inverted_autojunk {
                    count > test_length
                } else {
                    count <= test_length
                }
            };
            // **CPython deletes the popular elements. The published crate keeps
            // exactly those.** One operator, and 28% correct on long input.
            #[cfg(not(test))]
            let keep = |count: usize| count <= test_length;
            second_sequence_elements.retain(|_, indexes| keep(indexes.len()));
        }
        self.second_sequence_elements = second_sequence_elements;
    }

    pub fn find_longest_match(
        &self,
        first_start: usize,
        first_end: usize,
        second_start: usize,
        second_end: usize,
    ) -> Match {
        let first_sequence = &self.first_sequence;
        let second_sequence = &self.second_sequence;
        let second_sequence_elements = &self.second_sequence_elements;
        let (mut best_i, mut best_j, mut best_size) = (first_start, second_start, 0);
        let mut j2len: HashMap<usize, usize> = HashMap::new();
        for (i, item) in first_sequence.iter().enumerate().take(first_end).skip(first_start) {
            let mut new_j2len: HashMap<usize, usize> = HashMap::new();
            if let Some(indexes) = second_sequence_elements.get(item) {
                for j in indexes {
                    let j = *j;
                    if j < second_start {
                        continue;
                    }
                    if j >= second_end {
                        break;
                    }
                    let mut size = 0;
                    if j > 0
                        && let Some(previous) = j2len.get(&(j - 1))
                    {
                        size = *previous;
                    }
                    size += 1;
                    new_j2len.insert(j, size);
                    if size > best_size {
                        best_i = i + 1 - size;
                        best_j = j + 1 - size;
                        best_size = size;
                    }
                }
            }
            j2len = new_j2len;
        }
        // **Two identical passes, and that is the faithful shape here.** CPython runs
        // one extension over non-junk and a second over junk; with `isjunk=None` the
        // junk set is empty and its second pass extends over nothing. Rewriting this
        // into CPython's literal two-phase form was measured at 92.56% against this
        // form's 99.67%.
        for _ in 0..2 {
            while best_i > first_start
                && best_j > second_start
                && first_sequence.get(best_i - 1) == second_sequence.get(best_j - 1)
            {
                best_i -= 1;
                best_j -= 1;
                best_size += 1;
            }
            while best_i + best_size < first_end
                && best_j + best_size < second_end
                && first_sequence.get(best_i + best_size) == second_sequence.get(best_j + best_size)
            {
                best_size += 1;
            }
        }
        Match::new(best_i, best_j, best_size)
    }

    pub fn get_matching_blocks(&mut self) -> Vec<Match> {
        if let Some(blocks) = self.matching_blocks.as_ref() {
            return blocks.clone();
        }
        let (first_length, second_length) = (self.first_sequence.len(), self.second_sequence.len());
        let mut matches = Vec::new();
        let mut queue = vec![(0, first_length, 0, second_length)];
        while let Some((first_start, first_end, second_start, second_end)) = queue.pop() {
            let found = self.find_longest_match(first_start, first_end, second_start, second_end);
            if found.size == 0 {
                continue;
            }
            if first_start < found.first_start && second_start < found.second_start {
                queue.push((first_start, found.first_start, second_start, found.second_start));
            }
            if found.first_start + found.size < first_end
                && found.second_start + found.size < second_end
            {
                queue.push((
                    found.first_start + found.size,
                    first_end,
                    found.second_start + found.size,
                    second_end,
                ));
            }
            matches.push(found);
        }
        matches.sort();
        let (mut first_start, mut second_start, mut size) = (0, 0, 0);
        let mut non_adjacent = Vec::new();
        for found in &matches {
            if first_start + size == found.first_start && second_start + size == found.second_start
            {
                size += found.size;
            } else {
                if size != 0 {
                    non_adjacent.push(Match::new(first_start, second_start, size));
                }
                first_start = found.first_start;
                second_start = found.second_start;
                size = found.size;
            }
        }
        if size != 0 {
            non_adjacent.push(Match::new(first_start, second_start, size));
        }
        non_adjacent.push(Match::new(first_length, second_length, 0));
        self.matching_blocks = Some(non_adjacent.clone());
        non_adjacent
    }

    pub fn get_opcodes(&mut self) -> Vec<Opcode> {
        if let Some(opcodes) = self.opcodes.as_ref() {
            return opcodes.clone();
        }
        let mut opcodes = Vec::new();
        let (mut i, mut j) = (0, 0);
        for found in self.get_matching_blocks() {
            let tag = if i < found.first_start && j < found.second_start {
                "replace"
            } else if i < found.first_start {
                "delete"
            } else if j < found.second_start {
                "insert"
            } else {
                ""
            };
            if !tag.is_empty() {
                opcodes.push(Opcode::new(tag, i, found.first_start, j, found.second_start));
            }
            i = found.first_start + found.size;
            j = found.second_start + found.size;
            if found.size != 0 {
                opcodes.push(Opcode::new("equal", found.first_start, i, found.second_start, j));
            }
        }
        self.opcodes = Some(opcodes.clone());
        opcodes
    }

    pub fn get_grouped_opcodes(&mut self, n: usize) -> Vec<Vec<Opcode>> {
        let mut res = Vec::new();
        let mut codes = self.get_opcodes();
        if codes.is_empty() {
            codes.push(Opcode::new("equal", 0, 1, 0, 1));
        }
        if codes.first().expect("seeded above").tag == "equal" {
            let opcode = codes.first_mut().expect("seeded above");
            opcode.first_start = max(opcode.first_start, opcode.first_end.saturating_sub(n));
            opcode.second_start = max(opcode.second_start, opcode.second_end.saturating_sub(n));
        }
        if codes.last().expect("seeded above").tag == "equal" {
            let opcode = codes.last_mut().expect("seeded above");
            opcode.first_end = min(opcode.first_start + n, opcode.first_end);
            opcode.second_end = min(opcode.second_start + n, opcode.second_end);
        }
        let nn = n + n;
        let mut group: Vec<Opcode> = Vec::new();
        for code in &codes {
            let (mut first_start, mut second_start) = (code.first_start, code.second_start);
            if code.tag == "equal" && code.first_end - code.first_start > nn {
                group.push(Opcode::new(
                    code.tag,
                    code.first_start,
                    min(code.first_end, code.first_start + n),
                    code.second_start,
                    min(code.second_end, code.second_start + n),
                ));
                res.push(std::mem::take(&mut group));
                first_start = max(first_start, code.first_end.saturating_sub(n));
                second_start = max(second_start, code.second_end.saturating_sub(n));
            }
            group.push(Opcode::new(
                code.tag,
                first_start,
                code.first_end,
                second_start,
                code.second_end,
            ));
        }
        // CPython's `if group and not (len(group)==1 and group[0][0] == 'equal')`. The
        // published crate yields an empty group where CPython yields none — reachable
        // only from an empty `codes`, which the seeding above rules out, and corrected
        // because a vendored divergence nobody can reach is still a divergence.
        if !group.is_empty() && !(group.len() == 1 && group[0].tag == "equal") {
            res.push(group);
        }
        res
    }
}

/// `_format_range_unified`.
fn format_range_unified(start: usize, end: usize) -> String {
    let mut beginning = start + 1;
    let length = end - start;
    if length == 1 {
        return beginning.to_string();
    }
    if length == 0 {
        beginning -= 1;
    }
    format!("{beginning},{length}")
}

/// `difflib.unified_diff`, as CPython yields it.
///
/// The published crate always writes a tab before an empty file date and always ends
/// the three header lines with a newline; CPython omits the tab when the date is empty
/// and appends `lineterm`, which the product passes as `""`. The product drops those
/// header lines anyway, so the correction is for the next caller rather than this one.
pub fn unified_diff<T: Sequence + Display>(
    first_sequence: &[T],
    second_sequence: &[T],
    from_file: &str,
    to_file: &str,
    from_file_date: &str,
    to_file_date: &str,
    n: usize,
    lineterm: &str,
) -> Vec<String> {
    let matcher = SequenceMatcher::new(first_sequence, second_sequence);
    unified_diff_from(
        matcher,
        first_sequence,
        second_sequence,
        from_file,
        to_file,
        from_file_date,
        to_file_date,
        n,
        lineterm,
    )
}

/// The body of [`unified_diff`], with the matcher supplied.
///
/// Split out so the gate can run the **published crate's** matcher through the same
/// emission and watch it fail, rather than asserting that it would.
#[allow(clippy::too_many_arguments)]
fn unified_diff_from<T: Sequence + Display>(
    mut matcher: SequenceMatcher<'_, T>,
    first_sequence: &[T],
    second_sequence: &[T],
    from_file: &str,
    to_file: &str,
    from_file_date: &str,
    to_file_date: &str,
    n: usize,
    lineterm: &str,
) -> Vec<String> {
    let mut res = Vec::new();
    let mut started = false;
    for group in &matcher.get_grouped_opcodes(n) {
        if !started {
            started = true;
            let from_date = if from_file_date.is_empty() {
                String::new()
            } else {
                format!("\t{from_file_date}")
            };
            let to_date = if to_file_date.is_empty() {
                String::new()
            } else {
                format!("\t{to_file_date}")
            };
            res.push(format!("--- {from_file}{from_date}{lineterm}"));
            res.push(format!("+++ {to_file}{to_date}{lineterm}"));
        }
        let (first, last) = (
            group.first().expect("a group is never empty"),
            group.last().expect("a group is never empty"),
        );
        let first_range = format_range_unified(first.first_start, last.first_end);
        let second_range = format_range_unified(first.second_start, last.second_end);
        res.push(format!("@@ -{first_range} +{second_range} @@{lineterm}"));
        for code in group {
            if code.tag == "equal" {
                for item in
                    first_sequence.iter().take(code.first_end).skip(code.first_start)
                {
                    res.push(format!(" {item}"));
                }
                continue;
            }
            if code.tag == "replace" || code.tag == "delete" {
                for item in
                    first_sequence.iter().take(code.first_end).skip(code.first_start)
                {
                    res.push(format!("-{item}"));
                }
            }
            if code.tag == "replace" || code.tag == "insert" {
                for item in
                    second_sequence.iter().take(code.second_end).skip(code.second_start)
                {
                    res.push(format!("+{item}"));
                }
            }
        }
    }
    res
}

/// The two frozen corpora, and the mutation that separates them.
///
/// **The percentages in this module's header were reported by a seat that no longer
/// exists, with no corpus and no probe behind them.** A percentage whose instrument is
/// gone is a claim, not a measurement — which is why these fixtures exist and why the
/// inputs and CPython's answers are stored together. The Python route that produced
/// them is what the cutover deletes.
#[cfg(test)]
mod edit_diff_oracle_tests {
    use super::*;
    use crate::model::python_value_string;
    use crate::session_render::python_splitlines;
    use serde_json::Value;
    use std::path::PathBuf;

    fn corpus(name: &str) -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/edit-diff")
            .join(name);
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!(
                "the Edit-diff corpus is missing at {}: {error}. Rebuild it with \
                 `teammates/cutover-finisher/probes/generate_edit_diff_oracle.py`.",
                path.display()
            )
        });
        serde_json::from_slice(&bytes).expect("the Edit-diff corpus is valid JSON")
    }

    /// `str(input_data.get("old_string", ""))`, over the raw recorded value. A missing
    /// key is the empty string; a JSON `null` is `"None"`.
    fn side(case: &Value, key: &str) -> String {
        case.get(key).map_or_else(String::new, python_value_string)
    }

    fn ours(old: &str, new: &str) -> Vec<String> {
        let first = python_splitlines(old);
        let second = python_splitlines(new);
        unified_diff(&first, &second, "", "", "", "", 2, "")
    }

    fn as_published(old: &str, new: &str) -> Vec<String> {
        let first = python_splitlines(old);
        let second = python_splitlines(new);
        let matcher = SequenceMatcher::with_inverted_autojunk(&first, &second);
        unified_diff_from(matcher, &first, &second, "", "", "", "", 2, "")
    }

    fn recorded(case: &Value) -> Vec<String> {
        case["expected"]
            .as_array()
            .expect("a recorded diff")
            .iter()
            .map(|line| line.as_str().expect("a diff line").to_string())
            .collect()
    }

    fn digest(lines: &[String]) -> String {
        // The generator hashes `"\n".join(expected)`.
        sha256_hex(lines.join("\n").as_bytes())
    }

    /// SHA-256 in twenty lines, because the crate has `sha1` for git object ids and
    /// pulling a second hash crate to compare a fixture is not worth a dependency.
    fn sha256_hex(bytes: &[u8]) -> String {
        const K: [u32; 64] = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
            0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
            0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
            0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
            0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
            0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
            0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
            0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
            0xc67178f2,
        ];
        let mut state: [u32; 8] = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
            0x5be0cd19,
        ];
        let mut message = bytes.to_vec();
        let length = (bytes.len() as u64) * 8;
        message.push(0x80);
        while message.len() % 64 != 56 {
            message.push(0);
        }
        message.extend_from_slice(&length.to_be_bytes());
        for chunk in message.chunks(64) {
            let mut w = [0u32; 64];
            for (index, word) in chunk.chunks(4).enumerate() {
                w[index] = u32::from_be_bytes([word[0], word[1], word[2], word[3]]);
            }
            for index in 16..64 {
                let s0 = w[index - 15].rotate_right(7)
                    ^ w[index - 15].rotate_right(18)
                    ^ (w[index - 15] >> 3);
                let s1 = w[index - 2].rotate_right(17)
                    ^ w[index - 2].rotate_right(19)
                    ^ (w[index - 2] >> 10);
                w[index] = w[index - 16]
                    .wrapping_add(s0)
                    .wrapping_add(w[index - 7])
                    .wrapping_add(s1);
            }
            let mut v = state;
            for index in 0..64 {
                let s1 = v[4].rotate_right(6) ^ v[4].rotate_right(11) ^ v[4].rotate_right(25);
                let choose = (v[4] & v[5]) ^ ((!v[4]) & v[6]);
                let temp1 = v[7]
                    .wrapping_add(s1)
                    .wrapping_add(choose)
                    .wrapping_add(K[index])
                    .wrapping_add(w[index]);
                let s0 = v[0].rotate_right(2) ^ v[0].rotate_right(13) ^ v[0].rotate_right(22);
                let majority = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
                let temp2 = s0.wrapping_add(majority);
                v = [
                    temp1.wrapping_add(temp2),
                    v[0],
                    v[1],
                    v[2],
                    v[3].wrapping_add(temp1),
                    v[4],
                    v[5],
                    v[6],
                ];
            }
            for (slot, value) in state.iter_mut().zip(v) {
                *slot = slot.wrapping_add(value);
            }
        }
        state.iter().map(|word| format!("{word:08x}")).collect()
    }

    #[test]
    fn every_real_edit_reproduces_cpython() {
        let corpus = corpus("real-edits.json");
        let cases = corpus["cases"].as_array().expect("recorded Edit calls");
        let mut failures = Vec::new();
        for (index, case) in cases.iter().enumerate() {
            let old = side(case, "old_string");
            let new = side(case, "new_string");
            if ours(&old, &new) != recorded(case) {
                failures.push(index);
            }
        }
        assert!(
            cases.len() >= 2500,
            "Only {} real Edit calls are recorded. A shrunken corpus passes vacuously.",
            cases.len()
        );
        assert!(
            failures.is_empty(),
            "{} of {} real Edit calls disagree with CPython, first at index {}.",
            failures.len(),
            cases.len(),
            failures[0]
        );
    }

    /// **What this corpus cannot say.** Almost no real `Edit` reaches the 200 lines
    /// where autojunk engages, so a clean pass above proves the matcher and says
    /// nothing about the heuristic most likely to be wrong.
    #[test]
    fn the_real_corpus_cannot_reach_autojunk() {
        let corpus = corpus("real-edits.json");
        let over = corpus["over_200_lines"].as_u64().expect("the recorded count");
        let total = corpus["cases"].as_array().expect("cases").len() as u64;
        assert!(
            over * 20 < total,
            "{over} of {total} real Edit calls now reach 200 lines. This assertion \
             exists to keep the *reason* for the second corpus true: if real Edits \
             started exercising autojunk, `long-bodies.json` would no longer be the \
             only thing grading it and this gate's shape should be revisited."
        );
    }

    #[test]
    fn every_long_body_reproduces_cpython() {
        let corpus = corpus("long-bodies.json");
        let cases = corpus["cases"].as_array().expect("recorded pairs");
        let mut failures: Vec<String> = Vec::new();
        for (index, case) in cases.iter().enumerate() {
            let old = side(case, "old_string");
            let new = side(case, "new_string");
            let produced = ours(&old, &new);
            let expected = case["expected_digest"].as_str().expect("a recorded digest");
            if digest(&produced) == expected {
                continue;
            }
            let readable = case.get("expected").map(|_| recorded(case));
            failures.push(match readable {
                Some(lines) => format!(
                    "case {index}: {} lines produced against {} recorded\n  first \
                     recorded: {:?}\n  first ours:     {:?}",
                    produced.len(),
                    lines.len(),
                    lines.first(),
                    produced.first()
                ),
                None => format!("case {index}: digest differs (no readable copy kept)"),
            });
        }
        assert!(
            cases.len() >= 350,
            "Only {} long-body pairs are recorded. A shrunken corpus passes vacuously.",
            cases.len()
        );
        assert!(
            failures.is_empty(),
            "{} of {} long-body pairs disagree with CPython:\n{}",
            failures.len(),
            cases.len(),
            failures[..failures.len().min(3)].join("\n")
        );
    }

    /// The corpus's own discriminating power, measured rather than assumed.
    #[test]
    fn the_long_corpus_reaches_autojunk() {
        let corpus = corpus("long-bodies.json");
        let matters = corpus["autojunk_matters"].as_u64().expect("the recorded count");
        let total = corpus["cases"].as_array().expect("cases").len() as u64;
        assert!(
            matters * 10 >= total,
            "Autojunk changes CPython's own answer on only {matters} of {total} pairs. \
             Below a tenth this corpus is merely long rather than discriminating, and \
             the mutation below could die for some other reason."
        );
    }

    /// **The falsification, and the point of having two corpora.** The published
    /// crate's inverted filter survives the real corpus almost untouched and is
    /// slaughtered by the long one. A gate built only from real Edits would have
    /// shipped it.
    #[test]
    fn the_published_autojunk_filter_dies_on_the_long_corpus_and_survives_the_real_one() {
        let long = corpus("long-bodies.json");
        let long_cases = long["cases"].as_array().expect("cases");
        let long_killed = long_cases
            .iter()
            .filter(|case| {
                let old = side(case, "old_string");
                let new = side(case, "new_string");
                digest(&as_published(&old, &new))
                    != case["expected_digest"].as_str().expect("a digest")
            })
            .count();
        assert!(
            long_killed * 2 > long_cases.len(),
            "The published inverted filter is caught on only {long_killed} of {} \
             long-body pairs. This gate exists to kill that mutation; if it survives, \
             the correction in `chain_second_seq` is no longer being tested.",
            long_cases.len()
        );

        let real = corpus("real-edits.json");
        let real_cases = real["cases"].as_array().expect("cases");
        let real_killed = real_cases
            .iter()
            .filter(|case| {
                let old = side(case, "old_string");
                let new = side(case, "new_string");
                as_published(&old, &new) != recorded(case)
            })
            .count();
        assert!(
            real_killed * 100 < real_cases.len(),
            "The published inverted filter is caught on {real_killed} of {} real Edit \
             calls. **That number is supposed to be near zero** — it is the reason the \
             second corpus had to be built, and if the real corpus started catching \
             this mutation the argument for `long-bodies.json` would need restating \
             rather than quietly inheriting.",
            real_cases.len()
        );
    }
}
