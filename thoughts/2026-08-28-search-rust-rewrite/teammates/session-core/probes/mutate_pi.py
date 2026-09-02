"""Falsify the Pi differential against wrong ports, without shell escaping in the way."""

import shutil
import subprocess
import sys
from pathlib import Path

SESSION = Path("/Users/giladbarnea/dev/chats/rust/session.rs")
BACKUP = Path("/tmp/session_pi_backup.rs")
# The in-tree driver, not a scratchpad copy. A perishable original is what a probe
# finds first, and running one produced a wrong conclusion about durability today.
DRIVER = Path(__file__).resolve().parent / "drivers" / "render"
PROBE = Path(
    "/Users/giladbarnea/dev/chats/thoughts/2026-08-28-search-rust-rewrite/"
    "teammates/session-core/probes/claude_render_differential.py"
)

MUTATIONS = {
    # The prior team's exact defect: an unconditional terminator where Python's
    # grammar makes it optional.
    "require_duration_ms": (
        "(?:\\r?\\n<duration_ms>\\r?\\n.*\\r?\\n</duration_ms>)?",
        "\\r?\\n<duration_ms>\\r?\\n.*\\r?\\n</duration_ms>",
    ),
    "skills_never_split": (
        "let (skills, remainder) = split_pi_inline_skills(&blocks.join(\"\\n\\n\"));",
        "let (skills, remainder): (Vec<PiInlineSkill>, String) = "
        "(Vec::new(), blocks.join(\"\\n\\n\"));",
    ),
    # Ambiguity must yield nothing, never a guess. This anchor was wrong when first
    # written — indented for a nesting level the code does not have — so the hazard
    # went unfalsified while the harness honestly reported it as not applied.
    "ambiguity_takes_the_first": (
        "    let first = matching.next()?;\n    if matching.next().is_some() {\n        return None;\n    }",
        "    let first = matching.next()?;",
    ),
}


def run(command, **kwargs):
    return subprocess.run(command, shell=True, capture_output=True, text=True, **kwargs)


def main() -> int:
    shutil.copy(SESSION, BACKUP)
    print("falsifying the Pi differential (400-session sample):")
    for name, (old, new) in MUTATIONS.items():
        source = BACKUP.read_text()
        if old not in source:
            print(f"  {name:26} ANCHOR MISSING — mutation not applied, result meaningless")
            continue
        SESSION.write_text(source.replace(old, new, 1))
        build = run(
            f"cd {DRIVER} && CARGO_TARGET_DIR={DRIVER}/target cargo build --release 2>&1"
        )
        if "error[" in build.stdout or "error:" in build.stdout:
            print(f"  {name:26} did not compile (still a caught mutation)")
            shutil.copy(BACKUP, SESSION)
            continue
        result = run(
            f"cd /Users/giladbarnea/dev/chats && PROVIDER=pi "
            f"RENDER_BIN={DRIVER}/target/release/branchcheck "
            f"uv run python {PROBE} 400 2>&1 | grep mismatches"
        )
        print(f"  {name:26} {result.stdout.strip()}")
        shutil.copy(BACKUP, SESSION)

    shutil.copy(BACKUP, SESSION)
    run(f"cd {DRIVER} && CARGO_TARGET_DIR={DRIVER}/target cargo build --release")
    print("restored and rebuilt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
