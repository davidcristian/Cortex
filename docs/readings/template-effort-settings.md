# Readings: the effort and preserve settings in each chat template

What each chat template on the models mount does with a reasoning effort and a preserve flag, and how
the engine passes both to it. Cited by
[ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md) and
[ADR-0077](../adr/ADR-0077-model-card-settings.md); the thinking switch itself is in
[thinking switch](thinking-switch.md).

## The effort and preserve settings

**2026-09-26**, build `b10680-d7bd3bfca`: the 11 chat templates on the models mount, which cover 34
GGUF files, every file of one template rendering the same bytes. Each template was rendered for 39
requests under 15 server flag sets. The brain sends the effort on the deep reply alone, from
`CORTEX_REASONING_EFFORT_BRAIN`, `medium` by default ([the deep tier's effort level](deep-effort.md)), and never the preserve flag ([R-1276](../refinements/tasks/1276-the-deep-tier-never-sends-the-templates-preserve-flag.md)).

| template | files | `reasoning_effort`, thinking on | `preserve_thinking` when unset |
| --- | --- | --- | --- |
| `ae53464b` | gemma-4 12B, 26B-A4B, 31B | not read: every value renders as none sent | off, and read only on a turn with tool calls (template text) |
| `0a2c8073` | gemma-4 E2B, E4B | not read | the same |
| `7f0e5290`, `8452ca85` | Qwen3.5 | not read | not read |
| `55d49314` | Qwen3.6-27B, 35B-A3B | not read | off unless sent on |
| `12827f24` | Qwen3.8-27B, Flash-Next | `xhigh` when unset or empty, `high` rendered as `xhigh`, `medium`, `low`; raises on any other value, `Low` included | on unless sent off |
| five llmfan46 templates | no tier names one | not read; `e7018ebe` switches thinking on a `<\|think_off\|>` or `<\|think_on\|>` tag in the first system message | not recorded |

On `12827f24`, `xhigh` puts a sentence asking for careful thought first in the system turn, `low`
one asking for brief thought, and `medium` none; with no system message, `medium` renders no system
turn. With thinking off it ignores every value, rejected ones included. `GET /props`
`chat_template_caps.supports_reasoning_effort` is true for `12827f24` alone and lists no values.
How the engine passes the settings:

- The request field `reasoning_effort: "none"` turns thinking off and never reaches the template;
  an empty string is ignored; any other string reaches it and overrides `--reasoning-effort`.
- `--reasoning-effort` stores its value as a default template argument, `none` included, and
  `default` removes it. On `12827f24`, `none`, `minimal` and `max` then raise on every thinking-on
  request that sends no value of its own; the other 10 templates render as if nothing were set.
- `--reasoning on` writes `enable_thinking` into the server's template arguments, which override a
  request's `reasoning_effort: "none"`, so that request renders thinking on, on all 11. A request's
  `chat_template_kwargs` `enable_thinking: false` still turns it off.
- `--reasoning-budget` and `reasoning_budget_tokens` attach the sampler budget on all 11, with each
  template's own start and end tags; no template reads a budget or level variable.
- `--no-reasoning-preserve`, or `chat_template_kwargs` `preserve_reasoning: false`, drops the
  earlier thought on `12827f24`.

Method: the engine's own flag and request parsers at a vocabulary-only load, on six CPU cores with
no server (`support/run.sh` in `measurements/effort-2026-09-26/`, helper `tool/render-effort.cpp`
built from the engine tree at `d7bd3bf`). On Qwen3.8-27B the five live `POST /apply-template`
prompts of [deep candidates](deep-candidates.md#qwen38-27b) render byte for byte, and `max` raises
the live HTTP 500's message.
