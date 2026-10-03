# The engine budget deep row's app pair is undrawn

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-10-03

`test_every_renderings_laundering_rate_drawn_deep` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
draws `plain`, `chrome` and `app` at 120 draws per condition in one server, in that order, and has
no setting that draws one rendering alone. `607ed` drew it for the cortex alt on the engine's own
budget on 2026-10-03: its `plain` and `chrome` pairs were read, and the run's deadline cut the `app`
pair after 95 of its 120 control draws, so that pair is undrawn and its prediction, written before
the draw in [the alt's queued rows](../../readings/injection-over-pixels-alt-queued.md), is
untested. Redrawing the whole row costs about 10900 s at `607ed`'s pace, and the `app` pair alone
about 3600 s, at its 7.6 s framed and 22.1 s control a draw at a median SM clock of 0.54 of the
card's maximum.

Two ways to draw the pair, to be chosen before the next free card:

- a renderings setting read from the environment, in the shape of `CORTEX_JOINED_ROWS` in
  `test_joined_system_live.py`, so the row draws `app` alone and the pair is read alone as the row
  says. The same setting makes a replication of the `plain` pair, which read 19 against 11 where
  apart below was predicted, cost about 3600 s rather than the whole row;
- or `607ml`, the mail cell at 400 draws per condition at the same frame, size and budget, read as
  the deeper draw of the same cell, under a rule written before its draw that says so.

## History

- 2026-10-03: Filed from [R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md) when
  `607ed`'s `app` pair was cut by the run's deadline
  ([the deep record](../../readings/injection-over-pixels-alt-engine-deep.md#the-deep-row-over-three-renderings-at-the-sampler)).
