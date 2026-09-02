//! Pygments' `RegexLexer`, as much of it as the promoted tables use.
//!
//! The lexer *tables* are data — `(pattern, action, transition)` triples — and this
//! is the driver that runs them. Porting the reference's tables rather than
//! reimplementing its lexers is what makes fence highlighting measurable against
//! `markdown-it`'s standard rather than statistical: the token types are the
//! reference's own.
//!
//! **Measured over the five families worth porting** — typescript, javascript,
//! bash, python, markdown, 832 rules: 82.6% of rules emit a plain token, 16.6% are
//! `bygroups` over two to six groups, 0.7% are `default`, and one is a hand-written
//! callback. Transitions are 72.4% stay, 21.4% push one state, 6.0% pop one, 0.2%
//! push two. **The deepest pop is one; there is no `#push` and no `combined()`
//! state.** `include` and `inherit` cost nothing, because `RegexLexerMeta` expands
//! both when the class is built and a port copies the flat table.
//!
//! **`using()` appears only inside `bygroups`, four times, and always as
//! `using(this)`** — the same lexer re-entered from a given state stack, never a
//! second lexer nested. That is the distinction that keeps this a driver rather
//! than an interpreter.

use crate::search_query::{Regex, StepBudgetExceeded};
use std::sync::OnceLock;

/// A Pygments token type, by its dotted path — `Token.Name.Function`.
///
/// A string rather than an enum because the set is the reference's, not ours, and
/// the style table that resolves it is generated from the same place. A path with
/// no entry is a table error, not a rendering decision.
pub type TokenPath = String;

/// What one group of a `bygroups` match contributes.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum GroupAction {
    Token(TokenPath),
    /// `using(this, stack=…)`: re-lex this group's text with the same table,
    /// starting from the given state stack.
    UsingSelf(Vec<String>),
}

/// What one rule contributes when it matches.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Action {
    Token(TokenPath),
    /// `bygroups(...)`. A `None` slot skips its group; measured absent from all
    /// five families, and modelled because the reference has it.
    ByGroups(Vec<Option<GroupAction>>),
    /// `default(...)`: change state and emit nothing.
    Nothing,
}

/// Where the state stack goes after a rule matches.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Transition {
    Stay,
    /// A single state name or a tuple of them. Each entry is a name, `#pop` or
    /// `#push`, interpreted as Pygments does.
    States(Vec<String>),
    /// `#pop:n`, which Pygments resolves to a negative integer before the driver
    /// sees it.
    Pop(usize),
}

#[derive(Clone, Debug)]
pub struct Rule {
    pub pattern: String,
    pub action: Action,
    pub transition: Transition,
}

/// The flags a lexer declares, which are **not** search's.
///
/// `RegexLexer.flags` is a class attribute and differs by family: TypeScript, TSX
/// and JavaScript are `MULTILINE|DOTALL`; **bash, python and markdown are
/// `MULTILINE` alone.** Under DOTALL a `.` crosses a newline, so compiling a bash
/// rule with search's flags lets a pattern run past the line it was written for —
/// silently, and only on multi-line input.
///
/// **There is deliberately no default.** A default that is wrong for three of the
/// five families is a trap; a generated table states its flags because the
/// reference states them.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LexerFlags {
    pub multiline: bool,
    pub dotall: bool,
    pub ignorecase: bool,
}

#[derive(Clone, Debug)]
pub struct LexerTable {
    pub name: String,
    pub flags: LexerFlags,
    pub states: Vec<(String, Vec<Rule>)>,
}

impl LexerTable {
    fn state(&self, name: &str) -> Option<&[Rule]> {
        self.states
            .iter()
            .find(|(state, _)| state == name)
            .map(|(_, rules)| rules.as_slice())
    }
}

/// A table with its patterns compiled once.
pub struct CompiledLexer {
    table: LexerTable,
    programs: Vec<Vec<Regex>>,
}

/// A pattern that will not compile is a defect in the generated table, not an
/// input the renderer can meet, so it fails at construction with the state and
/// rule that carries it.
impl CompiledLexer {
    pub fn new(table: LexerTable) -> CompiledLexer {
        let programs = table
            .states
            .iter()
            .map(|(state, rules)| {
                rules
                    .iter()
                    .map(|rule| {
                        Regex::compile_with_flags(
                            &rule.pattern,
                            table.flags.ignorecase,
                            table.flags.multiline,
                            table.flags.dotall,
                        )
                        .unwrap_or_else(|_| {
                            panic!(
                                "lexer {}: state {state}: pattern {:?} does not compile",
                                table.name, rule.pattern
                            )
                        })
                    })
                    .collect()
            })
            .collect();
        CompiledLexer { table, programs }
    }

