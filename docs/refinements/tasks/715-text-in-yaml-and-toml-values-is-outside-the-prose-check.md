# Text in YAML and TOML values is outside the prose check

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-23

The prose check reads only the comments of a YAML or TOML file (decisions 11 and 16 of
[ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)). The text a person reads in their
values is never searched: a workflow's `name:` and a step's `name:` on the Actions page, the
`echo` lines of a workflow's `run:` block in its log and summary, a pre-commit hook's `name:` in
every commit's output, and a pytest marker's description in `pytest --markers`. On 2026-09-23 a
search of every tracked YAML and TOML file outside its comments found these table words:

- `.github/workflows/shuffle.yml`: `sweep` in the workflow's name, the `seed` input's
  description, two step names and two lines of the step summary, and `gated` in a third summary
  line. Its job id `sweep` and its concurrency group `shuffle-sweep` are names under decision 15.
- `.pre-commit-config.yaml`: `gates` in the `just-check` hook's name.
- `brain/pyproject.toml` and `scripts/pyproject.toml`: `gate` in the `integration` marker's
  description.

A `run:` block is shell, so `scripts/shellstrings.py` reads its double-quoted strings once the
block's text is found. The `scripts/` project has no YAML parser; `tomllib` is in the standard
library. A heredoc, in a workflow or anywhere else, is outside both readers; the tree has none.

**What would close it.** A reader that returns the string values of YAML and TOML files that a
person reads, with each workflow `run:` block passed through `shellstrings.py`, joining the
literals `proseliterals.py` returns; with the words above rewritten in the same change. Or a
sentence in decision 16 saying why configuration text stays out, with the words rewritten by hand.

## History

- 2026-09-23: opened when the prose check started reading the double-quoted strings of the
  justfile and the shell scripts, and a search of the other files a shell command lives in found
  the words above.
