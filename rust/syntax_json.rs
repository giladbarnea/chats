//! Pygments' JSON lexer, which is **not a `RegexLexer`**.
//!
//! Every other promoted family is a table of `(pattern, action, transition)` triples
//! that [`crate::syntax_lexer`] runs. `JsonLexer` is not: Pygments hand-writes it as
//! a character scanner with eleven flags and a queue, and there is no `_tokens` to
//! generate from. **So this is the one family that is a port of behaviour rather
//! than a projection of data**, and it is gated accordingly — against the
//! reference's own output over real fenced blocks, with the reference's own line
//! coverage standing in for the rule coverage a table would have.
//!
//! It is 12.4% of real fenced blocks, the third largest share.
//!
//! **The queue is the whole reason the scanner exists.** A quoted string is an object
//! key or a string value, and nothing inside it says which — only the next
//! punctuation does. So a closed string waits in the queue, and a `:` rewrites it
//! from `String.Double` to `Name.Tag` on the way out.

/// Pygments' four whitespace characters. **Not `char::is_whitespace`**, which
/// accepts a form feed and a vertical tab that this scanner treats as errors.
const WHITESPACE: [char; 4] = [' ', '\n', '\r', '\t'];

/// The characters of `true`, `false` and `null`, as a set rather than as words: the
/// reference does no validation, so `trustful` scans as one constant.
const CONSTANT: [char; 9] = ['a', 'e', 'f', 'l', 'n', 'r', 's', 't', 'u'];

