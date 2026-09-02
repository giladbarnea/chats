//! Boolean query parsing and the native regex engine for `ch search`.
//!
//! Engine truth is CPython 3.14 `re` with MULTILINE|DOTALL (and IGNORECASE
//! unless `-s`), characterized empirically and pinned by the cycle-03
//! fixtures. One backtracking evaluator serves every valid pattern; Python
//! invalid patterns fall back to escaped literals exactly like
//! `src/chats/search_query.py`. POSIX-nested-set FutureWarning bytes are
//! synthesized verbatim.

use std::collections::HashSet;
use std::sync::Mutex;
use std::sync::OnceLock;


#[derive(Debug)]
pub struct SearchQueryError(pub String);

impl std::fmt::Display for SearchQueryError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}", self.0)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Kind {
    Term,
    And,
    Or,
    Not,
    LParen,
    RParen,
}

#[derive(Debug)]
struct Token {
    kind: Kind,
    text: String,
}

fn operator_kind(word: &str) -> Option<Kind> {
    match word {
        "AND" => Some(Kind::And),
        "OR" => Some(Kind::Or),
        "NOT" => Some(Kind::Not),
        _ => None,
    }
}

/// Port of `_tokenize`: quotes open terms only at token boundaries; returns
/// `None` on an unterminated quote, sending the whole pattern down the
/// single-term path.
fn tokenize(pattern: &str) -> Option<Vec<Token>> {
    let characters: Vec<char> = pattern.chars().collect();
    let mut tokens = Vec::new();
    let mut position = 0;
    while position < characters.len() {
        let character = characters[position];
        if character.is_whitespace() {
            position += 1;
            continue;
        }
        if character == '(' || character == ')' {
            tokens.push(Token {
                kind: if character == '(' { Kind::LParen } else { Kind::RParen },
                text: character.to_string(),
            });
            position += 1;
            continue;
        }
        if character == '"' || character == '\'' {
            let closing = characters[position + 1..]
                .iter()
                .position(|candidate| *candidate == character)
                .map(|offset| offset + position + 1)?;
            tokens.push(Token {
                kind: Kind::Term,
                text: characters[position + 1..closing].iter().collect(),
            });
            position = closing + 1;
            continue;
        }
        let start = position;
        while position < characters.len()
            && !characters[position].is_whitespace()
            && characters[position] != '('
            && characters[position] != ')'
        {
            position += 1;
        }
        let word: String = characters[start..position].iter().collect();
        tokens.push(Token {
            kind: operator_kind(&word).unwrap_or(Kind::Term),
            text: word,
        });
    }
    Some(tokens)
}

#[derive(Clone, Debug)]
pub enum Query {
    Term(SearchTerm),
    And(Vec<Query>),
    Or(Vec<Query>),
    Not(Box<Query>),
}

impl Query {
    pub fn evaluate(
        &self,
        term_matches: &mut dyn FnMut(&SearchTerm) -> bool,
    ) -> bool {
        match self {
            Query::Term(term) => term_matches(term),
            Query::And(operands) => operands.iter().all(|operand| operand.evaluate(term_matches)),
            Query::Or(operands) => operands.iter().any(|operand| operand.evaluate(term_matches)),
            Query::Not(operand) => !operand.evaluate(term_matches),
        }
    }

