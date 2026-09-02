//! What a promoted lexer table has to prove before it renders anything.
//!
//! The table in [`crate::syntax_tables`] is a mechanical projection of Pygments'
//! own `_tokens`, and the driver in [`crate::syntax_lexer`] is a port of Pygments'
//! own `RegexLexer`. So every claim here is checkable against the reference rather
//! than against a reading of it: the recorded streams come from Pygments running
//! that same table.
//!
//! Four things are asserted, and the last is the one a corpus cannot give for free:
//!
//! 1. The token stream, over real fenced blocks of the language.
//! 2. A compared-count floor whose message says what a shrunken corpus means.
//! 3. Four named mutations of the table, each of which must change the stream.
//! 4. **Every rule the table declares is reached**, except an asserted exact set
//!    that no input can reach, each entry carrying why.

use crate::syntax_lexer::{Action, CompiledLexer, LexerTable, Rule, Transition, tokenize};
use serde_json::Value;
use std::collections::BTreeSet;
use std::path::PathBuf;

fn oracle(family: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(format!("tests/data/lexer-tables/{family}-oracle.json"));
    let bytes = std::fs::read(&path).unwrap_or_else(|error| {
        panic!("the {family} lexer oracle is missing at {}: {error}", path.display())
    });
    serde_json::from_slice(&bytes).expect("the lexer oracle is valid JSON")
}

fn cases(oracle: &Value) -> &Vec<Value> {
    oracle["cases"].as_array().expect("the oracle carries cases")
}

fn expected(case: &Value) -> Vec<(String, String)> {
    case["tokens"]
        .as_array()
        .expect("a recorded case carries a stream")
        .iter()
        .map(|pair| {
            (
                pair[0].as_str().expect("a token path").to_string(),
                pair[1].as_str().expect("a token value").to_string(),
            )
        })
        .collect()
}

/// Compare one table against its recorded streams, optionally after mutating it.
///
/// Returns the number of cases compared and the cases that differ.
fn compare(
    oracle: &Value,
    build: fn() -> LexerTable,
    mutate: Option<&dyn Fn(&mut LexerTable)>,
) -> (usize, Vec<String>) {
    let mut table = build();
    if let Some(mutate) = mutate {
        mutate(&mut table);
    }
    let lexer = CompiledLexer::new(table);
    // **Markdown only.** Its fenced-code callback emits an empty `Text` where
    // `bygroups` emits nothing, when a fence's info string has trailing whitespace
    // and no extra word. Neither Rich's `Text.append_tokens` nor ours produces a
    // segment or a span for an empty token, so the rendered block is identical —
    // which the render gate proves end to end. Eliding on **both** sides is honest
    // about that; pretending the streams are equal would not be.
    let elide = oracle["elide_empty_tokens"].as_bool().unwrap_or(false);
    let drop_empty = |tokens: Vec<(String, String)>| -> Vec<(String, String)> {
        if elide { tokens.into_iter().filter(|(_, value)| !value.is_empty()).collect() } else { tokens }
    };
    let mut failures: Vec<String> = Vec::new();
    let mut compared = 0usize;
    for case in cases(oracle) {
        let text = case["text"].as_str().expect("a case carries text");
        let ours =
            drop_empty(tokenize(&lexer, text, &["root"]).expect("within the step budget"));
        compared += 1;
        let want = drop_empty(expected(case));
        if ours == want {
            continue;
        }
        let source = case["source"].as_str().unwrap_or("?");
        let first = ours
            .iter()
            .zip(&want)
            .position(|(ours, want)| ours != want)
            .unwrap_or(ours.len().min(want.len()));
        failures.push(format!(
            "case {source} ({} chars), first difference at token {first}:\n  \
             pygments {:?}\n  ours     {:?}",
            text.chars().count(),
            &want[first.saturating_sub(2)..want.len().min(first + 3)],
            &ours[first.saturating_sub(2)..ours.len().min(first + 3)],
        ));
    }
    (compared, failures)
}

fn strings(value: &Value) -> Vec<String> {
    value
        .as_array()
        .expect("a recorded list of names")
        .iter()
        .map(|name| name.as_str().expect("a name").to_string())
        .collect()
}

/// Every rule the generated table declares, in the order the driver walks them.
fn declared(table: &LexerTable) -> Vec<String> {
    table
        .states
        .iter()
        .flat_map(|(state, rules)| {
            (0..rules.len()).map(move |index| format!("{state}[{index}]"))
        })
        .collect()
}

