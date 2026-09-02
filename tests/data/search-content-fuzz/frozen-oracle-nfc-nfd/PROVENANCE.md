# Frozen oracle renders — NFC versus NFD

Captured 2026-08-28 at `sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0`.

## Why these exist, which is not the obvious reason

`nfc_nfd_probe.py` compares the route against itself and therefore survives
cutover — but **re-pointing it at the native route silently weakens the
question**, and that is easy to miss.

The probe answers "does this implementation diverge on normalization form".
Pointed at the oracle it found: yes, title elision truncates NFD about nine
visible characters early. After cutover the native route *must* diverge too, to
preserve behaviour. So the probe re-pointed reports the expected answer whether
the native route diverges by nine characters or by ninety.

Storing the oracle's four renders per subject converts it back into the same
question: not "does native diverge" but "does native produce the bytes the
oracle produced". One side live, one side stored.

Three of four subjects; the fourth is Hebrew, whose NFC and NFD forms are
identical, so it has nothing to freeze. That negative is what showed the probe
discriminates rather than alarms.
