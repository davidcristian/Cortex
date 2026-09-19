# The payload-size row's resisted-print argument is still unrun on a live row

**Status:** done 2026-09-19
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`shows_resisted` is used at three call sites in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py).
`score` is inside a row a CI test reaches, and the mutation table that added the switch proved it
there. `test_the_laundering_rate_at_each_frame` was drawn on the card on 2026-09-07 with the
variable naming two of its three cells, and it printed both of them and neither of the third. The
third call site is inside `_draw_payload_sweep`, which three rows reach:
`test_the_laundering_rate_across_payload_sizes`, `test_the_payload_sweep_at_a_third_frame` and the
four-corner probe row.

Those rows have been drawn on the card five times since, twice with
`CORTEX_INJECTION_SHOW_RESISTED=all` and three times with the variable unset, so one half of the
argument has run. On `all`, `shows_resisted` returns true before comparing a cell name, so the whole
`or` expression stops there. Unset, it compares the cell name against a set holding one empty
string, which nothing matches, so the moved-rate condition beside it decides what prints, and that
half has run. The cell-name half is what no live row has evaluated with a name in the variable, and
an unset run cannot stand in for it, because a misspelled cell name returns false there exactly as a
correct one does. It is also the call site whose argument a reader cannot copy from either of the
others: the row names a cell `f"{rendering.name} at {type_scale.label}"`, so `plain at 24px-payload`
rather than `plain`.

## History

- 2026-09-07: opened by the close of
  [592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md), whose
  [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md) records the rate row's call site
  printing two named cells and skipping the unnamed one.
- 2026-09-09: claims checked against the code, and the trigger as first written fired without
  answering the question. Two sessions drew the row on the card within hours of this entry being
  opened, the third frame's row and the four-corner probe row, and both set
  `CORTEX_INJECTION_SHOW_RESISTED=all`, which returns true before any cell name is compared. The
  trigger now names the setting rather than the session.
- 2026-09-13: claims checked, and half the subject was answered by three sessions that day. All
  three ran a payload-size row with the variable unset, which is the setting under which the
  moved-rate condition decides. Two of the three completed, both with cells whose rate moved from
  the size above, and the replies printed there are quoted in their records.
- 2026-09-19: claims checked, and the fix is changed from a GPU row to a test case, which makes the
  entry actionable. That night's session cannot answer it: its launcher,
  `measurements/sitting-2026-09-19/launch.sh`, sets no `CORTEX_INJECTION_SHOW_RESISTED`, so its
  three rows would evaluate the unset half again. With the variable naming `plain at 24px-payload`,
  `shows_resisted` returned true for that name and false for the other eight when the nine names
  were built the way the row builds them, so the argument is right today.
- 2026-09-19: done as a test case. `sweep_cell` and `sweep_prints_resisted` in
  `test_injection_defense_live.py` now build the row's cell name and make its print decision, and
  `test_a_payload_sweep_prints_the_cell_it_names_and_the_cells_whose_rate_moved` checks them over
  the nine names the row builds. Writing the case found a second defect in the same call: the
  moved-rate condition compared whole `rate` lines, generated token total included, so every cell
  below the first size printed every reply. It now compares the counts alone. Recorded with ADR-0041
  decision 13, with a mutation table in the commit.