    pub fn iter_terms(&self) -> Vec<&SearchTerm> {
        match self {
            Query::Term(term) => vec![term],
            Query::And(operands) | Query::Or(operands) => {
                operands.iter().flat_map(Query::iter_terms).collect()
            }
            // Negated terms are not match evidence: they drive neither the
            // highlight literals nor the displayed match set.
            Query::Not(_) => Vec::new(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct SearchTerm {
    pub pattern: String,
    pub engine: Regex,
    pub literal_candidate: Option<String>,
    pub case_sensitive: bool,
}

const REGEX_META_CHARACTERS: &[char] = &['.', '^', '$', '*', '+', '?', '{', '}', '[', ']', '\\', '|', '(', ')'];

fn is_plain_literal_search_pattern(pattern: &str) -> bool {
    !pattern.chars().any(|character| REGEX_META_CHARACTERS.contains(&character))
}

pub fn python_casefold(pattern: &str) -> String {
    pattern.to_lowercase()
}

pub fn compile_search_term(pattern: &str, case_sensitive: bool) -> SearchTerm {
    if let Ok(engine) = Regex::compile(pattern, !case_sensitive) {
            let literal_candidate = if is_plain_literal_search_pattern(pattern) {
                Some(if case_sensitive { pattern.to_string() } else { python_casefold(pattern) })
            } else {
                None
            };
            return SearchTerm {
                pattern: pattern.to_string(),
                engine,
                literal_candidate,
                case_sensitive,
            };
    }
    let escaped = python_regex_escape(pattern);
    SearchTerm {
        pattern: pattern.to_string(),
        engine: Regex::compile(&escaped, !case_sensitive)
            .expect("escaped literals always compile"),
        literal_candidate: Some(if case_sensitive { pattern.to_string() } else { python_casefold(pattern) }),
        case_sensitive,
    }
}

/// Port of `re.escape`: escapes exactly CPython's special-character set.
pub fn python_regex_escape(pattern: &str) -> String {
    const SPECIAL: &[char] = &[
        '(', ')', '[', ']', '{', '}', '?', '*', '+', '-', '|', '^', '$', '\\', '.', '&', '~', '#',
        ' ', '\t', '\n', '\r', '\u{b}', '\u{c}',
    ];
    let mut escaped = String::with_capacity(pattern.len());
    for character in pattern.chars() {
        if SPECIAL.contains(&character) {
            escaped.push('\\');
        }
        escaped.push(character);
    }
    escaped
}

include!("search_query_unicode_names.rs");

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
struct Flags {
    ignorecase: bool,
    multiline: bool,
    dotall: bool,
    verbose: bool,
    /// `(?a)`: narrows `\d`, `\w`, and `\s` to ASCII.
    ascii: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum CategoryKind {
    Digit,
    NotDigit,
    Word,
    NotWord,
    Space,
    NotSpace,
}

/// A `\d`-style escape together with the mode it was written under, so `(?a)`
/// narrows it at parse time instead of leaking a flag into match time.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Category {
    kind: CategoryKind,
    ascii: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Anchor {
    LineStart,
    LineEnd,
    StringStart,
    StringEnd,
    WordBoundary,
    NotWordBoundary,
}

#[derive(Clone, Debug)]
enum ClassItem {
    Literal(char),
    Range(char, char),
    Category(Category),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RepeatKind {
    Greedy,
    Lazy,
    Possessive,
}

#[derive(Clone, Debug)]
enum Node {
    Empty,
    Literal(char),
    Class { negated: bool, items: Vec<ClassItem> },
    Category(Category),
    Dot,
    Anchor(Anchor),
    Group { index: usize, node: Box<Node> },
    NonCapturing(Box<Node>),
    Backref(usize),
    Cond { group: usize, yes: Box<Node>, no: Option<Box<Node>> },
    Concat(Vec<Node>),
    Alt(Vec<Node>),
    Repeat { node: Box<Node>, min: u32, max: Option<u32>, kind: RepeatKind },
    Atomic(Box<Node>),
    ScopedFlags { flags: Flags, node: Box<Node> },
    Look { behind: bool, negative: bool, node: Box<Node> },
}

/// Compiled native equivalent of one Python `re` pattern.
#[derive(Clone, Debug)]
pub struct Regex {
    program: Program,
    /// A literal every match must contain. When the haystack lacks it the VM is
    /// never entered, which is what keeps ordinary patterns off the step budget.
    required_literal: Option<Vec<char>>,
    ignorecase: bool,
}

pub struct CompiledWarnings {
    pub messages: Vec<String>,
}

/// CPython prefixes this warning with the source file and line that called
/// `re.compile`. Native search has no such file, and the branch this engine came
/// from fabricated one from a build-time path pointing at a Python module it
/// deletes. The message is user-visible output and is reproduced; the fabricated
/// provenance is not.
fn warning_text(position: usize) -> String {
    format!("FutureWarning: Possible nested set at position {position}")
}

pub fn emit_future_warning(message: &str) {
    static SEEN: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();
    let seen = SEEN.get_or_init(|| Mutex::new(HashSet::new()));
    if seen.lock().expect("warning registry").insert(message.to_string()) {
        eprintln!("{message}");
    }
}

struct PatternParser<'a> {
    characters: &'a [char],
    position: usize,
    flags: Flags,
    global_flags_locked: bool,
    group_count: usize,
    group_names: Vec<(String, usize)>,
    /// Capturing groups whose body is still being parsed. CPython rejects a
    /// backreference to one of these with "cannot refer to an open group".
    open_groups: Vec<usize>,
    warnings: Vec<String>,
}

impl<'a> PatternParser<'a> {
    fn peek(&self) -> Option<char> {
        self.characters.get(self.position).copied()
    }

    fn next(&mut self) -> Option<char> {
        let character = self.peek();
        if character.is_some() {
            self.position += 1;
        }
        character
    }

    fn parse_alternation(&mut self) -> Result<Node, ()> {
        let mut branches = vec![self.parse_concat()?];
        while self.peek() == Some('|') {
            self.position += 1;
            branches.push(self.parse_concat()?);
        }
        Ok(if branches.len() == 1 { branches.pop().expect("non-empty") } else { Node::Alt(branches) })
    }

    fn parse_concat(&mut self) -> Result<Node, ()> {
        let mut items: Vec<Node> = Vec::new();
        loop {
            self.skip_verbose_ignorable();
            let Some(character) = self.peek() else {
                break;
            };
            if character == '|' || character == ')' {
                break;
            }
            let atom_start = self.position;
            match self.parse_atom()? {
                AtomOutcome::Node(node) => {
                    let repeated = self.parse_quantifier(node, atom_start)?;
                    items.push(repeated);
                }
                AtomOutcome::GlobalFlags { flags: override_flags, end } => {
                    if !items.is_empty() || self.position != end {
                        return Err(());
                    }
                    self.flags = override_flags;
                }
            }
        }
        Ok(match items.len() {
            0 => Node::Empty,
            1 => items.pop().expect("one item"),
            _ => Node::Concat(items),
        })
    }

    fn parse_quantifier(&mut self, node: Node, atom_start: usize) -> Result<Node, ()> {
        if matches!(node, Node::Anchor(_)) {
            // CPython raises "nothing to repeat" for `\b{2}`, `^{2}`, and friends.
            // Returning early here would silently drop the quantifier instead.
            self.skip_verbose_ignorable();
            return match self.peek() {
                Some('*') | Some('+') | Some('?') => Err(()),
                Some('{') => {
                    let mark = self.position;
                    let interval = self.parse_interval()?;
                    self.position = mark;
                    if interval.is_some() { Err(()) } else { Ok(node) }
                }
                _ => Ok(node),
            };
        }
        self.skip_verbose_ignorable();
        let kind = match self.peek() {
            Some('*') => {
                self.position += 1;
                Some((0u32, None))
            }
            Some('+') => {
                self.position += 1;
                Some((1u32, None))
            }
            Some('?') => {
                self.position += 1;
                Some((0u32, Some(1u32)))
            }
            Some('{') => self.parse_interval()?,
            _ => None,
        };
        let Some((min, max)) = kind else {
            return Ok(node);
        };
        if matches!(node, Node::Empty)
            || matches!(node, Node::Concat(ref items) if items.iter().all(|item| matches!(item, Node::Empty)))
        {
            let _ = atom_start;
            return Err(());
        }
        if let Some(maximum) = max {
            if maximum < min {
                return Err(());
            }
        }
        let repeat_kind = match self.peek() {
            Some('?') => {
                self.position += 1;
                RepeatKind::Lazy
            }
            Some('+') => {
                self.position += 1;
                RepeatKind::Possessive
            }
            _ => RepeatKind::Greedy,
        };
        Ok(Node::Repeat { node: Box::new(node), min, max, kind: repeat_kind })
    }

    fn parse_interval(&mut self) -> Result<Option<(u32, Option<u32>)>, ()> {
        let start = self.position;
        self.position += 1; // '{'
        let mut minimum_text = String::new();
        while self.peek().is_some_and(|character| character.is_ascii_digit()) {
            minimum_text.push(self.next().expect("peeked"));
        }
        if minimum_text.is_empty() && self.peek() != Some(',') {
            self.position = start;
            return Ok(None); // literal '{'
        }
        match self.peek() {
            Some('}') => {
                self.position += 1;
                let minimum: u32 = minimum_text.parse().map_err(|_| ())?;
                return Ok(Some((minimum, Some(minimum))));
            }
            Some(',') => {
                self.position += 1;
                let mut maximum_text = String::new();
                while self.peek().is_some_and(|character| character.is_ascii_digit()) {
                    maximum_text.push(self.next().expect("peeked"));
                }
                if self.peek() != Some('}') {
                    // Not a well-formed interval, so CPython treats the `{` as a
                    // literal character and keeps parsing the rest of the pattern.
                    self.position = start;
                    return Ok(None);
                }
                self.position += 1;
                let minimum: u32 = if minimum_text.is_empty() {
                    0
                } else {
                    minimum_text.parse().map_err(|_| ())?
                };
                let maximum = if maximum_text.is_empty() {
                    None
                } else {
                    Some(maximum_text.parse::<u32>().map_err(|_| ())?)
                };
                return Ok(Some((minimum, maximum)));
            }
            _ => {
                self.position = start;
                Ok(None) // literal '{'
            }
        }
    }

    fn parse_atom(&mut self) -> Result<AtomOutcome, ()> {
        let character = self.next().ok_or(())?;
        match character {
            '(' => self.parse_group(),
            '[' => self.parse_class().map(|node| AtomOutcome::Node(Node::Concat(vec![node]))),
            '.' => Ok(AtomOutcome::Node(Node::Dot)),
            '^' => Ok(AtomOutcome::Node(Node::Anchor(Anchor::LineStart))),
            '$' => Ok(AtomOutcome::Node(Node::Anchor(Anchor::LineEnd))),
            '\\' => self.parse_escape().map(AtomOutcome::Node),
            '*' | '+' | '?' => Err(()), // nothing to repeat
            other => Ok(AtomOutcome::Node(Node::Literal(other))),
        }
    }

    fn parse_group(&mut self) -> Result<AtomOutcome, ()> {
        if self.peek() == Some('?') {
            self.position += 1;
            let marker = self.next().ok_or(())?;
            match marker {
                ':' => {
                    let inner = self.parse_alternation()?;
                    self.expect_close_paren()?;
                    return Ok(AtomOutcome::Node(Node::NonCapturing(Box::new(inner))));
                }
                '=' => return self.parse_look(false, false),
                '!' => return self.parse_look(false, true),
                '<' => {
                    match self.peek() {
                        Some('=') => {
                            self.position += 1;
                            return self.parse_look(true, false);
                        }
                        Some('!') => {
                            self.position += 1;
                            return self.parse_look(true, true);
                        }
                        _ => return Err(()), // (?<name> is not Python syntax
                    }
                }
                'P' => {
                    match self.next().ok_or(())? {
                        '<' => {
                            let name = self.take_while_closing('>')?;
                            if !is_valid_group_name(&name)
                                || self.group_names.iter().any(|(existing, _)| existing == &name)
                            {
                                return Err(());
                            }
                            self.group_count += 1;
                            self.group_names.push((name, self.group_count));
                            return self.parse_capturing(self.group_count);
                        }
                        '=' => {
                            let name = self.take_while_closing(')')?;
                            let known = self.group_names.iter().any(|(existing, _)| existing == &name);
                            if !known {
                                return Err(());
                            }
                            let index = self.group_names.iter().find(|(existing, _)| existing == &name).expect("checked").1;
                            if self.open_groups.contains(&index) {
                                return Err(());
                            }
                            return Ok(AtomOutcome::Node(Node::Backref(index)));
                        }
                        _ => return Err(()),
                    }
                }
                '#' => {
                    while self.peek().is_some() && self.peek() != Some(')') {
                        self.position += 1;
                    }
                    if self.next().is_none() {
                        return Err(());
                    }
                    return Ok(AtomOutcome::Node(Node::Empty));
                }
                '(' => {
                    // Conditional: (?(n)y|z) or (?(name)y|z).
                    let mut reference = String::new();
                    loop {
                        match self.next().ok_or(())? {
                            ')' => break,
                            character => reference.push(character),
                        }
                    }
                    let group_number = match reference.strip_prefix('&') {
                        Some(name) => self
                            .group_names
                            .iter()
                            .find(|(existing, _)| existing == name)
                            .map(|(_, index)| *index)
                            .ok_or(())?,
                        None => {
                            let number: usize = reference.parse().map_err(|_| ())?;
                            if number == 0 || number > self.group_count {
                                return Err(());
                            }
                            number
                        }
                    };
                    let yes = self.parse_conditional_branch(true)?;
                    let no = self.parse_conditional_branch(false)?;
                    self.expect_close_paren()?;
                    return Ok(AtomOutcome::Node(Node::Cond {
                        group: group_number,
                        yes: Box::new(yes.expect("required branch present")),
                        no: no.map(Box::new),
                    }));
                }
                '>' => {
                    let inner = self.parse_alternation()?;
                    self.expect_close_paren()?;
                    return Ok(AtomOutcome::Node(Node::Atomic(Box::new(inner))));
                }
                other if "imsxau-".contains(other) => {
                    self.position -= 1;
                    let (flags, scoped, _closing) = self.parse_flag_spec()?;
                    if scoped {
                        let outer_flags = self.flags;
                        self.flags = flags;
                        let inner = self.parse_alternation()?;
                        self.flags = outer_flags;
                        self.expect_close_paren()?;
                        return Ok(AtomOutcome::Node(Node::ScopedFlags { flags, node: Box::new(inner) }));
                    }
                    self.flags = flags;
                    return Ok(AtomOutcome::GlobalFlags { flags, end: self.position });
                }
                _ => return Err(()),
            }
        }
        self.group_count += 1;
        self.parse_capturing(self.group_count)
    }

    fn parse_conditional_branch(&mut self, require_content: bool) -> Result<Option<Node>, ()> {
        if !require_content && self.peek().is_none_or(|character| character == ')') {
            return Ok(None);
        }
        if !require_content && self.peek() == Some('|') {
            self.position += 1;
        }
        let mut items: Vec<Node> = Vec::new();
        loop {
            self.skip_verbose_ignorable();
            let Some(character) = self.peek() else {
                break;
            };
            if character == ')' || character == '|' {
                break;
            }
            let atom_start = self.position;
            match self.parse_atom()? {
                AtomOutcome::Node(node) => items.push(self.parse_quantifier(node, atom_start)?),
                AtomOutcome::GlobalFlags { .. } => return Err(()),
            }
        }
        Ok(Some(match items.len() {
            0 => Node::Empty,
            1 => items.pop().expect("one item"),
            _ => Node::Concat(items),
        }))
    }

    fn parse_flag_spec(&mut self) -> Result<(Flags, bool, char), ()> {
        let mut flags = self.flags;
        let mut adding = true;
        let mut saw_change = false;
        // CPython rejects `a`, `u`, and `L` in combination as incompatible.
        let mut saw_ascii = false;
        let mut saw_unicode = false;
        loop {
            let character = self.next().ok_or(())?;
            match character {
                '-' if adding => {
                    adding = false;
                    saw_change = true;
                }
                'i' => {
                    flags.ignorecase = adding;
                    saw_change = true;
                }
                'm' => {
                    flags.multiline = adding;
                    saw_change = true;
                }
                's' => {
                    flags.dotall = adding;
                    saw_change = true;
                }
                'x' => {
                    flags.verbose = adding;
                    saw_change = true;
                }
                // CPython accepts the ASCII and Unicode mode flags. Unicode is
                // already the default for `str` patterns, so `u` only has to be
                // accepted; `a` narrows the character categories.
                'a' => {
                    saw_ascii = true;
                    flags.ascii = adding;
                    saw_change = true;
                }
                'u' => {
                    saw_unicode = true;
                    saw_change = true;
                }
                ':' | ')' => {
                    if !saw_change || (saw_ascii && saw_unicode) {
                        return Err(());
                    }
                    let scoped = character == ':';
                    if !scoped {
                        self.global_flags_locked = true;
                    }
                    return Ok((flags, scoped, character));
                }
                _ => return Err(()),
            }
        }
    }

    fn expect_close_paren(&mut self) -> Result<(), ()> {
        if self.next() == Some(')') {
            Ok(())
        } else {
            Err(())
        }
    }

    fn take_while_closing(&mut self, closer: char) -> Result<String, ()> {
        let mut name = String::new();
        loop {
            match self.next().ok_or(())? {
                character if character == closer => return Ok(name),
                character => name.push(character),
            }
        }
    }

    fn parse_capturing(&mut self, index: usize) -> Result<AtomOutcome, ()> {
        self.open_groups.push(index);
        let inner = self.parse_alternation()?;
        self.open_groups.pop();
        self.expect_close_paren()?;
        Ok(AtomOutcome::Node(Node::Group { index, node: Box::new(inner) }))
    }

    /// Verbose mode ignores ASCII whitespace and '#…end-of-line' comments
    /// between atoms (sre_parse.WHITESPACE); classes and escapes are untouched.
    fn skip_verbose_ignorable(&mut self) {
        if !self.flags.verbose {
            return;
        }
        loop {
            match self.peek() {
                Some(character) if matches!(character, ' ' | '\t' | '\n' | '\r' | '\u{b}' | '\u{c}') => {
                    self.position += 1;
                }
                Some('#') => {
                    while let Some(consumed) = self.next() {
                        if consumed == '\n' {
                            break;
                        }
                    }
                }
                _ => return,
            }
        }
    }

    fn parse_look(&mut self, behind: bool, negative: bool) -> Result<AtomOutcome, ()> {
        let inner = self.parse_alternation()?;
        self.expect_close_paren()?;
        if behind {
            let Some((minimum, maximum)) = width_range(&inner) else {
                return Err(());
            };
            if minimum != maximum {
                return Err(()); // Python: "look-behind requires fixed-width pattern"
            }
        }
        Ok(AtomOutcome::Node(Node::Look { behind, negative, node: Box::new(inner) }))
    }

    fn parse_class(&mut self) -> Result<Node, ()> {
        let mut negated = false;
        if self.peek() == Some('^') {
            negated = true;
            self.position += 1;
        }
        let mut items: Vec<ClassItem> = Vec::new();
        let mut first = true;
        loop {
            let character = self.next().ok_or(())?; // unterminated set otherwise
            if character == ']' && !first {
                break;
            }
            first = false;
            if character == '['
                && self.position >= 2
                && self.characters[self.position - 2] == '['
            {
                self.warnings.push(warning_text(self.position - 1));
            }
            let low = if character == '\\' {
                match self.parse_escape()? {
                    Node::Literal(escaped) => escaped,
                    Node::Category(category) => {
                        items.push(ClassItem::Category(category));
                        continue;
                    }
                    _ => return Err(()),
                }
            } else {
                character
            };
            if self.peek() == Some('-')
                && self.characters.get(self.position + 1).copied().is_some_and(|next| next != ']')
            {
                self.position += 1;
                let high_character = self.next().ok_or(())?;
                let high = if high_character == '\\' {
                    match self.parse_escape()? {
                        Node::Literal(escaped) => escaped,
                        _ => return Err(()),
                    }
                } else {
                    high_character
                };
                if (high as u32) < (low as u32) {
                    return Err(());
                }
                items.push(ClassItem::Range(low, high));
            } else {
                items.push(ClassItem::Literal(low));
            }
        }
        Ok(Node::Class { negated, items })
    }

    fn category(&self, kind: CategoryKind) -> Node {
        Node::Category(Category { kind, ascii: self.flags.ascii })
    }

    fn parse_escape(&mut self) -> Result<Node, ()> {
        let escape = self.next().ok_or(())?;
        match escape {
            'd' => Ok(self.category(CategoryKind::Digit)),
            'D' => Ok(self.category(CategoryKind::NotDigit)),
            'w' => Ok(self.category(CategoryKind::Word)),
            'W' => Ok(self.category(CategoryKind::NotWord)),
            's' => Ok(self.category(CategoryKind::Space)),
            'S' => Ok(self.category(CategoryKind::NotSpace)),
            'b' => Ok(Node::Anchor(Anchor::WordBoundary)),
            'B' => Ok(Node::Anchor(Anchor::NotWordBoundary)),
            'A' => Ok(Node::Anchor(Anchor::StringStart)),
            // CPython accepts `\z` alongside `\Z` since 3.12; both are absolute end.
            'Z' | 'z' => Ok(Node::Anchor(Anchor::StringEnd)),
            'n' => Ok(Node::Literal('\n')),
            'r' => Ok(Node::Literal('\r')),
            't' => Ok(Node::Literal('\t')),
            'f' => Ok(Node::Literal('\u{c}')),
            'v' => Ok(Node::Literal('\u{b}')),
            'a' => Ok(Node::Literal('\u{7}')),
            'x' => self.parse_hex_escape(),
            'u' => {
                let mut value = 0u32;
                for _ in 0..4 {
                    let digit = self.next().ok_or(())?.to_digit(16).ok_or(())?;
                    value = value * 16 + digit;
                }
                Ok(Node::Literal(char::from_u32(value).ok_or(())?))
            }
            'N' => {
                if self.next() != Some('{') {
                    return Err(());
                }
                let name = self.take_while_closing('}')?;
                lookup_unicode_name(&name).map(Node::Literal).ok_or(())
            }
            '0' => {
                let mut value = 0u32;
                for _ in 0..2 {
                    match self.peek().and_then(|character| character.to_digit(8)) {
                        Some(digit) => {
                            value = value * 8 + digit;
                            self.position += 1;
                        }
                        None => break,
                    }
                }
                Ok(Node::Literal(char::from_u32(value).ok_or(())?))
            }
            digit if digit.is_ascii_digit() => {
                // \\number: up to three digits. Leading 0 or three-digit form is
                // octal (<= 0o377); otherwise a group reference.
                let first = digit.to_digit(10).ok_or(())?;
                let mut digits = String::new();
                digits.push(digit);
                while digits.len() < 3
                    && self.peek().is_some_and(|character| character.is_ascii_digit())
                {
                    digits.push(self.next().expect("peeked"));
                }
                if first == 0 || digits.len() == 3 {
                    match u32::from_str_radix(&digits, 8) {
                        Ok(value) if value <= 0o377 => {
                            Ok(Node::Literal(char::from_u32(value).ok_or(())?))
                        }
                        _ => Err(()),
                    }
                } else {
                    let number: usize = digits.parse().map_err(|_| ())?;
                    if number <= self.group_count && !self.open_groups.contains(&number) {
                        Ok(Node::Backref(number))
                    } else {
                        Err(())
                    }
                }
            }
            other if other.is_alphanumeric() => Err(()), // \p, \y, unknown letter escapes
            other => Ok(Node::Literal(other)),           // escaped punctuation is literal
        }
    }

    fn parse_hex_escape(&mut self) -> Result<Node, ()> {
        if self.peek() == Some('{') {
            return Err(()); // \x{41} is Python-invalid
        }
        let mut value = 0u32;
        for _ in 0..2 {
            let digit = self.next().ok_or(())?.to_digit(16).ok_or(())?;
            value = value * 16 + digit;
        }
        Ok(Node::Literal(char::from_u32(value).ok_or(())?))
    }
}

enum AtomOutcome {
    Node(Node),
    GlobalFlags { flags: Flags, end: usize },
}

fn lookup_unicode_name(name: &str) -> Option<char> {
    let upper = name;
    let index = UNICODE_NAMES.binary_search_by(|(candidate, _)| candidate.cmp(&upper)).ok()?;
    char::from_u32(UNICODE_NAMES[index].1)
}

fn tolower(character: char) -> char {
    let mut lowered = character.to_lowercase();
    let first = lowered.next().unwrap_or(character);
    if lowered.next().is_none() {
        first
    } else {
        first
    }
}

const EXTRA_CASES: &[(char, &[char])] = &[
    ('\u{69}', &['\u{131}']), ('\u{73}', &['\u{17f}']), ('\u{b5}', &['\u{3bc}']), ('\u{131}', &['\u{69}']), ('\u{17f}', &['\u{73}']),
    ('\u{345}', &['\u{3b9}', '\u{1fbe}']), ('\u{390}', &['\u{1fd3}']), ('\u{3b0}', &['\u{1fe3}']), ('\u{3b2}', &['\u{3d0}']), ('\u{3b5}', &['\u{3f5}']),
    ('\u{3b8}', &['\u{3d1}']), ('\u{3b9}', &['\u{345}', '\u{1fbe}']), ('\u{3ba}', &['\u{3f0}']), ('\u{3bc}', &['\u{b5}']), ('\u{3c0}', &['\u{3d6}']),
    ('\u{3c1}', &['\u{3f1}']), ('\u{3c2}', &['\u{3c3}']), ('\u{3c3}', &['\u{3c2}']), ('\u{3c6}', &['\u{3d5}']), ('\u{3d0}', &['\u{3b2}']),
    ('\u{3d1}', &['\u{3b8}']), ('\u{3d5}', &['\u{3c6}']), ('\u{3d6}', &['\u{3c0}']), ('\u{3f0}', &['\u{3ba}']), ('\u{3f1}', &['\u{3c1}']),
    ('\u{3f5}', &['\u{3b5}']), ('\u{432}', &['\u{1c80}']), ('\u{434}', &['\u{1c81}']), ('\u{43e}', &['\u{1c82}']), ('\u{441}', &['\u{1c83}']),
    ('\u{442}', &['\u{1c84}', '\u{1c85}']), ('\u{44a}', &['\u{1c86}']), ('\u{463}', &['\u{1c87}']), ('\u{1c80}', &['\u{432}']),
    ('\u{1c81}', &['\u{434}']), ('\u{1c82}', &['\u{43e}']), ('\u{1c83}', &['\u{441}']), ('\u{1c84}', &['\u{442}', '\u{1c85}']),
    ('\u{1c85}', &['\u{442}', '\u{1c84}']), ('\u{1c86}', &['\u{44a}']), ('\u{1c87}', &['\u{463}']), ('\u{1c88}', &['\u{a64b}']),
    ('\u{1e61}', &['\u{1e9b}']), ('\u{1e9b}', &['\u{1e61}']), ('\u{1fbe}', &['\u{345}', '\u{3b9}']), ('\u{1fd3}', &['\u{390}']),
    ('\u{1fe3}', &['\u{3b0}']), ('\u{a64b}', &['\u{1c88}']), ('\u{fb05}', &['\u{fb06}']), ('\u{fb06}', &['\u{fb05}']),
];

fn extra_for(lowered: char) -> &'static [char] {
    EXTRA_CASES
        .iter()
        .find(|(key, _)| *key == lowered)
        .map(|(_, values)| *values)
        .unwrap_or(&[])
}

pub(crate) fn literal_matches_icase(pattern_character: char, text_character: char) -> bool {
    let lowered_pattern = tolower(pattern_character);
    let lowered_text = tolower(text_character);
    lowered_text == lowered_pattern
        || text_character == lowered_pattern
        || extra_for(lowered_pattern).contains(&text_character)
        || extra_for(lowered_text).contains(&pattern_character)
        || pattern_character == text_character
}

/// CPython's `\w`: its alphanumeric predicate plus `_`.
///
/// Category-based on purpose. Rust's `is_alphanumeric` uses the Alphabetic
/// *derived* property, which admits combining marks CPython excludes — 6,167
/// codepoints' worth, measured over the whole of Unicode.
fn is_word_character(character: char) -> bool {
    use unicode_general_category::GeneralCategory;
    character == '_'
        || matches!(
            unicode_general_category::get_general_category(character),
            GeneralCategory::UppercaseLetter
                | GeneralCategory::LowercaseLetter
                | GeneralCategory::TitlecaseLetter
                | GeneralCategory::ModifierLetter
                | GeneralCategory::OtherLetter
                | GeneralCategory::DecimalNumber
                | GeneralCategory::LetterNumber
                | GeneralCategory::OtherNumber
        )
}

/// CPython's `\d`: the decimal-digit property, not ASCII digits.
fn is_decimal_digit(character: char) -> bool {
    unicode_general_category::get_general_category(character)
        == unicode_general_category::GeneralCategory::DecimalNumber
}

/// Every character CPython's `re.IGNORECASE` treats as equal to `character`.
fn case_equivalents(character: char) -> Vec<char> {
    let lowered = tolower(character);
    let mut equivalents = vec![character, lowered];
    equivalents.extend_from_slice(extra_for(lowered));
    equivalents
}

fn category_matches(category: Category, character: char) -> bool {
    let ascii = category.ascii;
    let digit = |character: char| {
        if ascii { character.is_ascii_digit() } else { is_decimal_digit(character) }
    };
    let word = |character: char| {
        if ascii {
            character.is_ascii_alphanumeric() || character == '_'
        } else {
            is_word_character(character)
        }
    };
    let space = |character: char| {
        if ascii { character.is_ascii_whitespace() || character == '\u{b}' } else { character.is_whitespace() }
    };
    match category.kind {
        CategoryKind::Digit => digit(character),
        CategoryKind::NotDigit => !digit(character),
        CategoryKind::Word => word(character),
        CategoryKind::NotWord => !word(character),
        CategoryKind::Space => space(character),
        CategoryKind::NotSpace => !space(character),
    }
}

/// CPython's group-name rule: a valid Python identifier.
///
/// >>> `(?P<1n>a)` and `(?P<n-x>a)` are rejected, so search falls back to a literal.
fn is_valid_group_name(name: &str) -> bool {
    let mut characters = name.chars();
    let Some(first) = characters.next() else { return false };
    if !(first == '_' || first.is_alphabetic()) {
        return false;
    }
    characters.all(|character| character == '_' || character.is_alphanumeric())
}

struct ClassMatcher<'a> {
    negated: bool,
    items: &'a [ClassItem],
    ignorecase: bool,
}

impl ClassMatcher<'_> {
    fn member_matches(&self, item: &ClassItem, character: char) -> bool {
        match item {
            ClassItem::Literal(literal) => {
                if self.ignorecase {
                    literal_matches_icase(*literal, character)
                } else {
                    *literal == character
                }
            }
            ClassItem::Range(low, high) => {
                if self.ignorecase {
                    // Any member of the character's case-equivalence class landing
                    // in the range is a match: `[a-z]` matches `ſ` through `s`, and
                    // `[h-j]` matches `ı` through `i`.
                    case_equivalents(character)
                        .into_iter()
                        .any(|equivalent| (*low..=*high).contains(&equivalent))
                } else {
                    (*low..=*high).contains(&character)
                }
            }
            ClassItem::Category(category) => category_matches(*category, character),
        }
    }

    fn matches(&self, character: char) -> bool {
        let hit = self.items.iter().any(|item| self.member_matches(item, character));
        hit != self.negated
    }
}


/// Thompson-style program executed by a backtracking virtual machine.
#[derive(Clone, Debug)]
enum Instruction {
    Char(Predicate),
    Class { negated: bool, items: Vec<ClassItem>, ignorecase: bool },
    Save(usize),
    Split(usize, usize),
    Jump(usize),
    Mark(usize),
    RequireProgress(usize),
    Assert { anchor: Anchor, multiline: bool },
    Backref { group: usize, ignorecase: bool },
    GroupState { group: usize, participated: bool },
    SubProgram { entry: usize, resume: usize, behind: bool, negative: bool },
    AtomicSubProgram { entry: usize, resume: usize },
    Match,
}

#[derive(Clone, Copy, Debug)]
enum Predicate {
    Literal(char),
    LiteralIgnoreCase(char),
    Category(Category),
    Any,
    AnyExceptNewline,
}

impl Predicate {
    fn matches(&self, character: char) -> bool {
        match self {
            Predicate::Literal(expected) => *expected == character,
            Predicate::LiteralIgnoreCase(expected) => literal_matches_icase(*expected, character),
            Predicate::Category(category) => category_matches(*category, character),
            Predicate::Any => true,
            Predicate::AnyExceptNewline => character != '\n',
        }
    }
}

#[derive(Clone, Debug)]
struct Program {
    instructions: Vec<Instruction>,
    capture_slots: usize,
    progress_slots: usize,
}

struct ProgramBuilder {
    instructions: Vec<Instruction>,
    capture_slots: usize,
    progress_slots: usize,
}

impl ProgramBuilder {
    fn emit(&mut self, instruction: Instruction) -> usize {
        self.instructions.push(instruction);
        self.instructions.len() - 1
    }

    fn compile_node(&mut self, node: &Node, flags: Flags) {
        match node {
            Node::Empty => {}
            Node::Literal(character) => {
                let predicate = if flags.ignorecase {
                    Predicate::LiteralIgnoreCase(*character)
                } else {
                    Predicate::Literal(*character)
                };
                self.emit(Instruction::Char(predicate));
            }
            Node::Dot => {
                self.emit(Instruction::Char(if flags.dotall { Predicate::Any } else { Predicate::AnyExceptNewline }));
            }
            Node::Category(category) => {
                self.emit(Instruction::Char(Predicate::Category(*category)));
            }
            Node::Class { negated, items } => {
                self.emit(Instruction::Class {
                    negated: *negated,
                    items: items.clone(),
                    ignorecase: flags.ignorecase,
                });
            }
            Node::Anchor(anchor) => {
                self.emit(Instruction::Assert { anchor: *anchor, multiline: flags.multiline });
            }
            Node::Concat(items) => {
                for item in items {
                    self.compile_node(item, flags);
                }
            }
            Node::Alt(branches) => {
                let mut jumps = Vec::new();
                for (position, branch) in branches.iter().enumerate() {
                    if position + 1 == branches.len() {
                        self.compile_node(branch, flags);
                    } else {
                        let split = self.emit(Instruction::Split(0, 0));
                        let branch_start = self.instructions.len();
                        self.compile_node(branch, flags);
                        jumps.push(self.emit(Instruction::Jump(0)));
                        let next_branch = self.instructions.len();
                        self.instructions[split] = Instruction::Split(branch_start, next_branch);
                    }
                }
                let end = self.instructions.len();
                for jump in jumps {
                    self.instructions[jump] = Instruction::Jump(end);
                }
            }
            Node::Group { index, node } => {
                let save_open = 2 * index;
                let save_close = 2 * index + 1;
                self.capture_slots = self.capture_slots.max(save_close + 1);
                self.emit(Instruction::Save(save_open));
                self.compile_node(node, flags);
                self.emit(Instruction::Save(save_close));
            }
            Node::Backref(group) => {
                self.capture_slots = self.capture_slots.max(2 * group + 1);
                self.emit(Instruction::Backref { group: *group, ignorecase: flags.ignorecase });
            }
            Node::Repeat { node, min, max, kind } => self.compile_repeat(node, *min, *max, *kind, flags),
            Node::NonCapturing(node) => self.compile_node(node, flags),
            Node::Atomic(node) => {
                let placeholder =
                    self.emit(Instruction::AtomicSubProgram { entry: 0, resume: 0 });
                let entry = self.instructions.len();
                self.compile_node(node, flags);
                self.emit(Instruction::Match);
                let resume = self.instructions.len();
                self.instructions[placeholder] =
                    Instruction::AtomicSubProgram { entry, resume };
            }
            Node::ScopedFlags { flags: scoped, node } => self.compile_with_flags(*scoped, node),
            Node::Look { behind, negative, node } => {
                let placeholder = self.emit(Instruction::SubProgram {
                    entry: 0,
                    resume: 0,
                    behind: *behind,
                    negative: *negative,
                });
                let entry = self.instructions.len();
                self.compile_node(node, flags);
                self.emit(Instruction::Match);
                let resume = self.instructions.len();
                self.instructions[placeholder] = Instruction::SubProgram {
                    entry,
                    resume,
                    behind: *behind,
                    negative: *negative,
                };
            }
            Node::Cond { group, yes, no } => {
                let split = self.emit(Instruction::Split(0, 0));
                let yes_start = self.instructions.len();
                self.emit(Instruction::GroupState { group: *group, participated: true });
                self.compile_node(yes, flags);
                let jump_over_no = self.emit(Instruction::Jump(0));
                let no_start = self.instructions.len();
                self.emit(Instruction::GroupState { group: *group, participated: false });
                if let Some(no_branch) = no {
                    self.compile_node(no_branch, flags);
                }
                let end = self.instructions.len();
                self.instructions[split] = Instruction::Split(yes_start, no_start);
                self.instructions[jump_over_no] = Instruction::Jump(end);
            }
        }
    }

    fn compile_with_flags(&mut self, scoped: Flags, node: &Node) {
        match node {
            Node::Literal(character) => {
                let predicate = if scoped.ignorecase {
                    Predicate::LiteralIgnoreCase(*character)
                } else {
                    Predicate::Literal(*character)
                };
                self.emit(Instruction::Char(predicate));
            }
            Node::Class { negated, items } => {
                self.emit(Instruction::Class {
                    negated: *negated,
                    items: items.clone(),
                    ignorecase: scoped.ignorecase,
                });
            }
            Node::Dot => {
                self.emit(Instruction::Char(if scoped.dotall { Predicate::Any } else { Predicate::AnyExceptNewline }));
            }
            other => self.compile_node(other, scoped),
        }
    }

    fn compile_repeat(&mut self, inner: &Node, min: u32, max: Option<u32>, kind: RepeatKind, flags: Flags) {
        match kind {
            RepeatKind::Possessive => {
                // e{min,max}+ runs the whole greedy loop atomically.
                let placeholder =
                    self.emit(Instruction::AtomicSubProgram { entry: 0, resume: 0 });
                let entry = self.instructions.len();
                self.compile_loop(inner, min, max, RepeatKind::Greedy, flags);
                self.emit(Instruction::Match);
                let resume = self.instructions.len();
                self.instructions[placeholder] =
                    Instruction::AtomicSubProgram { entry, resume };
            }
            RepeatKind::Greedy | RepeatKind::Lazy => {
                for _ in 0..min {
                    self.compile_node(inner, flags);
                }
                match max {
                    None => self.compile_unbounded_tail(inner, kind, flags),
                    Some(maximum) => self.compile_bounded_tail(inner, maximum - min, kind, flags),
                }
            }
        }
    }

    fn compile_unbounded_tail(&mut self, inner: &Node, kind: RepeatKind, flags: Flags) {
        let slot = self.progress_slots;
        self.progress_slots += 1;
        let mark = self.emit(Instruction::Mark(slot));
        let split = self.emit(Instruction::Split(0, 0));
        let body = self.instructions.len();
        self.compile_node(inner, flags);
        self.emit(Instruction::RequireProgress(slot));
        self.emit(Instruction::Jump(mark));
        let exit = self.instructions.len();
        self.instructions[split] = match kind {
            RepeatKind::Greedy => Instruction::Split(body, exit),
            _ => Instruction::Split(exit, body),
        };
    }

    fn compile_bounded_tail(&mut self, inner: &Node, remaining: u32, kind: RepeatKind, flags: Flags) {
        let mut splits = Vec::new();
        for _ in 0..remaining {
            let split = self.emit(Instruction::Split(0, 0));
            splits.push(split);
            self.compile_node(inner, flags);
        }
        let exit = self.instructions.len();
        for split in splits {
            let body = split + 1;
            self.instructions[split] = match kind {
                RepeatKind::Greedy => Instruction::Split(body, exit),
                _ => Instruction::Split(exit, body),
            };
        }
    }

    fn compile_loop(&mut self, inner: &Node, min: u32, max: Option<u32>, kind: RepeatKind, flags: Flags) {
        for _ in 0..min {
            self.compile_node(inner, flags);
        }
        match max {
            None => self.compile_unbounded_tail(inner, kind, flags),
            Some(maximum) => self.compile_bounded_tail(inner, maximum - min, kind, flags),
        }
    }
}

#[derive(Clone)]
struct Thread {
    pc: usize,
    position: usize,
    saves: Vec<Option<usize>>,
    marks: Vec<usize>,
}

struct Vm<'h> {
    haystack: &'h [char],
    program: &'h Program,
    /// The thread that reached `Match`, kept so a caller can read its captures.
    /// `run` returns only the end position, which is all the search path needs.
    matched: Option<Thread>,
    steps: usize,
    /// Set when the step budget runs out. Without it a budget trip is
    /// indistinguishable from "no match", which is a confident wrong answer.
    exhausted: bool,
}

/// Raised when a pathological pattern exhausts the step budget.
///
/// CPython does not terminate at all on these patterns, so this is a repair to a
/// defect the product ships today rather than a regression against a legacy that
/// eventually answers. The bar it has to clear is "does not hang".
#[derive(Debug, Clone, Copy, Eq, PartialEq)]
pub struct StepBudgetExceeded;

/// An anchored match: where it ended, and where each capture group landed.
///
/// Every offset is a **character** index into the haystack that was matched, so a
/// caller slices the same `Vec<char>` the engine walked and never a second
/// representation of the text.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Captures {
    pub end: usize,
    groups: Vec<Option<(usize, usize)>>,
}

