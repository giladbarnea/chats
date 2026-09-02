#!/usr/bin/env python3
"""Record `ch-legacy`'s answers for the two operator-against-summary-facet claims.

**The last consultation of the Python search authority.** `test_search_operators.py`
is deleted with it; 20 of its 22 claims have a counterpart elsewhere and **these two
do not** — an operator term evaluated against the session SUMMARY facet is asserted
nowhere else in the tree.

**The harness is imported from the gate, and here the import rule points the only
way it can:** the module that defined these shapes is being deleted, so **the
surviving gate owns the definition** and this recording is taken with the same one
it will be graded against.

**Written by `g5-runner`; the assertions are `deletion-owner`'s.** The runner
records, an implementer asserts — *the runner writing the gate he then verified is
the one sentence that would undo that split.*

    capture_operator_facet_baseline.py <out-dir>
"""
from __future__ import annotations

import base64, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import oracle_digest  # noqa: E402
from test_legacy_operator_facet_frozen import CLAIMS, run_claim, write_claim_home  # noqa: E402

LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"


def capture() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, claim in sorted(CLAIMS.items()):
        home = Path(tempfile.mkdtemp()) / "home"
        home.mkdir(parents=True)
        write_claim_home(home, claim)
        done = run_claim(LEGACY, claim, home)
        out[name] = {
            "returncode": done.returncode,
            "stdout": base64.b64encode(done.stdout).decode(),
            "stderr": base64.b64encode(done.stderr).decode(),
        }
    return out


def refuse_unless_discriminating(captured: dict[str, dict]) -> None:
    """Refuse rather than write.

    **The last two checks mirror `test_a_claim_that_stopped_discriminating_fails_here`
    deliberately**, so the property is enforced before the write and after it. A
    claim that selects every session in its pool decides nothing, and reproducing it
    would pass on any port at all — *this corpus's form of a comparison that cannot
    fail.* The one-session pool is exempt for the same reason the gate exempts it:
    selecting the whole of a pool of one is the claim, not the absence of one.
    """
    missing = sorted(set(CLAIMS) - set(captured))
    if missing or len(captured) != len(CLAIMS):
        raise SystemExit(
            f"refusing to write: captured {len(captured)} of {len(CLAIMS)} claims"
            + (f", missing {missing}" if missing else "")
            + ". The route that could answer is about to be deleted; a short "
            "recording is indistinguishable from a complete one once written."
        )
    for name, entry in captured.items():
        ids = base64.b64decode(entry["stdout"]).decode().split()
        pool = set(CLAIMS[name]["sessions"])
        if not ids:
            raise SystemExit(
                f"refusing to write: {name} matched no session. A comparison that "
                "cannot fail, recorded as if it could."
            )
        if set(ids) == pool and len(pool) > 1:
            raise SystemExit(
                f"refusing to write: {name} matched every session in its pool "
                f"({sorted(ids)}). The claim is about which sessions the summary "
                "facet decides, and a case selecting all of them decides nothing."
            )


def main() -> int:
    out_dir = Path(sys.argv[1])
    captured = capture()
    refuse_unless_discriminating(captured)
    digest = oracle_digest.oracle_route_digest()
    record = {
        "what_this_is": (
            "`ch-legacy`'s answers for the two claims in `test_search_operators.py` "
            "that had no counterpart anywhere else: a boolean operator term "
            "evaluated against the session SUMMARY facet. Recorded 2026-09-02 by "
            "g5-runner immediately before the Python search authority was deleted. "
            "Both routes were measured and agreed first, so this stores a "
            "verified-correct answer rather than a mystery."
        ),
        "degradation": (
            "BEFORE: `test_search_operators.py` ran the Python authority and "
            "asserted the port matched it on an operator term satisfied only by a "
            "session's summary. AFTER: this asserts the port still produces what "
            "Python produced on 2026-09-02 at oracle route digest "
            f"{digest}. It can no longer detect that this recording was itself "
            "wrong, because the route that would have said so is gone."
        ),
        "oracle_route_digest": digest,
        "oracle_route_digest_recipe": "tests/oracle_digest.py::oracle_route_digest",
        "revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "revision_note": (
            "The revision the oracle route digest is re-derivable FROM, together "
            "with tests/data/oracle-route-inputs/. A revision alone cannot "
            "reproduce it: the digest covers .venv/bin/ch-legacy and the installed "
            "RECORD, and git holds neither."
        ),
        "reference": str(LEGACY),
        "reference_identity": hashlib.sha256(LEGACY.read_bytes()).hexdigest()[:16],
        "claims": captured,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "legacy-operator-facet-baseline.json"
    target.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(f"recorded {len(captured)} claims")
    for name, entry in sorted(captured.items()):
        ids = base64.b64decode(entry["stdout"]).decode().split()
        print(f"  {name:44} exit {entry['returncode']}  ids {ids}  "
              f"(pool {sorted(CLAIMS[name]['sessions'])})")
    print(f"oracle    {digest}")
    print(f"revision  {record['revision'][:12]}")
    print(f"reference {record['reference_identity']}")
    print(f"file      {target} ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
