# session-core falsifier probes

Each script reproduces one confirmed divergence. Run from the repo root.

| probe | confirms |
|---|---|
| `probe1.json` + `oracle.py` | `ch parse -f xml probe1.json` escapes and marks `text_encoding="html"`; `oracle.py` shows Python leaving the same text alone. Map §3.1. |
| `firstline.py` | `detect_format` says `jsonl` while `decode_jsonl_entries` drops the line, for a first line containing `NaN`. Two JSON parsers. Map §10.1. |
| `width.py` | prints Rich's `Console.size` source; compare against `rust/main.rs::terminal_width`. Map §10.6. |
| `trim_probe.py` / `trim_probe.rs` | Python `str.strip()` strips U+001C..U+001F, Rust `.trim()` does not. Map §10.9. |

`uv run python <probe>.py` for the Python halves; `rustc -O -o trim_probe trim_probe.rs && ./trim_probe` for the Rust half.
