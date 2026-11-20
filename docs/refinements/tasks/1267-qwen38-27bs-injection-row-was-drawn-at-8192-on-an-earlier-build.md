# Qwen3.8-27B's injection row was drawn at 8192 on an earlier build

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-20

ADR-0004 decision 8 names `Qwen3.8-27B-UD-Q4_K_M` as the deep pick and gives its injection row:
0 of 100 framed draws obeyed against 0 of 100 unframed. The row was drawn on 2026-09-26 on engine
build b10680, on a server started by hand at `--ctx-size 8192` with no drafter, at the template's
default effort and the harness's 1600-token cap
([deep candidates](../../readings/deep-candidates.md),
[injection text rows](../../readings/injection-text-rows.md)). An injection row follows the
tier's deployed configuration ([ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)),
and the deployed deep tier has since moved to a 16384 context, a `q8_0` KV cache and build b12375.
The unframed 0 of 100 was predicted at 15 and did not hold, so framed and control are not apart
and the row shows no effect of the framing on this model.

## What to draw

The framed and the unframed row, 100 draws each, on
`unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` at the deep tier's argv as the model host
writes it today (16384, one slot, `q8_0`), thinking on, effort unset. Write the prediction into
this file before the first draw.

- The committed probe is the deep tier's row of the
  [injection probes runbook](../../runbooks/injection-probes.md#the-deep-tiers-row), whose
  command selects this file with `-k "27B"`. Read the context and cache type its server
  starts with before the draw, and change the harness if they are not the tier's.
- The 100-draw rows used `text_rows.py`, the driver
  [R-714](714-the-injection-text-rows-are-drawn-only-at-temperature-0.md) wrote.

If [R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md) gives
the tier an effort level first, draw the row at that level too.

What would close it: the row added to injection text rows with its date, context and build, and
ADR-0004 decision 8 citing it, or the decision reopened if the framed count reads apart from 0.

## History

- 2026-11-20: filed when the maintainer made Qwen3.8-27B the deep pick. The injection row the
  decision cites was drawn at the tier's earlier context on an earlier build.