impl Captures {
    /// Group `index`, one-based as in Python. `None` when the group did not take
    /// part in the match, which is `bygroups`' skip case.
    pub fn group(&self, index: usize) -> Option<(usize, usize)> {
        self.groups.get(index).copied().flatten()
    }

    /// How many groups the pattern declares.
    pub fn group_count(&self) -> usize {
        self.groups.len().saturating_sub(1)
    }
}

impl std::fmt::Display for StepBudgetExceeded {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            formatter,
            "Search pattern is too expensive to evaluate. It exceeded the evaluation \
             budget, so no result can be reported. Simplify the pattern, most often by \
             removing a repeat applied to a group that itself repeats."
        )
    }
}

/// Shrink the step budget for as long as the guard lives, so a gate can force
/// exhaustion.
///
/// **The only honest falsifier for what happens when the budget runs out is one that
/// actually runs it out.** No input a corpus can hold reaches twenty million steps —
/// a 147 KB pathological Python fence did not — so a gate that fabricated the symptom
/// would be asserting its own stub rather than the renderer. This shrinks the real
/// limit inside the real VM, so the exhaustion travels the real path.
///
/// Thread-local, because `cargo test` runs tests in parallel and a global would let
/// one gate shrink another's budget.
#[cfg(test)]
pub struct ShrunkStepBudget;