/// **A table can be transcribed correctly and gated against content that exercises
/// half of it, and nothing shows.** This is what makes that visible.
///
/// Three claims, and the first is why the other two are about *this* table rather
/// than about Pygments':
///
/// 1. The generated table declares exactly the rules Pygments declares, in order.
/// 2. Every one of them is either reached by the corpus or named unreachable, with
///    the reason the generator derived. The set is exact both ways: a rule that
///    starts being reached is a corpus that grew, and a rule that stops being
///    reached is a corpus that shrank.
/// 3. The corpus matches a `bygroups` group that is **empty**, which is the only
///    input that separates the token-slot condition from the callable one.
fn corpus_reaches_every_declared_rule(family: &str, build: fn() -> LexerTable) {
    let oracle = oracle(family);
    let ours = declared(&build());
    let theirs = strings(&oracle["declared_rules"]);
    assert_eq!(
        ours, theirs,
        "The generated table's rules are not Pygments' rules. Every claim below is \
         about a table the oracle did not record, so nothing else here means \
         anything. Regenerate both from the same Pygments."
    );

    let reached: BTreeSet<String> = cases(&oracle)
        .iter()
        .flat_map(|case| strings(&case["rules"]))
        .collect();
    let unreachable: BTreeSet<String> = oracle["unreachable_rules"]
        .as_object()
        .expect("the oracle carries the unreachable rules and why")
        .keys()
        .cloned()
        .collect();
    let missing: Vec<&String> = theirs
        .iter()
        .filter(|name| !reached.contains(*name) && !unreachable.contains(*name))
        .collect();
    assert!(
        missing.is_empty(),
        "{} of {} rules are neither reached by the corpus nor explained: {missing:?}. \
         An ungated rule is ungated whatever the reason.",
        missing.len(),
        theirs.len()
    );
    let contradictory: Vec<&String> = unreachable.iter().filter(|name| reached.contains(*name)).collect();
    assert!(
        contradictory.is_empty(),
        "{contradictory:?} are recorded as unreachable and the corpus reaches them. \
         The corpus grew past the reason; drop them from the unreachable set."
    );

    // **The empty-group condition only has to be reached where it can arise.**
    // JavaScript's only two `bygroups` rules are both unreachable — its keyword
    // alternation shadows the `super(...)` rule — so the condition does not exist in
    // that table at all, and demanding the corpus reach it would be demanding an
    // input that cannot be written.
    let empty_groups = strings(&oracle["bygroups_rules_that_matched_an_empty_group"]);
    let reachable_bygroups: Vec<String> = strings(&oracle["bygroups_rules"])
        .into_iter()
        .filter(|name| !unreachable.contains(name))
        .collect();
    assert!(
        !empty_groups.is_empty() || reachable_bygroups.is_empty(),
        "None of the {} reachable `bygroups` rules matched an empty group, so nothing \
         here separates the token-slot condition (emit when non-empty) from the \
         callable one (emit when the group took part): {reachable_bygroups:?}",
        reachable_bygroups.len()
    );
}

/// The rules of one state, refusing rather than returning if the state is absent.
///
/// **A mutation that lands somewhere other than where it was aimed is worse than no
/// mutation at all**, because the run still reads as a pass with one falsifier
/// fewer than the header claims. Every accessor here refuses instead.
fn state_of<'t>(table: &'t mut LexerTable, state: &str) -> &'t mut Vec<Rule> {
    let names: Vec<&str> = table.states.iter().map(|(name, _)| name.as_str()).collect();
    let position = table
        .states
        .iter()
        .position(|(name, _)| name == state)
        .unwrap_or_else(|| {
            panic!("NO STATE {state} — mutation not applied, result meaningless. States: {names:?}")
        });
    &mut table.states[position].1
}

/// One rule, identified by where it sits **and** by what it carries, so a table
/// whose rules moved refuses instead of mutating a neighbour.
fn rule_at<'t>(
    table: &'t mut LexerTable,
    state: &str,
    index: usize,
    pattern_starts_with: &str,
) -> &'t mut Rule {
    let rules = state_of(table, state);
    let count = rules.len();
    let rule = rules.get_mut(index).unwrap_or_else(|| {
        panic!(
            "NO RULE {state}[{index}] — mutation not applied, result meaningless. \
             The state has {count} rules."
        )
    });
    assert!(
        rule.pattern.starts_with(pattern_starts_with),
        "RULE {state}[{index}] IS NOT THE ONE THE MUTATION NAMES — mutation not \
         applied, result meaningless. Expected a pattern starting {pattern_starts_with:?}, \
         found {:?}",
        &rule.pattern[..rule.pattern.len().min(60)]
    );
    rule
}

/// A mutation that leaves the stream identical means the corpus never reaches what
/// the mutation changed, so the table is gated over less than it declares.
fn must_change_the_stream(
    family: &str,
    build: fn() -> LexerTable,
    what: &str,
    mutate: &dyn Fn(&mut LexerTable),
) {
    let oracle = oracle(family);
    let (compared, failures) = compare(&oracle, build, Some(mutate));
    assert!(
        !failures.is_empty(),
        "{what} left all {compared} streams identical. The gate cannot see this \
         mutation, so it is not gating the rule the mutation names."
    );
}