    fn programs_for(&self, name: &str) -> Option<&[Regex]> {
        self.table
            .states
            .iter()
            .position(|(state, _)| state == name)
            .map(|index| self.programs[index].as_slice())
    }
}

/// Everything Pygments' `Whitespace` and `Error` fallbacks need to name.
const WHITESPACE: &str = "Token.Text.Whitespace";
const ERROR: &str = "Token.Error";

/// Split `text` into `(token path, text)` pairs, as
/// `RegexLexer.get_tokens_unprocessed` does.
///
/// `stack` is the initial state stack, `["root"]` for a whole document and
/// something else only for a `using(this, stack=…)` re-entry.
pub fn tokenize(
    lexer: &CompiledLexer,
    text: &str,
    stack: &[&str],
) -> Result<Vec<(TokenPath, String)>, StepBudgetExceeded> {
    let characters: Vec<char> = text.chars().collect();
    let mut out: Vec<(TokenPath, String)> = Vec::new();
    tokenize_into(lexer, &characters, stack, &mut out)?;
    Ok(out)
}

fn tokenize_into(
    lexer: &CompiledLexer,
    characters: &[char],
    stack: &[&str],
    out: &mut Vec<(TokenPath, String)>,
) -> Result<(), StepBudgetExceeded> {
    let slice = |range: std::ops::Range<usize>| -> String { characters[range].iter().collect() };
    let mut position = 0usize;
    let mut state_stack: Vec<String> = stack.iter().map(|state| state.to_string()).collect();

    loop {
        let current = state_stack
            .last()
            .cloned()
            .expect("the state stack never empties: a pop keeps at least one");
        let rules = lexer
            .table
            .state(&current)
            .unwrap_or_else(|| panic!("lexer {}: no state {current}", lexer.table.name));
        let programs = lexer
            .programs_for(&current)
            .expect("a state's rules and its programs are built together");

        let mut matched = false;
        for (rule, program) in rules.iter().zip(programs) {
            let Some(captures) = program.match_at(characters, position)? else {
                continue;
            };
            match &rule.action {
                Action::Token(token) => {
                    out.push((token.clone(), slice(position..captures.end)));
                }
                Action::ByGroups(groups) => {
                    apply_bygroups(lexer, characters, groups, &captures, out)?;
                }
                Action::Nothing => {}
            }
            position = captures.end;
            apply_transition(&rule.transition, &mut state_stack);
            matched = true;
            break;
        }
        if matched {
            continue;
        }

        // No rule matched. **A newline resets the stack to `root` and emits
        // whitespace; anything else emits `Error` and advances one character.**
        // Not `Text` for the newline — Pygments emits `Whitespace`, and the two
        // resolve to different Monokai styles.
        let Some(character) = characters.get(position) else {
            return Ok(());
        };
        if *character == '\n' {
            state_stack = vec!["root".to_string()];
            out.push((WHITESPACE.to_string(), "\n".to_string()));
        } else {
            out.push((ERROR.to_string(), character.to_string()));
        }
        position += 1;
    }
}

/// `bygroups`: each group's text takes the action in the matching slot.
///
/// **A token action emits only when the group's text is non-empty; a callable
/// emits whenever the group took part in the match.** The two conditions are
/// different in Python — `if data` against `if data is not None` — and the
/// difference is reachable whenever a group can match empty.
fn apply_bygroups(
    lexer: &CompiledLexer,
    characters: &[char],
    groups: &[Option<GroupAction>],
    captures: &crate::search_query::Captures,
    out: &mut Vec<(TokenPath, String)>,
) -> Result<(), StepBudgetExceeded> {
    for (index, action) in groups.iter().enumerate() {
        let Some(action) = action else {
            continue;
        };
        let span = captures.group(index + 1);
        match action {
            GroupAction::Token(token) => {
                if let Some((start, end)) = span
                    && end > start
                {
                    out.push((token.clone(), characters[start..end].iter().collect()));
                }
            }
            GroupAction::UsingSelf(stack) => {
                if let Some((start, end)) = span {
                    let names: Vec<&str> = stack.iter().map(String::as_str).collect();
                    tokenize_into(lexer, &characters[start..end], &names, out)?;
                }
            }
        }
    }
    Ok(())
}

/// Pygments' state transition, including the two guards that stop a stack
/// underflowing.
fn apply_transition(transition: &Transition, stack: &mut Vec<String>) {
    match transition {
        Transition::Stay => {}
        Transition::States(states) => {
            for state in states {
                match state.as_str() {
                    // A tuple's `#pop` keeps the last state; an integer pop has a
                    // different guard. Both are the reference's.
                    "#pop" => {
                        if stack.len() > 1 {
                            stack.pop();
                        }
                    }
                    "#push" => {
                        let top = stack.last().cloned().expect("never empty");
                        stack.push(top);
                    }
                    name => stack.push(name.to_string()),
                }
            }
        }
        Transition::Pop(depth) => {
            if *depth >= stack.len() {
                stack.truncate(1);
            } else {
                stack.truncate(stack.len() - depth);
            }
        }
    }
}