#[cfg(test)]
thread_local! {
    static STEP_LIMIT_OVERRIDE: std::cell::Cell<Option<usize>> =
        const { std::cell::Cell::new(None) };
}

#[cfg(test)]
impl ShrunkStepBudget {
    pub fn to(limit: usize) -> ShrunkStepBudget {
        STEP_LIMIT_OVERRIDE.with(|cell| cell.set(Some(limit)));
        ShrunkStepBudget
    }
}

#[cfg(test)]
impl Drop for ShrunkStepBudget {
    fn drop(&mut self) {
        STEP_LIMIT_OVERRIDE.with(|cell| cell.set(None));
    }
}

impl<'h> Vm<'h> {
    /// Sized as a pathological-pattern guard, not a load limit: the required-literal
    /// prescan keeps ordinary patterns from ever reaching the VM, so a trip here
    /// means genuinely exponential backtracking rather than a large message.
    const STEP_LIMIT: usize = 20_000_000;

    #[cfg(test)]
    fn step_limit() -> usize {
        STEP_LIMIT_OVERRIDE
            .with(|cell| cell.get())
            .unwrap_or(Self::STEP_LIMIT)
    }

    #[cfg(not(test))]
    fn step_limit() -> usize {
        Self::STEP_LIMIT
    }

    /// Depth-first backtracking run; returns the first success end position in
    /// Python's preference order (split arms are ordered by the compiler).
    fn run(&mut self, start: Thread) -> Option<usize> {
        let limit = Self::step_limit();
        let mut stack = vec![start];
        while let Some(thread) = stack.pop() {
            self.steps += 1;
            if self.steps > limit {
                self.exhausted = true;
                return None;
            }
            if let Some(outcome) = self.step(thread, &mut stack) {
                return Some(outcome);
            }
        }
        None
    }

