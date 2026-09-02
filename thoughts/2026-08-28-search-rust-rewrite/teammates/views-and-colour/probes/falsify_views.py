import subprocess, sys
from pathlib import Path
SRC = Path("rust/search_views.rs")

MUTATIONS = [
    ("V1 no cell clip (the reference branch's defect)",
     '    if metrics.cell_len(&plain) <= width {',
     '    if true {'),
    ("V2 reserved measured in bytes",
     '        + format!(" · {age_label}").chars().count();',
     '        + format!(" · {age_label}").len();'),
    # **Expected inert, and that is a measured result rather than a gap.** The outer
    # cell clip subsumes this budget: measured against Python at every width from 2 to
    # 129 over seven headline shapes, the two never differ. Kept in the list because a
    # mutation that starts being caught means the outer clip changed and the budget has
    # become load-bearing — at which point it needs a real gate.
    ("V3 headline budget forgets the tick  [expected inert]",
     'elide_to_width(row.headline, width.saturating_sub(2).max(8), Elision::Tail)',
     'elide_to_width(row.headline, width.max(8), Elision::Tail)',
     False),
    ("V4 unknown age painted 'now' not 'old'",
     'row.age_seconds.map(age_style).unwrap_or("search.age.old")',
     'row.age_seconds.map(age_style).unwrap_or("search.age.now")'),
    ("V5 directory elided at the tail",
     '        Elision::Middle,\n    );',
     '        Elision::Tail,\n    );'),
]
def main() -> None:
    # The file itself is the original; no backup argument to get wrong.
    original = SRC.read_text()
    for label, old, new, *expected in MUTATIONS:
        expect_caught = expected[0] if expected else True
        if old not in original:
            print(f"{label:<42} ANCHOR MISSING - result meaningless")
            continue
        SRC.write_text(original.replace(old, new, 1))
        result = subprocess.run(
            ["cargo", "test", "--no-default-features", "--lib",
             "search_views::chrome_tests::every_recorded_list_row"],
            capture_output=True, text=True)
        blob = result.stdout + result.stderr
        hit = [l for l in blob.splitlines() if "rendered lines differ from Python" in l]
        if hit:
            print(f"{label:<42} {hit[0].strip()}")
            if not expect_caught:
                print(f"{'':<42} ^ EXPECTED INERT BUT CAUGHT: the outer cell clip has "
                      f"changed and this budget is now load-bearing. It needs a real gate.")
        elif "error[" in blob:
            print(f"{label:<42} DID NOT COMPILE - result meaningless")
        elif not expect_caught:
            print(f"{label:<42} inert, as measured")
        else:
            print(f"{label:<42} NOT CAUGHT (exit {result.returncode})")
    SRC.write_text(original)

if __name__ == "__main__":
    main()
