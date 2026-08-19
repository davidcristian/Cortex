# What the decimal value form still refuses

**Status:** open, dead until a consumer
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** A decimal coupling that needs ordering rather than equality, or one whose far side is
a Rust literal carrying its own type suffix.

Opened 2026-08-19 by the close of [R-308](308-crosscheck-cannot-tie-a-decimal.md), which taught
`scripts/values.py` a decimal and left two edges of that form deliberately unbuilt. Both fail
closed, which is why neither is a hole: the scan reports a fault rather than passing, so nothing
can be silently unheld behind either.

**An ordering cannot compare decimals.** `relation_fault` keeps `Relation.ORDERED` to readings that
are `int`, and a decimal is `Digits` rather than a number, so an ordering over one exits with `an
ordering compares integers, and a site here declares something else`. That is the honest answer
while nothing needs it: `<=` over the characters would file `10.0` under `9.0`, and a comparator
that guesses is the defect this whole scan was written against. What closing it looks like is a
numeric comparison used **only** by the ordering arm, since the equality arm's whole point is that
`5` and `5.0` are two spellings and therefore two sites; one comparator serving both would undo the
decision the form is built on.

The consumer this is waiting for does not exist yet, and the near miss is worth naming so nobody
mistakes it for one. The two deadlines on the brain to body seam really are ordered, the short one
being defensible only under the capture's, but both are declared in
`brain/packages/body_client/src/cortex_body_client/gateway.py` and an ordering may carry no
mentions, so an entry over them would name two places in one file and one language, which
`test_every_registered_constant_spans_more_than_one_language` refuses on its own. The trigger is a
decimal bound whose two sites are genuinely in two trees.

**A decimal carrying a language's type suffix does not reduce.** `10.0f64` and `10.0_f64` are
refused with the exponent and the sign, for the reason the reducer refuses a `frozenset` spelled in
Rust: no coupling in this repo spells one, and a reducer that guesses at a form nothing writes is a
gate agreeing with itself about syntax it has never seen. Nothing in the body declares a float
constant at all today (`const NAME: f64` finds nothing under `body/crates` or
`body/app/src-tauri`), so the trigger is the first Rust decimal that has to agree with a Python
one, and the fix is a suffix the reducer strips rather than a new form.

## Trail

- 2026-08-19: opened by the close of [R-308](308-crosscheck-cannot-tie-a-decimal.md), which landed
  the decimal form these two refusals belong to.
