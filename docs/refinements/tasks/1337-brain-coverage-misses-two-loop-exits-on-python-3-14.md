# Brain coverage misses two loop exits on Python 3.14

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-11-24

`requires-python` in [brain/pyproject.toml](../../../brain/pyproject.toml) is `>=3.12`, and no file
names the interpreter, so `uv sync` in a fresh checkout takes the newest Python it finds. In a fresh
`git worktree` on 2026-11-24 it took Python 3.14.7, while the main checkout's venv runs 3.12.3. On
3.14.7 `pytest --cov` read 99.99% with two branches missed, `brain_phase.py` `138->169` and
`load_wait.py` `97->110`, each the exit of an `async for` loop. The same tree read 100% on 3.12.3,
so `just check` fails on a machine whose uv takes 3.14, with no change to the code. The scripts
tree read 100% on both.

What would close it: either the interpreter named for the brain and the scripts (a
`.python-version` file or an upper bound on `requires-python`, with a scan that fails when the two
disagree), or tests that reach both exits on both versions, with the reason for the choice written
in ADR-0002.

## History

- 2026-11-24: filed when `just check` ran in a fresh `git worktree` whose venv uv built on 3.14.7.