/// A table built once and reused, so patterns compile a single time per process.
pub struct LazyLexer {
    cell: OnceLock<CompiledLexer>,
    build: fn() -> LexerTable,
}

impl LazyLexer {
    pub const fn new(build: fn() -> LexerTable) -> LazyLexer {
        LazyLexer { cell: OnceLock::new(), build }
    }

    pub fn get(&self) -> &CompiledLexer {
        self.cell.get_or_init(|| CompiledLexer::new((self.build)()))
    }
}

#[cfg(test)]
pub(crate) mod engine_tests {
    use super::*;
    use serde_json::Value;
    use std::path::PathBuf;

    pub(crate) fn oracle() -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/message-renderer/lexer-engine-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the lexer engine oracle is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the lexer engine oracle is valid JSON")
    }

    fn group_action(slot: &Value) -> Option<GroupAction> {
        if slot.is_null() {
            return None;
        }
        if let Some(token) = slot.get("token").and_then(Value::as_str) {
            return Some(GroupAction::Token(token.to_string()));
        }
        let stack = slot["using_self"]
            .as_array()
            .expect("a using_self carries a stack")
            .iter()
            .map(|state| state.as_str().expect("a state name").to_string())
            .collect();
        Some(GroupAction::UsingSelf(stack))
    }

    /// The recorded table, rebuilt. **The same data built the Python lexer that
    /// produced the expected stream**, so this compares two drivers rather than two
    /// transcriptions of a table.
    pub(crate) fn table_from(recorded: &Value) -> LexerTable {
        table_from_with_flags(recorded, &serde_json::json!({
            "multiline": true, "dotall": false, "ignorecase": false
        }))
    }

    /// The recorded table, rebuilt with the flags the recorded lexer declared.
    pub(crate) fn table_from_with_flags(recorded: &Value, recorded_flags: &Value) -> LexerTable {
        let states = recorded
            .as_object()
            .expect("the table is an object")
            .iter()
            .map(|(state, rules)| {
                let rules = rules
                    .as_array()
                    .expect("a state carries rules")
                    .iter()
                    .map(|rule| {
                        let action = match &rule["action"] {
                            Value::Null => Action::Nothing,
                            action if action.get("token").is_some() => Action::Token(
                                action["token"].as_str().expect("a token path").to_string(),
                            ),
                            action => Action::ByGroups(
                                action["bygroups"]
                                    .as_array()
                                    .expect("bygroups slots")
                                    .iter()
                                    .map(group_action)
                                    .collect(),
                            ),
                        };
                        let transition = match &rule["transition"] {
                            Value::Null => Transition::Stay,
                            Value::Number(depth) => {
                                Transition::Pop(depth.as_u64().expect("a pop depth") as usize)
                            }
                            states => Transition::States(
                                states
                                    .as_array()
                                    .expect("a state list")
                                    .iter()
                                    .map(|state| {
                                        state.as_str().expect("a state name").to_string()
                                    })
                                    .collect(),
                            ),
                        };
                        Rule {
                            pattern: rule["pattern"].as_str().expect("a pattern").to_string(),
                            action,
                            transition,
                        }
                    })
                    .collect();
                (state.clone(), rules)
            })
            .collect();
        let flags = &recorded_flags;
        LexerTable {
            name: "Probe".to_string(),
            flags: LexerFlags {
                multiline: flags["multiline"].as_bool().expect("a multiline flag"),
                dotall: flags["dotall"].as_bool().expect("a dotall flag"),
                ignorecase: flags["ignorecase"].as_bool().expect("an ignorecase flag"),
            },
            states,
        }
    }

    fn expected(case: &Value) -> Vec<(String, String)> {
        case["tokens"]
            .as_array()
            .expect("a recorded stream")
            .iter()
            .map(|pair| {
                (
                    pair[0].as_str().expect("a token path").to_string(),
                    pair[1].as_str().expect("a token value").to_string(),
                )
            })
            .collect()
    }

    #[test]
    fn the_driver_reproduces_pygments_on_every_mechanism() {
        let oracle = oracle();
        let lexer = CompiledLexer::new(table_from_with_flags(
            &oracle["table"],
            &oracle["flags"],
        ));
        let mut failures: Vec<String> = Vec::new();
        let mut compared = 0usize;
        for case in oracle["cases"].as_array().expect("recorded cases") {
            let text = case["text"].as_str().expect("an input");
            let ours = tokenize(&lexer, text, &["root"]).expect("within budget");
            compared += 1;
            let want = expected(case);
            if ours == want {
                continue;
            }
            failures.push(format!("input {text:?}\n  pygments {want:?}\n  ours     {ours:?}"));
        }
        assert!(
            compared >= 15,
            "Only {compared} inputs were compared; the corpus cannot cover the \
             mechanisms it claims to."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} inputs differ from Pygments:\n\n{}",
            failures.len(),
            failures[..failures.len().min(4)].join("\n\n")
        );
    }
}

