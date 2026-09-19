# What the decimal value form still refuses

**Status:** open, waiting for a consumer
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-09-19
**Trigger:** A decimal pair that needs ordering rather than equality, or one whose far side is a
Rust literal with its own type suffix.

`scripts/values.py` reads a decimal, and two edges of that form are deliberately unbuilt. Both fail
closed: the scan reports an error rather than passing, so nothing can go unchecked behind either.

An ordering cannot compare decimals. `relation_fault` limits `Relation.ORDERED` to values that are
`int`, and a decimal is `Digits` rather than a number, so an ordering over one exits with `an
ordering compares integers, and a site here declares something else`. That is the correct answer
while nothing needs it: `<=` over the characters would sort `10.0` under `9.0`, which is the defect
this scan was written against. Closing it means a numeric comparison used only by the ordering
branch, since the equality branch depends on `5` and `5.0` being two different values.

The near miss is worth naming so nobody mistakes it for a consumer. The two deadlines between brain
and body really are ordered, the short one being defensible only under the capture's, but both are
declared in `brain/packages/body_client/src/cortex_body_client/gateway.py`, and an ordering may
have no mentions, so an entry over them would name two places in one file, which
`test_every_registered_constant_spans_more_than_one_seam_side` refuses. That test compares language
and brain package together rather than language alone, so the trigger is a decimal bound whose two
declarations sit apart: two trees, two languages in one tree, or two brain packages.

A decimal with a language's type suffix does not reduce. `10.0f64` and `10.0_f64` are refused along
with the exponent and the sign, for the same reason the reducer rejects a `frozenset` written in
Rust: no pair in this repo uses one, and guessing at a form nothing writes would have the scan
compare values on syntax it has never seen. Nothing in the body declares a float constant at all
today (`const NAME: f64` finds nothing under `body/crates` or `body/app/src-tauri`), so the trigger
is the first Rust decimal that has to agree with a Python one, and the fix is a suffix the reducer
strips rather than a new form.

## History

- 2026-08-19: Opened by the close of [R-308](308-crosscheck-cannot-tie-a-decimal.md), which added
  the decimal form these two refusals belong to.
- 2026-09-13: Checked again and left open, with one correction. Both refusals still stand exactly
  as written: `relation_fault` in `scripts/readings.py` limits an ordering to values that pass
  `isinstance(value, int)` and exits with the same sentence otherwise, and `scripts/values.py`
  still raises on a type suffix alongside the exponent and the sign. Neither trigger has fired. The
  registry declares fourteen decimal constants today, from `DEFAULT_VRAM_GB` at 3.5 to
  `DEFAULT_ADMISSION_WAIT_S` at 7200.0, and every one is an equality; the only two orderings are
  the capture edge pair and the receive limit pair, integers on both sides. Nothing under
  `body/crates` or `body/app/src-tauri` declares an `f64` constant. What changed is the near miss:
  the test that refuses a one-sided entry was renamed and widened to compare language and brain
  package together, so two brain packages now count as two sides and a decimal ordering between
  them would be registrable. The two gateway deadlines still are not, both being declared in one
  file.
- 2026-09-19: Checked again and left open, neither trigger fired. `relation_fault` in
  `scripts/readings.py` and the `DECIMAL` form in `scripts/values.py` are unchanged, and neither
  `scripts/settingscheck.py` nor the search-text reporting changed on 2026-09-17 touches them: the
  new scan reads settings through `moduleconstants.py` and never reduces a value. The registry
  still declares fourteen decimal constants, all equalities, but the range the previous entry gave
  was wrong at its low end: it runs from `DEFAULT_CPUS` at 2.0 in the orchestrator's subagent
  config, not from `DEFAULT_VRAM_GB` at 3.5, to `DEFAULT_ADMISSION_WAIT_S` at 7200.0. The two
  orderings are still the capture edge pair and the receive limit pair, integers on both sides, and
  nothing under `body/crates` or `body/app/src-tauri` declares an `f64` or `f32` constant. The
  ordering half lost its one proposed consumer on 2026-09-19, when the entry asking for the tool
  call and delegated run bounds to be ordered closed as satisfied, a suite case already comparing
  them and both constants living in one package. The next near miss is covered the same way: the
  subagent stall ceiling (600.0, orchestrator) must stay under the run deadline (2400.0, core),
  which is two packages and so registrable, but `SubagentsConfig`'s validator raises when it does
  not, and `test_config.py` builds that config from its shipped defaults.
