import json, pathlib, sys

py = json.loads(pathlib.Path(sys.argv[1]).read_text())
rs = json.loads(pathlib.Path(sys.argv[2]).read_text())
rs_by_id = {r["id"]: r for r in rs["results"]}

rows = []
for p in py["results"]:
    r = rs_by_id[p["id"]]
    for mode in ("insensitive", "sensitive"):
        pa, ra = p[mode], r[mode]
        compile_diff = pa["compiled_as"] != ra["compiled_as"]
        match_diff = pa["matches"] != ra["matches"]
        if compile_diff or match_diff:
            rows.append({
                "id": p["id"], "mode": mode, "pattern": p["pattern"],
                "py_as": pa["compiled_as"], "rs_as": ra["compiled_as"],
                "py_match": pa["matches"], "rs_match": ra["matches"],
                "haystacks": p["haystacks"],
                "py_err": pa["compile_error"], "rs_err": ra["compile_error"],
                "kind": ("ACCEPT-BOUNDARY" if compile_diff else "MATCH-SEMANTICS"),
            })

print(f"total probes: {len(py['results'])}  divergent (probe,mode) pairs: {len(rows)}\n")
for row in rows:
    print(f"[{row['kind']}] {row['id']} ({row['mode']})  pattern={row['pattern']!r}")
    print(f"   python: {row['py_as']:16} matches={row['py_match']}  err={row['py_err']}")
    print(f"   rust:   {row['rs_as']:16} matches={row['rs_match']}  err={row['rs_err']}")
    print(f"   haystacks={row['haystacks']}")
    print()