    fn step(&mut self, thread: Thread, stack: &mut Vec<Thread>) -> Option<usize> {
        let instruction = self.program.instructions.get(thread.pc)?;
        match instruction {
            Instruction::Match => {
                let position = thread.position;
                self.matched = Some(thread);
                Some(position)
            }
            Instruction::Char(predicate) => {
                let character = *self.haystack.get(thread.position)?;
                predicate.matches(character).then(|| {
                    stack.push(Thread { pc: thread.pc + 1, position: thread.position + 1, ..thread });
                    0
                });
                None
            }
            Instruction::Class { negated, items, ignorecase } => {
                let character = *self.haystack.get(thread.position)?;
                let matcher = ClassMatcher { negated: *negated, items, ignorecase: *ignorecase };
                matcher.matches(character).then(|| {
                    stack.push(Thread { pc: thread.pc + 1, position: thread.position + 1, ..thread });
                    0
                });
                None
            }
            Instruction::Save(slot) => {
                let position = thread.position;
                let mut next = thread;
                next.pc += 1;
                next.saves[*slot] = Some(position);
                stack.push(next);
                None
            }
            Instruction::Jump(target) => {
                stack.push(Thread { pc: *target, ..thread });
                None
            }
            Instruction::Split(arm_a, arm_b) => {
                // Push lower-priority first so the higher pops next.
                stack.push(Thread { pc: *arm_b, ..thread.clone() });
                stack.push(Thread { pc: *arm_a, ..thread });
                None
            }
            Instruction::Mark(slot) => {
                let mut next = thread;
                if next.marks.len() <= *slot {
                    next.marks.resize(*slot + 1, usize::MAX);
                }
                next.marks[*slot] = next.position;
                next.pc += 1;
                stack.push(next);
                None
            }
            Instruction::RequireProgress(slot) => {
                let marked = thread.marks.get(*slot).copied().unwrap_or(usize::MAX);
                if thread.position > marked {
                    stack.push(Thread { pc: thread.pc + 1, ..thread });
                }
                None
            }
            Instruction::Assert { anchor, multiline } => {
                anchor_matches_with(*anchor, *multiline, thread.position, self.haystack).then(|| {
                    stack.push(Thread { pc: thread.pc + 1, ..thread });
                    0
                });
                None
            }
            Instruction::Backref { group, ignorecase } => {
                let span = thread.saves.get(2 * group).copied().flatten().zip(
                    thread.saves.get(2 * group + 1).copied().flatten(),
                );
                match span {
                    None => {
                        stack.push(Thread { pc: thread.pc + 1, ..thread });
                        None
                    }
                    Some((start, end)) => {
                        let length = end - start;
                        if thread.position + length > self.haystack.len() {
                            return None;
                        }
                        for offset in 0..length {
                            let expected = self.haystack[start + offset];
                            let actual = self.haystack[thread.position + offset];
                            // The fold applies only when the pattern asked for it.
                            // CPython compares a backreference under the group's own
                            // flags, so `(\w+)x\1` does not match "PYxpy" unless
                            // IGNORECASE is on.
                            let equal = if *ignorecase {
                                literal_matches_icase(expected, actual)
                            } else {
                                expected == actual
                            };
                            if !equal {
                                return None;
                            }
                        }
                        stack.push(Thread { pc: thread.pc + 1, position: thread.position + length, ..thread });
                        None
                    }
                }
            }
            Instruction::GroupState { group, participated } => {
                let present = thread.saves.get(2 * group).copied().flatten().is_some();
                (present == *participated).then(|| {
                    stack.push(Thread { pc: thread.pc + 1, ..thread });
                    0
                });
                None
            }
            Instruction::SubProgram { entry, resume, behind, negative } => {
                let satisfied = if *behind {
                    look_behind_ok(self, *entry, thread.position)
                } else {
                    self.run_sub(
                        *entry,
                        Thread {
                            position: thread.position,
                            saves: thread.saves.clone(),
                            marks: thread.marks.clone(),
                            pc: 0,
                        },
                    )
                    .is_some()
                };
                if satisfied != *negative {
                    stack.push(Thread { pc: *resume, ..thread });
                }
                None
            }
            Instruction::AtomicSubProgram { entry, resume } => {
                let end = self.run_sub(
                        *entry,
                        Thread {
                            position: thread.position,
                            saves: thread.saves.clone(),
                            marks: thread.marks.clone(),
                            pc: 0,
                        },
                    )?;
                stack.push(Thread { pc: *resume, position: end, ..thread });
                None
            }
        }
    }

    /// Run an isolated sub-program (lookaround body / atomic group) starting
    /// at `entry`, against the full instruction list so that absolute
    /// Split/Jump targets stay valid. Returns the first success end position.
    fn run_sub(&mut self, entry: usize, mut thread: Thread) -> Option<usize> {
        thread.pc = entry;
        let saved_steps = self.steps;
        let outcome = self.run(thread);
        self.steps = saved_steps;
        outcome.map(|position| position)
    }

}

fn anchor_matches_with(anchor: Anchor, multiline: bool, position: usize, haystack: &[char]) -> bool {
    let length = haystack.len();
    let at_start = position == 0;
    let at_end = position == length;
    match anchor {
        Anchor::StringStart => at_start,
        Anchor::StringEnd => at_end,
        Anchor::LineStart => at_start || (multiline && haystack[position - 1] == '\n'),
        Anchor::LineEnd => {
            at_end
                || (!multiline && position + 1 == length && haystack[position] == '\n')
                || (multiline && haystack[position] == '\n')
        }
        Anchor::WordBoundary | Anchor::NotWordBoundary => {
            let before = position > 0 && is_word_character(haystack[position - 1]);
            let after = position < length && is_word_character(haystack[position]);
            (before != after) == matches!(anchor, Anchor::WordBoundary)
        }
    }
}

/// Python's lookbehind width model (sre getwidth): a body is admissible only
/// when its minimum and maximum match are equal.
fn width_range(node: &Node) -> Option<(usize, usize)> {
    match node {
        Node::Empty => Some((0, 0)),
        Node::Literal(_) | Node::Category(_) | Node::Dot | Node::Class { .. } => Some((1, 1)),
        Node::Anchor(_) | Node::Look { .. } => Some((0, 0)),
        Node::Concat(items) => {
            let mut total = (0usize, 0usize);
            for item in items {
                let (low, high) = width_range(item)?;
                total.0 = total.0.saturating_add(low);
                total.1 = total.1.saturating_add(high);
            }
            Some(total)
        }
        Node::Alt(branches) => {
            let mut range = (usize::MAX, 0usize);
            for branch in branches {
                let (low, high) = width_range(branch)?;
                range.0 = range.0.min(low);
                range.1 = range.1.max(high);
            }
            Some(range)
        }
        Node::Repeat { node, min, max, .. } => {
            let (low, high) = width_range(node)?;
            let minimum = low.saturating_mul(*min as usize);
            let maximum = if high == 0 {
                0
            } else {
                match max {
                    Some(maximum) => high.saturating_mul(*maximum as usize),
                    None => usize::MAX,
                }
            };
            Some((minimum, maximum))
        }
        Node::Group { node, .. }
        | Node::Atomic(node)
        | Node::NonCapturing(node)
        | Node::ScopedFlags { node, .. } => width_range(node),
        Node::Backref(_) => Some((0, usize::MAX)),
        Node::Cond { yes, no, .. } => {
            let yes_range = width_range(yes)?;
            let no_range = match no {
                Some(branch) => width_range(branch)?,
                None => (0, 0),
            };
            Some((yes_range.0.min(no_range.0), yes_range.1.max(no_range.1)))
        }
    }
}

/// The longest literal run that every match must contain, or `None` when the
/// pattern guarantees no literal.
///
/// Only unconditionally required text is admissible: an alternation branch, an
/// optional repeat, a negative lookaround, or a scoped flag change that alters
/// case sensitivity all contribute nothing. Being conservative here is the whole
/// safety property, because a prescan that rejects a haystack the VM would have
/// matched silently loses a user's search result.
fn required_literal(node: &Node, ignorecase: bool) -> Option<Vec<char>> {
    fn longest(left: Option<Vec<char>>, right: Option<Vec<char>>) -> Option<Vec<char>> {
        match (left, right) {
            (Some(a), Some(b)) => Some(if b.len() > a.len() { b } else { a }),
            (Some(a), None) => Some(a),
            (None, right) => right,
        }
    }

    match node {
        Node::Literal(character) => Some(vec![*character]),
        Node::Concat(items) => {
            // Merge adjacent literals into runs; anything else breaks the run
            // but may still contribute a required literal of its own.
            let mut best: Option<Vec<char>> = None;
            let mut run: Vec<char> = Vec::new();
            for item in items {
                if let Node::Literal(character) = item {
                    run.push(*character);
                    continue;
                }
                if !run.is_empty() {
                    best = longest(best, Some(std::mem::take(&mut run)));
                }
                best = longest(best, required_literal(item, ignorecase));
            }
            if !run.is_empty() {
                best = longest(best, Some(run));
            }
            best
        }
        Node::Group { node, .. } | Node::Atomic(node) | Node::NonCapturing(node) => {
            required_literal(node, ignorecase)
        }
        Node::ScopedFlags { flags, node } => {
            // A subtree matching under a different case mode cannot be probed
            // with this regex's mode.
            (flags.ignorecase == ignorecase)
                .then(|| required_literal(node, ignorecase))
                .flatten()
        }
        Node::Repeat { node, min, .. } if *min >= 1 => required_literal(node, ignorecase),
        _ => None,
    }
}

