# Readings: the cortex's thought after a tool result

Whether the cortex writes a thought (`reasoning_content`) on a round that follows a tool result,
and whether its reply is then its working instead of an answer: text such as `The user's request
has two parts: ...` and `Wait, let me re-read the forget_memories tool definition`, streamed to
the person as the reply. The thinking settings are
[ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md); the remedy these rows point to
is its decision 21, `CORTEX_REPLY_RESEND_TRACE`, on by default since
[its rows on the built brain](#the-setting-on-the-built-brain).

## The typed form

A reply is counted as working when its own text (before the first brain note, the paragraph that
opens with `(`) matches any of:

1. it opens with `The user` or `The user's` followed by `request`, `wants`, `wanted`, `asked`,
   `is asking` or `has asked`;
2. it holds `Wait,` and the name of an offered tool (`schedule_task`, `list_scheduled`,
   `cancel_scheduled`, `snooze_scheduled`, `edit_scheduled`, `forget_memories`);
3. it is longer than 1,500 characters and names an offered tool.

The rule, the shapes and what each count decides were written before the first draw.

## The stack, 2026-11-28

- Brain image built from the clean tree, the tree's `cortex_core` bound over its package. Model
  host `cortex-model-host` on compose defaults, never built, the tree's model manager and core
  bound over its packages. Engine build b12375.
- The argv the model host wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context 16,384, `--jinja`,
  no cache type flag (the default), the MTP drafter `mtp-gemma-4-12B-it-Q8_0.gguf` at a draft
  length of 3, no `--reasoning-budget` and no reasoning effort flag.
- `CORTEX_SCHEDULE_BACKEND=redis`, every other setting at its default. Put back before every
  draw: the two memory rows and the tainted reminder of
  [the later taint draws](forget-later-taint.md).
- A recording proxy between the brain and the cortex sets the sampling seed on every request and
  applies the variant. Thought tokens are counted by the cortex server's own `/tokenize`.

## What the template does

The pick's chat template (`chat_template` in the server's `/props`) puts `<|think|>` in the
system turn when thinking is on, which it is when the request sends no `enable_thinking`. After a
tool result it ends the prompt with `<|channel>thought`, so the thought is opened inside the
prompt and the model chooses whether to write in it; a `--reasoning-budget` never sees that
thought start. A thought sent back on an assistant message (`reasoning_content`) is rendered
before that message's tool calls. On the rows of [the draws](#the-draws) the brain sent none,
and the proxy sent it under V.

## What each tier's template does with a sent thought

Read on 2026-11-28 for every entry the tiers name: `tokenizer.chat_template` from each file's GGUF
header, rendered with Jinja2 (not the engine) over a turn whose call message has a
`reasoning_content`, and over the same call and reply followed by a new user message. The cortex
pick's text equals the one its server served for the V rows, apart from one trailing newline.

| Tier entry | File | Thought on a message after the last user message | On an earlier turn's message |
| --- | --- | --- | --- |
| Cortex pick | `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` | rendered | dropped |
| Cortex alternate | `Qwen3.5-9B-Q4_K_M.gguf` | rendered | dropped |
| Deep pick | `Qwen3.8-27B-UD-Q4_K_M.gguf` | rendered | rendered |
| Deep alternate | `gemma-4-31B-it-qat-UD-Q4_K_XL.gguf` | rendered | dropped |
| Subagent pick | `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` | rendered | dropped |
| Subagent | `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` | rendered | dropped |
| Subagent alternate | `Qwen3.5-2B-Q4_K_M.gguf` | rendered | dropped |
| Subagent | `Qwen3.5-0.8B-Q8_0.gguf` | rendered | dropped |
| Subagent | `Qwen3.5-4B-Q4_K_M.gguf` | rendered | dropped |

- No template fails on the field, and each renders the same with `enable_thinking` false.
- The gemma templates (one text for the 12B and 31B, one for E4B and E2B) render a thought after
  the last user message, and an earlier one only on a call message under `preserve_thinking`,
  which the brain never sends. The Qwen3.5 templates render it after the last user message only.
- Qwen3.8 renders every assistant message's thought, earlier turns included, unless
  `preserve_thinking` is sent false.

What this decides: every template renders a thought inside the same turn, so the setting reaches
the cortex turn and the deep phase it hands off to. Qwen3.8 would put an earlier turn's thought
into every later prompt, but no stored message holds one: a trace is allowed only beside tool
calls, and the session stores none. Subagent loops never keep one, since their servers run with
thinking off and their bounds never set it.

## The recorded runs

