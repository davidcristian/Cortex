# The pair's budget half has no injection row of its own

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-04 by the close of
[R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which built two
of the three cells its own hand run had measured.

`SWITCHES` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
holds the request key and the shipped pair. The third cell the hand run behind R-525 drew was
`--reasoning-budget 0` alone, with no kwarg and no request key, and it is not a row. That cell is
the one the ADR-0005 budget-alone addendum found behaving differently from the pair on everything
else it measured: the budget alone empties the reasoning channel and loses 11 of 40 answers to a
narration written into the reply instead, where the pair loses 3 of 40 to the channel. Whether a
reply written that way is more or less obedient to an injected instruction is a question the
injection corpus can answer and has answered only by hand.

**Why it was left.** A row for the budget alone is half of a pair the harness deliberately does not
spell: `shipped_reasoning_off` reads the tier's whole tail off `ModelHostConfig`, and naming one
half of it means either typing the flag here, which is the second spelling R-525 was careful to
avoid, or teaching the harness which items of a tail belong to which lever, which is a shape it has
no reason to know.

**What would close it.** Decide where a lever's own name lives. The tier declares a tail and the
harness reads it whole; a row that pulls half of it needs the tail to be readable as levers rather
than as items, which is the same question `flagcheck.REQUIREMENTS` already answers on its own side
by writing the pair as one requirement carrying two flags. If the sidecar's tail were declared as
that pair rather than as four strings, both readers would have the same structure and the row would
name a lever instead of a slice.

## Trail

- 2026-09-04: opened by the close of
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which made
  the request key and the shipped pair rows and left the pair's halves unnamed.
