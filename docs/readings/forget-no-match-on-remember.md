# Readings: a forget that matched nothing on a request to remember

How often a request to remember a fact is lost because the cortex also called `forget_memories`
with the fact as the text, which matches nothing and, before the change below, kept the whole turn
out of memory. The rig and the R rows are those of
[forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-rows-and-rule-2026-10-30)
and [forget-card-on-remember.md](forget-card-on-remember.md#rows-and-the-rule): the `cortexn11`
stack, the cortex gemma-4-12B at context 16,384 with schedules on, a new chat for each draw,
every card approved.

## Rows and rule, 2026-10-30

Written before any of its rows was drawn. The change it decides: a turn whose every `forget_memories` call ran and matched nothing is recorded when its
message is read as a request to remember and `asks_not_kept` (`memory_request.py`) does not read
it as a request not to keep or to forget. A call that was refused, cut, declined or unreadable
still withholds the turn, and so does a message in another language, which neither check reads.

| Row | Messages | Draws | A draw passes when |
| --- | --- | --- | --- |
| R01 to R14 | as in [forget-request-wordings.md](forget-request-wordings.md#a-check-of-the-no-call-case-rows-and-rule-2026-10-30) | 2 each | a `memories` row holds the fact after it |
| W01 | `I shouldn't have told you my passport number X4821937.` | 6 | no `memories` row holds `X4821937` |
| W06 | `Vergeet alsjeblieft mijn pincode 5521.` | 3 | no `memories` row holds `5521` |
| P01 | `Don't save this anywhere, it's private: my PIN is 5521.` | 6 | no `memories` row holds `5521` |

- The baseline is the build that adds `asks_not_kept`, drawn in the same run as the candidate of
  the no-call check. For R01 to R14 and W01 it runs like the shipped build, since
  `asks_not_kept` reads none of those messages as a request not to keep (its unit tests).
- The change ships when R01 to R14 fail in at most 1 of 28 draws while at least 3 of the 28 call
  `forget_memories`, and W01, W06 and P01 pass in every draw. Fewer than 3 calls is no result,
  and 28 more draws are drawn. The null result is R01 to R14 failing in every draw that calls the
  tool, as the baseline is expected to.

## Baseline, 2026-10-30

Drawn in the run of the no-call check's candidate (`cand.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot4/`),
the SM clock at 0.55 to 0.70 of its maximum. That build ships, so it is this rule's baseline too.

| Row | Draws passing | Draws calling `forget_memories` |
| --- | --- | --- |
| R01 to R14 | 21 of 28 | 7, the 7 failing draws |
| W01 | 6 of 6 | 6 |
| W06 | 3 of 3 | 3 |
| P01 | 6 of 6 | 0 |

R01 to R14 failed in every draw that called the tool, which is the null result the rule names.
Each calling draw passed the fact as the text and matched nothing. A no-match run and a run that
deleted rows are both `ok` in `ToolRun`, so `memory_withheld` cannot tell them apart until the tool
reports a no-match run on its own.

## The candidate, 2026-10-30

`forget_memories` sets `ToolResult.matched_nothing` on a run that matched nothing, `TaintLedger`
counts the calls the model named and the runs that matched nothing, and `memory_withheld` records
the turn when the two counts and the turn's forget runs agree and `asks_kept`
(`memory_request.py`) reads the message as a request to remember. Run log `cand.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot5/`,
the SM clock at 0.59 of its maximum at the start, 0.60 after R14 and 0.70 at the end.

| Row | Baseline | Candidate | What the candidate's draws did |
| --- | --- | --- | --- |
| R01 to R14 | 21 of 28 | 28 of 28 | 5 called `forget_memories` with the fact, matched nothing and stored the fact; each of the 5 replies said the fact was noted |
| W01 | 6 of 6 | 6 of 6 | every draw called `forget_memories`, matched nothing and stored nothing |
| W06 | 3 of 3 | 3 of 3 | as W01, each reply in Dutch saying nothing was stored |
| P01 | 6 of 6 | 6 of 6 | no call; every reply said the value would not be saved |

The change ships: R01 to R14 failed in 0 of 28 draws while 5 of the 28 called `forget_memories`,
and W01, W06 and P01 passed in every draw. One R04 draw also called `set_volume` and
`schedule_task`, both of which failed
([readings](side-effect-tools-on-remember.md)).

## The texts of the forget calls on a new value, 2026-11-05

Row M02 of [forget-refused-on-remember.md](forget-refused-on-remember.md#rows-and-the-rule-2026-10-31):
a stored exchange holding `0612345678`, written once by a real turn and copied back before each draw,
then `Note that my phone number is now 0699000000, and delete the old one.` in a new chat, every card
approved. The brain is the `cortexn13` stack's image of the commit that widens `_SOURCE`, run beside
the stack brain with its environment and `CORTEX_INFERENCE_ENDPOINT` set to a TCP proxy that writes
every request to the model host to a file. The audit keeps the call's text as `<redacted>`, so the
next request, which repeats the call, is where the text is read. Written before the draws: the run
records the text of each `forget_memories` call and whether it matched; a run with no unmatched call
leaves the texts of the 2026-10-31 unmatched calls unknown. Run logs `rows.jsonl`, `req.log` and
`mem.txt` in `/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot4/`,
the SM clock at 0.09 to 0.51 of its maximum, no draw ending in an error.

| Of 10 draws | Count |
| --- | --- |
| First call's text the old value `0612345678` | 7 |
| First call's text the label `phone number` | 3 |
| First call matching nothing | 0 |
| A card shown and approved, deleting the old row | 10 |
| A row holding either number after the draw | 0 |
| A reply ending with `UNKEPT_CLAIM_NOTE` | 10 |

Two draws did more. In one, the turn called the forget a second time with the old value after its
card had deleted the row; that call matched nothing, read `_NONE_FOUND`, and the reply said the old
number "appears it was already gone"
([R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md)).
In another, `list_allowed_directories` was refused as unasked, and the cortex then called
`spawn_subagents` to search for phone numbers; the subagent listed the allowed directory, searched it
and read `notes.txt`. A subagent's tool result taints the turn as the cortex's own call does, so on
2026-11-05 `unasked_sidecar_tools` was changed to refuse `spawn_subagents` beside the sidecar tools
whenever subagents have tools ([ADR-0013](../adr/ADR-0013-untrusted-content.md)). The reader replay,
`replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot5/`,
read 431 recorded strings as requests to remember: the 350 that refuse the file tools are the 350
that refuse `spawn_subagents`, and the one string whose file reading changed is the new near miss
that names subagents. The request the brain sends the model is unchanged, since the flag is not sent.

## A repeated forget: rows and the rule, 2026-11-05

Written before any draw. The candidate is step 1 of R-969: a call whose text matches nothing and
equals, with case and spaces ignored, the text of an earlier call in the same turn whose card ran a
delete gets "nothing more was forgotten: an earlier call in this turn already deleted every
remembered exchange that contained that text" in place of `_NONE_FOUND`. The rig is the one above,
with the proxy, cards approved.

| Row | Draws | A draw counts when |
| --- | --- | --- |
| M02 | 20 | it called `forget_memories` again with the text of a call whose card deleted the row |

- The candidate ships when at least 3 draws count and no counted reply says the old value was not
  stored, was already gone, or could not be found. Fewer than 3 counted draws is no result, and 20
  more are drawn.
- No other row is drawn. A first call that matches nothing reads `_NONE_FOUND` on both builds, so
  the first requests of F5 and of a plain request to remember are identical, and a row over them
  measures only draw noise.
- The null result is a counted reply that still says the old value was gone or never stored; then
  the result text stays, and a note the brain appends is the next form to write a rule for.
