# Frozen oracle output — the seven age-colour cases

These are the **oracle's own bytes**, captured 2026-08-28 at
`sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0`, for the seven cases where the branch's stored
expectations and the Python oracle disagree.

They disagree only in the SGR colour of the age token: the branch's corpus
normalizes the age *text* to `{AGE}` but leaves its colour, and the fixture
mtimes age with wall-clock time until they cross a theme bucket.

## Why these exist

Everything else in the 173-case reproduction matches the branch's stored
expectations, so the branch's own files already record the oracle's answer.
For these seven they do not, and **after the Python route is deleted the
oracle's side becomes unrecoverable**. Captured while it was still possible.

Normalization applied is the branch harness's `_normalize`, byte for byte,
so these are directly comparable with `search-command-fixtures/expected/`.

Not a contract. A record of what the oracle produced, for the one place a
recorded finding asserts a difference and only one side was stored.
