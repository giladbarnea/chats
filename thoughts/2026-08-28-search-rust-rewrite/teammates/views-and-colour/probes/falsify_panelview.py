import subprocess, sys
from pathlib import Path
SRC = Path("rust/search_views.rs")
MUTATIONS = [
    ("W1 empty segment emits an escape pair",
     '    if segment.text.is_empty() {\n        return String::new();\n    }\n', ''),
    ("W2 title budget ignores the metadata suffix",
     '                width\n                    .saturating_sub(2)\n                    .saturating_sub(metadata_suffix_width)\n                    .max(8),',
     '                width.saturating_sub(2).max(8),'),
    ("W3 facts budget shares the list row's rule",
     'elide_to_width(&directory, width.saturating_sub(28).max(16), Elision::Middle)',
     'elide_to_width(&directory, width.saturating_sub(4).max(16), Elision::Middle)'),
    ("W4 strip drops the space after the title",
     '    strip.push(Segment::styled(" ", border));\n',
     ''),
    ("W5 strip clipped to width - 5",
     'render_line(&strip, inner, metrics, rendering)',
     'render_line(&strip, inner - 1, metrics, rendering)'),
    ("W6 age suffix width measured in bytes",
     '    let metadata_suffix_width = format!("  ·  {}  ·  {age_label}", row.session_id)\n        .chars()\n        .count();',
     '    let metadata_suffix_width = format!("  ·  {}  ·  {age_label}", row.session_id).len();'),
]
def main() -> None:
    # The file itself is the original; no backup argument to get wrong.
    original = SRC.read_text()
    for label, old, new in MUTATIONS:
        if old not in original:
            print(f"{label:<44} ANCHOR MISSING - result meaningless"); continue
        SRC.write_text(original.replace(old, new, 1))
        result = subprocess.run(
            ["cargo", "test", "--no-default-features", "--lib", "search_views::chrome_tests"],
            capture_output=True, text=True)
        blob = result.stdout + result.stderr
        hit = [l for l in blob.splitlines() if "differ from" in l]
        if hit:
            print(f"{label:<44} {hit[0].strip()}")
        elif "error[" in blob:
            print(f"{label:<44} DID NOT COMPILE - result meaningless")
        elif result.returncode != 0:
            print(f"{label:<44} caught (panic)")
        else:
            print(f"{label:<44} NOT CAUGHT")
    SRC.write_text(original)

if __name__ == "__main__":
    main()
