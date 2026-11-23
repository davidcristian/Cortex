# Readings: the deep tier behind a full handoff prompt

What the deep pick and its alternate do when a handoff's prompt fills most of the deep tier's 16384
context: the four [stop-row questions](deep-candidates.md#the-four-stop-row-questions) sent behind a
prompt of 10,800 tokens, which leaves 5,584 tokens for the trace and the reply. The rows answer
[R-1271](../refinements/tasks/1271-no-stop-row-is-drawn-beside-a-full-handoff-prompt.md), and its
pass rule and predictions were written into the run's notes before the first launch. The decision
that rests on them is [ADR-0004](../adr/ADR-0004-model-lineup.md) decision 8. Token counts depend
on the text, the template and the vocabulary, not on the machine, so they are given as counts.

## How the rows were drawn

**2026-11-23**, engine build `b12375-9d25e0014` from the `cortex-model-host` image, each file alone
on the 24 GB card. Only the model host of the repo's compose files was started, with
`CORTEX_MODEL_FILE_BRAIN` naming the file and every other setting on its compose default; the
cortex was stopped and the deep tier started over the control API. The deep pick's two launches
also named its file as `CORTEX_MODEL_FILE_BRAIN_DRAFT`, as the
[model swap runbook](../runbooks/model-swap.md) deploys it, and the alternate ran without its
drafter, as its earlier stop rows did. The argv the model host wrote, after the model path:

| launch | argv | card above the floor at ready |
| --- | --- | --- |
| Qwen3.8-27B `UD-Q4_K_M`, both launches | `-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 0 --spec-type draft-mtp --spec-draft-n-max 3 --cache-type-k q8_0 --cache-type-v q8_0 --cache-type-k-draft q8_0 --cache-type-v-draft q8_0` | 16,963 and 16,973 MiB |
| gemma-4-31B `UD-Q4_K_XL` | `-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 0 --cache-type-k q8_0 --cache-type-v q8_0` | 18,364 MiB |

Each draw sends the request the deep phase builds, made with the brain's own code:
`SECURITY_PREAMBLE`; user and assistant messages of this repo's ADR prose (the ADR files in order,
whitespace collapsed, 1,500 characters a message, each user message opening with a line asking what
that part decides); the question; the cortex's `escalate_to_brain` call with the question as its
brief; and `HANDOFF_TAKEN_MSG` as that call's result. `tools` holds the deep phase's eight
built-ins (the volume pair, `escalate_to_brain` and the five schedule tools), 8,705 characters of
JSON. The effort is the level the brain sends, under the name `effort_wire_name` reads off
`/props`: at the default `medium`, `medium` on the pick and nothing on the alternate, whose
template lists no levels; the brain's `high` is sent to the pick as `xhigh`. Seeds are `100*q + d`,
with no cap and the engine's sampler.

The prose was sized for each question with `/apply-template` and `/tokenize`, whose count matched
what a one-token completion reported, so that every draw's prompt was 10,798 to 10,800 tokens:
28,186 to 29,133 characters of prose in 24 messages. The eight built-ins are fewer tokens than the
22 tools the [history window](history-window.md#the-cortexs-whole-prompt) record counted, so the
prose is longer than the 24,000 character window; it stands for the window with the recalled
memories and the recap that come on top of it.

## The rows

A draw stopped with a reply when it ended on `stop` with a non-empty reply. Every draw answered
HTTP 200, none called a tool and no reply holds a literal `</think>`.

| cell | stopped (predicted) | held | right | reasoning tokens, median (range) | longest draw that stopped, generated | draws that filled the context |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8-27B, `medium`, draft layer | 11 (11, 10 to 12) | yes | 9 | 902.5 (106 to 5584) | 4630 | Q4 d1 |
| gemma-4-31B, nothing sent | 9 (10, 9 to 12) | yes | 9 | 2119 (1145 to 5586) | 4550 | Q2 d3, Q4 d1, Q4 d2 |
| Qwen3.8-27B, `xhigh`, draft layer | 11 (10, 8 to 12) | yes | 10 | 1410.5 (434 to 5349) | 5528 | Q2 d2 |

- **The draws that filled the context.** Each generated the whole room. Qwen3.8-27B's Q4 d1 at
  `medium` and gemma-4-31B's Q4 d1 and d2 spent it reasoning and wrote no reply; gemma-4-31B's Q2
  d3 reasoned 5,141 tokens and was cut 442 tokens into its reply. At `xhigh` Q2 d2 reasoned 5,349 tokens and was cut
  231 tokens into its reply, and Q4 d3 stopped 58 tokens before the end of the context.
- **Against the short prompt.** Behind the plain preamble and the question alone, 266 to 322
  tokens, the drafted `medium` cell stopped on 12 with a median of 2378 reasoning tokens (976 to
  4232) and a longest draw of 5123 ([deep effort](deep-effort.md#the-drafted-medium-stop-cell)),
  and gemma-4-31B's 2026-09-30 file stopped on 12, two of its draws generating 6,860 and 9,134
  ([history window](history-window.md#the-deep-tier-at-16384)). The drafted `xhigh` cell there stopped on 12 with
  a median of 2883.5 (831 to 14,964), against 1410.5 here. Neither comparison was written down
  before the draw.
- **Right by hand.** Wrong: Qwen3.8-27B's Q2 d1 at `medium` (44/15, which stops at the third
  sock), its Q4 d2 at `medium` (16 hours, with a Tuesday that leaves the midday shift to one
  person) and its Q2 d3 at `xhigh` (284/105). Every gemma-4-31B reply that stopped is right.

## The rule applied

| cell | the rule, written before the first launch | read | files |
| --- | --- | --- | --- |
| Qwen3.8-27B, `medium` | 10 or fewer of 12 files a defect; 11 or 12 files nothing, since 1 of the 24 `medium` draws at 16384 also generated more than this room | 11 | nothing |
| gemma-4-31B | the same rule, for the alternate | 9 | [R-1302](../refinements/tasks/1302-a-full-handoff-prompt-leaves-the-alternate-deep-model-too-little-context-to-reply.md) |
| Qwen3.8-27B, `xhigh` | files nothing: a deployment that sets `high` chooses longer traces | 11 | nothing |

Method: `up.sh`, `chain.sh`, `tools.py` and `room16.py` in `~/.cache/cortex-run/2026-11-23/s2/`,
over the questions of `measurements/deep-2026-09-26/q27-drivers/questions.py`; `cells/` there has
every reply with its reasoning and token counts, `final.py` prints the rows and `notes.md` has the
rule, the predictions and the hand reading.
