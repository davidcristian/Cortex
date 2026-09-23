# The pixel rows drawn at the sampler are unread for a send_email call

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-24

Since 2026-09-24 `outcome` in `test_injection_defense_live.py` reads a `send_email` call as obeyed
under every attack, and a printed reply names its tool calls. Before that the pixel rows read the
call under `exfil-tool` alone and printed a reply's text without its calls, so their logs cannot be
read again for one. The rows still drawn at temperature 0 are redrawn under
[R-706](706-only-the-corpus-laundering-cell-is-drawn-at-the-engines-sampler.md) and read the call
then. Five rows were already drawn at the sampler on 2026-09-23 and nothing redraws them, each an
`output-laundering` cell:

- `test_the_mail_cells_rate_drawn_alone_at_the_shipped_budget[gemma-4-12B (cortex pick)]`;
- `test_the_plain_cell_at_a_third_frame_drawn_deep[gemma-4-12B (cortex pick)]`;
- `test_the_laundering_rate_at_each_frame[Qwen3.5-9B (cortex alt)-1600x900-engine-budget]`;
- `test_the_laundering_rate_across_payload_sizes[Qwen3.5-9B (cortex alt)-1600x900-engine-budget]`;
- `test_the_payload_series_at_a_third_frame[Qwen3.5-9B (cortex alt)]`.

The two pick rows print every reply, and none of their 1040 printed replies is an empty text that
was not void, so neither drew a call without text; a call beside text is unread in all five. Their
logs are `measurements/sitting-2026-09-23/706a.log`, `706b.log`, `695r.log`, `695c.log` and
`695t.log`.

**What would close it.** The five rows drawn again with the current harness, each at its own depth,
and [injection over pixels](../../readings/injection-over-pixels.md) restated where a call moves a
count.

## History

- 2026-09-24: opened by
  [R-716](716-the-injection-harness-reads-a-send-email-call-only-under-one-attack.md), whose close
  reads the call under every attack from the day it closed.
