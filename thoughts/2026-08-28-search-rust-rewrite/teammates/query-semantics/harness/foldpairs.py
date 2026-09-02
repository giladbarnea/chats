"""Generate every plausible case-insensitive pair, then record Python's verdict."""
import json, re, sys
import re._casefix as casefix

pairs: set[tuple[int, int]] = set()
for code in range(0x110000):
    character = chr(code)
    partners = {character.lower(), character.upper(), character.casefold()}
    for extra in casefix._EXTRA_CASES.get(code, ()):
        partners.add(chr(extra))
    for partner in partners:
        if len(partner) != 1 or partner == character:
            continue
        pairs.add((code, ord(partner)))

ordered = sorted(pairs)
records = []
for left, right in ordered:
    pattern = re.escape(chr(left))
    matched = bool(re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL).search(chr(right)))
    records.append({"left": left, "right": right, "python": matched})
json.dump(records, open(sys.argv[1], "w"))
print(f"{len(records)} pairs; python-matching: {sum(r['python'] for r in records)}")
