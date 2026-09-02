import json, orjson
from chats.parsing import detect_format, decode_jsonl_entries, _read_first_jsonl_entry

cases = {
    "nan":        '{"type": "user", "v": NaN}\n{"type": "user", "message": {"role":"user","content":"hi"}}',
    "bigint":     '{"type": "user", "v": 123456789012345678901234567890}\n{"type":"user"}',
    "dupkey":     '{"type": "user", "a": 1, "a": 2}',
    "leading_blank": '\n\n{"type": "user", "message": {"role":"user","content":"hi"}}',
}
for name, content in cases.items():
    fmt = detect_format(content)
    entries = decode_jsonl_entries(content)
    print(f"{name:15} detect={fmt:5} decoded_entries={len(entries)}")

# stdlib vs orjson on the same first line
for name, line in {"NaN": '{"type":"u","v":NaN}', "bigint": '{"type":"u","v":' + "9"*40 + '}'}.items():
    s = o = None
    try: s = type(json.loads(line)).__name__
    except Exception as e: s = f"ERR {type(e).__name__}"
    try: o = type(orjson.loads(line)).__name__
    except Exception as e: o = f"ERR {type(e).__name__}"
    print(f"{name:8} stdlib={s:20} orjson={o}")
