# A row's card reading misses what the ceiling did between its ends

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-17

Opened 2026-09-17 by the close of
[R-662](662-a-sitting-records-the-cards-ceiling-by-hand.md), which made every row of
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
print a reading of the card once its server answers `/health` and again as the row ends
(`print_card`, rendered by
[card_reading.py](../../../brain/packages/inference/tests/card_reading.py)).

Two readings bound the ceiling a row ran under only if the ceiling holds still between them, and it
does not. Six readings taken between 01:40 and 01:45 on 2026-09-17, with no model on the card,
put `enforced.power.limit` at 0.87, 0.83, 0.80, 0.80, 0.80 and 0.88 of `power.max_limit` (the
[ADR-0029 harness-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)). A priced row
serves for several minutes to over an hour, so a dip between its two readings goes unrecorded, and
a row whose two readings agree can still have served part of its time under a lower ceiling. The end
reading is also taken after the last reply, so its clock and draw are figures just after load rather
than under it.

**Trigger:** the first sitting that publishes a row's price from its `card reading at` lines.

**What would close it.** A sampler inside `_server` that reads the card every few seconds while the
row serves, on a thread beside the event loop the row's requests run on, and prints the lowest and
highest ceiling ratio it saw, and the highest clock ratio, on the end line. The summary is pure and
belongs in `card_reading.py` beside `render`, held by `test_card_reading.py`; the thread and its
interval stay in the harness. Before building it, check that a `docker exec` every few seconds does
not itself move the figures it reads, by comparing a sampled row's tokens a second with an
unsampled one under the same ceiling.

## Trail

- 2026-09-17: opened by the close of
  [R-662](662-a-sitting-records-the-cards-ceiling-by-hand.md).
