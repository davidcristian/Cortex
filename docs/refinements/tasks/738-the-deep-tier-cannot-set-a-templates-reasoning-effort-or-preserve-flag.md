# The deep tier cannot set a template's reasoning effort or preserve flag

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a Qwen3.8 artifact named in `CORTEX_MODEL_FILE_BRAIN` by a compose default, a recipe
or an env file in this tree, or ADR-0004 decision 8 naming Qwen3.8-27B as the deep pick or its
alternate. Read it with `grep -rn 'CORTEX_MODEL_FILE_BRAIN' docker/ justfile` and decision 8's
first sentence.
**Verified:** 2026-09-26

The Qwen3.8 chat template reads two settings the deep tier cannot send. `reasoning_effort` takes
`xhigh`, the value when nothing is sent, `medium` and `low`, reads `high` as `xhigh` and raises on
anything else. `preserve_thinking` is on unless sent off. The engine takes the first as a request
field or `--reasoning-effort`, and the second as `--no-reasoning-preserve` or a template argument.
The deep tier's argv (`tiers.py`, `config.py` in `cortex_model_manager`) has a setting for neither
and `build_payload` sends neither, so a Qwen3.8 deep tier runs at `xhigh` with preserve on.

Measured 2026-09-26 ([deep candidates](../../readings/deep-candidates.md)): on the stop row
Qwen3.8-27B stopped on 10 of 12 draws at `xhigh`, filling the 8192 context on 2 of 3 draws of one
question, and on 12 of 12 at `low` and at `medium`, with the median wall of a draw 0.78 and 0.97 of
the pick's. The engine's own effort value `max` fails a request with HTTP 500 (live), and `minimal`
raises the same way (rendered offline); read from the engine source, a server-wide flag set to
either would fail each handoff rather than the server's start. With preserve on, every earlier
assistant reply renders behind an empty thought, the brain storing no reasoning; whether that
changes a reply over a real multi-turn history has not been drawn.

A fix is a deep-tier setting beside `CORTEX_REASONING_BUDGET_BRAIN`, checked against the template's
values, plus the preserve flag if a multi-turn row shows it matters; its name is the maintainer's.
[ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md) then asks for the injection row
drawn again at the chosen effort.

## History

- 2026-09-26: filed by the deep candidates' measurement.
