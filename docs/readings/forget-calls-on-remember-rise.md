# Readings: the rise of forget calls on a request to remember

On 2026-11-12 the cortex called `forget_memories` on 7 of the 8 first requests of the language
setup ([recalled memory language](recalled-memory-reply-language.md)) and on 94 of 135 first
requests of the store turns in the `cortexn20` proxy log
([task 1163](../refinements/tasks/1163-a-refused-forget-call-on-a-request-to-remember-costs-a-round.md)).
On 2026-11-07 the French, German and Romanian requests made no forget call in 9 draws
([language flows](overlay-language-and-locale-flows.md#8-requests-to-remember-in-four-more-languages)),
and on 2026-10-31 the cortex called it on 4 and 5 of 15 requests over an empty pool
([listed tools](unasked-tools-listed-on-remember.md)). This record separates the causes.

## What the log shows before any draw

The eight first requests of the setup held no recall block: the cortex saw the system message,
the person's message and five tools, `list_scheduled`, `cancel_scheduled`, `snooze_scheduled`,
`edit_scheduled` and `forget_memories`. The `cortexn20` stack runs with `CORTEX_TOOLS_BACKEND`
unset (no sidecar tools), no subagents and no body, so it lists no `spawn_subagents`, no
`escalate_to_brain`, no file tools and no body tool. The 2026-11-07 stack listed
`spawn_subagents`, since one of its draws called it. That night's full tool list is not in the
tree; the two brain tools are the part of it this record can rebuild.

## Rows and rule, written 2026-11-12 before any draw

| Row | Message | Language |
| --- | --- | --- |
| `m1` | `Remember that my bike lock code is 5180.` | English |
| `m2` | `Remember that my dentist is called Dr Weber.` | English |
| `m3` | `Merk dir, dass mein Hund Bello heißt.` | German |
| `m4` | `Souviens-toi que le code de mon casier à la piscine est 7731.` | French |

Conditions, each a first request of a new chat:

- **H**: the brain code of `master` at this record (second brain `s10cand`), empty pool.
- **S**: the start build `d1620de90` (second brain `s1head`), empty pool. One turn per row on H
  and on S gives the two first requests. When they are the same text, the build cannot reach the
  first request, explanation (a) is out, and S is not drawn again.
- **P**: H with the eight rows the language setup stored, whose `m3` and `m4` rows hold the
  brain's note that nothing was deleted. Drawn only for a row whose first request holds a recall
  block with that row; a row with no block is reported, since the pool cannot reach it.
- **T**: H's recorded first request with `escalate_to_brain` and `spawn_subagents` added after
  the five tools, their specs built from the brain code.

H, P and T are drawn by sending the recorded first request to the model host through the
recording proxy five times per row, with nothing else changed, and counting the responses that
call `forget_memories`. No brain runs these draws, so no row is stored.

What each outcome means:

- **(a) tonight's code**: H and S first requests differ and H calls more often than S by at
  least 3 of 20 draws.
- **(b) the pool**: P calls on at least 3 more of its draws than H on the same rows. When the
  setup requests held no recall block, the pool cannot explain the setup's 7 of 8 whatever P shows.
- **(c) the stack, not the code**: T calls on at least 8 fewer of its 20 draws than H. That names
  the shorter tool list of this stack, which earlier nights' code did not change, as the cause.
- **(d) draw noise**: H calls on at most 4 of 20, near the 2026-10-31 rate, so tonight's counts
  were a run of draws and not a change.
- H calling often with none of (a), (b) and (c) holding leaves earlier nights' code, or a stack
  difference T does not rebuild, as untested causes; a build of the 2026-11-07 tree decides it.

## Condition L, written 2026-11-12 after H, S, P and T and before L was drawn

The model host's image is built `FROM ghcr.io/ggml-org/llama.cpp:server-cuda`, a tag that moves,
and tonight's build runs llama-server build 12282 (`aa75ff323`), where 2026-11-07 ran 12169 and
2026-10-31 ran 12004. **L** sends H's four recorded first requests five times each to a second
llama-server from `ghcr.io/ggml-org/llama.cpp:server-cuda-b12169`, with the same model file and
flags (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192`). L calling on at least
8 fewer of its 20 draws than H names the llama-server build as the cause; L within 3 of H rules it
out.

**C**, written after L was drawn and before C was: the brain code of 2026-11-07 (`59c23be0f`)
builds the same system message and the same specs for four of the five tools; only
`edit_scheduled` differs, by the `at` argument added since. C sends H's requests with that tool's
2026-11-07 spec in its place, five times per row, on the stack's llama-server. C calling on at
least 8 fewer of 20 than H names the code of the nights between as the cause.

Draws stop at 20 minutes; a condition not drawn by then is named as not drawn.

## The draws, 2026-11-12

The `cortexn20` stack: gemma-4-12B (`gemma-4-12b-it-qat-q4_0.gguf`) at a context of 16,384
tokens, llama-server build 12282, every card approved. SM clock at the draws: 0.57 to 0.73 of
`clocks.max.sm`.

| Condition | `m1` | `m2` | `m3` | `m4` | All |
| --- | --- | --- | --- | --- | --- |
| H, through each brain once | 1 of 1 | 1 of 1 | 1 of 1 | 1 of 1 | 4 of 4 |
| S, through each brain once | 1 of 1 | 1 of 1 | 1 of 1 | 1 of 1 | 4 of 4 |
| H, recorded request | 4 of 5 | 2 of 5 | 4 of 5 | 4 of 5 | **14 of 20** |
| T, two brain tools added | 5 of 5 | 2 of 5 | 3 of 5 | 3 of 5 | **13 of 20** |
| L, llama-server build 12169 | 5 of 5 | 4 of 5 | 5 of 5 | 3 of 5 | **17 of 20** |
| C, the 2026-11-07 `edit_scheduled` | 4 of 5 | 5 of 5 | 5 of 5 | 4 of 5 | **18 of 20** |
| P, the setup pool recalled | | | 1 of 5 | 1 of 5 | **2 of 10** |

The H and S first requests were the same text on all four rows, so (a) is out without a draw.
Each P request held a recall block with the row's stored fact and its note; on the same two rows
H called on 8 of 10. The P turn of `m4` through the brain showed a card listing the stored French
row (`Listed because they also hold 7731`), and the approved card deleted it. T's draws called
`spawn_subagents` three times, with an instruction to remember the fact.

**Result.** None of (a), (b), (c) and (d) holds. Tonight's code does not reach the first request;
the pool lowers the calls rather than raising them, and the setup's requests held no recall block;
the two brain tools, the code since 2026-11-07 and the llama-server build each leave the rate
within 4 of H; and 14 of 20 is far above the 4 of 15 and 5 of 15 of 2026-10-31. What tonight's
requests share is an empty recall block and a list of five tools with no body and no sidecar tool,
a condition no earlier record drew: the 2026-11-07 draws came after flows of that night had stored
the same facts, and the 2026-10-31 draws listed the body's tools. The body's and the sidecar's
tools are separated [below](#the-body-and-the-sidecar-the-draws-2026-11-12).
A brain-appended note in a stored row does not raise the calls on these rows, so the note stays in
the row, as the turn stores what it showed.

**Method.** `first.sh` (the brain turns), `replay.py <proxy.jsonl> <condition> <draws> <line>...`
(the direct draws; `URL` names another server, `EDIT` the spec for C), `cmp.py` (the H and S
requests) and `srccheck.py` (the request text against a source tree), in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot11/`.

## The body and the sidecar, rows and rule written 2026-11-12 before any draw

The `cortexn21` stack runs the same model and context on llama-server build 12316. A second brain
`s2full`, built from `d545e60f8`, has the Linux shell as the body (`CORTEX_BODY_BACKEND=grpc`,
the shell's `BodyService` reached at `host.docker.internal:23151`), schedules on
(`CORTEX_SCHEDULE_BACKEND=redis`), `CORTEX_VISION=auto` and the filesystem sidecar of
`docker/docker-compose.tools.yml`. Rows `m1` to `m4` above are each sent once through `s2full`
over an empty pool, and each first request is read from the proxy log. The conditions send it to
the model host directly, five draws per row:

- **F**: the recorded request with every tool it lists.
- **B**: F with the sidecar's tools removed, leaving the body's tools, the schedule tools and
  `forget_memories`.
- **N**: F with the sidecar's and the body's tools removed, the five tools H listed.

What each outcome means:

- B calls on at most 4 of 20 and on at least 8 fewer than N: the body's tools bring the rate
  down, and the rows of task 1163 run with the body attached.
- F calls on at most 4 of 20 and on at least 8 fewer than B: the sidecar's tools bring it down.
- B within 3 of N, or F within 3 of B: that group of tools does not move the rate.
- N on at most 4 of 20: H's 14 of 20 does not repeat on this stack's engine build, so no cause is
  named from these rows.
- Any other gap is no result for that pair. Draws stop at 15 minutes.

## The body and the sidecar, the draws, 2026-11-12

Each `s2full` first request listed 16 tools: `get_volume`, the four schedule tools other than
`schedule_task`, `forget_memories` and the ten sidecar tools. `set_volume` and `schedule_task` are
left out by `unasked_tools`, and no `capture_screen` is listed, since this model host reports no
vision tower. Proxy lines 103 and 105 to 107; SM clock 0.58 to 0.67 of `clocks.max.sm`.

| Condition | Tools | `m1` | `m2` | `m3` | `m4` | All |
| --- | --- | --- | --- | --- | --- | --- |
| F, every tool | 16 | 1 of 5 | 3 of 5 | 1 of 5 | 1 of 5 | **6 of 20** |
| B, no sidecar tool | 6 | 3 of 5 | 4 of 5 | 4 of 5 | 5 of 5 | **16 of 20** |
| N, H's five tools | 5 | 4 of 5 | 4 of 5 | 4 of 5 | 4 of 5 | **16 of 20** |

B equals N, so the body's tool does not move the rate, and N repeats H's 14 of 20 on this engine
build. F calls on 10 fewer than B but on more than 4, which the rule above reads as no result.

**Replication of F and B, written before these draws.** F and B are drawn again, five times per
row, in that order. Over the 40 draws of each, F calling on at most 12 and on at least 16 fewer
than B names the sidecar's tools as what brings the rate down; F within 6 of B rules them out; any
other gap is no result.

| Replication | `m1` | `m2` | `m3` | `m4` | This pass | Both passes |
| --- | --- | --- | --- | --- | --- | --- |
| F, every tool | 1 of 5 | 1 of 5 | 4 of 5 | 2 of 5 | 8 of 20 | **14 of 40** |
| B, no sidecar tool | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | 19 of 20 | **35 of 40** |

**Result.** The body's tool does not change the rate: B and N both call on 16 of 20. The sidecar's
tools lower it by 21 of 40 draws, in the same direction in both passes and on every row, but F's
14 of 40 is above the bound of 12, so by the rule the sidecar's pair is no result for the question
whether they restore the 2026-10-31 rate. That night's 9 of 30 is near 14 of 40; whether its
stack listed the sidecar's tools is not in the tree. So a stack with a body and no sidecar sees
about the rate of H, and one with the sidecar sees 14 of 40 against 35 of 40 without it. A direct
draw runs no tool and stores no row. Script
`replay.py` and run logs `draws.jsonl` and `draws2.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/b21ab427-7e2c-4723-9504-d59e434516ce/scratchpad/slot2/`.
