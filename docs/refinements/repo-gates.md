# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** none, every entry landed

**Repo gates ([ADR-0026](../adr/ADR-0026-prose-style-gates.md)):**
- **The fail-open `scripts/` gate config closed 2026-07-12
  ([ADR-0026 addendum](../adr/ADR-0026-prose-style-gates.md)).** `scripts/pyproject.toml`
  enumerated the modules it measured, once in the pytest `--cov=` list and again in
  pyright's `include`; adding `dashcheck.py` silently escaped BOTH the 100% coverage gate
  and strict typing until the omission was spotted by eye (the tree still reported 100%,
  because a module nobody measures cannot lower the average). Both now measure the tree
  rather than a list: `--cov=.` with an explicit coverage omit for `tests/` and `.venv/`
  (test files stay unmeasured, as before), and a pyright `include` of `"."` with an
  explicit exclude. A new script is gated by default; escaping needs a written exclusion.
  Proven to fail on an unlisted probe script (coverage 98.62% + two strict pyright
  errors) before being trusted.