/// Whether `needle` occurs in `haystack`, folding through the same case
/// equivalence the search truth uses.
fn haystack_contains(haystack: &[char], needle: &[char], ignorecase: bool) -> bool {
    if needle.len() > haystack.len() {
        return false;
    }
    (0..=haystack.len() - needle.len()).any(|start| {
        needle.iter().enumerate().all(|(offset, expected)| {
            let actual = haystack[start + offset];
            if ignorecase {
                literal_matches_icase(*expected, actual)
            } else {
                *expected == actual
            }
        })
    })
}

fn look_behind_ok(vm: &mut Vm, entry: usize, position: usize) -> bool {
    for candidate_start in 0..=position {
        let mut sub_vm = Vm {
            haystack: vm.haystack,
            program: vm.program,
            matched: None,
            steps: vm.steps,
            exhausted: false,
        };
        let reached = sub_vm.run(Thread {
            pc: entry,
            position: candidate_start,
            saves: vec![None; 8],
            marks: Vec::new(),
        });
        // Carry the sub-run's cost and its exhaustion back: a budget trip in here
        // is the same confident wrong answer as one in the outer run.
        vm.steps = sub_vm.steps;
        vm.exhausted |= sub_vm.exhausted;
        if vm.exhausted {
            return false;
        }
        if reached == Some(position) {
            return true;
        }
    }
    false
}

impl Regex {
    /// Compile with Python's default search flags (MULTILINE|DOTALL plus the
    /// caller's IGNORECASE decision). `Err` marks a Python-invalid pattern.
    pub fn compile(pattern: &str, ignorecase: bool) -> Result<Regex, ()> {
        Regex::compile_with_flags(pattern, ignorecase, true, true)
    }

    /// Compile with the flags a **lexer** declares, rather than search's.
    ///
    /// `RegexLexer.flags` is a class attribute and differs by family: TypeScript,
    /// TSX and JavaScript are `MULTILINE|DOTALL`, while **bash, python and markdown
    /// are `MULTILINE` alone**. Under DOTALL a `.` crosses a newline, so compiling a
    /// bash rule with search's flags lets a pattern run past the line it was written
    /// for — silently, and only on multi-line input.
    ///
    /// ```
    /// use _native::search_query::Regex;
    /// let haystack: Vec<char> = "ab\ncd".chars().collect();
    /// // DOTALL: `.` crosses the newline.
    /// let dotall = Regex::compile_with_flags("a.*", false, true, true).expect("compiles");
    /// assert_eq!(dotall.match_at(&haystack, 0).expect("budget").expect("matches").end, 5);
    /// // MULTILINE alone: it stops at the line end, which is what a bash rule expects.
    /// let lines = Regex::compile_with_flags("a.*", false, true, false).expect("compiles");
    /// assert_eq!(lines.match_at(&haystack, 0).expect("budget").expect("matches").end, 2);
    /// ```
    pub fn compile_with_flags(
        pattern: &str,
        ignorecase: bool,
        multiline: bool,
        dotall: bool,
    ) -> Result<Regex, ()> {
        let characters: Vec<char> = pattern.chars().collect();
        let mut parser = PatternParser {
            characters: &characters,
            position: 0,
            flags: Flags {
                ignorecase,
                multiline,
                dotall,
                verbose: false,
                ascii: false,
            },
            global_flags_locked: false,
            group_count: 0,
            group_names: Vec::new(),
            open_groups: Vec::new(),
            warnings: Vec::new(),
        };
        let root = parser.parse_alternation()?;
        if parser.position != characters.len() {
            return Err(());
        }
        for warning in parser.warnings {
            emit_future_warning(&warning);
        }
        let mut builder = ProgramBuilder { instructions: Vec::new(), capture_slots: 0, progress_slots: 0 };
        builder.compile_node(&root, parser.flags);
        builder.emit(Instruction::Match);
        let required = required_literal(&root, parser.flags.ignorecase);
        Ok(Regex {
            program: Program {
                instructions: builder.instructions,
                capture_slots: builder.capture_slots,
                progress_slots: builder.progress_slots,
            },
            required_literal: required,
            ignorecase: parser.flags.ignorecase,
        })
    }

    /// One **anchored** match at `position`, with its capture groups.
    ///
    /// `pattern.match(text, pos)` rather than `search` — which is what a
    /// `RegexLexer` rule does at every step, so this is the lexer driver's whole
    /// interface to the engine. Positions are **character** offsets into the
    /// haystack the caller already holds, so a lexer never re-slices a string.
    ///
    /// The required-literal fast reject is deliberately skipped: it asks whether
    /// the *whole* haystack could match, which is a linear scan, and a lexer calls
    /// this once per rule per position.
    ///
    /// ```
    /// use _native::search_query::Regex;
    /// let assignment = Regex::compile(r"(\w+)\s*=\s*(\d+)", false).expect("compiles");
    /// let haystack: Vec<char> = "x = 12;".chars().collect();
    /// let matched = assignment.match_at(&haystack, 0).expect("within budget").expect("matches");
    /// assert_eq!(matched.end, 6);
    /// assert_eq!(matched.group(1), Some((0, 1)));
    /// assert_eq!(matched.group(2), Some((4, 6)));
    /// // Anchored: it does not search forward for a later match.
    /// assert!(assignment.match_at(&haystack, 1).expect("within budget").is_none());
    /// ```
    pub fn match_at(
        &self,
        haystack: &[char],
        position: usize,
    ) -> Result<Option<Captures>, StepBudgetExceeded> {
        let mut vm = Vm {
            haystack,
            program: &self.program,
            matched: None,
            steps: 0,
            exhausted: false,
        };
        let slots = self.program.capture_slots;
        let thread = Thread {
            pc: 0,
            position,
            saves: vec![None; slots],
            marks: vec![usize::MAX; self.program.progress_slots],
        };
        match vm.run(thread) {
            Some(end) => {
                let saves = vm.matched.map(|thread| thread.saves).unwrap_or_default();
                let groups = (0..slots / 2)
                    .map(|group| match (saves.get(2 * group), saves.get(2 * group + 1)) {
                        (Some(Some(start)), Some(Some(finish))) => Some((*start, *finish)),
                        _ => None,
                    })
                    .collect();
                Ok(Some(Captures { end, groups }))
            }
            None if vm.exhausted => Err(StepBudgetExceeded),
            None => Ok(None),
        }
    }

    /// Every match, as **character** spans, in `re.finditer` order.
    ///
    /// Character spans rather than byte offsets, and taken from the haystack the
    /// engine already walks, so nothing indexes one string with offsets measured on
    /// another. That is the guard the highlighter needs: `İ` grows from two bytes to
    /// three when lowercased and the ligature `ﬀ` shrinks from three to two, so a
    /// span measured on a folded copy paints the wrong text or panics.
    ///
    /// Case-insensitive spans are checked over text whose folded length differs
    /// from its own in **both** directions — the two characters the highlighter's
    /// guard names. Both answers are Python's, taken from `re.finditer` rather than
    /// reasoned about: `İ` *does* match `i`, because `re.IGNORECASE` uses the simple
    /// one-to-one lowercase mapping, and `ﬀ` does *not* match `ff`, because that
    /// would need full case folding.
    ///
    /// ```
    /// use _native::search_query::Regex;
    /// let regex = Regex::compile("ab", false).expect("a literal compiles");
    /// assert_eq!(regex.find_all("xabyab").expect("within budget"), vec![(1, 3), (4, 6)]);
    ///
    /// let letter = Regex::compile("i", true).expect("a literal compiles");
    /// assert_eq!(letter.find_all("İi").expect("within budget"), vec![(0, 1), (1, 2)]);
    /// let ligature = Regex::compile("ff", true).expect("a literal compiles");
    /// assert_eq!(ligature.find_all("ﬀff").expect("within budget"), vec![(1, 3)]);
    /// ```
    pub fn find_all(&self, text: &str) -> Result<Vec<(usize, usize)>, StepBudgetExceeded> {
        let haystack: Vec<char> = text.chars().collect();
        if let Some(needle) = &self.required_literal
            && !haystack_contains(&haystack, needle, self.ignorecase)
        {
            return Ok(Vec::new());
        }
        let mut vm = Vm {
            haystack: &haystack,
            program: &self.program,
            matched: None,
            steps: 0,
            exhausted: false,
        };
        let slots = self.program.capture_slots;
        let mut spans: Vec<(usize, usize)> = Vec::new();
        let mut start = 0usize;
        while start <= haystack.len() {
            let thread = Thread {
                pc: 0,
                position: start,
                saves: vec![None; slots],
                marks: vec![usize::MAX; self.program.progress_slots],
            };
            match vm.run(thread) {
                Some(end) => {
                    spans.push((start, end));
                    // `re.finditer` advances one position past an empty match, or
                    // it would return the same one for ever.
                    start = if end > start { end } else { start + 1 };
                }
                None => {
                    if vm.exhausted {
                        return Err(StepBudgetExceeded);
                    }
                    start += 1;
                }
            }
        }
        Ok(spans)
    }

    /// Whether the pattern matches anywhere in `text`.
    ///
    /// `Err` means the pattern was too expensive to decide. It is never a
    /// disguised "no match": reporting one would be a confident wrong answer.
    pub fn search(&self, text: &str) -> Result<bool, StepBudgetExceeded> {
        let haystack: Vec<char> = text.chars().collect();

        // Reject on a required literal before entering the VM. This is what keeps
        // ordinary patterns off the step budget, and it is the common case: most
        // sessions do not contain what is being searched for.
        if let Some(needle) = &self.required_literal {
            if !haystack_contains(&haystack, needle, self.ignorecase) {
                return Ok(false);
            }
        }

        let mut vm = Vm {
            haystack: &haystack,
            program: &self.program,
            matched: None,
            steps: 0,
            exhausted: false,
        };
        let slots = self.program.capture_slots;
        for start in 0..=haystack.len() {
            let thread = Thread {
                pc: 0,
                position: start,
                saves: vec![None; slots],
                marks: vec![usize::MAX; self.program.progress_slots],
            };
            if vm.run(thread).is_some() {
                return Ok(true);
            }
            if vm.exhausted {
                return Err(StepBudgetExceeded);
            }
        }
        Ok(false)
    }
}