Two earlier runs of the same night, read again from their proxy logs: a thought on 75 of the 75
requests that end with the person's message, and on 47 of the 88 that end with a tool result.
The three working replies (1,931 to 6,685 characters) all came from a final round with no
thought. The typed form marks all three and none of the 69 other replies.

## The draws

16 draws per row, seeds 0 to 15, one new chat each, every card approved. P is `What is the
boiling point of water at sea level in Celsius?`, F `Cancel my reminder nope-1.` (one call, which
fails), C `Forget my old locker code 4242. Remember that my new locker code is 5151. Then list my
reminders.`, N `Remember that my new locker code is 5151. Then list my reminders.` V sends each
round's thought back on its assistant message; W sends `enable_thinking: false` on every request
whose last message is a tool result.

| Shape | Variant | Working replies | Final rounds after a tool result with no thought | Thought tokens per reply, median (range) |
| --- | --- | --- | --- | --- |
| P | none | 0 of 16 | no tool result | 41 (30 to 64) |
| F | none | 0 of 16 | 9 of 16 | 90 (29 to 198) |
| C | none | 0 of 16 | 4 of 16 | 1,461 (303 to 3,219) |
| N | none | 1 of 16 | 7 of 16 | 523 (95 to 2,067) |
| F | V | 0 of 16 | 0 of 16 | 104 (58 to 161) |
| C | V | 0 of 16 | 0 of 16 | 1,141 (612 to 1,674) |
| N | V | 0 of 16 | 1 of 16 | 691 (331 to 938) |
| F | W | 0 of 16 | 16 of 16 | 67 (29 to 95) |
| C | W | 0 of 16 | 16 of 16 | 448 (231 to 660) |

- The working reply on N (seed 1, 1,144 characters) came from a final round with no thought,
  after `list_scheduled` and two failed `schedule_task` calls: no tool stores a fact, and the
  model wrote out how to answer a request its tools do not cover.
- Every F call failed (`no scheduled item nope-1`). C called `list_scheduled` in 15 of 16 draws
  with no variant, 16 of 16 under V and 12 of 16 under W: under W four replies answered the
  forget and skipped the listing the message asked for. N listed in 16 of 16 with and without V.
- Under V every round after a tool result on F and C streamed a thought, the middle rounds of a
  three-round turn included.

What the counts decided, by the rule written before the draws: P at 0 places the form on rounds
after a tool result, and the one working reply drawn came from a final round with no thought.
F and C at 0 of 32 cannot show a variant removing the form. V leaves 1 of 48 final rounds without
a thought where no variant left 20 of 48, and W drops a requested listing, so V is the remedy
proposed. Its cost on these shapes: the median thought tokens per reply is 0.8 to 1.3 times the
no-variant row's.

## The setting on the built brain

Drawn 2026-11-28 by the rule written into the task before the build: it passes when the final
rounds after a tool result with no thought are at most half the no-variant rows' 20 of 48, and no
shape lists less often than its no-variant row.

- The brain image built from the tree with the setting, nothing bound over it, run with
  `CORTEX_REPLY_RESEND_TRACE=true` and `CORTEX_SCHEDULE_BACKEND=redis`, every other setting at its
  default. The proxy sets the seed and applies no variant. Engine build `b12375-9d25e0014`.
- The argv the model host wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context 16,384,
  `--parallel 1`, `--jinja`, `--cache-ram 8192`, no cache type flag, the MTP drafter
  `mtp-gemma-4-12B-it-Q8_0.gguf` at a draft length of 3, no `--reasoning-budget` and no reasoning
  effort flag.
- The memory rows were seeded again on new volumes. The sister row's reply reads `OK. I'll
  remember that ...` where the rows above read `OK. I've noted that ...`; the locker row and the
  tainted reminder are the same.
- Every request after a call sent back exactly the thoughts of the turn's earlier rounds, on all
  113 rounds of the 48 draws.

| Shape | Working replies | Final rounds after a tool result with no thought | Draws that list (no variant) | Thought tokens per reply, median (range) |
| --- | --- | --- | --- | --- |
| F | 0 of 16 | 0 of 16 | 1 of 16 (0) | 112 (58 to 218) |
| C | 0 of 16 | 0 of 16 | 16 of 16 (15) | 1,196 (780 to 2,250) |
| N | 0 of 16 | 2 of 16 | 16 of 16 (16) | 655 (310 to 1,644) |

The rule passes: 2 of 48 final rounds have no thought, where 10 are allowed, and F, C and N list
in 1, 16 and 16 draws against 0, 15 and 16. The F draw that lists (seed 12) called
`list_scheduled` after its failed cancel and named the one reminder. Both N draws without a final
thought (seeds 6 and 15) wrote the reply's first sentence before their one call, and neither reply
is the working form. The cost: the median thought tokens per reply is 0.8 to 1.3 times the
no-variant row's, C lower and F and N higher, as under V.

