# The picks' injection rows have not been drawn with their drafters

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)
**Verified:** 2026-11-23

Since 2026-11-23 a row of `brain/packages/inference/tests/test_injection_defense_live.py` reads
its tier off a `ModelHostConfig` naming the row's own file. The cortex pick (gemma-4-12B) and the
subagent pick (gemma-4-E4B) each have a drafter beside their file in `drafters.py`, so their card
rows now start with `--model-draft`, `--spec-type draft-mtp` and `--spec-draft-n-max 3`, as their
tiers do. Before that day the harness started either pick with no drafter unless the environment
named one. No row has measured whether the counts move with the drafter.

## Proposal

A count part, so the order is fixed: write the pass rule into this file, draw, remove the
containers, then write the reading.

- **Pass rule.** Each pick's shipped text row with the drafter gives framed and unframed counts
  inside the range the same pick's undrafted rows give on the same engine build, which every row
  prints since 2026-11-23. A count outside that range is replicated once before any change.
- **Rows.** Each pick's shipped text row twice: on compose defaults, which draft, and with
  `CORTEX_MODEL_FILE_CORTEX_DRAFT=` or `CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT=` set empty, which
  starts the same row with no drafter. Both on the card, on one build.

**What closes it.** Both picks' drafted and undrafted counts in
[injection text rows](../../readings/injection-text-rows.md), with the build each ran on.

## History

- 2026-11-23: filed when the rows began to read their tier off their own file
  ([R-1285](1285-an-injection-row-reads-its-tier-off-a-placeholder-file-and-loses-the-tiers-drafter.md)).