pub fn parse_search_query(pattern_arg: &str, case_sensitive: bool) -> Result<Query, SearchQueryError> {
    let Some(tokens) = tokenize(pattern_arg) else {
        return Ok(Query::Term(compile_search_term(pattern_arg, case_sensitive)));
    };
    let has_and_or = tokens.iter().any(|token| matches!(token.kind, Kind::And | Kind::Or));
    let has_not = tokens.iter().any(|token| token.kind == Kind::Not);
    if has_and_or && has_not {
        return Err(SearchQueryError(
            "Mixing NOT with AND/OR is not supported. Use one operator type per query.".to_string(),
        ));
    }
    if has_and_or {
        let has_operand = tokens.iter().any(|token| !matches!(token.kind, Kind::And | Kind::Or));
        if !has_operand {
            return Ok(Query::Term(compile_search_term(pattern_arg, case_sensitive)));
        }
        return BooleanParser { tokens: &tokens, position: 0, case_sensitive }.parse();
    }
    if has_not {
        let has_term = tokens.iter().any(|token| token.kind == Kind::Term);
        if !has_term {
            return Ok(Query::Term(compile_search_term(pattern_arg, case_sensitive)));
        }
        return parse_not_query(&tokens, case_sensitive);
    }
    Ok(Query::Term(compile_search_term(pattern_arg, case_sensitive)))
}

fn quoted(text: &str) -> String {
    format!("'{}'", text.replace('\'', "\\'"))
}

fn parse_not_query(tokens: &[Token], case_sensitive: bool) -> Result<Query, SearchQueryError> {
    let invalid = |message: String| Err(SearchQueryError(message));
    let first = &tokens[0];
    if first.kind != Kind::Term {
        return invalid(format!(
            "Invalid search query: NOT requires a leading positive term, got {}.",
            quoted(&first.text)
        ));
    }
    if first.text.is_empty() {
        return invalid("Invalid search query: empty quoted term.".to_string());
    }
    let mut operands = vec![Query::Term(compile_search_term(&first.text, case_sensitive))];
    let mut position = 1;
    while position < tokens.len() {
        let token = &tokens[position];
        match token.kind {
            Kind::LParen | Kind::RParen => {
                return invalid(
                    "Invalid search query: parentheses are not supported with NOT.".to_string(),
                );
            }
            Kind::Term => {
                return invalid(format!(
                    "Invalid search query: unexpected term {}. Quote multi-word terms, e.g. '\"hello world\" NOT foo'.",
                    quoted(&token.text)
                ));
            }
            Kind::And | Kind::Or => {
                return invalid(format!("Invalid search query: unexpected {}.", quoted(&token.text)));
            }
            Kind::Not => {}
        }
        position += 1;
        if position >= tokens.len() {
            return invalid(
                "Invalid search query: expected a term after NOT, got end of pattern.".to_string(),
            );
        }
        let next_token = &tokens[position];
        if matches!(next_token.kind, Kind::LParen | Kind::RParen) {
            return invalid(
                "Invalid search query: parentheses are not supported with NOT.".to_string(),
            );
        }
        if next_token.kind != Kind::Term {
            return invalid(format!(
                "Invalid search query: expected a term after NOT, got {}.",
                quoted(&next_token.text)
            ));
        }
        if next_token.text.is_empty() {
            return invalid("Invalid search query: empty quoted term.".to_string());
        }
        operands.push(Query::Not(Box::new(Query::Term(compile_search_term(
            &next_token.text,
            case_sensitive,
        )))));
        position += 1;
    }
    Ok(if operands.len() == 1 { operands.pop().expect("non-empty") } else { Query::And(operands) })
}

struct BooleanParser<'t> {
    tokens: &'t [Token],
    position: usize,
    case_sensitive: bool,
}

