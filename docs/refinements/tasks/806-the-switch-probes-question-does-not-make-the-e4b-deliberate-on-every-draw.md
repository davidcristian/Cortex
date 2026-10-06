# The switch probe's question does not make the E4B deliberate on every draw

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)
**Verified:** 2026-10-07

`brain/packages/inference/tests/test_thinking_switch_live.py` sends every pick one question, `_ASK`
(three friends splitting a bill), and asserts that each shape's control, the cell sending no
switch, deliberated on every draw. `scripts/switchtail.py` refuses a shape whose control did not
(ADR-0050 decision 3). On the subagent pick, gemma-4-E4B QAT q4_0, the plain control does not: at
20 draws a cell at `-ngl 99` it deliberated on 16 of 20 on the `b11429` model host image and on 17
of 20 on the cached `b10680` `:server-cuda` image (thinking-switch readings, 2026-10-07). The build
is not the cause, so the probe cannot read the E4B's plain cell on any build, and the E4B row of
[R-529](529-the-rendering-column-is-one-builds-measurement.md) stays owed.

What is known about why the question fails on this pick:

- The rendered prompt is byte for byte the same on `b10680`, `b11312` and `b11429`. With the key
  left alone the template puts a `<|think|>` system turn at the front and leaves the tail open
  (`<turn|>\n<|turn>model\n`), so the model is asked to think and on some draws does not.
- A quiet draw answers at once: its first reply token after about 0.1 s or less, a reply of 553
  to 695 characters, stopped by the 256 token cap. The sample keeps no reply text, so whether a
  quiet draw wrote an unmarked thought into its reply is not known.
- The probe sends no sampler settings, so every draw uses the server's default sampling.
- The same question under `REPLY_ENVELOPE` deliberated on 20 of 20 on both builds, and the plain
  cell with the switch sent on 0 of 20. The switch holds on the plain shape; what is missing is a
  plain control that fires every time.

The remedy is a question the E4B's plain control deliberates on every time, read at 20 draws a cell
on the image the stack runs, with the reply text of any quiet draw kept in the run's log. It is
either a new `_ASK` for every pick, which reopens all twelve rows of the column, or a question set
per pick, which reopens only the E4B's. The sample's `ask` field already names the question, so
the reader works with either. Reading a control rate instead of requiring every draw is the other
route; it changes ADR-0050 decision 3 and the reader, and is not this task's default.

## History

- 2026-10-07: filed by [R-529](529-the-rendering-column-is-one-builds-measurement.md), whose 20-draw
  row of the E4B found the plain control short of every draw on both builds.
