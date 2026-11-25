# Brain coverage misses two loop exits on Python 3.14

**Status:** done 2026-11-25
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

`requires-python` in [brain/pyproject.toml](../../../brain/pyproject.toml) is `>=3.12`, and the one
file naming the interpreter, the root `.python-version`, is not read by uv in `brain/` or
`scripts/`, since uv reads the file in the project directory only. So `uv sync` in a fresh checkout
takes the newest Python it finds. In a fresh
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
- 2026-11-25: done. Reproduced on a scratch venv on 3.14.7: the same two arcs missed. The exits are
  real behaviour the suite already runs: the tests of the two modules alone reach both on 3.12 and
  on 3.14 under the C tracer, and miss them on 3.14 only under coverage's default `sys.monitoring`
  core, while the C tracer on 3.14 misses another arc instead (`recap_prompt.py` `57->66`, a plain
  `for` exit). No test can add an exit the suite already runs, so the interpreter is named:
  `brain/.python-version` and `scripts/.python-version` hold `3.12`, the image's Python, and a
  fresh environment in either tree now builds on 3.12.3. `crosscheck.py` reads a TOML key, and a
  new entry ties the three `.python-version` files to pyright's `pythonVersion` in both trees and
  to the brain image base. The brain image's context leaves the file out. The reason is in
  ADR-0002 decision 8.
