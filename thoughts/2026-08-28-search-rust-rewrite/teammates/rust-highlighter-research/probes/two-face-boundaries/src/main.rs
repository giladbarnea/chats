use std::collections::BTreeSet;
use std::env;
use std::fs;

use serde_json::Value;
use two_face::re_exports::syntect::parsing::{ParseState, SyntaxReference, SyntaxSet};
use two_face::re_exports::syntect::util::LinesWithEndings;

fn pygments_boundaries(case: &Value) -> BTreeSet<usize> {
    let mut boundaries = BTreeSet::from([0]);
    let mut offset = 0;
    for token in case["tokens"].as_array().expect("tokens array") {
        offset += token[1].as_str().expect("token text").len();
        boundaries.insert(offset);
    }
    boundaries
}

fn syntect_boundaries(
    syntax_set: &SyntaxSet,
    syntax: &SyntaxReference,
    source: &str,
) -> BTreeSet<usize> {
    let mut parser = ParseState::new(syntax);
    let mut boundaries = BTreeSet::from([0, source.len()]);
    let mut offset = 0;
    for line in LinesWithEndings::from(source) {
        for (index, _) in parser.parse_line(line, syntax_set).expect("parse line") {
            boundaries.insert(offset + index);
        }
        offset += line.len();
        boundaries.insert(offset);
    }
    boundaries
}

fn main() {
    let mut arguments = env::args().skip(1);
    let family = arguments.next().expect("family");
    let path = arguments.next().expect("oracle path");
    assert!(arguments.next().is_none(), "family and oracle path only");

    let extension = match family.as_str() {
        "typescript" => "ts",
        "tsx" => "tsx",
        "bash" => "sh",
        "python" => "py",
        _ => panic!("unsupported family {family}"),
    };
    let oracle: Value = serde_json::from_slice(&fs::read(path).expect("read oracle"))
        .expect("parse oracle");
    let cases = oracle["cases"].as_array().expect("cases array");
    let syntax_set = two_face::syntax::extra_newlines();
    let syntax = syntax_set
        .find_syntax_by_extension(extension)
        .expect("two-face has the syntax");
    let mut agreement_sum = 0.0;
    let mut exact = 0;

    for case in cases {
        let source = case["text"].as_str().expect("case text");
        let pygments = pygments_boundaries(case);
        let syntect = syntect_boundaries(&syntax_set, syntax, source);
        let union = pygments.union(&syntect).count();
        let shared = pygments.intersection(&syntect).count();
        agreement_sum += shared as f64 / union as f64;
        exact += usize::from(pygments == syntect);
    }

    println!(
        "{family}: cases={} exact={} mean_boundary_jaccard={:.1}%",
        cases.len(),
        exact,
        100.0 * agreement_sum / cases.len() as f64,
    );
}
