---
date: 2026-10-04
---

# Color-test isolation

The two baseline failures came from inherited `TERM=dumb`. Rich uses an
80-column layout and suppresses ANSI output in that terminal mode, defeating
the tests' requested width and color. Both passed under `TERM=xterm-256color`.

The recording helper in `tests/test_colored_rendering.py` and the colored CLI
helper in `tests/test_pi_custom_messages.py` now set the terminal mode they
require. The renderer did not need a change.

The failing tests now run with both inherited terminal modes. The affected
files passed all 65 tests after both `dumb` cases first failed as expected.
The full runner passed 2,035 Python tests, four performance tests, and every
shell suite. Three existing tests were skipped. Installed/local parity and
the editable checkout origin also passed verification.
