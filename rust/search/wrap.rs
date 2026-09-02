//! Python `textwrap.wrap` for the inputs argparse feeds it.
//!
//! argparse normalizes whitespace to single spaces before wrapping, so the only
//! parts of `textwrap` that matter here are chunking on spaces and hyphens, the
//! greedy line fill, and long-word breaking. The hyphen rule is why `--no-paging`
//! becomes `--no-` + `paging` at narrow widths.
//!
//! Deliberately not ported: the em-dash rule, which splits before `--` when it
//! follows word punctuation. No help string in the grammar reaches it, and the
//! width sweep over 181 widths would fail if one did.

/// Python's `[^\d\W]`: a word character that is not a digit.
fn is_letter(character: char) -> bool {
    (character.is_alphanumeric() || character == '_')
        && unicode_general_category::get_general_category(character)
            != unicode_general_category::GeneralCategory::DecimalNumber
}

/// Split one whitespace-free word the way `wordsep_re` does.
///
/// A hyphen ends a chunk when two letters precede it (or letter-hyphen-letter)
/// and a letter, optional hyphen, letter follows.
///
/// ```
/// # use _native::search::wrap::split_word;
/// assert_eq!(split_word("--no-paging"), vec!["--no-", "paging"]);
/// assert_eq!(split_word("--color"), vec!["--color"]);
/// ```
pub fn split_word(word: &str) -> Vec<String> {
    let characters: Vec<char> = word.chars().collect();
    let mut chunks = Vec::new();
    let mut start = 0;
    for index in 0..characters.len() {
        if characters[index] != '-' {
            continue;
        }
        let two_letters_before = index >= 2
            && is_letter(characters[index - 1])
            && is_letter(characters[index - 2]);
        let letter_hyphen_letter_before = index >= 3
            && is_letter(characters[index - 1])
            && characters[index - 2] == '-'
            && is_letter(characters[index - 3]);
        if !(two_letters_before || letter_hyphen_letter_before) {
            continue;
        }
        let after = &characters[index + 1..];
        let follows = match after {
            [first, second, ..] if is_letter(*first) && is_letter(*second) => true,
            [first, '-', third, ..] if is_letter(*first) && is_letter(*third) => true,
            _ => false,
        };
        if !follows {
            continue;
        }
        chunks.push(characters[start..=index].iter().collect::<String>());
        start = index + 1;
    }
    if start < characters.len() {
        chunks.push(characters[start..].iter().collect::<String>());
    }
    if chunks.is_empty() {
        chunks.push(String::new());
    }
    chunks
}

/// Break a chunk that cannot fit, preferring a hyphen boundary. Python's
/// `_handle_long_word`.
fn break_long(chunk: &str, space_left: usize) -> usize {
    let characters: Vec<char> = chunk.chars().collect();
    let mut end = space_left.max(1);
    if characters.len() > space_left {
        if let Some(hyphen) = characters[..space_left.min(characters.len())]
            .iter()
            .rposition(|character| *character == '-')
        {
            if hyphen > 0 && characters[..hyphen].iter().any(|character| *character != '-') {
                end = hyphen + 1;
            }
        }
    }
    end.min(characters.len())
}

/// Wrap `text` to `width`, matching `textwrap.wrap(text, width)`.
///
/// ```
/// # use _native::search::wrap::wrap;
/// assert_eq!(wrap("a b c", 3), vec!["a b", "c"]);
/// assert_eq!(wrap("", 10), Vec::<String>::new());
/// ```
pub fn wrap(text: &str, width: usize) -> Vec<String> {
    // argparse's `_split_lines` collapses whitespace and strips before wrapping.
    let normalized: String = text.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.is_empty() {
        return Vec::new();
    }

    let mut chunks: Vec<String> = Vec::new();
    for (index, word) in normalized.split(' ').enumerate() {
        if index > 0 {
            chunks.push(" ".to_string());
        }
        chunks.extend(split_word(word));
    }
    chunks.reverse();

    let mut lines: Vec<String> = Vec::new();
    while !chunks.is_empty() {
        // `drop_whitespace`: a wrapped line never starts with the space that
        // ended the previous one.
        if !lines.is_empty() && chunks.last().is_some_and(|chunk| chunk.trim().is_empty()) {
            chunks.pop();
        }

        let mut line: Vec<String> = Vec::new();
        let mut length = 0usize;
        while let Some(chunk) = chunks.last() {
            let chunk_length = chunk.chars().count();
            if length + chunk_length > width {
                break;
            }
            length += chunk_length;
            line.push(chunks.pop().expect("peeked"));
        }

        if let Some(chunk) = chunks.last() {
            if chunk.chars().count() > width {
                let space_left = width.saturating_sub(length);
                let end = break_long(chunk, space_left);
                let characters: Vec<char> = chunk.chars().collect();
                line.push(characters[..end].iter().collect());
                let remainder: String = characters[end..].iter().collect();
                chunks.pop();
                if !remainder.is_empty() {
                    chunks.push(remainder);
                }
            }
        }

        if line.last().is_some_and(|chunk| chunk.trim().is_empty()) {
            line.pop();
        }
        if !line.is_empty() {
            lines.push(line.concat());
        } else if !chunks.is_empty() {
            // No progress possible; drop a chunk rather than spin forever.
            chunks.pop();
        }
    }
    lines
}
