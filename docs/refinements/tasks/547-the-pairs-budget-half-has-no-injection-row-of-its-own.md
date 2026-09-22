# The reasoning budget on its own has no injection row

**Status:** done 2026-09-05
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`SWITCHES` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
had the request key and the shipped flag pair. The third case measured by hand behind
[R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md) was
`--reasoning-budget 0` alone, with no keyword argument and no request key, and it was not a row.
That case is the one measured (ADR-0049) behaving differently from the pair on everything else: the
budget alone empties the reasoning channel and loses 11 of 40 answers to a narration written into
the reply instead, where the pair loses 3 of 40 to the channel. Whether a reply written that way is
more or less obedient to an injected instruction is a question the injection corpus can answer and
had answered only by hand.

**Why it was left.** A row for the budget alone is half of a pair the harness deliberately does not
write out: `shipped_reasoning_off` reads the tier's whole flag tail off `ModelHostConfig`, and
naming one half of it means either typing the flag here, which is the second copy R-525 was careful
to avoid, or teaching the harness which items of a tail belong to which setting.

**What would close it.** Decide where a setting's own name lives. The tier declares a tail and the
harness reads it whole; a row that takes half of it needs the tail to be readable as settings rather
than as items, which is what `flagcheck.REQUIREMENTS` already does on its own side by writing the
pair as one requirement with two flags.

## History

- 2026-09-04: opened by the close of
  [R-525](525-the-injection-harness-sends-a-request-key-and-never-the-tiers-argv.md), which made the
  request key and the shipped pair rows and left the pair's halves unnamed.
- 2026-09-05: done. The row was missing, as the entry says, but its account of the cost was not:
  R-525 typed the keyword argument's flag name into the harness, `test_switch_rows.py` types both
  names and checks the tail's halves by position, and `hostedtiers.py` and `flagcheck.REQUIREMENTS`
  read the same tail by flag name; what was never typed is the values. Declaring the tail as a pair
  of settings was priced and declined, since `moduleconstants.items` reduces a `Starred` item to
  `None` and `hostedtiers.py` raises on it, so the check would need a new reduction for a reading
  its readers already make. A setting's name is its flag: `lever(argv, flag)` reads one half of the
  tier's tail, `template_kwargs` reads through it, and `BUDGET_ALONE` is the third entry of
  `SWITCHES`, on the card alone. The text rows print their empty or capped replies per row. Five
  mutations each fail `test_switch_rows.py` (16 tests). Measured on the pick: 0 of 10 framed, 1 on
  the control, 0 empty or capped of 20, in 61 s, against the hand run's 0 of 10 and 1, 2, 1. Opened
  [R-560](560-the-text-rows-score-an-empty-or-capped-reply-as-resistance.md).
