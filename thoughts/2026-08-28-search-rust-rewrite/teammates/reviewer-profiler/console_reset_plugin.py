"""Pytest plugin: reset the cached Console singletons before every test.

Diagnostic instrument, not a fix. Load it without editing any test file:

    PYTHONPATH=thoughts/2026-08-28-search-rust-rewrite/teammates/reviewer-profiler \
      uv run pytest tests/ --ignore=tests/test_search_perf.py -n 8 --dist=loadfile \
      -p console_reset_plugin

Hypothesis it tests: `chats.console` caches four `Console` objects in module
globals, and a Rich `Console` freezes its environment, width, `no_color` and
colour system at construction. So the first in-process test in a worker that
touches a console fixes that configuration for every later test in the same
worker, and a later `monkeypatch.setenv("COLUMNS", ...)` cannot move it.

Under `-n 8 --dist=loadfile` the file-to-worker assignment varies between runs,
so which test constructs the console first varies, and so does what every later
test in that worker inherits. That predicts exactly the reported signature: a
different failing set each run, no standalone reproduction, and no reproduction
outside pytest.

If the failing set becomes stable with this plugin loaded, the hypothesis holds.
If it stays random, it is disproved and the cause is elsewhere.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_console_singletons():
    from chats import console

    for name in ("_console", "_error_console", "_warning_console", "_hint_console"):
        setattr(console, name, None)
    yield
    for name in ("_console", "_error_console", "_warning_console", "_hint_console"):
        setattr(console, name, None)
