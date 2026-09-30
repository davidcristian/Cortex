# The precis sentence read lower on one condition

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On the default pick, drawn on CPU, the `precis` sentence took the figures-keeping summarization from
25 to 13 of 32, with 6 copies of the body against none and 13 cap refusals against 7
([reply envelope](../../readings/reply-envelope.md), "The role sentences"). It is the one cell of
three whose intervals do not overlap, so it needs a replication before any wording changes.

Written down before the replication is drawn:

1. **The default pick on the card**, the compose file's argv at `-ngl 99`, the figures-keeping
   summarization with and without the `precis` sentence, four bodies at eight seeded draws a cell,
   through `brain/packages/orchestrator/tests/test_envelope_cost_live.py` with
   `CORTEX_ENVELOPE_INSTRUCTION` set as the readings section shows. The reading replicates if the
   role column is again lower with the two intervals apart. A replication is the evidence for
   rewording or removing `precis`; an overlap leaves it shipped, with the CPU reading kept as one
   condition's result. Drawn: 27 of 32 without the sentence and 12 of 32 with it, the intervals
   apart, so it replicates. A rewording drawn next on the card ships in its place (ADR-0072).
2. **Qwen3.5-2B, the roster alternate**, which the rows did not reach: the three shapes with and
   without their role, drawn the same way. No card or CPU row of it exists. The row: the argv of
   `llama-subagent-qwen` in the roster compose file with `-ngl 99`, each shape constrained at four
   bodies and eight seeded draws a cell, and the figures shape with the shipped rewording, all in
   one server session. A role changes delivery on this model only where its interval and the
   plain cell's do not overlap; overlap on all three shapes is the null result.

Record the engine build, the argv and an `nvidia-smi` SM clock beside any card row. Done when both
are in the readings record and ADR-0072 states the result.

## History

- 2026-09-29: Filed by the close of
  [R-748](748-a-role-sentence-is-unmeasured-against-the-envelope-readings.md), whose CPU rows on
  the default pick read this cell apart and did not reach the alternate.
- 2026-09-30: Item 1 drawn on the card: 27 of 32 without the `precis` sentence and 12 of 32 with
  it, 7 copies and 13 cap refusals, the intervals apart, so the CPU drop replicates. Recorded in the
  readings record and ADR-0072. Open on item 2.
- 2026-09-30: Item 2's row and its rule written down before the draw.
