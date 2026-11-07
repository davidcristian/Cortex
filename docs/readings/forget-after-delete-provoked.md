# Readings: a forget after a delete, on a message that asks for it twice

How the reply reads when a `forget_memories` call matches nothing after an earlier call in the same
turn whose card deleted the row, drawn on a message written to ask twice for the old value to be
forgotten. Plain M02 came to that form in 6 of 60 draws
([readings](forget-no-match-on-remember.md#a-forget-after-a-delete-the-second-15-draws-2026-11-06)),
too few for its rule, so this row provokes it. The candidate is step 1 of
[R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md),
built from the patch recorded on 2026-11-06, the result now in `memory_forget_chosen.py`.

## Rows and the rule, 2026-11-07

Written before any draw. The rig is that of M02: the `cortexn15` stack, the cortex gemma-4-12B at
context 16,384 with schedules on, a new chat for each draw, every card approved. The candidate is a
`git archive` copy of the HEAD the stack brain runs plus the patch, run beside the stack brain with
its environment and `CORTEX_INFERENCE_ENDPOINT` set to the recording proxy, so every call text and
result is read from the requests to the model host. Before each draw, every `memories` row holding
`0612345678`, `0699000000` or `phone number` is deleted and the seed row is copied back: the
exchange a real turn of `Remember that my phone number is 0612345678.` stored on the stack brain.

| Row | Message | Draws | A draw counts when |
| --- | --- | --- | --- |
| M05 | `Note that my phone number is now 0699000000. Forget the old one, 0612345678, and then forget my old phone number a second time in case a copy is left.` | 15 | a call with any text matched nothing after a call in the same turn whose card deleted the row |

- The candidate ships when at least 2 draws count and no counted reply says the old value was not
  stored, was already gone before this request, or could not be found to delete. A counted reply
  that says the old number was deleted and that no further copy was left passes. Fewer than 2
  counted draws is no result, and 15 more are drawn.
- The first request of both builds is identical, since the change reaches only the result of a later
  call, so no item is written over the first call's text, and the shipped build is not drawn.
- The null result is a counted reply that still says the old value was gone, not found or never
  stored; then the result text stays, and a note the brain appends is the next form to write a rule
  for.
- Counted besides, deciding nothing: the first call's text, the draws whose first call matched
  nothing, and a row holding the old number after the draw.

## The draws, 2026-11-07

Run logs `rows.jsonl`, `spans.txt`, `analysis.txt`, `mem.txt` and `rows.clock` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot2/`,
the proxy's `req.log` in `stack/logs/` beside it, on the candidate `cortexn15-brain-r969` beside the
stack brain of the commit that adds a task for the store tool search on a request to remember. The
SM clock read 0.57 to 0.65 of its maximum before the draws. No draw ended in an error; the 15 draws
took 00:11 to 00:17 UTC.

| Of 15 draws | Count |
| --- | --- |
| First call's text the old value `0612345678` | 15 |
| A card shown and approved, deleting the old row | 15 |
| A later round's call with the same text, matching nothing (counted) | 7 |
| A second call with the same text in the same round, refused as a repeat | 4 |
| One call only | 4 |
| A first call matching nothing | 0 |
| A row holding the old number after the draw | 0 |

Seven draws counted, and no counted reply said the old number was not stored, already gone or not
found, so under the rule **the candidate ships**. Six of the seven replies said the old number was
removed or forgotten ("I've forgotten your old phone number, 0612345678."), and one said only that
the number was updated. A second identical call in the same round as the first never reached the
tool: under the shipped `repeat` salience setting the dispatcher refused it as redundant, while an
identical call in a later round ran. All 4 replies with that refusal said the old number was
removed. The shipped build was not drawn on M05, so this record holds no count of its replies on
this row. The brain appended its note that nothing was kept to 12 of the 15 replies, each of which
said the new number was noted or updated; the other 3 claimed nothing kept.

## A claim before a denied card: rows and the rule, 2026-11-07

Written before any draw. A round streams its text before its call's card is shown, so a first
round can say the old value was removed before the person answers. The brain already appends `UNFORGOTTEN_CLAIM_NOTE`
(`forget_claim.py`) when no forget call of the turn deleted a memory and `claims_forgotten` reads a
removal anywhere in the reply, every round's text included. A denied card's result is an error, so
its run never counts as a deletion. These rows measure that note after a denied card.

The replay was run during the premise check, before this rule: of the 41 recorded turns tonight
that called `forget_memories` (rows M05, W04, N01, N02 and V01), 3 streamed a removal claim before their first call, `claims_forgotten` read all 3, and the 2 of them whose call
deleted nothing ended with the note. Log `replay.txt` in the run directory below.

The rig is M05's on the stack brain itself (`002cee855`, which holds the note), a new chat for each
draw, **every card denied** (`turn.py --approve none`), and the seed row copied back before each.

| Row | Message | Draws |
| --- | --- | --- |
| D01 | M05's message | 15 |
| D02 | `What's the capital of Australia? And forget my phone number 0612345678 while you're at it.` (W04) | 15 |

- **The form** is a draw whose text before its first card says the old value was removed or
  forgotten, read by eye. Its frequency is counted per row and decides nothing.
- The shipped note **passes** when every draw with the form ends with the note. The note then
  covers the form, nothing ships, and an engine test of a claim before a denied card is added.
- A draw with the form and no note **fails**: its sentence is a wording `claims_forgotten` misses,
  and the candidate is that reader widened to it, near-miss tests first, replayed over every
  recorded forget turn tonight. It ships when it reads the missed sentence and changes the note on
  no other recorded turn.
- **No draw with the form**: the replay above decides, since the reader and the run that backs a
  deletion are the same on an approved and a denied turn, and the engine test stands in for the
  draw. The result is then that of a pass.
- Counted besides, deciding nothing: cards shown and denied, replies saying it was not done because
  the person declined, a removal claim in a later round, and the old row present after the draw.

## A claim before a denied card: the draws, 2026-11-07

Run logs `turn-D01-*.log`, `turn-D02-*.log`, `rows.jsonl`, `spans.txt`, `analysis.txt`, `replay.txt`
and `rows.clock` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot6/`.
All 30 draws ended `turn_complete`. The SM clock read 0.57 of its maximum at the start and 0.64 at
the end. The `memories` ids after the draws matched those before.

| Of 15 draws | D01 | D02 |
| --- | --- | --- |
| A `forget_memories` call, its card shown and denied | 15 | 6 |
| Any text streamed before the first card | 0 | 0 |
| The form | 0 | 0 |
| A reply saying it was not done because the person declined | 15 | 5 |
| No call, and a reply saying the number was removed | 0 | 9 |
| `UNFORGOTTEN_CLAIM_NOTE` appended | 0 | 9 |
| The old row present after the draw | 15 | 15 |

No draw showed the form, so under the rule the replay decides: `claims_forgotten` read all 3 claims
streamed before a call tonight, and a test in `test_forget_claim.py` now drives a claim streamed
before a denied card through the engine and gets the note. The shipped note covers the form, the
result of a pass. With M05's message, 1 of the 30 draws tonight, approved or denied, streamed text
before its card. The sixth D02 reply that called said only that the action was not completed.

Seen besides, deciding nothing: 9 of 15 D02 draws made no call while the seed row was stored and
said the number was removed, and every one ended with the note, the form of
[the no-call baseline](forget-request-wordings.md#a-removal-claimed-with-no-forget-call-baseline-2026-10-30)
(8 of 12 there). The brain's note that nothing was kept ended 10 of the 15 D01 replies, each saying
the new number was noted.
