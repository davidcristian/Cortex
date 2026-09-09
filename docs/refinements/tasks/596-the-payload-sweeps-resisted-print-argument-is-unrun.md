# The payload sweep's resisted-print argument is still unrun on a live row

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09
**Trigger:** the next sitting that draws the payload-size sweep on the GPU with
`CORTEX_INJECTION_SHOW_RESISTED` naming a cell rather than set to `all`.

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
four-corner probe row. Two of those have been drawn on the card since, both with
`CORTEX_INJECTION_SHOW_RESISTED=all`, and `all` is what leaves the argument unrun: `shows_resisted`
returns true on it before comparing a cell name, so the whole `or` expression short-circuits and
neither half of it has ever been evaluated on a live row.

It is also the call site whose argument a reader cannot copy from either of the others. The sweep
names a cell `f"{rendering.name} at {type_scale.label}"`, so `plain at 24px-payload` rather than
`plain`, and its argument is that name joined by `or` to the condition that prints a cell whose
rate moved from the size above it. A wrong argument there prints nothing where a reader expects a
cell's misses, or prints every reply of a nine-cell row.

**What would close it.** One sweep row drawn on the GPU with the variable naming one of its cells
rather than set to `all`, `plain at 24px-payload` being the one whose replies the frame rows are
read against, and the printed replies read. The row already prints every reply of a cell whose rate
moved, so the reading is whether the named cell prints its misses where its rate did not move, and
whether the other eight cells withhold theirs. Then a line in the ADR saying the third call site was
exercised, or a fix if it printed nothing.

## Trail

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
