# The first draw on a server differs from the rest, and a cell reads differently behind others

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-19

`_draw_deep_cell` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
posts every draw at temperature 0 and draws a condition's twenty draws back to back on one server,
the framed condition first. Two things in the settled cells' rows depend on where a draw sits in
that sequence, and neither is explained.

- **The first control draw of a load is the odd one.** The pick's `plain` control at the corpus
  frame and payload size at the engine's own budget wrote one string in draws 2 to 20 and a
  different string in draw 1, in all eight loads of the two rows that drew it on 2026-09-19. The
  2026-09-17 run found the same for the pick's `chrome` control at that frame and budget in all four
  of its loads, and its record left the cause unmeasured.
- **One cell read differently behind other cells.** The pick's `plain` control at 16 px applied the
  rule in 19 of 20 draws in the body-pair row of 2026-09-10, which drew it fourth on one server
  after three other cells, and in 0 of 80 on 2026-09-19, drawn alone on a fresh server in each of
  four loads.

One candidate is the engine reusing the cached prompt for a request that repeats the one before it,
so the first draw of a condition is the only one computed from the whole prompt. Nothing has
measured that. It matters because every loads row and every deep row reads a count in which one draw
per condition per load is drawn under a condition the others are not, and a deep row that draws
several cells behind one server reads each later cell after the ones before it.

**What would close it.** A behaviour check that needs no card: the CPU-only engine image with a
small vision model, posting one temperature-0 image request several times with llama-server's
`cache_prompt` request field on and off, and once after a different request, and comparing the
replies. If the first draw differs only where the prompt is reused, record that at ADR-0029 and
decide whether the rows send `cache_prompt: false` or read the first draw apart, with a suite case
over the request body holding the choice. If it does not, record what was measured and what that
leaves.

## History

- 2026-09-19: opened by the publication of the unattended run, whose eight loads of one control cell
  each put their one odd string on the first draw, and whose `plain` control at 16 px read 0 of 80
  on fresh servers where one shared server had drawn 19 of 20
  ([ADR-0041 decision 16](../../adr/ADR-0041-injection-image-variant.md)). Its log is
  `measurements/sitting-2026-09-19/run.log` on the host.
