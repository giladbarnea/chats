#!/usr/bin/env python3
"""Run a command under a real pty at a chosen width and capture raw bytes.

Colored output cannot be compared through a pipe. Piped, Rich reports 80 columns
and a `COLUMNS`-only helper also returns 80, so the two agree at exactly the
width where a width defect is invisible. Only a real terminal separates them.

`COLUMNS` is scrubbed from the child environment on purpose. Leaving it set is
how a width probe ends up measuring its own shell rather than the code.
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import termios


def run_at_width(
    arguments: list[str],
    *,
    columns: int,
    rows: int = 40,
    environment: dict[str, str] | None = None,
    allow_dumb: bool = False,
    stream: str = "stdout",
) -> bytes:
    """Run `arguments` on a pty sized `columns` x `rows`, returning raw bytes.

    `stream` selects what is observed, and it is a real dimension rather than a
    convenience. Colour on stderr is decided by whether *stderr* is a terminal, so
    a harness that sends stderr to a pipe or to DEVNULL cannot see stderr colour at
    all — it is off by construction. Six gates import this function, and while it
    defaulted to stdout every one of them was structurally blind to that class.

      "stdout"  stderr discarded            (default; unchanged for existing callers)
      "stderr"  stdout discarded, stderr on the pty
      "both"    interleaved on one pty, as a user at a terminal sees them
    """
    controller, follower = pty.openpty()
    fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    # An unpinned ambient input does not fail loudly — it silently makes the two
    # routes incomparable. So defaults are applied only to an inherited
    # environment; a caller who passes one owns it verbatim.
    if environment is not None:
        # The caller owns it verbatim. Defaulting a variable they deliberately
        # omitted is how this harness twice measured a tier it never set.
        child_environment = dict(environment)
    else:
        child_environment = dict(os.environ)
        for inherited in ("COLUMNS", "LINES", "NO_COLOR", "FORCE_COLOR"):
            child_environment.pop(inherited, None)
        child_environment.setdefault("TERM", "xterm-256color")
        child_environment.setdefault("COLORTERM", "truecolor")
        child_environment.setdefault("TZ", "Asia/Jerusalem")
    if child_environment.get("TERM") == "dumb" and not allow_dumb:
        raise ValueError(
            "TERM=dumb pins Rich to 80 columns by a different path than the width "
            "fallback, so a width gate would pass for the wrong reason."
        )

    sinks = {
        "stdout": (follower, subprocess.DEVNULL),
        "stderr": (subprocess.DEVNULL, follower),
        "both": (follower, follower),
    }
    if stream not in sinks:
        raise ValueError(f"stream must be one of {sorted(sinks)}, not {stream!r}")
    stdout_sink, stderr_sink = sinks[stream]

    process = subprocess.Popen(
        arguments,
        stdin=follower,
        stdout=stdout_sink,
        stderr=stderr_sink,
        env=child_environment,
        close_fds=True,
    )
    os.close(follower)

    chunks = []
    try:
        while True:
            ready, _, _ = select.select([controller], [], [], 120)
            if not ready:
                break
            try:
                chunk = os.read(controller, 65536)
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(controller)
        process.wait(timeout=120)
    return b"".join(chunks)


def observed_width(output: bytes) -> int:
    """Longest visible line in display columns, ignoring SGR and the pty's CRLF.

    Counts characters after decoding, not bytes. The box-drawing characters in a
    panel border are three bytes each, so a byte count reports three times the
    real width and makes every route look identical at the wrong number.
    """
    import re
    import unicodedata

    plain = re.sub(r"\x1b\[[0-9;]*m", "", output.decode("utf-8", "replace"))
    plain = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", plain)

    def columns(line: str) -> int:
        return sum(
            2 if unicodedata.east_asian_width(character) in ("W", "F") else 1
            for character in line
            if unicodedata.category(character) != "Mn"
        )

    return max((columns(line.rstrip("\r")) for line in plain.split("\n")), default=0)
