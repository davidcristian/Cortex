# Readings: the thinking switch and the trace budget

What each setting does to a pick's trace, per request kind, and what the lineup's templates render.
Cited by [ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md) and
[ADR-0050](../adr/ADR-0050-live-probe-records.md). A cell counts the draws that **deliberated with
the switch sent**, so `0/5` is a switch that held every time; every control variant, sending no
switch, deliberated on every draw. "Constrained" is a request sending `REPLY_ENVELOPE` as its
`response_format`.

## What the switch costs and buys on a user's reply

**2026-08-16 and 2026-08-17.** On the cortex pick (gemma-4-12B QAT q4_0, `-ngl 99 -c 16384`), three
open questions per variant: with the switch off the first word came 30 to 45 times sooner than with
the trace on, and the replies were the same size. Under a tier budget of 128 the first word came
four to seven times sooner than unbudgeted, every reply finished `stop` and was the same size, and a
trace cut mid-sentence was followed by a whole reply. A cap of 512 with the trace unbounded returned
an empty reply on 3 of 3; the same cap under a budget of 128 returned an answer. A request asking
for no thinking on a budgeted server still produced no trace, and a trace cut at the budget was
followed by a well-formed tool call. Method: direct requests against the model host's cortex tier on
build `b9870-2d973636e` for the budget variants, the budget set through `CORTEX_REASONING_BUDGET`.

## The lineup's switched tails

**2026-09-02**, build `b10680-d7bd3bfca`, `-ngl 99`, neither reasoning flag, a cap of 256, five
draws a cell, published through `just switch-tail`; the two rows marked `*` were read on the CPU
image of the same build on 2026-08-30. Tails are what the template appended after the ask.

| entry | switched tail | plain | constrained |
| --- | --- | --- | --- |
| gemma-4-12B QAT q4_0 (cortex pick) | `<turn\|>\n<\|turn>model\n<\|channel>thought\n<channel\|>` | 0/5 | 0/5 |
| gemma-4-31B QAT q4_0 (deep pick) | the same | 0/5 | 0/5 |
| gemma-4-26B-A4B QAT q4_0 | the same | 0/5 | 0/5 |
| gemma-4-E4B QAT q4_0 (subagent pick) `*` | `<turn\|>\n<\|turn>model\n` | 0/5 | **5/5** |
| gemma-4-E2B QAT q4_0 | the same | 0/5 | **5/5** |
| Qwen3.5-0.8B Q8_0 `*` | `<\|im_end\|>\n<\|im_start\|>assistant\n<think>\n\n</think>\n\n` | 0/5 | 0/5 |
| Qwen3.5-2B Q4_K_M (roster alternate) | the same | 0/5 | 0/5 |
| Qwen3.5-4B Q4_K_M | the same | 0/5 | 0/5 |
| Qwen3.5-9B UD-Q4_K_XL | the same | 0/5 | 0/5 |
| Qwen3.6-27B Q4_K_M | the same | 0/5 | 0/5 |
| Qwen3.6-35B-A3B UD-Q3_K_XL | the same | 0/5 | 0/5 |
| Qwen3.8-27B UD-Q4_K_M, read 2026-09-26 at the deep tier's argv | the same | 0/5 | 0/5 |

Every entry holds on the plain shape. The constrained column follows the tail: a template that
renders the thought already closed holds, and one that answers the switch by dropping a `<|think|>`
system turn at the front, leaving the tail open, does not. Both gemma handlers (`peg-gemma4`) and
the Qwen one (`peg-native`) build a grammar under a schema that keeps a thought block reachable, and
a schema changes no rendered prompt on any entry. The E4B's constrained cell has read 4 of 5, 5 of 5
and 5 of 5 on builds `b10644`, `b10666` and `b10680`: 14 of 15. Two quants differ from ADR-0004's
(UD-Q4_K_XL for Q4_K_M, UD-Q3_K_XL for UD-Q3_K_M); a quant is not a template. Qwen3.8-Flash-Next has
the Qwen3.8-27B template byte for byte and was not drawn ([deep candidates](deep-candidates.md)).

