# The payload sweep's resisted-print argument is still unrun on a live row

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19

Opened 2026-09-07 by the close of
[592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md), which set
`CORTEX_INJECTION_SHOW_RESISTED` on three rate rows and left the third call site where it was.

`shows_resisted` is honoured at three call sites in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py).
`score` is inside a row a CI test reaches, and the mutation table that landed the switch proved it
there. `test_the_laundering_rate_at_each_frame` was drawn on the card on 2026-09-07 with the
variable naming two of its three cells, and it printed both of them and neither of the third. The
third call site is inside `_draw_payload_sweep`, which three rows reach:
`test_the_laundering_rate_across_payload_sizes`, `test_the_payload_sweep_at_a_third_frame` and the
four-corner probe row. Those rows have been drawn on the card five times since,
twice with `CORTEX_INJECTION_SHOW_RESISTED=all` and three times with the variable unset, and what
is left unrun is now one half of the argument rather than both. On `all`, `shows_resisted` returns true before
comparing a cell name, so the whole `or` expression short-circuits. Unset, it compares the cell
name against a set holding one empty string, which no spelling matches, so it returns false and
the moved-rate condition beside it decides what prints. That half has now run: the three rows
drawn today carry cells whose rate moved from the size above, and the replies they printed are
quoted in their addenda. The cell-name half is what no live row has evaluated with a name in the
variable, and an unset run cannot stand in for it, because a misspelled cell name returns false
there exactly as a correct one does.

It is also the call site whose argument a reader cannot copy from either of the others. The sweep
names a cell `f"{rendering.name} at {type_scale.label}"`, so `plain at 24px-payload` rather than
`plain`, and its argument is that name joined by `or` to the condition that prints a cell whose
rate moved from the size above it. A wrong argument there prints nothing where a reader expects a
cell's misses, or prints every reply of a nine-cell row.

**What would close it.** A suite case, not a sitting. What is unrun is a string comparison
between the name the row prints and the name it compares, and the card adds nothing to that: an
hour of sweep on the GPU evaluates the same `shows_resisted` call on the same nine names that a
CI case can evaluate without the card. The one thing a CI case cannot reach today is the
sweep's own spelling, because `cell` is built inline in `_draw_payload_sweep`, which only an
`integration` row runs. So:

1. Move the sweep's cell name and its print decision out of `_draw_payload_sweep` into two small
   functions in
   [test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py):
   one builds `f"{rendering.name} at {type_scale.label}"` and is used for both the printed
   `[cell]` label and the comparison, and the other returns
   `shows_resisted(cell) or (seen is not None and fired != seen)`.
2. Hold them in
   [test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py)
   beside `test_a_resisted_cell_prints_its_replies_when_the_environment_names_it`: with the
   variable naming `plain at 24px-payload`, that cell prints its resisted replies and the other
   eight do not unless their rate moved from the size above; unset, only a moved rate prints; and
   `all` prints every cell.

Then close this as landed with a line in ADR-0029 saying the third call site is held by the suite.
The edit is under `brain/`, so it waits for a slot with no sitting running.

## Trail

- 2026-09-19: claims re-derived from the code, and the remedy is changed from a GPU row to a suite
  case, which makes the entry actionable. The account of the call site holds: the cell name, the
  `or` with the moved-rate condition, and the three rows that reach it are as the body says.
  Tonight's sitting cannot answer it. Its launcher, `measurements/sitting-2026-09-19/launch.sh`,
  sets no `CORTEX_INJECTION_SHOW_RESISTED`: its own environment carries no `CORTEX_` variable and
  each row adds only `CORTEX_MODELS_DIR`, so its three sweep rows would evaluate the unset half
  that 2026-09-13 already ran. The trigger waited on somebody choosing to set the variable, which
  no pre-registered sitting does. With the variable naming `plain at 24px-payload`,
  `shows_resisted` returned true for that name and false for the other eight when the nine names
  were built the way the sweep builds them, so the argument is right today, and the suite case
  would keep it right.
- 2026-09-13: claims re-derived from the code, and half of the subject has been answered by three
  sittings drawn today. All three ran a sweep row with `CORTEX_INJECTION_SHOW_RESISTED` unset,
  which is neither of the two settings this entry had seen, and unset is the setting under which
  the moved-rate condition decides: `shows_resisted` compares the cell name against a set holding
  one empty string, returns false for every spelling, and hands the decision to the condition
  beside it. Two of the three rows completed, both with cells whose rate moved from the size
  above, and the replies printed there are quoted in the sweep addenda. What remains is the cell
  name itself, which only a run naming a cell can check, so the trigger stands as written.
- 2026-09-09: claims re-derived from the code, and the trigger as first written has fired without
  answering the question. Two sittings drew the sweep on the card within hours of this entry being
  opened, the third frame's row and the four-corner probe row, and both set
  `CORTEX_INJECTION_SHOW_RESISTED=all`. So "no sitting has drawn it with the variable set" is now
  false while the entry's subject survives: `all` returns true from `shows_resisted` before any
  cell name is compared, so the sweep's cell spelling and the moved-rate condition beside it are
  both still unevaluated. The trigger names the setting now rather than the sitting. Everything
  else holds, including the cell name `f"{rendering.name} at {type_scale.label}"` and the argument
  joining it by `or` to the moved-rate condition.
- 2026-09-07: opened by the close of
  [592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md), whose
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) records the rate
  row's call site printing two named cells and skipping the unnamed one.