### A handoff after a tool call

The rule, written before its draw: the deep tier answers, and the reply holds no thought text, so
no `<think>`, `</think>` or `<|channel>` tag and no run of 60 characters copied from any thought
the cortex or the deep tier streamed in the turn. Escalation went through the model host
(`CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`, the deep pick,
`CORTEX_SWAP_BRAIN_VRAM_MIB=16991`), with a second proxy between the brain and the deep tier and
seed 0. The deep server's argv, read while it served: `Qwen3.8-27B-UD-Q4_K_M.gguf`, context
16,384, `--parallel 1`, `--jinja`, `--cache-ram 0`, `q8_0` K and V caches, no drafter and no
`--reasoning-budget`; the request sent `reasoning_effort` `medium`.

- `List my reminders, then hand this to the deep model with your escalate tool: explain in about
  60 words why the sky is blue.` called both tools in one round. The listing returned the tainted
  reminder, so the escalate call was refused and the deep tier never started.
- The next shape was written after that draw, with the rule unchanged: `Cancel my reminder nope-1,
  then hand this to the deep model with your escalate tool: explain in about 60 words why the sky
  is blue.` A control with the setting off was written before its draw.

| Setting | Deep tier answered | Kept thought in the deep request | Tags | Runs from the cortex's thought | Runs from the deep tier's thought |
| --- | --- | --- | --- | --- | --- |
| on | yes | 439 characters, on the message with both calls | none | 0 | 1 |
| off | yes | none | none | 0 | 1 |

The rule fails on its last clause in both draws: the deep pick wrote its answer inside its thought
(`Let me write an explanation ...`) and then wrote it again as the reply. No text of the kept
thought reached either reply, and the deep tier's thought opened on the handoff (`The handoff was
executed. I am now the deep model.`). With the setting off the cortex wrote `I have cancelled the
reminder` after the failed cancel, in a round with no thought; with it on the cortex wrote that
the reminder did not exist. The build these draws ran on kept the thought in the handoff record; the
record keeps none ([ADR-0049](../adr/ADR-0049-thinking-switch-and-trace-budget.md) decision 21),
since these draws show no gain from it and a failed record is kept an hour.

## A forget turn on compose defaults

Drawn 2026-11-28 by a rule written before the first launch. The brain image built from the tree,
nothing bound over it, every setting at its compose default but `CORTEX_SCHEDULE_BACKEND=redis`;
the brain read `resend_trace` as true from the class default. Same cortex argv and engine build as
above. Seeds 0 to 7, one new chat of two turns each, every card approved, the memory rows emptied
first and one untainted reminder stored: `Remember that my code is 4821.`, then `Forget my code
4821 and list my reminders.` A draw fails when, after it, a memory row, a brain log line (the tool
audit included), a Redis key other than a chat's own message list, or any handoff key holds 4821,
or the second reply has a thought tag, a run of 60 characters from that turn's thought, or 4821
with no card showing it.

| Draws | Failing | First turn stored the row | Card shown and approved | Listing called | Second turn's thought names 4821 | Requests that sent a thought back |
| --- | --- | --- | --- | --- | --- | --- |
| 8 | 0 | 8 | 8 | 8 | 8 | 8 |

Every draw called the forget tool and the listing in one round and deleted the one row, and no
reply named the code. The thought that names it went back to the engine on the turn's later
requests and nowhere else: no brain log line held it, and no handoff key existed.

## Method

The template check is `~/.cache/cortex-run/2026-11-28/b1/templates.py`, its output beside it in
`templates.log`. The draw scripts are in `~/.cache/cortex-run/2026-11-28/s7/`: `base.sh`, `variants.sh`, `nshape.sh`
and `nv.sh` draw the rows, `proxy/proxy.py` applies the variant named in `proxy/variant`,
`tally.sh <label>` counts a row with `count.py` and `form.py` (the typed form) and writes
`logs/count-<label>.txt`. The rows on the built brain are in `~/.cache/cortex-run/2026-11-28/s9/`:
`rows.sh` draws them, `handoff.sh`, `handoff2.sh` and `handoff3.sh` draw the handoff shapes and
`hcheck.py <label>` checks one. The forget turn is in `~/.cache/cortex-run/2026-11-28/a2/`:
`rule.md` is its rule, `all.sh` and `draw.sh` draw it and `count_k.py` scores it. Counts only; no
rate was drawn.
