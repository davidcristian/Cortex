# The fail-open scripts gate config

**Status:** landed 2026-07-12
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

`scripts/pyproject.toml` enumerated the modules it measured, once in the pytest `--cov=` list and
again in pyright's `include`; adding `dashcheck.py` escaped BOTH the 100% coverage gate
and strict typing until the omission was spotted by eye (the tree still reported 100%,
because a module nobody measures cannot lower the average). Both now measure the tree
rather than a list: `--cov=.` with an explicit coverage omit for `tests/` and `.venv/`
(test files stay unmeasured, as before), and a pyright `include` of `"."` with an
explicit exclude. A new script is gated by default; escaping needs a written exclusion.
Proven to fail on an unlisted probe script (coverage 98.62% + two strict pyright
errors) before being trusted.

## Trail

- 2026-07-12: Closed. `scripts/pyproject.toml` enumerated the modules it measured twice, in the
  pytest `--cov=` list and again in pyright's `include`, so `dashcheck.py` escaped both the 100%
  coverage gate and strict typing until the omission was spotted by eye. Both now measure the tree
  rather than a list, a new script is gated by default, and the change was proven to fail on an
  unlisted probe script before being trusted.
