---
date: 2026-08-20
title: Slice Five baseline
---

# Slice Five baseline

The working tree started clean at commit `807b4e4`.

The functional baseline passed 987 Python tests and skipped 3. Its performance stage had one existing failure: `ch search . -ma 4h --list` took 2,568 ms against its 1,750 ms budget. An independent run measured 2,465 ms. The other three budgets passed. All 13 shell suites passed separately, including the real-launcher seam.

The live main-session pool contained 4,870 files and about 6.3 GB.

The exact launcher is `~/.local/bin/ch`. It resolves to `~/.local/share/uv/tools/chats/bin/ch`, whose shebang uses Python 3.14.7. Project Python is also 3.14.7. Both import this checkout and `src/chats/_native.abi3.so`.

The uv receipt SHA-256 was `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. It records the editable checkout that the user established with `uv tool install -e .`. Project setup did not create that global install. Slice Five discovery did not change global tool state.

Fresh exact-launcher discovery compared the current gate with a transient case-sensitive gate. The selected command was:

```sh
~/.local/bin/ch search -s slice-five-unmatchable-literal-019f -l --color never --no-paging
```

Production took 7.47 and 8.65 seconds. The prototype took 2.41, 2.39, and 2.40 seconds. Every run exited 1.

Two more `search -s QUERY -ll --color never --no-paging` misses improved from 9.49 to 3.13 seconds and from 9.65 to 4.89 seconds. A real-hit `PyO3` query improved from 19.84 to 15.16 seconds. It kept the same exit code and byte-identical one-ID stdout. These are end-to-end results. The selection does not rely on a scanner microbenchmark.

For comparison, repeated exact-launcher medians were about 0.9 seconds for recent directory lookup and 1.9 seconds for directory-filtered search. A cached-cwd ceiling reduced locally paired medians from 878 to 606 ms and from 1,911 to 1,624 ms. This confirmed a much smaller absolute window than the selected search gate.
