# The engine budget deep row's app pair is undrawn

**Status:** done 2026-10-04
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`test_every_renderings_laundering_rate_drawn_deep` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
draws `plain`, `chrome` and `app` at 120 draws per condition in one server, in that order. `607ed`
drew it for the cortex alt on the engine's own budget on 2026-10-03: its `plain` and `chrome` pairs
were read, and the run's deadline cut the `app` pair after 95 of its 120 control draws, so that
pair is undrawn and its prediction, written before the draw in [the alt's queued
rows](../../readings/injection-over-pixels-alt-queued.md), is untested.

**Chosen 2026-10-04: a renderings setting.** `CORTEX_INJECTION_DEEP_RENDERINGS` names the
renderings the row draws, comma-separated, every one when unset, and fails the row before a server
starts when it names none. With it set to `app` the row draws the pair alone in about 3700 s, at
`607ed`'s 7.6 s framed and 22.1 s control a draw at a median SM clock of 0.54 of the card's maximum,
where the whole row costs about 10900 s. The other way, `607ml` read as the deeper draw of the same
cell, was not taken: it would score a 400-draw cell from another collected row against a range
computed for 120 draws, and it would leave the replication of the `plain` pair, which read 19
against 11 where apart below was predicted, at the whole row's price. `607ml` stays its own row
under its own prediction.

**What would close it.** `607eda`, the `app` pair drawn alone, read by hand against its
prediction in [the alt's deep record](../../readings/injection-over-pixels-alt-engine-deep.md).

## History

- 2026-10-03: Filed from [R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md) when
  `607ed`'s `app` pair was cut by the run's deadline
  ([the deep record](../../readings/injection-over-pixels-alt-engine-deep.md#the-deep-row-over-three-renderings-at-the-sampler)).
- 2026-10-04: the renderings setting chosen and built. `607eda` and `607edp`, the `plain` pair's
  replication, written down before the draw and queued in `measurements/sitting-2026-10-04/`.
- 2026-10-04: `607eda` drew the pair alone, exit 0, and is read by hand: 7 against 13 of 119, p
  0.24, not apart where apart below was predicted, so `607m`'s apart below has no replication from
  it ([the deep record](../../readings/injection-over-pixels-alt-engine-deep.md#the-deep-rows-app-pair-alone-at-the-sampler)).
  The deep row's three pairs are drawn and read, and the task is done.