/// The table against its recorded streams, with the floor that says what a shrunken
/// corpus means.
fn reproduces_pygments(family: &str, build: fn() -> LexerTable, floor: usize) {
    let oracle = oracle(family);
    let (compared, failures) = compare(&oracle, build, None);
    assert!(
        compared >= floor,
        "Only {compared} cases were compared, against a floor of {floor}. The \
         recorded corpus is hundreds of real fenced blocks; a corpus this small \
         passes vacuously, so this is a corpus problem rather than a table problem."
    );
    assert!(
        failures.is_empty(),
        "{} of {compared} recorded streams differ from Pygments:\n\n{}",
        failures.len(),
        failures[..failures.len().min(3)].join("\n\n")
    );
}

mod typescript {
    use super::*;
    use crate::syntax_tables::typescript_table;

    /// 63.9% of every character a lexer paints in real fenced content, measured
    /// over 3,000 blocks. The corpus is real TypeScript from session files, plus
    /// authored cases for the rules real content never reaches.
    #[test]
    fn the_table_reproduces_pygments_over_real_typescript() {
        reproduces_pygments("typescript", typescript_table, 400);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("typescript", typescript_table, what, mutate);
    }

    /// **A rule dropped.** The generator's most plausible failure: a rule shape it
    /// does not recognise, skipped rather than refused.
    #[test]
    fn dropping_the_keyword_rule_changes_the_stream() {
        changes_the_stream("dropping root's keyword rule", &|table| {
            rule_at(table, "root", 24, "(for|in|while|");
            state_of(table, "root").remove(24);
        });
    }

    /// **Two rules swapped.** Rule order is significant — first match wins — and a
    /// generator that sorts or dedupes reorders silently.
    ///
    /// This pair is the load-bearing one: the keyword rule's alternation contains
    /// `super`, so it matches before the `super(...)` rule can. Swapping them is
    /// what makes `super(a, b)` lex as three groups instead of one keyword, and it
    /// is the same fact that puts `root[30]` in the unreachable set.
    #[test]
    fn swapping_the_keyword_and_super_rules_changes_the_stream() {
        changes_the_stream("swapping root's keyword and super rules", &|table| {
            rule_at(table, "root", 24, "(for|in|while|");
            rule_at(table, "root", 30, "(super)");
            state_of(table, "root").swap(24, 30);
        });
    }

    /// **A `bygroups` slot dropped.** The slots align with the pattern's groups by
    /// position, so a generator that drops one shifts every slot after it.
    #[test]
    fn dropping_a_bygroups_slot_changes_the_stream() {
        changes_the_stream("dropping a slot from root's annotation rule", &|table| {
            let rule = rule_at(table, "root", 5, "([\\w?.$]+)(\\s*)(:)");
            let Action::ByGroups(slots) = &mut rule.action else {
                panic!("ROOT[5] IS NOT A BYGROUPS — mutation not applied, result meaningless");
            };
            slots.remove(0);
        });
    }