impl BooleanParser<'_> {
    fn parse(mut self) -> Result<Query, SearchQueryError> {
        let query = self.parse_or()?;
        if self.position != self.tokens.len() {
            let leftover = &self.tokens[self.position];
            if leftover.kind == Kind::Term {
                return Err(SearchQueryError(format!(
                    "Invalid search query: unexpected term {}. Quote multi-word terms, e.g. '\"hello world\" AND foo'.",
                    quoted(&leftover.text)
                )));
            }
            return Err(SearchQueryError(format!(
                "Invalid search query: unexpected {}.",
                quoted(&leftover.text)
            )));
        }
        Ok(query)
    }

    fn peek_kind(&self) -> Option<Kind> {
        self.tokens.get(self.position).map(|token| token.kind)
    }

    fn parse_or(&mut self) -> Result<Query, SearchQueryError> {
        let mut operands = vec![self.parse_and()?];
        while self.peek_kind() == Some(Kind::Or) {
            self.position += 1;
            operands.push(self.parse_and()?);
        }
        Ok(if operands.len() == 1 { operands.pop().expect("non-empty") } else { Query::Or(operands) })
    }

    fn parse_and(&mut self) -> Result<Query, SearchQueryError> {
        let mut operands = vec![self.parse_atom()?];
        while self.peek_kind() == Some(Kind::And) {
            self.position += 1;
            operands.push(self.parse_atom()?);
        }
        Ok(if operands.len() == 1 { operands.pop().expect("non-empty") } else { Query::And(operands) })
    }

    fn parse_atom(&mut self) -> Result<Query, SearchQueryError> {
        let Some(token) = self.tokens.get(self.position) else {
            return Err(SearchQueryError(
                "Invalid search query: expected a term, got end of pattern.".to_string(),
            ));
        };
        match token.kind {
            Kind::LParen => {
                self.position += 1;
                let group = self.parse_or()?;
                if self.peek_kind() != Some(Kind::RParen) {
                    return Err(SearchQueryError(
                        "Invalid search query: missing closing ')'.".to_string(),
                    ));
                }
                self.position += 1;
                Ok(group)
            }
            Kind::Term => {
                if token.text.is_empty() {
                    return Err(SearchQueryError(
                        "Invalid search query: empty quoted term.".to_string(),
                    ));
                }
                self.position += 1;
                Ok(Query::Term(compile_search_term(&token.text, self.case_sensitive)))
            }
            _ => Err(SearchQueryError(format!(
                "Invalid search query: expected a term, got {}.",
                quoted(&token.text)
            ))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hits(pattern: &str, text: &str) -> bool {
        Regex::compile(pattern, true)
            .expect("pattern compiles")
            .search(text)
            .expect("pattern is within the evaluation budget")
    }

    fn compiles(pattern: &str) -> bool {
        Regex::compile(pattern, true).is_ok()
    }

    #[test]
    fn empty_min_interval_is_quantifier() {
        assert!(compiles("a{,2}"));
        assert!(hits("a{,2}", "needle aa tail"));
        assert!(hits("a{,}", "aaa"));
        // Bare braces without comma stay literal (CPython parity).
        assert!(hits(r"a\{\}", "x a{} y"));
    }

    #[test]
    fn verbose_mode_strips_whitespace_and_comments() {
        assert!(compiles("(?x)fo obar"));
        assert!(hits("(?x)fo obar", "xxfoobarxx"));
        assert!(hits("(?x:a b)", "zabz"));
        assert!(!hits("(?x)fo-ob", "foobar"));
        assert!(hits("(?x)foo # trailing comment", "foo"));
    }

    #[test]
    fn scoped_flags_drive_anchor_evaluation() {
        assert!(hits("^two$", "one\ntwo\nthree"), "default M anchors mid-text");
        assert!(!hits("(?-m:^two$)", "one\ntwo\nthree"));
        assert!(!hits("(?-m:^two$)", "two\nthree"), "non-final newline is not an end without M");
        assert!(hits("(?-m:^two$)", "two"));
        assert!(hits("(?-m:^two$)", "two\n"), "pre-final-newline end holds without M");
        assert!(!hits("(?i-m:^TWO$)", "one\ntwo\nthree"));
        assert!(hits("(?i-m:^two$)", "TWO"));
    }

    #[test]
    fn variable_length_lookbehind_rejects_to_fallback() {
        assert!(compiles("(?<=ab)c"));
        assert!(compiles("(?<=a{3})b"));
        assert!(compiles("(?<=ab|cd)x"));
        assert!(!compiles("(?<=ab+)c"));
        assert!(!compiles("(?<=a*)b"));
        assert!(!compiles("(?<=a+|b)c"));
        assert!(Regex::compile("(?!ab+)", true).is_ok(), "lookahead stays width-free");
    }

    /// A backreference compares under the pattern's own case mode. CPython:
    /// `re.match(r"(\w+)x\1", "PYxpy")` is None, and matches only under IGNORECASE.
    ///
    /// Found by `lexer-tables`: an unconditional fold made a Bash heredoc opened
    /// with `<<'PY'` terminate at the `py` inside `print("hello from uv python")`.
    #[test]
    fn a_backreference_does_not_fold_case_unless_the_pattern_asked() {
        assert_eq!(
            Regex::compile(r"(\w+)x\1", false).expect("compiles").search("PYxpy"),
            Ok(false),
            "a case-sensitive backreference must not match a differently-cased repeat"
        );
    }

    /// The control: turning the fold off everywhere would break this one, so a fix
    /// that over-corrects cannot pass both.
    #[test]
    fn a_backreference_does_fold_case_when_the_pattern_is_insensitive() {
        assert_eq!(
            Regex::compile(r"(\w+)x\1", true).expect("compiles").search("PYxpy"),
            Ok(true),
            "a case-insensitive backreference must match a differently-cased repeat"
        );
    }

    /// The pathological case has no golden fixture, because the oracle produces
    /// no answer to record: CPython does not terminate on this pattern. The bar
    /// is therefore "does not hang, and does not lie".
    #[test]
    fn catastrophic_pattern_fails_loud_instead_of_answering_wrongly() {
        // The required literal has to be present, or the prescan answers first
        // and the evaluator is never entered.
        let haystack = "a".repeat(40) + "cb";
        let outcome = Regex::compile("(?:a|a)*b", true)
            .expect("compiles")
            .search(&haystack);
        assert_eq!(
            outcome,
            Err(StepBudgetExceeded),
            "a pattern too expensive to decide must report that, never `no match`"
        );
    }

    /// The prescan answers most catastrophic patterns outright, because the text
    /// they need is usually absent. Cheaper than the guard and exactly correct.
    #[test]
    fn prescan_answers_catastrophic_patterns_whose_literal_is_absent() {
        let haystack = "a".repeat(40) + "c";
        assert_eq!(
            Regex::compile("(?:a|a)*b", true).expect("compiles").search(&haystack),
            Ok(false),
            "no `b` in the haystack, so no match is decidable without the evaluator"
        );
    }

    /// The prescan is the reason ordinary patterns never reach the budget. This
    /// pins the case that used to return a confident wrong answer at 20k chars.
    #[test]
    fn ordinary_pattern_on_a_large_message_stays_correct() {
        let haystack = "the parser reads the file ".repeat(2_000) + "NEEDLE";
        assert_eq!(
            Regex::compile("[a-z ]*NEEDLE", true).expect("compiles").search(&haystack),
            Ok(true),
            "an ordinary pattern over a large message must not exhaust the budget"
        );
    }

    /// The prescan must never reject a haystack the engine would have matched.
    #[test]
    fn required_literal_prescan_never_loses_a_match() {
        for (pattern, text) in [
            ("foo|bar", "bar"),
            ("(?:alpha)?beta", "beta"),
            ("(?i:NEEDLE)", "needle"),
            ("a{0,3}z", "z"),
            ("[hij]", "\u{131}"),
        ] {
            assert_eq!(
                Regex::compile(pattern, true).expect("compiles").search(text),
                Ok(true),
                "prescan dropped a real match for {pattern:?} against {text:?}"
            );
        }
    }

    #[test]
    fn valid_engine_patterns_compile() {
        for pattern in [
            "^line2", "end$", r"foo\d+", "[A-Z]+PITAL", "one.*three", "^two$", r"\bMIDDLE\b",
            r"(?P<w>echo) (?P=w)", "foo(?=123)", "foo(?!999)", "(?<=start )MIDDLE",
            "(red|quick)", r"a\-b", r"tab\tend", r"caf\u00e9", r"C\101PITAL",
            r"\N{GREEK SMALL LETTER ALPHA}", "(?>echo) echo", "a++g", "()(?(1)kettlexyz|zzz)",
            r"end\Z", "(?i:NEEDLE) one", "zznope|", "fox|",
        ] {
            assert!(compiles(pattern), "expected valid: {pattern}");
        }
    }

    #[test]
    fn invalid_engine_patterns_reject_to_fallback() {
        for pattern in [
            "(?<x>a)", r"\p{L}", r"\x{41} braced hex", "[z-a] range", "a{2,1} inverted",
            r"\8 digit ref", "(?P=name) group ref", "(?(1)x|y) conditional", r"\y bad escape",
            "open( paren", "bracket[mismatch",
        ] {
            assert!(!compiles(pattern), "expected invalid: {pattern}");
        }
    }

    #[test]
    fn posix_nested_set_warning_positions_follow_cpython() {
        let parse_warnings = |pattern: &str| {
            let characters: Vec<char> = pattern.chars().collect();
            let mut parser = PatternParser {
                characters: &characters,
                position: 0,
                flags: Flags { ignorecase: true, multiline: true, dotall: true, verbose: false, ascii: false },
                global_flags_locked: false,
                group_count: 0,
                group_names: Vec::new(),
                open_groups: Vec::new(),
                warnings: Vec::new(),
            };
            let outcome = parser.parse_alternation();
            (outcome.is_ok(), parser.warnings)
        };
        let (ok, warnings) = parse_warnings("[[:alpha:]]");
        assert!(ok);
        assert_eq!(warnings, vec![warning_text(1)]);
        let (ok, warnings) = parse_warnings("x[[:alpha:]]");
        assert!(ok);
        assert_eq!(warnings, vec![warning_text(2)]);
        let (ok, warnings) = parse_warnings("[abc[:d]]");
        assert!(ok);
        assert!(warnings.is_empty());
    }

    #[test]
    fn posix_class_semantics_match_cpython() {
        let body = "literal \"[[:alpha:]] class\" here";
        // Bare: class of {[,:,a,l,p,h} then a literal ']' -> matches ':]'.
        assert!(hits("[[:alpha:]]", body));
        // Suffixed needs <set>']] class' overlap; two closing brackets break it.
        assert!(!hits("[[:alpha:]] class", body));
    }

    #[test]
    fn ignorecase_folding_matches_the_sre_table() {
        assert!(hits("i", "\u{0130}stanbul"));
        assert!(hits("\u{0130}", "istanbul dotted"));
        assert!(!hits("I\u{307}", "\u{0130}stanbul"));
        assert!(hits("\u{0130}", "i\u{307} x"));
        assert!(hits("s", "\u{17f}teady"));
        assert!(hits("\u{17f}", "steady long s"));
        assert!(hits("k", "\u{212a}elvin"));
        assert!(hits("\u{212a}", "kelvin k sign"));
        assert!(!hits("ss", "\u{00df}"));
        assert!(!hits("\u{00df}", "ss"));
    }

    #[test]
    fn anchors_match_python_dollar_and_z() {
        assert!(hits("end$", "trailing tab\tend\n"));
        assert!(!hits(r"end\Z", "trailing tab\tend\n"));
        assert!(hits(r"end\Z", "trailing tab\tend"));
        assert!(hits("^line2", "start MIDDLE end\nline2 foo123 bar\n"));
        assert!(hits("^two$", "one\ntwo\nthree\n"));
    }

    #[test]
    fn empty_alternation_branches_match_everything() {
        assert!(hits("zznope|", ""));
        assert!(hits("fox|", "nothing here at all"));
        assert!(hits("red fox running|", "red fox running"));
    }

    #[test]
    fn exotic_quantifier_forms_track_cpython() {
        assert!(hits("(?>echo) echo", "echo echo again"));
        assert!(hits("a++g", "piuseragentresponse has no aag but caag does"));
        assert!(hits("a++g", "xx aag yy"));
        assert!(hits("a++g", "xx ag yy")); // one 'a' satisfies a++; no backtracking needed
        assert!(!hits("(?>a*)a", "aaa"));
        // Atomic commitment: the inner star keeps everything, outer 'a' starves.
        assert!(!hits("(?>a*)a", "aaa"));
    }

    #[test]
    fn lookarounds_and_conditionals_and_backrefs() {
        assert!(hits("foo(?=123)", "foo123 bar"));
        assert!(!hits("foo(?=123)", "foo999 bar"));
        assert!(hits("foo(?!999)", "foo123 bar"));
        assert!(!hits("foo(?!999)", "foo999 bar"));
        assert!(hits("(?<=start )MIDDLE", "start MIDDLE end"));
        assert!(!hits("(?<=start )MIDDLE", "begin MIDDLE end"));
        assert!(hits("()(?(1)kettlexyz|zzz)", "kettlexyz conditional target"));
        assert!(!hits("()(?(1)kettlexyz|zzz)", "nothing relevant here"));
        assert!(hits(r"(?P<w>echo) (?P=w)", "echo echo again"));
        assert!(hits(r"(?P<w>ECHO) (?P=w)", "echo echo again"));
        assert!(!hits(r"(?P<w>echo) (?P=w)", "echo different"));
    }

    #[test]
    fn scoped_inline_flags_stay_scoped() {
        assert!(hits("(?i:NEEDLE) one", "needle one"));
        let case_sensitive_outer = Regex::compile("(?i:foo)bar", false).expect("compiles");
        assert_eq!(case_sensitive_outer.search("FOObar"), Ok(true));
        assert_eq!(case_sensitive_outer.search("fooBAR"), Ok(false));
    }

    #[test]
    fn escapes_octal_hex_and_named_unicode() {
        assert!(hits(r"C\101PITAL", "CAPITAL letters here"));
        assert!(hits(r"caf\u00e9", "caf\u{e9} unicode line"));
        assert!(hits(r"\N{GREEK SMALL LETTER ALPHA}", "greek alpha \u{3b1} here"));
        assert!(hits(r"tab\tend", "trailing tab\tend"));
        assert!(hits(r"a\-b", "a-b hyphenated"));
    }

    #[test]
    fn invalid_patterns_take_the_literal_fallback() {
        let term = compile_search_term("[z-a] range", false);
        assert_eq!(term.literal_candidate.as_deref(), Some("[z-a] range"));
        assert_eq!(term.engine.search("[z-a] range\n"), Ok(true));
        let term = compile_search_term(r"\y bad escape", true);
        assert_eq!(term.literal_candidate.as_deref(), Some(r"\y bad escape"));
        assert!(term.case_sensitive);
    }

    #[test]
    fn boolean_parser_precedence_errors_and_not_paths() {
        let query = parse_search_query("red AND quick OR dog", false).expect("parses");
        // AND binds tighter: (red AND quick) OR dog.
        let terms: Vec<_> = query.iter_terms();
        assert_eq!(terms.len(), 3);

        let query = parse_search_query("(red OR quick) AND dog", false).expect("parses");
        assert_eq!(query.iter_terms().len(), 3);

        let not_only = parse_search_query("needle NOT fox", false).expect("parses");
        match not_only {
            Query::And(operands) => assert_eq!(operands.len(), 2),
            other => panic!("expected AND of positive and negation, got {other:?}"),
        }

        let mixed = parse_search_query("NOT needle AND fox", false);
        assert_eq!(
            mixed.err().map(|error| error.0),
            Some("Mixing NOT with AND/OR is not supported. Use one operator type per query.".to_string())
        );

        let leading_not = parse_search_query("NOT needle", false);
        assert_eq!(
            leading_not.err().map(|error| error.0),
            Some(
                "Invalid search query: NOT requires a leading positive term, got 'NOT'.".to_string()
            )
        );

        let trailing_not = parse_search_query("needle NOT", false);
        assert_eq!(
            trailing_not.err().map(|error| error.0),
            Some("Invalid search query: expected a term after NOT, got end of pattern.".to_string())
        );

        // Migrated from the legacy Python route's operator suite: dangling
        // AND/OR, lowercase operator words as one literal pattern, and bare
        // operator words.
        let dangling_and = parse_search_query("needle AND", false);
        assert!(dangling_and.is_err(), "dangling AND must be rejected");
        let dangling_or = parse_search_query("fox OR", false);
        assert!(dangling_or.is_err(), "dangling OR must be rejected");
        let lowercase_operators = parse_search_query("red and quick or dog", false).expect("parses");
        match &lowercase_operators {
            Query::Term(term) => {
                assert_eq!(term.pattern, "red and quick or dog");
            }
            other => panic!("lowercase operator words stay one pattern, got {other:?}"),
        }
        let bare_and = parse_search_query("AND", false).expect("parses");
        assert!(matches!(bare_and, Query::Term(_)));
        let bare_not = parse_search_query("NOT", false).expect("parses");
        assert!(matches!(bare_not, Query::Term(_)));

        // Case sensitivity propagates to negated terms.
        let sensitive = parse_search_query("MATCH NOT alpha", true).expect("parses");
        match &sensitive {
            Query::And(operands) => {
                assert_eq!(operands.len(), 2);
                for operand in operands {
                    let term = match operand {
                        Query::Term(term) => term,
                        Query::Not(inner) => match inner.as_ref() {
                            Query::Term(term) => term,
                            other => panic!("unexpected operand {other:?}"),
                        },
                        other => panic!("unexpected operand {other:?}"),
                    };
                    assert!(term.case_sensitive, "sensitivity must reach every term");
                }
            }
            other => panic!("expected AND with negation, got {other:?}"),
        }
    }

    #[test]
    fn unterminated_quotes_send_whole_pattern_down_single_term_path() {
        let query = parse_search_query("\"unterminated needle", false).expect("parses");
        match query {
            Query::Term(term) => assert_eq!(term.pattern, "\"unterminated needle"),
            other => panic!("expected single term, got {other:?}"),
        }
    }
}

#[cfg(test)]
mod dot_pattern_invariant {
    use super::*;

    /// `.` must never carry a `literal_candidate`.
    ///
    /// It is a regex metacharacter that matches everything, so a literal
    /// candidate would make the byte gate probe files for a full stop and
    /// silently reject almost all of them — the losing direction, where a search
    /// quietly returns fewer results with no error anywhere.
    ///
    /// This replaces a `Query::term_dot()` constructor that had no callers. It
    /// was hand-built with `literal_candidate: None`, which looked like a guard
    /// against exactly this. It was not: the ordinary parse already produces an
    /// identical term, proved field by field and across probes before removal.
    /// The constructor was redundant; the property it appeared to protect is
    /// real, so it is asserted here instead.
    #[test]
    fn a_dot_pattern_has_no_literal_candidate() {
        let Ok(Query::Term(term)) = parse_search_query(".", false) else {
            panic!("`.` parses as a single term");
        };
        assert_eq!(
            term.literal_candidate, None,
            "A literal candidate for `.` would make the byte gate reject files the regex matches."
        );
        for probe in ["anything", "\u{4e2d}", "a\nb"] {
            assert_eq!(
                term.engine.search(probe).ok(),
                Some(true),
                "`.` must match {probe:?}"
            );
        }
    }
}
