# A control at temperature zero has one answer and is counted as many

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-22

With the prompt cache off, a control's prompt is the same bytes in every draw, so at temperature 0
every draw writes one string: a control reading is one answer per cell, applied or not. The framed
variant's draws differ only through the fence's random nonce, so its count is a rate over nonces.
The instrument in `brain/packages/inference/tests/test_injection_defense_live.py` still reads the
control as many draws:

- The depth constants (`_DEEP_RATE_RUNS`, `_DIRECTION_RUNS`, `_OBEYED_RUNS`, `_MAIL_RUNS`,
  `_LOAD_DRAWS`) draw the control as often as the framed variant, and the comments beside the first
  two size the depth by an exact test against a silent control.
- `assert_drawn` and `assert_refuses` count a control's identical draws as that many draws.
- `_draw_cell_across_loads` prints a control count per load that no longer changes between loads.
- The readings set framed counts against control counts as two rates, such as the alt candidate's 9
  of 280 against 0 "at one chance in 546".

**What would close it.** A decision in ADR-0041 on what a framed rate is compared with: the
control's one answer, drawn once per cell, or a control that varies per draw the way the framed
variant does, such as a nonce-shaped string in its tool text, which changes the conversation the
control stands for. The depth constants, the two assertions and the published comparisons then
follow that decision.

## History

- 2026-09-22: opened by the close of
  [R-696](696-an-arms-first-draw-on-a-server-differs-from-the-rest.md), whose rows now evaluate the
  whole prompt on every draw.
