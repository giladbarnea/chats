from chats.parsing import decode_jsonl_entries, detect_format

CASES = [
    ("U+001C FS", ""),
    ("U+001F US", ""),
    ("U+0085 NEL", ""),
    ("U+00A0 NBSP", " "),
    ("U+2028 LS", " "),
    ("U+3000 IDSP", "　"),
    ("U+200B ZWSP", "​"),
]

for name, prefix in CASES:
    content = prefix + '{"type":"user","message":{"role":"user","content":"hi"}}'
    print(
        f"{name:13} py_isspace={str(prefix.isspace()):5} "
        f"decoded={len(decode_jsonl_entries(content))} detect={detect_format(content)}"
    )
