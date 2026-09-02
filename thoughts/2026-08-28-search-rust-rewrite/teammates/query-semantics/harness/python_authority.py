"""Record Python `re` authority behavior for each probe, mirroring compile_search_term."""
import json, pathlib, re, sys

REGEX_META_CHARACTERS = frozenset(".^$*+?{}[]\\|()")

def is_plain_literal(pattern: str) -> bool:
    return not any(character in REGEX_META_CHARACTERS for character in pattern)

def authority(pattern: str, haystacks: list[str], case_sensitive: bool) -> dict:
    flags = re.MULTILINE | re.DOTALL
    if not case_sensitive:
        flags |= re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
        compiled_as = "regex"
        error = None
    except re.error as exc:
        regex = re.compile(re.escape(pattern), flags)
        compiled_as = "literal-fallback"
        error = str(exc)
    return {
        "compiled_as": compiled_as,
        "compile_error": error,
        "literal_candidate_is_none": not (is_plain_literal(pattern) or compiled_as == "literal-fallback"),
        "matches": [bool(regex.search(h)) for h in haystacks],
    }

probes = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = []
for probe in probes:
    out.append({
        "id": probe["id"],
        "pattern": probe["pattern"],
        "haystacks": probe["haystacks"],
        "insensitive": authority(probe["pattern"], probe["haystacks"], False),
        "sensitive": authority(probe["pattern"], probe["haystacks"], True),
    })
print(json.dumps({"python_version": sys.version.split()[0], "results": out}, ensure_ascii=True, indent=1))
