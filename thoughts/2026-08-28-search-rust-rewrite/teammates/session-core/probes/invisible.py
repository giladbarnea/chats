import json
import unicodedata

import orjson

print("=== lone surrogate: stdlib json vs orjson ===")
line = '{"type":"user","v":"\\ud800"}'
for name, loader in (("stdlib", json.loads), ("orjson", orjson.loads)):
    try:
        value = loader(line)
        print(f"  {name:7} accepted -> {value['v']!r}")
    except Exception as error:
        print(f"  {name:7} ERROR {type(error).__name__}")

print("\n=== NFC vs NFD: identical on screen, different code-point counts ===")
for form in ("NFC", "NFD"):
    sample = unicodedata.normalize(form, "café résumé naïve")
    print(
        f"  {form}: {len(sample):2} code points, "
        f"{len(sample.encode('utf-8')):2} bytes, renders {sample!r}"
    )

print("\n=== bidi and invisible marks present in real Hebrew transcripts ===")
for name, codepoint in (
    ("ZWSP U+200B", "​"),
    ("LRM U+200E", "‎"),
    ("RLM U+200F", "‏"),
    ("LRI U+2066", "⁦"),
    ("PDI U+2069", "⁩"),
    ("ZWJ U+200D", "‍"),
):
    sample = f"a{codepoint}b"
    print(f"  {name:12} len={len(sample)} bytes={len(sample.encode('utf-8'))} repr={sample!r}")

print("\n=== confusables ===")
for name, sample in (("latin a", "a"), ("cyrillic a", "а"), ("fullwidth a", "ａ")):
    print(f"  {name:12} {sample!r} bytes={sample.encode('utf-8')!r}")
