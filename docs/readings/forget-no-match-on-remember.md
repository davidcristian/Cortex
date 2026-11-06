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

## A repeated forget: the draws, 2026-11-05

Run logs `rows.jsonl`, `req.log`, `mem.txt` and `rows.clock` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot6/`,
on a candidate built from the working tree with the result above, run through the proxy beside the
stack brain of the commit that notes no file was searched. The SM clock read 0.08 to 0.52 of its
maximum before the draws. No draw ended in an error.

| Of 20 draws | Count |
| --- | --- |
| First call's text the old value `0612345678` | 6 |
| First call's text the label `phone number` | 11 |
| First call's text the new value `0699000000`, matching nothing | 2 |
| No `forget_memories` call; the reply asked for the old number | 1 |
| A later call repeating the text of a call whose card deleted the row | 0 |
| A later call with the new value after a delete, matching nothing | 4 |
| A row holding the old number after the draw | 3 |

No draw counted, so under the rule **this is no result**, and the candidate is not committed. The
draws show forms the candidate does not reach. In 2 draws the first call's text was the new number,
which no row holds: it matched nothing, the old row stayed, the turn was stored, and each reply
said it could not find the old number ("I couldn't find your old phone number in my memory to
delete it"). In 4 draws a call with the new number followed the delete and matched nothing, and one
of those replies said "I couldn't find any previous phone number in my memory to delete" though the
earlier call had deleted it. With the 10 draws above, a repeat of the deleting text came in 1 of 30
draws, and a call naming the new value in 6 of 20.

## A forget after a delete: rows and the rule, 2026-11-06

Written before any draw. The candidate is step 1 of R-969: a call that matches nothing in a turn in
which an earlier call's card already ran a delete gets "nothing more was forgotten: no remembered
exchange contains that text, and an earlier call in this turn already deleted what the user asked
to forget, so tell the user it was deleted and do not say that it was not stored or could not be
found" in place of `_NONE_FOUND`, whatever the call's text. `ForgetChosenTool` keeps the turn ids
whose card ran a delete, bounded as `_shown` is. The rig is the one above, with the proxy, cards
approved, and the `seed4` row written again in tonight's stack by a real turn.

| Row | Draws | A draw counts when |
| --- | --- | --- |
| M02 | 15 | a call with any text matched nothing after a call in the same turn whose card deleted the row |

- The candidate ships when at least 2 draws count and no counted reply says the old value was not
  stored, was already gone, or could not be found. Fewer than 2 counted draws is no result, and 15
  more are drawn in a later slot.
- The first request of both builds is identical, since the change reaches only the result of a later
  call, so no item is written over the first call's text.
- The null result is a counted reply that still says the old value was gone, not found or never
  stored; then the result text stays, and a note the brain appends is the next form to write a rule
  for.

## A forget after a delete: the draws, 2026-11-06

Run logs `rows.jsonl`, `req.log`, `mem.txt` and `rows.clock` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot8/`,
on a candidate built from the working tree with the result above (its diff and seven tests are
`r969-candidate.diff` and `r969-test_forget_after_delete.py` beside them; seven mutation rows over
the tests all failed), run through the proxy beside the stack brain of the commit that refuses a
day-before reminder stored on the wrong date. The `seed4` row was written again by a real turn on
the stack brain. The SM clock read 0.57 to 0.71 of its maximum before the draws. No draw ended in
an error; the 15 draws took 04:13 to 04:19 UTC.

| Of 15 draws | Count |
| --- | --- |
| First call's text the old value `0612345678` | 10 |
| First call's text the label `phone number` | 3 |
| First call's text the new value `0699000000`, matching nothing | 2 |
| A card shown and approved, deleting the old row | 13 |
| A later call with any text after a delete, matching nothing | 1 |
| A row holding the old number after the draw | 2 |

One draw counted, so under the rule **this is no result**, and the candidate is not committed; 15
more draws decide it. The counted draw's later call named the new number `0699000000`, read the
new result, and its reply said the old number was forgotten and the new one noted, with
`UNKEPT_CLAIM_NOTE` appended. The 2 draws whose first call named the new number are step 2's form
again: in both the old row stayed and the turn was stored, one reply asked for the old number
("could you please tell me what the old number was?") though `_NONE_FOUND` says not to ask, and the
other said no old number was stored. One draw whose call named the label said it had no access to
the previous number and had cleared the phone number memories. With the 30 draws of 2026-11-05, a
call matching nothing after a delete came in 6 of 45 draws, and a first call naming the new value
in 4 of 45.

## A forget after a delete: the second 15 draws, 2026-11-06

Run logs `rows.jsonl`, `req.log`, `mem.txt`, `rows.clock` and `run.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot10/`,
on the same candidate (its diff is [recorded as a patch](forget-after-delete-patch.md); the seven
mutation rows over its tests all failed again), through the proxy beside the stack brain of the
commit that keeps the file tools on a value named by a record, the `seed4` row copied in before each
draw. The SM clock read 0.57 to 0.73 of its maximum before the draws. No draw ended in an error; the
15 draws took 04:51 to 04:56 UTC.

| Of 15 draws | Count |
| --- | --- |
| First call's text the old value `0612345678` | 6 |
| First call's text the label `phone number` | 3 |
| First call's text `old phone number`, matching nothing | 2 |
| First call's text the new value `0699000000`, matching nothing | 2 |
| No forget call in the turn | 2 |
| A card shown and approved, deleting the old row | 9 |
| A later call with any text after a delete, matching nothing | 0 |
| A row holding the old number after the draw | 6 |

Over the 30 draws of both rows 1 counted, under the rule's 2, so **the candidate does not ship** and
the behaviour stays; its result text is kept as the patch. The form it changes came in 6 of the 60
draws of M02 over the three nights and 1 of the 30 on this candidate, so the next draw of step 1 is
a row written to provoke it (a message that asks twice to forget the old value), under the same
rule, rather than 15 more of M02. Step 2's form, a first call naming the new number, came in 2 of 15
again, 6 of 60 in all: in both the old row stayed, the turn was stored and the reply said no old
number was found. The 2 draws naming `old phone number` matched nothing the same way and replied the
same; the 2 draws with no forget call asked for the old number.
