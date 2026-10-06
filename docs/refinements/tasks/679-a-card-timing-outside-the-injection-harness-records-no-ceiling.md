# A card timing outside the injection harness records no ceiling

**Status:** open, waiting for its trigger
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-10-06
**Trigger:** a figure from one of the harnesses below, a turn-cost interval or a decode rate, is
published in `docs/` with a date after 2026-09-17 and no card reading beside it. The added lines
of `git log -p --since=<the last check> -- docs/` that match `tok/s`, `test_turn_cost_live` or
`test_decode_cadence_live` are the candidates to read.

Only the injection harness prints the card's ceiling at each end of a row. Other live harnesses time
work on the card and print nothing about the ceiling it ran under.
[test_turn_cost_live.py](../../../brain/packages/orchestrator/tests/test_turn_cost_live.py) writes
each block's turns to a JSON sample that `scripts/contrast.py` reads, and its A/B/A order pairs the
two conditions in time but cannot pair them under a ceiling that moved within minutes on 2026-09-17.
[test_decode_cadence_live.py](../../../brain/packages/inference/tests/test_decode_cadence_live.py)
separates a tier that has the card from one paged to host memory by its decode rate, and a lowered
ceiling lowers that rate too. Neither starts its own container the way the injection harness does:
both run against the composed stack, where the card is visible from the model host's container.

**What would close it.** Read the card through `docker exec` into the model host's container, with
the query and the reader in
[card_reading.py](../../../brain/packages/inference/tests/card_reading.py), which the brain's pytest
`pythonpath` already makes importable from any package's tests. For the turn-cost blocks, write the
start and end readings into the JSON sample rather than printing them, so `contrast.py` can report
the ceiling each block ran under beside the interval. Check the list of harnesses again first; the
two above are the ones that publish a time or a rate taken on the card.

## History

- 2026-09-17: opened by the close of
  [R-662](662-a-measurement-run-records-the-cards-ceiling-by-hand.md), which made only the injection harness
  print the card's ceiling
  ([ADR-0041 decision 20](../../adr/ADR-0041-injection-image-variant.md)).
- 2026-09-24: read against the tree and not fired. Neither harness nor `scripts/contrast.py`
  imports `card_reading.py`, which only the injection harness and its own test do. The one decode
  rate a `docs/` change since 2026-09-17 touched, 28.92 to 29.82 tok/s in
  `docs/runbooks/model-swap-measurements.md`, is the 2026-08-07 control API reading, whose row
  changed only its fit column on 2026-09-22, and the 2026-09-22 deep margin reading came from its
  own script with `clocks.sm` beside each start.
  A third live harness, `test_model_read_wording_live.py` of 2026-09-24, logs each row's wall
  clock to price the next draw and publishes neither a turn cost nor a decode rate.
- 2026-10-03: not fired. Neither harness nor `scripts/contrast.py` has a commit since 2026-09-24,
  and `card_reading.py` is still imported only by the injection harness and `test_card_reading.py`.
  Every decode rate a `docs/` change added since then has a card reading beside it: the decode probe
  row of `docs/readings/deep-candidates.md` (2026-09-26) has a column with each model's SM clock and
  ceiling, and the decode draws in `docs/readings/flash-next.md` (2026-09-26 and 2026-10-01) give
  the SM clock of their requests. No turn-cost interval was published. The detached launcher the
  overnight runs use now samples the card every 15 s into a `clocks.csv` beside its rows and can
  skip a row whose ceiling is low at its start (`measurements/sitting-2026-10-03/drivers/launch.sh`,
  outside the tree), so a harness drawn under it has a reading in its run directory; a harness run
  by hand still has none.
