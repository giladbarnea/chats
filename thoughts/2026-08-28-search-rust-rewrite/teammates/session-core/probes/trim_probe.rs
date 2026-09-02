fn main() {
    let cases = [
        ("U+001C FS", '\u{1c}'),
        ("U+001F US", '\u{1f}'),
        ("U+0085 NEL", '\u{85}'),
        ("U+00A0 NBSP", '\u{a0}'),
        ("U+2028 LS", '\u{2028}'),
        ("U+3000 IDSP", '\u{3000}'),
        ("U+200B ZWSP", '\u{200b}'),
    ];
    for (name, character) in cases {
        let line = format!("{character}{{\"type\":\"user\"}}");
        println!(
            "{:13} rust_trim_strips={}",
            name,
            line.trim().starts_with('{')
        );
    }
}
