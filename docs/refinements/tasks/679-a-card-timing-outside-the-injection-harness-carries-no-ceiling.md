# A card timing outside the injection harness carries no ceiling

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-17
**Trigger:** a figure from one of the harnesses below, a turn-cost interval or a decode rate, is
published in `docs/` with a date after 2026-09-17 and no card reading beside it.

Opened 2026-09-17 by the close of
[R-662](662-a-sitting-records-the-cards-ceiling-by-hand.md), which made only the injection harness
print the card's ceiling at each end of a row (the
[ADR-0029 harness-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)).

Other live harnesses time work on the card and print nothing about the ceiling it ran under.
[test_turn_cost_live.py](../../../brain/packages/orchestrator/tests/test_turn_cost_live.py) writes
each block's turns to a JSON sample that `scripts/contrast.py` reads, and its A/B/A order pairs arms
in time but cannot pair them under a ceiling that moved within minutes on 2026-09-17.
[test_decode_cadence_live.py](../../../brain/packages/inference/tests/test_decode_cadence_live.py)
separates a tier that has the card from one paged to host memory by its decode rate, and a lowered
ceiling lowers that rate too. Neither starts its own container the way the injection harness does:
both run against the composed stack, where the card is visible from the model host's container.

**What would close it.** Read the card through `docker exec` into the model host's container, with
the query and the reader in
[card_reading.py](../../../brain/packages/inference/tests/card_reading.py), which the brain's
pytest `pythonpath` already makes importable from any package's tests. For the turn-cost blocks,
write the start and end readings into the JSON sample rather than printing them, so `contrast.py`
can report the ceiling each block ran under beside the interval. Re-derive the list of harnesses
first; the two above are the ones that publish a time or a rate taken on the card.

## Trail

- 2026-09-17: opened by the close of
  [R-662](662-a-sitting-records-the-cards-ceiling-by-hand.md).