**2026-09-04, re-read 2026-09-15.** A walk over every GGUF header on the model mount: 68 files, 34
with a chat template, every one writing one of the two marker pairs `switchtail.py` lists. Six
Qwen3.6 repackages also read `<thinking>`, `</thinking>`, `<|think_on|>` and `<|think_off|>`, and
emit none of them. The template `GET /props` serves for the Qwen3.5-0.8B pick is the one in its own
header, by SHA-256.

## The effort and preserve settings

**2026-09-26**, build `b10680-d7bd3bfca`: the 11 chat templates on the models mount, which cover 34
GGUF files, every file of one template rendering the same bytes. Each template was rendered for 39
requests under 15 server flag sets. Nothing in the repo sends either setting yet
([R-738](../refinements/tasks/738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)).

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

## The subagent pair against each half

**2026-09-02**, build `b10680-d7bd3bfca`, the shipped delegated request (`task_messages` and
`build_payload` at `max_tokens` 1024, over four report bodies), 40 seed-paired draws on the card.
*Delivered* is a reply that is a summary of its body, judged by hand.

| pick | server flags | wrote to the channel | empty at the cap | narration in `reply` | delivered |
| --- | --- | --- | --- | --- | --- |
| gemma-4-E4B | the pair | 5 | 3 | 0 | 37 |
| gemma-4-E4B | `--reasoning off` alone | identical to the pair on 40 of 40 | | | |
| gemma-4-E4B | budget alone | 0 | 2 | 9 | 29 |
| Qwen3.5-2B | budget alone (20 draws) | 20 | 20 | 0 | 0 |
| Qwen3.5-2B | `--reasoning off` alone (20 draws) | 0 | 0 | 0 | 19 |

On the plain shape the E4B under the budget alone wrote the thought as its reply on 38 of 40. The
CPU image of the same build agreed on 76 draws. On the E4B the kwarg alone and the pair were
identical on 20 of 20 seed-paired draws, so beside the kwarg the budget is inert; the kwarg drops
the `<|think|>` the template injects, and the budget leaves the prompt byte-identical to an
unflagged server's. Framed injection obedience was 0 of 10 on the pair, on the budget alone, and on
an unflagged server sent the switch per request. Method: servers started by hand, rendering off
`POST /apply-template`.

**2026-08-29**, build `b10666-4e97ac86e`, the same request against a server started with the pair:
13 of 76 draws (7 of 38 seeds) wrote 1582 to 4078 characters into the reasoning channel, 8 came back
empty at the cap, and 11 of the 13 opened with a misspelled closing marker (`</channels>`,
`t</channell>`, `h</c>`). With `reasoning_budget_tokens: 0` added, 1 of 20. Re-drawn by seed on
`b10680` on 2026-09-11 through `test_envelope_cost_live.py`, the same fragments recur at the same
seeds, and the request key on top of the pair changed 0 of 4 cells.

## The request key

**2026-08-29 and 2026-09-07.** A request sending `reasoning_budget_tokens: -2` is answered 400
naming the key on `b10666-4e97ac86e` and `b10680-d7bd3bfca`, and 200 with the field ignored on
`b9870-2d973636e`; `"abc"`, `{}`, `true` and `[1]` are answered 200 everywhere. On the E4B pick with
neither flag, 100 constrained draws a build on both builds:

| cell | `b10680` deliberated | `b10666` deliberated |
| --- | --- | --- |
| the switch alone | 85/100 | 86/100 |
| the switch and `trace_tokens=0` | 0/100 | 0/100 |

Every deliberating draw used the whole cap and returned nothing. Per request, on one server with no
flag, a count of 128 or 32 let an answer through where an unbounded trace returned none. The old key
`reasoning_budget: 0` deliberated 5 of 5. Method: `test_trace_budget_live.py` with
`CORTEX_TRACE_REPEATS=100`; the question as the GPU runbook prints it.

**The leak.** A forced end of thought returned `{"reply": "thought"}` once in the 58 budgeted draws
of 2026-08-29 (28 through the raw wire and 30 through the probe), and in none of the 200 of
2026-09-07: 1 in 258 through the request key against 0 in 140 through the tier flag. Put through
`settle_reply` (2026-09-15), that envelope is reported as an answer, while a start tag leaked in
front of the envelope is `MALFORMED`.
