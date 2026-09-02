use std::collections::BTreeSet;
use std::env;
use std::fs;

use arborium::Highlighter;
use arborium_highlight::{FlatToken, spans_to_flat_tokens};
use serde_json::Value;

fn pygments_boundaries(case: &Value) -> BTreeSet<usize> {
    let mut boundaries = BTreeSet::from([0]);
    let mut offset = 0;
    for token in case["tokens"].as_array().expect("tokens array") {
        offset += token[1].as_str().expect("token text").len();
        boundaries.insert(offset);
    }
    boundaries
}

fn arborium_tokens(
    highlighter: &mut Highlighter,
    language: &str,
    source: &str,
) -> Vec<FlatToken> {
    let spans = highlighter
        .highlight_spans(language, source)
        .expect("Arborium highlights the language");
    spans_to_flat_tokens(source, spans)
}

fn arborium_boundaries(source: &str, tokens: &[FlatToken]) -> BTreeSet<usize> {
    let mut boundaries = BTreeSet::from([0, source.len()]);
    for token in tokens {
        boundaries.insert(token.start as usize);
        boundaries.insert(token.end as usize);
    }
    boundaries
}

fn main() {
    let mut arguments = env::args().skip(1);
    let family = arguments.next().expect("family");
    let path = arguments.next().expect("oracle path");
    let output_json = arguments.next().as_deref() == Some("--json");
    assert!(arguments.next().is_none(), "family, oracle path, and optional --json only");

    let language = match family.as_str() {
        "typescript" => "typescript",
        "tsx" => "tsx",
        "bash" => "bash",
        "python" => "python",
        _ => panic!("unsupported family {family}"),
    };
    let oracle: Value = serde_json::from_slice(&fs::read(path).expect("read oracle"))
        .expect("parse oracle");
    let cases = oracle["cases"].as_array().expect("cases array");
    let mut highlighter = Highlighter::new();
    let mut agreement_sum = 0.0;
    let mut exact = 0;
    let mut records = Vec::new();

    for case in cases {
        let source = case["text"].as_str().expect("case text");
        let pygments = pygments_boundaries(case);
        let tokens = arborium_tokens(&mut highlighter, language, source);
        let arborium = arborium_boundaries(source, &tokens);
        let union = pygments.union(&arborium).count();
        let shared = pygments.intersection(&arborium).count();
        agreement_sum += shared as f64 / union as f64;
        exact += usize::from(pygments == arborium);
        records.push(serde_json::json!({
            "tokens": tokens
                .iter()
                .map(|token| serde_json::json!([token.start, token.end, token.tag]))
                .collect::<Vec<_>>(),
        }));
    }

    if output_json {
        println!("{}", serde_json::to_string(&records).expect("serialize records"));
        return;
    }
    println!(
        "{family}: cases={} exact={} mean_boundary_jaccard={:.1}%",
        cases.len(),
        exact,
        100.0 * agreement_sum / cases.len() as f64,
    );
}