#[cfg(test)]
mod no_match_rule_tests {
    use super::*;
    use super::engine_tests::{oracle, table_from};

    fn probe() -> CompiledLexer {
        CompiledLexer::new(table_from(&oracle()["table"]))
    }

    /// **A newline that no rule matches resets the stack to `root` and emits
    /// `Whitespace`.** The rule the first mate expected a port to get subtly wrong
    /// with no corpus noticing, so it is asserted directly rather than only through
    /// the recorded stream.
    ///
    /// The input opens a string, so the lexer is inside `instring`; the newline is
    /// unmatched there. After it, `name` must lex as a **root** token.
    #[test]
    fn an_unmatched_newline_resets_the_stack_to_root() {
        let lexer = probe();
        let tokens = tokenize(&lexer, "\"open\nname", &["root"]).expect("within budget");
        assert_eq!(
            tokens,
            vec![
                ("Token.Literal.String".to_string(), "\"".to_string()),
                ("Token.Literal.String".to_string(), "open".to_string()),
                ("Token.Text.Whitespace".to_string(), "\n".to_string()),
                ("Token.Name".to_string(), "name".to_string()),
            ],
            "the newline must emit Whitespace — not Text — and drop the state stack \
             back to root"
        );
    }

    /// The falsification: without the reset the same input lexes differently, so the
    /// assertion above is guarding a real branch rather than restating an accident.
    #[test]
    fn without_the_reset_the_same_input_lexes_differently() {
        let lexer = probe();
        // Starting inside `instring` is what the un-reset lexer would still be doing
        // after the newline: the tail is string content rather than a root name.
        let unreset = tokenize(&lexer, "name", &["instring"]).expect("within budget");
        assert_eq!(
            unreset,
            vec![("Token.Literal.String".to_string(), "name".to_string())],
            "if this stops differing from the root lexing, the probe table's states \
             have converged and the reset is no longer observable"
        );
    }

    /// **An unmatched character that is not a newline emits `Error` and advances
    /// exactly one character**, leaving the stack alone.
    #[test]
    fn an_unmatched_character_emits_one_error_and_advances_one() {
        let lexer = probe();
        let tokens = tokenize(&lexer, "~~a", &["root"]).expect("within budget");
        assert_eq!(
            tokens,
            vec![
                ("Token.Error".to_string(), "~".to_string()),
                ("Token.Error".to_string(), "~".to_string()),
                ("Token.Name".to_string(), "a".to_string()),
            ],
            "each unmatched character is its own Error token, one character wide"
        );
    }

    /// The recorded corpus must reach every mechanism it claims to gate. A stream
    /// comparison catches a wrong driver only where the corpus exercises it, and
    /// this desk's gates have failed by omission three times.
    #[test]
    fn the_recorded_corpus_reaches_every_mechanism() {
        let oracle = oracle();
        let mut newline_reset = 0usize;
        let mut errors = 0usize;
        let mut empty_group_skipped = 0usize;
        let mut using_self = 0usize;
        for case in oracle["cases"].as_array().expect("cases") {
            let text = case["text"].as_str().expect("an input");
            for pair in case["tokens"].as_array().expect("a stream") {
                let token = pair[0].as_str().expect("a token path");
                let value = pair[1].as_str().expect("a value");
                if token == "Token.Text.Whitespace" && value == "\n" {
                    newline_reset += 1;
                }
                if token == "Token.Error" {
                    errors += 1;
                }
            }
            // `let  y` has an empty third group in one arm and a two-space second;
            // `re[]` has an empty `using` group.
            if text.starts_with("let ") {
                empty_group_skipped += 1;
            }
            if text.starts_with("re[") || text.starts_with("st{") {
                using_self += 1;
            }
        }
        assert!(newline_reset >= 2, "no recorded case reaches the newline reset");
        assert!(errors >= 2, "no recorded case reaches the Error fallback");
        assert!(empty_group_skipped >= 2, "no recorded case exercises bygroups");
        assert!(using_self >= 2, "no recorded case exercises using(this)");
    }
}