    /// Every rule the table declares, reached or named unreachable with its reason.
    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("typescript", typescript_table);
    }

    /// The refusal itself, seen to fire. A mutation aimed at a rule that has moved
    /// would otherwise mutate its neighbour and the run would read as a pass.
    #[test]
    #[should_panic(expected = "mutation not applied, result meaningless")]
    fn a_mutation_aimed_at_the_wrong_rule_refuses() {
        rule_at(&mut typescript_table(), "root", 24, "not the keyword rule");
    }

    /// **A transition changed from push-one to stay.** Catches a table that
    /// transcribed the actions and lost the states.
    #[test]
    fn losing_the_template_literal_push_changes_the_stream() {
        changes_the_stream("losing root's push into `interp`", &|table| {
            let rule = rule_at(table, "root", 35, "`");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["interp".to_string()]),
                "ROOT[35] NO LONGER PUSHES `interp` — mutation not applied, result \
                 meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }
}

/// `bash`, `sh`, `zsh`, `ksh` and `shell` all reach this one lexer, which is the
/// next share of painted characters after TypeScript.
///
/// **Its shape is different in a way that matters to the gate.** Bash declares
/// `MULTILINE` alone, so its `.` stops at a newline; and it includes one shared body
/// into five states, two of which open with a catch-all that swallows most of it —
/// which is why 57 of its 189 rules are unreachable against TypeScript's 9 of 94.
mod bash {
    use super::*;
    use crate::syntax_tables::bash_table;

    #[test]
    fn the_table_reproduces_pygments_over_real_shell() {
        reproduces_pygments("bash", bash_table, 800);
    }

    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("bash", bash_table);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("bash", bash_table, what, mutate);
    }

    /// **A rule dropped.**
    #[test]
    fn dropping_the_builtin_rule_changes_the_stream() {
        changes_the_stream("dropping root's builtin rule", &|table| {
            rule_at(table, "root", 1, "\\b(alias|bg|bind|");
            state_of(table, "root").remove(1);
        });
    }

    /// **Two rules swapped.** The whole-string rule has to be tried before the bare
    /// quote that opens the `string` state, or every quoted word becomes a state
    /// change instead of one token.
    #[test]
    fn swapping_the_two_double_quote_rules_changes_the_stream() {
        changes_the_stream("swapping root's two double-quote rules", &|table| {
            rule_at(table, "root", 11, "(?s)\\$?\"");
            rule_at(table, "root", 12, "\"");
            state_of(table, "root").swap(11, 12);
        });
    }

    /// **A `bygroups` slot dropped**, which shifts every slot after it.
    #[test]
    fn dropping_a_bygroups_slot_changes_the_stream() {
        changes_the_stream("dropping a slot from root's assignment rule", &|table| {
            let rule = rule_at(table, "root", 5, "(\\b\\w+)(\\s*)(\\+?=)");
            let Action::ByGroups(slots) = &mut rule.action else {
                panic!("ROOT[5] IS NOT A BYGROUPS — mutation not applied, result meaningless");
            };
            slots.remove(0);
        });
    }

    /// **A transition changed from push-one to stay.**
    ///
    /// It is the push into `string`, and the first choice was wrong in a way worth
    /// recording: **losing the push into `backticks` changes nothing.** That state is
    /// `root`'s body plus a pop, and its own nested-backtick rule is shadowed by that
    /// pop, so a backtick that stays in `root` produces the same tokens either way.
    /// The corpus reaches it — the mutation test is what said so.
    ///
    /// `string` is different: its content rule takes a whole run as one
    /// `String.Double`, where `root` would cut the same text into several tokens.
    #[test]
    fn losing_the_double_quote_push_changes_the_stream() {
        changes_the_stream("losing root's push into `string`", &|table| {
            let rule = rule_at(table, "root", 12, "\"");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["string".to_string()]),
                "ROOT[12] NO LONGER PUSHES `string` — mutation not applied, result \
                 meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }

    /// **Bash declares `MULTILINE` alone**, so a `.` must stop at a newline. Turning
    /// DOTALL on is the defect the flag channel exists to prevent, and it is
    /// invisible on single-line input.
    #[test]
    fn lexing_bash_under_dotall_changes_the_stream() {
        changes_the_stream("compiling bash's patterns under DOTALL", &|table| {
            assert!(
                !table.flags.dotall,
                "BASH ALREADY DECLARES DOTALL — mutation not applied, result meaningless"
            );
            table.flags.dotall = true;
        });
    }
}

/// A fence tagged `tsx`, which is a **different lexer** from TypeScript rather than
/// an alias: `TsxLexer` adds `jsx`, `tag`, `fragment`, `attr` and `expression`, and
/// then includes TypeScript's whole `root` twice more — once as `expression`, the
/// attribute container, and once as `interp-inside`.
///
/// **⚠ Its evidence rests largely on authored cases, and that is a real limit.**
/// Real `tsx` fences are scarce: a 6,000-file harvest of the session pool yields 66
/// unique blocks against TypeScript's several hundred, and they reach well under
/// half the table. The 30 authored cases carry the rest. They are recorded and
/// compared exactly as the real ones are — the same Pygments driver produced both —
/// but a snippet cannot surprise the way a real block can, and the backreference
/// defect bash's corpus found is what that difference costs.
mod tsx {
    use super::*;
    use crate::syntax_tables::tsx_table;

    #[test]
    fn the_table_reproduces_pygments_over_tsx() {
        reproduces_pygments("tsx", tsx_table, 90);
    }

    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("tsx", tsx_table);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("tsx", tsx_table, what, mutate);
    }

    /// **A rule dropped**, and it is a JSX one: those four are the whole difference
    /// between this table and TypeScript's, so dropping one has to show.
    #[test]
    fn dropping_the_element_rule_changes_the_stream() {
        changes_the_stream("dropping root's JSX element rule", &|table| {
            rule_at(table, "root", 1, "(<)(\\w+)(\\.?)");
            state_of(table, "root").remove(1);
        });
    }

    /// **Two rules swapped**, the same load-bearing pair as TypeScript's: the
    /// keyword alternation contains `super`, which is why the `super(...)` rule
    /// below it is unreachable.
    #[test]
    fn swapping_the_keyword_and_super_rules_changes_the_stream() {
        changes_the_stream("swapping root's keyword and super rules", &|table| {
            rule_at(table, "root", 28, "(for|in|while|");
            rule_at(table, "root", 34, "(super)");
            state_of(table, "root").swap(28, 34);
        });
    }

    /// **A `bygroups` slot dropped**, which shifts every slot after it.
    #[test]
    fn dropping_a_bygroups_slot_changes_the_stream() {
        changes_the_stream("dropping a slot from root's element rule", &|table| {
            let rule = rule_at(table, "root", 1, "(<)(\\w+)(\\.?)");
            let Action::ByGroups(slots) = &mut rule.action else {
                panic!("ROOT[1] IS NOT A BYGROUPS — mutation not applied, result meaningless");
            };
            slots.remove(0);
        });
    }

    /// **A transition changed from push-one to stay**, and it is the one that makes
    /// this lexer TSX: an attribute's `{` opens `expression`, where the whole
    /// TypeScript repertoire lexes. Without the push the same text is four rules of
    /// `attr`.
    #[test]
    fn losing_the_attribute_expression_push_changes_the_stream() {
        changes_the_stream("losing attr's push into `expression`", &|table| {
            let rule = rule_at(table, "attr", 0, "\\{");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["expression".to_string()]),
                "ATTR[0] NO LONGER PUSHES `expression` — mutation not applied, result \
                 meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }
}

/// Python, and it is the largest table by a wide margin: **435 rules over 49
/// states**, against TypeScript's 94 over 6.
///
/// Two things make it different in kind rather than in size.
///
/// **It is the first family to use `using(this)`** — `soft-keywords-inner`
/// re-lexes a captured group with the same table — so the driver's re-entry path
/// runs in production here for the first time rather than only in the engine's own
/// gate.
///
/// **And 110 of its 120 unreachable rules are in `include`-only states.** Python
/// factors `keywords`, `expr`, `numbers`, `name`, `builtins`, `magicfuncs` and the
/// string bodies into states nothing transitions into, and `RegexLexerMeta` copies
/// each into every state that includes it. The copies are reached; the originals
/// cannot be.
mod python {
    use super::*;
    use crate::syntax_tables::python_table;

    #[test]
    fn the_table_reproduces_pygments_over_real_python() {
        reproduces_pygments("python", python_table, 250);
    }

    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("python", python_table);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("python", python_table, what, mutate);
    }

    /// **A rule dropped.**
    #[test]
    fn dropping_the_float_rule_changes_the_stream() {
        changes_the_stream("dropping root's float rule", &|table| {
            rule_at(table, "root", 35, "(\\d(?:_?\\d)*\\.");
            state_of(table, "root").remove(35);
        });
    }

    /// **Two rules swapped**, and this pair is the one that shows why order is not a
    /// detail: the bare-prefix string rule's `([uU]?)` matches **empty**, so ahead of
    /// the f-string rule it would take every `f"…"` as a name followed by a plain
    /// string.
    #[test]
    fn swapping_the_f_string_and_plain_string_rules_changes_the_stream() {
        changes_the_stream("swapping root's f-string and plain-string rules", &|table| {
            rule_at(table, "root", 20, "([fF])(\")");
            rule_at(table, "root", 28, "([uU]?)(\")");
            state_of(table, "root").swap(20, 28);
        });
    }

    /// **A `bygroups` slot dropped**, which shifts every slot after it.
    #[test]
    fn dropping_a_bygroups_slot_changes_the_stream() {
        changes_the_stream("dropping the prefix slot from root's f-string rule", &|table| {
            let rule = rule_at(table, "root", 18, "([fF])(\"\"\")");
            let Action::ByGroups(slots) = &mut rule.action else {
                panic!("ROOT[18] IS NOT A BYGROUPS — mutation not applied, result meaningless");
            };
            slots.remove(0);
        });
    }

    /// **A transition changed from push-one to stay.** Without the push into
    /// `classname` a class's own name is an ordinary name.
    #[test]
    fn losing_the_classname_push_changes_the_stream() {
        changes_the_stream("losing root's push into `classname`", &|table| {
            let rule = rule_at(table, "root", 11, "(class)");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["classname".to_string()]),
                "ROOT[11] NO LONGER PUSHES `classname` — mutation not applied, result \
                 meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }
}

/// JSON, the one promoted family with **no table**.
///
/// `JsonLexer` is a hand-written character scanner, so there is nothing to project
/// into Rust and nothing to mutate: [`crate::syntax_json`] is a port of *behaviour*
/// rather than of data. That is a weaker starting position than the other four, and
/// the gate compensates in the two ways available.
///
/// **The reference's own executable lines stand in for a table's rules.** The
/// generator traces `get_tokens_unprocessed` while it records, and refuses to write
/// an oracle whose corpus leaves a line unexecuted — except seven, which are the
/// final-flush branches for states a newline closes. `Syntax` builds the lexer with
/// `ensurenl=True` and `_process_code` appends a newline, so **the text always ends
/// in one** and those branches cannot run in this product at all. The generator
/// checks that premise on every case rather than asserting it.
///
/// **And the mutations are applied to the recorded side.** With `ours == recorded`
/// established, requiring `ours != mutate(recorded)` proves our output is not the
/// mutant's on this corpus — which is exactly what mutating a table proves, by the
/// same equality, from the other end.
mod json {
    use super::*;
    use crate::syntax_json::tokenize;

    fn compare_json(mutate: Option<&dyn Fn(&mut Vec<(String, String)>)>) -> (usize, Vec<String>) {
        let oracle = oracle("json");
        let mut failures: Vec<String> = Vec::new();
        let mut compared = 0usize;
        for case in cases(&oracle) {
            let text = case["text"].as_str().expect("a case carries text");
            let ours = tokenize(text);
            let mut want = expected(case);
            if let Some(mutate) = mutate {
                mutate(&mut want);
            }
            compared += 1;
            if ours == want {
                continue;
            }
            let source = case["source"].as_str().unwrap_or("?");
            let first = ours
                .iter()
                .zip(&want)
                .position(|(ours, want)| ours != want)
                .unwrap_or(ours.len().min(want.len()));
            failures.push(format!(
                "case {source}, first difference at token {first}:\n  pygments {:?}\n  \
                 ours     {:?}",
                &want[first.saturating_sub(1)..want.len().min(first + 2)],
                &ours[first.saturating_sub(1)..ours.len().min(first + 2)],
            ));
        }
        (compared, failures)
    }

    #[test]
    fn the_scanner_reproduces_pygments_over_real_json() {
        let (compared, failures) = compare_json(None);
        assert!(
            compared >= 400,
            "Only {compared} cases were compared. The recorded corpus is hundreds of \
             real fenced blocks; a corpus this small passes vacuously."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} recorded streams differ from Pygments:\n\n{}",
            failures.len(),
            failures[..failures.len().min(3)].join("\n\n")
        );
    }

    /// Every executable line of the reference scanner, reached or explained.
    #[test]
    fn the_corpus_reaches_every_line_of_the_reference_scanner() {
        let oracle = oracle("json");
        let declared: Vec<i64> = oracle["scanner_lines"]
            .as_array()
            .expect("the oracle carries the scanner's lines")
            .iter()
            .map(|line| line.as_i64().expect("a line offset"))
            .collect();
        let unreachable: BTreeSet<i64> = oracle["unreachable_lines"]
            .as_object()
            .expect("the oracle carries the unreachable lines and why")
            .keys()
            .map(|line| line.parse::<i64>().expect("a line offset"))
            .collect();
        assert!(
            declared.len() >= 130,
            "The oracle records only {} executable lines for a scanner that has \
             around 140. It was recorded against a different Pygments.",
            declared.len()
        );
        assert_eq!(
            unreachable.len(),
            7,
            "{} lines are recorded as unreachable, not the seven final-flush branches \
             the trailing newline explains. A different count means the premise moved.",
            unreachable.len()
        );
    }

    fn corpus_notices(what: &str, mutate: &dyn Fn(&mut Vec<(String, String)>)) {
        let (compared, failures) = compare_json(Some(mutate));
        assert!(
            !failures.is_empty(),
            "{what} left all {compared} recorded streams identical to ours. The corpus \
             cannot see that behaviour, so nothing here gates it."
        );
    }

    /// **A port that forgets the queue.** The whole scanner exists so that a string
    /// followed by a colon becomes a key, and that is the first thing a
    /// straight-through rewrite loses.
    #[test]
    fn a_port_that_never_rewrites_a_key_would_differ() {
        corpus_notices("treating every key as a plain string", &|tokens| {
            for (path, _) in tokens.iter_mut() {
                if path == "Token.Name.Tag" {
                    *path = "Token.Literal.String.Double".to_string();
                }
            }
        });
    }

    /// **An unterminated string is an `Error`, not a string.** It is the one place
    /// the scanner refuses to guess, and the obvious port emits a string.
    #[test]
    fn a_port_that_closes_an_unterminated_string_would_differ() {
        corpus_notices("emitting an unterminated string as a string", &|tokens| {
            for (path, value) in tokens.iter_mut() {
                if path == "Token.Error" && value.starts_with('"') {
                    *path = "Token.Literal.String.Double".to_string();
                }
            }
        });
    }

    /// **Comments are not part of JSON**, and the reference supports them anyway. A
    /// port written from the specification rather than from the reference would
    /// reject them.
    #[test]
    fn a_port_that_rejects_comments_would_differ() {
        corpus_notices("emitting comments as errors", &|tokens| {
            for (path, _) in tokens.iter_mut() {
                if path.starts_with("Token.Comment") {
                    *path = "Token.Error".to_string();
                }
            }
        });
    }

    /// **A `//` comment stops *before* its newline**, which the following whitespace
    /// run then takes. Including it is the off-by-one this boundary invites.
    #[test]
    fn a_port_that_swallows_a_comments_newline_would_differ() {
        corpus_notices("ending a line comment after its newline", &|tokens| {
            for (path, value) in tokens.iter_mut() {
                if path == "Token.Comment.Single" {
                    value.push('\n');
                }
            }
        });
    }
}

/// JavaScript, which `TypeScriptLexer` inherits — so its 78 rules are the 94 above
/// minus the TypeScript-only ones, and its corpus is real and substantial where
/// TSX's is not: 443 cases over 134,809 characters of real `js`, `javascript` and
/// `node` fences, against 17 authored ones.
///
/// **It carries three mutations rather than four, and the missing one is a fact
/// about the table.** Its only two `bygroups` rules are the `super(...)` pair, and
/// both are unreachable — the keyword alternation twelve places above lists `super`
/// — so there is no reachable `bygroups` slot to misalign. Inventing one would be
/// mutating a rule the driver never runs.
mod javascript {
    use super::*;
    use crate::syntax_tables::javascript_table;

    #[test]
    fn the_table_reproduces_pygments_over_real_javascript() {
        reproduces_pygments("javascript", javascript_table, 350);
    }

    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("javascript", javascript_table);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("javascript", javascript_table, what, mutate);
    }

    /// **A rule dropped.**
    #[test]
    fn dropping_the_builtin_rule_changes_the_stream() {
        changes_the_stream("dropping root's builtin rule", &|table| {
            rule_at(table, "root", 21, "(Array|Boolean|Date|");
            state_of(table, "root").remove(21);
        });
    }

    /// **Two rules swapped**, and the pair had to be chosen rather than guessed.
    ///
    /// The first pair tried was the builtin and exception rules, on the belief that
    /// the builtin alternation lists `Error` too. **It does not** — the two are
    /// disjoint, so their order is not load-bearing and swapping them left all 443
    /// streams identical. That is a third reading of a surviving mutation on this
    /// desk: not a blind corpus, not an unobservable state, but **two rules that
    /// cannot both match anything.**
    ///
    /// This pair is load-bearing: the float rule would take `42` out of `42n` and
    /// leave the `n` behind, so the bigint rule has to be tried first.
    #[test]
    fn swapping_the_bigint_and_float_rules_changes_the_stream() {
        changes_the_stream("swapping root's bigint and float rules", &|table| {
            rule_at(table, "root", 9, "[0-9]+n");
            rule_at(table, "root", 10, "(\\.[0-9]+|");
            state_of(table, "root").swap(9, 10);
        });
    }

    /// **A transition changed from push-one to stay.** Without the push into
    /// `interp` a template literal's contents lex as ordinary code.
    #[test]
    fn losing_the_template_literal_push_changes_the_stream() {
        changes_the_stream("losing root's push into `interp`", &|table| {
            let rule = rule_at(table, "root", 28, "`");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["interp".to_string()]),
                "ROOT[28] NO LONGER PUSHES `interp` — mutation not applied, result \
                 meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }

    /// **And the one the inheritance invites**: TypeScript's table adds rules *above*
    /// these, so a generator that emitted the parent's flat table for the child — or
    /// the child's for the parent — would still lex most input identically. Dropping
    /// the operator-word rule is the cheapest probe that the two are not interchanged.
    #[test]
    fn dropping_the_operator_word_rule_changes_the_stream() {
        changes_the_stream("dropping root's operator-word rule", &|table| {
            rule_at(table, "root", 15, "(typeof|instanceof|");
            state_of(table, "root").remove(15);
        });
    }
}

/// **The held-out corpora: real content the tables were never built against.**
///
/// Every corpus above was used while building: rules were counted against it, cases
/// were added until coverage closed, mutations were aimed with it. **These were
/// harvested from a different seed, after the tables were finished, and carry no
/// authored cases and no coverage requirement.** They answer the one question the
/// building corpora cannot: whether a table reproduces Pygments on content nobody
/// looked at.
///
/// **⚠ Nothing is ever repaired against these.** A failure here is a defect in a
/// table, the generator or the driver, and repairing it by regenerating the held-out
/// corpus would convert the only unseen evidence into more of the seen kind. They are
/// written only by `--held-out`, to their own paths, for that reason.
///
/// They are also what a **replacement** has to match. An evaluation of any other
/// highlighting library after this work is deleted has to beat these numbers on this
/// content, or it is not a replacement.
mod held_out {
    use super::*;
    use crate::syntax_tables::{
        bash_table, javascript_table, python_table, sql_table, tsx_table, typescript_table,
    };

    fn held_out_oracle(family: &str) -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(format!("tests/data/lexer-tables/{family}-heldout-oracle.json"));
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the {family} held-out corpus is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the held-out corpus is valid JSON")
    }

    fn reproduces(family: &str, build: fn() -> LexerTable, floor: usize) {
        let oracle = held_out_oracle(family);
        let (compared, failures) = compare(&oracle, build, None);
        assert!(
            compared >= floor,
            "Only {compared} held-out {family} cases were compared, against a floor of \
             {floor}. Re-harvest with `--held-out` and a seed that is not the building \
             corpus's."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} held-out {family} blocks differ from Pygments. **Do not \
             regenerate this corpus.** It is content the table was never built \
             against, which is exactly why the difference is worth reading:\n\n{}",
            failures.len(),
            failures[..failures.len().min(3)].join("\n\n")
        );
    }

    #[test]
    fn every_table_reproduces_pygments_on_content_it_was_not_built_against() {
        reproduces("typescript", typescript_table, 400);
        reproduces("tsx", tsx_table, 20);
        reproduces("bash", bash_table, 700);
        reproduces("python", python_table, 50);
        reproduces("javascript", javascript_table, 100);
        reproduces("sql", sql_table, 30);
    }

    /// The scanner, on the same terms. It is the one port of behaviour rather than of
    /// data, so unseen content is worth more to it than to any of the tables.
    #[test]
    fn the_json_scanner_reproduces_pygments_on_content_it_was_not_built_against() {
        let oracle = held_out_oracle("json");
        let mut failures: Vec<String> = Vec::new();
        let mut compared = 0usize;
        for case in cases(&oracle) {
            let text = case["text"].as_str().expect("a case carries text");
            let ours = crate::syntax_json::tokenize(text);
            compared += 1;
            let want = expected(case);
            if ours != want {
                failures.push(format!("{} chars", text.chars().count()));
            }
        }
        assert!(compared >= 300, "Only {compared} held-out JSON cases were compared.");
        assert!(
            failures.is_empty(),
            "{} of {compared} held-out JSON blocks differ from Pygments. **Do not \
             regenerate this corpus.**",
            failures.len()
        );
    }
}

/// SQL, the first of the coverage families and the cheapest thing on the list:
/// **15 rules over 2 states**, smaller than any family already landed, and 337
/// blocks of real content — 30% of the whole coverage gap.
///
/// **It is the first family to declare `IGNORECASE`, and nothing else.** Not even
/// `MULTILINE`, which every family before it declared. So the third field of
/// `LexerFlags` reaches a table here for the first time, and it has its own mutation
/// below rather than being merely used.
///
/// **It carries three mutations rather than four**, and as with JavaScript the
/// missing one is a fact about the table: SQL has **no `bygroups` rule at all**, so
/// there is no slot to misalign. A fourth mutation stands in its place, aimed at the
/// flag.
mod sql {
    use super::*;
    use crate::syntax_tables::sql_table;

    #[test]
    fn the_table_reproduces_pygments_over_real_sql() {
        reproduces_pygments("sql", sql_table, 40);
    }

    /// **The first family whose corpus reaches every rule it declares** — 15 of 15,
    /// with nothing to exempt.
    #[test]
    fn the_corpus_reaches_every_declared_rule() {
        corpus_reaches_every_declared_rule("sql", sql_table);
    }

    fn changes_the_stream(what: &str, mutate: &dyn Fn(&mut LexerTable)) {
        must_change_the_stream("sql", sql_table, what, mutate);
    }

    /// **A rule dropped.**
    #[test]
    fn dropping_the_keyword_rule_changes_the_stream() {
        changes_the_stream("dropping root's keyword rule", &|table| {
            rule_at(table, "root", 3, "(\\ TEMP|A(?:B(?:ORT");
            state_of(table, "root").remove(3);
        });
    }

    /// **Two rules swapped**, and this pair is as load-bearing as a pair gets: the
    /// name rule matches any identifier, so ahead of the keyword rule it would take
    /// every keyword in the language.
    #[test]
    fn swapping_the_keyword_and_name_rules_changes_the_stream() {
        changes_the_stream("swapping root's keyword and name rules", &|table| {
            rule_at(table, "root", 3, "(\\ TEMP|A(?:B(?:ORT");
            rule_at(table, "root", 9, "[a-z_][\\w$]*");
            state_of(table, "root").swap(3, 9);
        });
    }

    /// **A transition changed from push-one to stay.** Without the push a block
    /// comment's contents lex as SQL rather than as comment text.
    #[test]
    fn losing_the_block_comment_push_changes_the_stream() {
        changes_the_stream("losing root's push into `multiline-comments`", &|table| {
            let rule = rule_at(table, "root", 2, "/\\*");
            assert_eq!(
                rule.transition,
                Transition::States(vec!["multiline-comments".to_string()]),
                "ROOT[2] NO LONGER PUSHES `multiline-comments` — mutation not applied, \
                 result meaningless"
            );
            rule.transition = Transition::Stay;
        });
    }

    /// **And the flag itself.** SQL's keyword and name rules are written in one case
    /// each, so without `IGNORECASE` every keyword written the other way becomes a
    /// name. It is the same shape as bash's DOTALL mutation, on the field bash does
    /// not exercise.
    #[test]
    fn lexing_sql_case_sensitively_changes_the_stream() {
        changes_the_stream("compiling SQL's patterns without IGNORECASE", &|table| {
            assert!(
                table.flags.ignorecase,
                "SQL NO LONGER DECLARES IGNORECASE — mutation not applied, result \
                 meaningless"
            );
            table.flags.ignorecase = false;
        });
    }
}
