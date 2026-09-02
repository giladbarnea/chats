"""The one definition of the oracle's identity.

Both the contract suite and the fixture generators need this, and neither may
own it. The generator briefly imported it from the suite, which made computing a
digest depend on a corpus the generator was in the middle of deleting — a load
order coupling that turned a shared definition into a crash. A module that
imports nothing of either has no such order.

The digest spans the **whole Python route**, not just its sources. A compiled
launcher can be copied private; a Python route cannot — it is a script plus an
interpreter plus an installed distribution, and a concurrent reinstall replaces
the parts a copy does not cover.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ORACLE_SOURCE_ROOT = PROJECT_ROOT / "src" / "chats"
VENV_ROOT = PROJECT_ROOT / ".venv"
LEGACY_ENTRY = VENV_ROOT / "bin" / "ch-legacy"


def oracle_route_digest() -> str:
    """Digest the sources, the entry script, and the installed distribution record.

    >>> oracle_route_digest().startswith("sha256:")
    True
    """
    digest = hashlib.sha256()
    for path in sorted(ORACLE_SOURCE_ROOT.rglob("*.py")):
        digest.update(path.relative_to(ORACLE_SOURCE_ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    installed_records = sorted(
        VENV_ROOT.glob("lib/python*/site-packages/chats-*.dist-info/RECORD")
    )
    for path in [LEGACY_ENTRY, *installed_records]:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<missing>")
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"