const INTEGER: [char; 11] = ['-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
const FLOAT: [char; 4] = ['.', 'e', 'E', '+'];
const PUNCTUATION: [char; 5] = ['{', '}', '[', ']', ','];

const STRING_DOUBLE: &str = "Token.Literal.String.Double";
const NAME_TAG: &str = "Token.Name.Tag";
const WHITESPACE_TOKEN: &str = "Token.Text.Whitespace";
const KEYWORD_CONSTANT: &str = "Token.Keyword.Constant";
const NUMBER_FLOAT: &str = "Token.Literal.Number.Float";
const NUMBER_INTEGER: &str = "Token.Literal.Number.Integer";
const PUNCTUATION_TOKEN: &str = "Token.Punctuation";
const COMMENT_SINGLE: &str = "Token.Comment.Single";
const COMMENT_MULTILINE: &str = "Token.Comment.Multiline";
const ERROR: &str = "Token.Error";

/// One scanned run: the token's dotted path and its text.
type Token = (String, String);

/// Split JSON into `(token path, text)` pairs, as `JsonLexer.get_tokens_unprocessed`
/// does.
///
/// No validation: the reference scans `--1--` as an integer and `trustful` as a
/// constant, and reproducing that is the point.
///
/// ```
/// use _native::syntax_json::tokenize;
/// let tokens = tokenize("{\"a\": 1}");
/// assert_eq!(tokens[0], ("Token.Punctuation".to_string(), "{".to_string()));
/// // A string before a colon is a key, not a value.
/// assert_eq!(tokens[1], ("Token.Name.Tag".to_string(), "\"a\"".to_string()));
/// assert_eq!(tokens[4], ("Token.Literal.Number.Integer".to_string(), "1".to_string()));
/// ```
pub fn tokenize(text: &str) -> Vec<Token> {
    let characters: Vec<char> = text.chars().collect();
    let mut out: Vec<Token> = Vec::new();
    // The queue holds tokens whose type is not decided yet, because a `:` after a
    // string turns it into a key.
    let mut queue: Vec<Token> = Vec::new();

    let mut in_string = false;
    let mut in_escape = false;
    let mut in_unicode_escape = 0usize;
    let mut in_whitespace = false;
    let mut in_constant = false;
    let mut in_number = false;
    let mut in_float = false;
    let mut in_punctuation = false;
    let mut in_comment_single = false;
    let mut in_comment_multiline = false;
    let mut expecting_second_comment_opener = false;
    let mut expecting_second_comment_closer = false;

    let mut start = 0usize;
    let slice = |range: std::ops::Range<usize>| -> String { characters[range].iter().collect() };

    for stop in 0..characters.len() {
        let character = characters[stop];

        // Each arm either `continue`s — leaving `start` where it is, so the run
        // grows — or falls through to have the same character evaluated fresh.
        if in_string {
            if in_unicode_escape > 0 {
                if character.is_ascii_hexdigit() {
                    in_unicode_escape -= 1;
                    if in_unicode_escape == 0 {
                        in_escape = false;
                    }
                } else {
                    in_unicode_escape = 0;
                    in_escape = false;
                }
            } else if in_escape {
                if character == 'u' {
                    in_unicode_escape = 4;
                } else {
                    in_escape = false;
                }
            } else if character == '\\' {
                in_escape = true;
            } else if character == '"' {
                queue.push((STRING_DOUBLE.to_string(), slice(start..stop + 1)));
                in_string = false;
                in_escape = false;
                in_unicode_escape = 0;
            }
            continue;
        } else if in_whitespace {
            if WHITESPACE.contains(&character) {
                continue;
            }
            let token = (WHITESPACE_TOKEN.to_string(), slice(start..stop));
            if queue.is_empty() {
                out.push(token);
            } else {
                queue.push(token);
            }
            in_whitespace = false;
        } else if in_constant {
            if CONSTANT.contains(&character) {
                continue;
            }
            out.push((KEYWORD_CONSTANT.to_string(), slice(start..stop)));
            in_constant = false;
        } else if in_number {
            if INTEGER.contains(&character) {
                continue;
            } else if FLOAT.contains(&character) {
                in_float = true;
                continue;
            }
            let path = if in_float { NUMBER_FLOAT } else { NUMBER_INTEGER };
            out.push((path.to_string(), slice(start..stop)));
            in_number = false;
            in_float = false;
        } else if in_punctuation {
            if PUNCTUATION.contains(&character) {
                continue;
            }
            out.push((PUNCTUATION_TOKEN.to_string(), slice(start..stop)));
            in_punctuation = false;
        } else if in_comment_single {
            if character != '\n' {
                continue;
            }
            let token = (COMMENT_SINGLE.to_string(), slice(start..stop));
            if queue.is_empty() {
                out.push(token);
            } else {
                queue.push(token);
            }
            in_comment_single = false;
        } else if in_comment_multiline {
            if character == '*' {
                expecting_second_comment_closer = true;
            } else if expecting_second_comment_closer {
                expecting_second_comment_closer = false;
                if character == '/' {
                    let token = (COMMENT_MULTILINE.to_string(), slice(start..stop + 1));
                    if queue.is_empty() {
                        out.push(token);
                    } else {
                        queue.push(token);
                    }
                    in_comment_multiline = false;
                }
            }
            continue;
        } else if expecting_second_comment_opener {
            expecting_second_comment_opener = false;
            if character == '/' {
                in_comment_single = true;
                continue;
            } else if character == '*' {
                in_comment_multiline = true;
                continue;
            }
            out.append(&mut queue);
            out.push((ERROR.to_string(), slice(start..stop)));
        }

        start = stop;

        if character == '"' {
            in_string = true;
        } else if WHITESPACE.contains(&character) {
            in_whitespace = true;
        } else if character == 'f' || character == 'n' || character == 't' {
            out.append(&mut queue);
            in_constant = true;
        } else if INTEGER.contains(&character) {
            out.append(&mut queue);
            in_number = true;
        } else if character == ':' {
            // **The queue's whole purpose.** A string that reaches a colon was an
            // object key all along, so its type is rewritten on the way out.
            for (path, value) in queue.drain(..) {
                let path = if path == STRING_DOUBLE { NAME_TAG.to_string() } else { path };
                out.push((path, value));
            }
            in_punctuation = true;
        } else if PUNCTUATION.contains(&character) {
            out.append(&mut queue);
            in_punctuation = true;
        } else if character == '/' {
            expecting_second_comment_opener = true;
        } else {
            out.append(&mut queue);
            out.push((ERROR.to_string(), character.to_string()));
        }
    }

    // Whatever is still open at the end of the text. **An unterminated string is an
    // `Error`, not a string** — the one place the scanner refuses to guess.
    out.append(&mut queue);
    let rest = || -> String { characters[start..].iter().collect() };
    if in_string {
        out.push((ERROR.to_string(), rest()));
    } else if in_float {
        out.push((NUMBER_FLOAT.to_string(), rest()));
    } else if in_number {
        out.push((NUMBER_INTEGER.to_string(), rest()));
    } else if in_constant {
        out.push((KEYWORD_CONSTANT.to_string(), rest()));
    } else if in_whitespace {
        out.push((WHITESPACE_TOKEN.to_string(), rest()));
    } else if in_punctuation {
        out.push((PUNCTUATION_TOKEN.to_string(), rest()));
    } else if in_comment_single {
        out.push((COMMENT_SINGLE.to_string(), rest()));
    } else if in_comment_multiline {
        out.push((ERROR.to_string(), rest()));
    } else if expecting_second_comment_opener {
        out.push((ERROR.to_string(), rest()));
    }
    out
}
