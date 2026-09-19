# A serving line cannot say how long a row ran under a lowered ceiling

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** a row whose price is published in `docs/` prints a `card readings every` line with its
lowest ceiling ratio under 0.50 of max and its highest above 0.50.

Opened 2026-09-19 by the close of
[R-678](678-a-rows-card-reading-misses-the-ceiling-between-its-ends.md), which made every card row
of [test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
read the card every 5 s while it serves and print the lowest, median and highest of the ceiling and
clock ratios on one line (`render_serving` in
[card_reading.py](../../../brain/packages/inference/tests/card_reading.py)).

A range and a median describe a row whose ceiling stayed in one state, which is every row read so
far: the unattended sitting of 2026-09-17 and the draws of 2026-09-19 all served between 0.80 and
0.88 of `power.max_limit`. The capped sittings of 2026-09-13 served under a third of it. A row that
crosses between those states during a sitting prints a range spanning both, and the median says only
which side most readings fell on. How much of the row's time went to each side, which is what
converts its token total into a time, is not on the line. The threshold in the trigger sits between
the two states this card has been read in.

**What would close it.** The readings are already in hand when the line is rendered, so the line
could count those under a fraction the write-up states, but that fraction is chosen after the
sitting. Writing every reading as one JSON line to a file named by an environment variable, beside
the run log, lets a write-up take the share under any ceiling afterwards. Decide between the two
when the trigger fires, with the row that fired it as the example.

## Trail

- 2026-09-19: opened by the close of
  [R-678](678-a-rows-card-reading-misses-the-ceiling-between-its-ends.md).
