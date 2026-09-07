# The payload sweep's resisted-print argument is still unrun on a live row

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** the next sitting that draws the payload-size sweep on the GPU.

Opened 2026-09-07 by the close of
[592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md), which set
`CORTEX_INJECTION_SHOW_RESISTED` on three rate rows and left the third call site where it was.

`shows_resisted` is honoured at three call sites in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py).
`score` is inside a row a CI test reaches, and the mutation table that landed the switch proved it
there. `test_the_laundering_rate_at_each_frame` was drawn on the card on 2026-09-07 with the
variable naming two of its three cells, and it printed both of them and neither of the third.
`test_the_laundering_rate_across_payload_sizes` is the one left: no CI test reaches it and no
sitting has drawn it with the variable set.

It is also the call site whose argument a reader cannot copy from either of the others. The sweep
names a cell `f"{rendering.name} at {type_scale.label}"`, so `plain at 24px-payload` rather than
`plain`, and its argument is that name joined by `or` to the condition that prints a cell whose
rate moved from the size above it. A wrong argument there prints nothing where a reader expects a
cell's misses, or prints every reply of a nine-cell row.

**What would close it.** One sweep row drawn on the GPU with the variable naming one of its cells,
`plain at 24px-payload` being the one whose replies the frame rows are read against, and the
printed replies read. The row already prints every reply of a cell whose rate moved, so the
reading is whether the named cell prints its misses where its rate did not move. Then a line in
the ADR saying the third call site was exercised, or a fix if it printed nothing.

## Trail

- 2026-09-07: opened by the close of
  [592](592-the-resisted-print-switch-has-never-been-set-on-a-live-row.md), whose
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) records the rate
  row's call site printing two named cells and skipping the unnamed one.
