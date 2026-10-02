# A serving line cannot say how long a row ran under a lowered ceiling

**Status:** open, waiting for its trigger
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-10-02
**Trigger:** a row whose price is published in `docs/` prints a `card readings every` line with its
lowest ceiling ratio under 0.50 of max and its highest above 0.50.

Every card row of
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
reads the card every 5 s while it serves and prints the lowest, median and highest of the ceiling
and clock ratios on one line (`render_serving` in
[card_reading.py](../../../brain/packages/inference/tests/card_reading.py)).

A range and a median describe a row whose ceiling stayed in one state, which is every row read so
far: the unattended run of 2026-09-17 and the draws of 2026-09-19 all served between 0.80 and 0.88
of `power.max_limit`, and the capped runs of 2026-09-13 served under a third of it. A row that
crosses between those states while it runs prints a range spanning both, and the median says only
which side most readings fell on. How much of the row's time went to each side, which is what turns
its token total into a time, is not on the line. The threshold in the trigger sits between the two
states this card has been read in.

**What would close it.** The readings are in hand when the line is rendered, so the line could count
those under a fraction the write-up states, but that fraction is chosen after the run. Writing every
reading as one JSON line to a file named by an environment variable, beside the run log, lets a
write-up take the share under any ceiling afterwards. Decide between the two when the trigger fires,
with the row that fired it as the example.

## History

- 2026-09-19: opened by the close of
  [R-678](678-a-rows-card-reading-misses-the-ceiling-between-its-ends.md).
- 2026-10-02: checked again, and the trigger has not fired. All 73 `card readings every` lines in
  the unattended runs from 2026-09-22 to tonight read their lowest ceiling at 0.80 to 0.91 of max,
  and the launchers' own samplers agree: every `clocks.csv` from 2026-09-23 on, tonight's two
  included, reads `enforced.power.limit` at 0.80 to 0.91 of `power.max_limit` (the 2026-09-22 one
  read no limit). `render_serving` in `card_reading.py` is unchanged. One part of the premise is
  out of date: every card row since 2026-09-22 has run under a launcher that writes every reading,
  timestamped, to `clocks.csv` every 15 s beside its `ROW START` and `ROW END` lines, and readings
  records already quote a row's range from it. So the share of a launcher row's time under any
  ceiling can be taken after the run today. The remedy above still matters for a row run outside a
  launcher, and for keeping that record in the tree, since each launcher is a script under the
  ignored `measurements/` directory.
