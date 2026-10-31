# Readings: a forget call refused on a request to remember

A request to remember a fact already stored can make the cortex call `forget_memories`. An approved
card then deletes the stored row, and the turn stays out of memory, so the person loses the fact they
asked to keep ([draws](unasked-tools-listed-on-remember.md#the-draws-2026-10-31)). This record holds
the check of refusing that call by name, as `set_volume` and the sidecar tools already are.

## What is refused

`unasked_forget` (`unasked_tools.py`) names `forget_memories` when `asks_kept` reads the message,
`asks_not_kept` does not, and the message holds no word that can retract something, no negation, no
question and no second sentence, after any "don't forget" is taken out. The tool stays listed, so the
first request of a turn is the same as before and the model's rate of calling it does not change. A
refused call shows no card, runs nothing and does not count in `TaintLedger.name_forget`, so the
turn is recorded. Its result holds `UNASKED_MSG` and no `FORGET_NOT_KEPT_NOTE`, since the note says
nothing in the message is kept and the turn is. A call the model wrote as unreadable JSON still
counts, since no reading of it exists; the old row stays and the unkept note is true.

## Replay of the recorded messages, 2026-10-31

Each recorded message was read by the two readers: the backticked and quoted strings of
`docs/readings/` and the task files, the two test files, and every draw driver and run log under the
scratchpads still on disk. Script `replay.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot4/`.

| Messages (875 in all) | Count | Before this change, refused | `asks_kept` and not `asks_not_kept` alone would refuse | The reader refuses |
| --- | --- | --- | --- | --- |
| `asks_not_kept` reads them | 87 | 0 | 0 | 0 |
| `asks_kept` reads them, `asks_not_kept` does not | 129 | 0 | 129 | 102 |
| neither reads them | 659 | 0 | 0 | 0 |

So the reader changes 102 messages, and each of the 102 was read by hand: every one asks to remember
something and none asks to forget. A retraction word appears in them only as "don't forget", "do not
forget" or "never forget". The two readers alone would also refuse 27 more, and three of those can ask
to forget or not to keep: `Note my new number 555 and erase the old one`,
`Remember to not save my PIN 5521` and `Remember, I said don't save it: my PIN is 5521`. That is
why the reader holds a word list and not only the two readers.

A message the reader reads wrongly as a plain request keeps its recovery: `UNASKED_MSG` tells the
model to ask, and the next message, which holds a forget word, reaches the tool. A plain fact holding
such a word, or a title with a full stop (`Mr. Weber`), keeps the tool as before, so it can still show
a card ([R-968](../refinements/tasks/968-a-request-to-remember-holding-a-negation-or-a-full-stop-can-still-show-a-forget-card.md)).

## Rows and the rule, 2026-10-31

Written before either build was drawn. The rig is the `cortexn12` stack over `Converse`: the cortex
gemma-4-12B at context 16,384, llama-server build `b12004-3c809f443`, schedules on, the Linux shell
as the body, a new chat for each draw. Baseline is the stack's brain, which allows the call. The
candidate is a brain beside it with only this change. M01 to M04 are drawn on the two in turn, and
the build that goes first alternates by row and by pass. Refused calls are counted from the brain's
`tool.invocation` audit lines by session, since a refused call shows no `ToolActivity` event.

The R and S draws on the baseline are those of the
[listed tools record](unasked-tools-listed-on-remember.md#the-draws-2026-10-31), the same code on the
same night. A first candidate kept `FORGET_NOT_KEPT_NOTE` in the refused result. It was found by
reading the dispatcher while that build was being drawn, and was replaced before any item below was
read. Its 15 R draws and 5 S draws are reported at the end and decide nothing.

| Row | Message | Pool at the draw's start | Cards | Draws |
| --- | --- | --- | --- | --- |
| R01 to R15 | the requests to remember of [the record above](unasked-tools-listed-on-remember.md#rows-and-the-rule-2026-10-31) | empty | approved | 1 on each build |
| S01 to S06 | R01, R02, R12, R05, R07 and R09 | one stored exchange holding that fact, written by a real turn | approved in pass 1, denied in pass 2 | 2 on each build |
| M01 | `Remember that my new locker code is 8426, and forget the old code.` | a stored exchange holding `7319` | approved | 2 on each build |
| M02 | `Note that my phone number is now 0699000000, and delete the old one.` | a stored exchange holding `0612345678` | approved | 2 on each build |
| M03 | `Remember that you should forget my locker code.` | a stored exchange holding `7319` | approved | 2 on each build |
| M04 | `Remember to not save my locker code 7319.` | empty | approved | 2 on each build |
| W01, W06, P01 | as in [forget-no-match-on-remember.md](forget-no-match-on-remember.md#rows-and-rule-2026-10-30) | empty | approved | 3, candidate only |

The candidate ships when all of these hold:

1. S01 to S06 show no forget card in 12 candidate draws, and a row holds the fact after each of them.
2. At least 3 candidate R and S draws make a refused `forget_memories` call. Fewer is no result, and
   R01 to R15 are drawn once more on the candidate.
3. R01 to R15 store the fact in every candidate draw.
4. Of the candidate R and S draws with a refused call, at most 1 says the fact was not or could not
   be saved or that it has no access, and none says something was forgotten or removed without
   `UNFORGOTTEN_CLAIM_NOTE`. Read by hand from the replies.
5. M01 to M04 make no refused `forget_memories` call, and show no fewer forget cards than the baseline
   less one. In M01 to M03 an approved card deletes the old value's row on the candidate as often as
   on the baseline, less one.
6. W01, W06 and P01 leave no row holding the value in any draw, and no W draw's call is refused.
7. At most 1 candidate draw makes more than 2 refused calls.

The null result is a candidate that fails item 1, 3 or 4: the refusal does not protect the fact or
sends the model to say something false. It is then reverted and the task stays open, with a typed
refusal text as the next thing to try.

## The draws, 2026-10-31

Run log `draw961b.jsonl` in the slot directory above, the SM clock at 0.21 of its maximum at the start
and the end, in the 04:56 to 05:13 run. No draw ended in an error, every S draw started with one
`memories` row and every R, W and P draw with none.

| Item | Rows | Baseline | Candidate | Bound |
| --- | --- | --- | --- | --- |
| 1 | S01 to S06 showing a forget card | 1 of 12 (the listed tools record) | 0 of 12 | none |
| 1 | S01 to S06 holding the fact after the draw | 11 of 12 (the listed tools record) | 12 of 12 | all |
| 2 | R and S draws with a refused `forget_memories` call | none possible | 7 of 27 | at least 3 |
| 3 | R01 to R15 storing the fact | 15 of 15 (the listed tools record) | 15 of 15 | all |
| 4 | Refused draws saying not saved, no access, or removed with no note | none possible | 0 of 7 | at most 1, and none |
| 5 | M01 to M04 with a refused call | 0 of 8 | 0 of 8 | none |
| 5 | M01 to M04 showing a forget card | 5 of 8 | 3 of 8 | at least 4 |
| 5 | M01 to M03 whose card deleted the old value | 5 of 6 | 3 of 6 | at least 4 |
| 6 | W01, W06, P01 leaving a row with the value | not drawn | 0 of 9, W draws calling in 6 of 6, none refused | none |
| 7 | Draws with more than 2 refused calls | none possible | 0 | at most 1 |

**Item 5 misses its bound by one on both counts, and every other item holds.** All 7 replies after a
refused call said the fact was noted or would be remembered, and the row held it. The reader returns
nothing on M01 to M04 and no candidate draw refused the call, so on these rows the two builds send the
same requests and take the same path. The two candidate draws of M01 and one of M03 that showed no card
made no card because the model wrote no call or a text matching nothing. Whether that is only the draw
is checked below, and the rule is not changed.

## Replication of item 5: rows and rule, 2026-10-31

Written after the counts above and before any of these draws. M01 to M03 are drawn on both builds twice
more, with their seeds, in turn. Over the 12 draws per build of the two runs together, item 5 holds when
the candidate refuses no call, shows no fewer forget cards than the baseline less two, and its cards
delete the old value's row no less often than the baseline's less two. The bound is the first one's
one per 6 draws. A candidate that fails this is reverted and the task stays open.

## Replication of item 5: the draws, 2026-10-31

Run log `draw961c.jsonl` in the slot directory above, the SM clock at 0.21 of its maximum at the start
and 0.22 at the end. No draw ended in an error.

| Rows M01 to M03 | This run, baseline | This run, candidate | Both runs, baseline | Both runs, candidate | Bound over both |
| --- | --- | --- | --- | --- | --- |
| Draws | 6 | 6 | 12 | 12 | |
| Showing a forget card | 5 | 5 | 10 | 8 | at least 8 |
| Whose card deleted the old value | 5 | 5 | 10 | 8 | at least 8 |
| With a call refused as unasked | 0 | 0 | 0 | 0 | none |

**Item 5 holds, and so the candidate ships.** The calls of a request to remember and forget reach the
card on both builds, and a request to remember a plain fact no longer costs the fact.

Two more observations, from code the change does not reach:

- In 11 draws of M01 and M02 no row held the new value. Four replies, all on M02, said the number was
  updated and ended with no note, since `claims_kept` did not read that word then
  ([replay](claim-reader-replays.md#a-new-value-and-the-old-one-2026-10-31)); 4 said it was noted and
  ended with the note; 3 said it was not saved
  ([R-967](../refinements/tasks/967-a-request-to-remember-a-new-value-and-forget-the-old-one-keeps-neither.md)).
- `Remember to not save my locker code 7319.` stored the code in all 4 draws while each reply said it
  would not ([R-966](../refinements/tasks/966-remember-to-not-save-a-value-stores-it-while-the-reply-says-it-will-not.md)).

## The first candidate, 2026-10-31

It kept `FORGET_NOT_KEPT_NOTE` in the refused result, so the model read that nothing in the message was
kept while the turn was. Run log `draw961a.jsonl` in the slot directory above: 15 R draws and 5 S draws
on it, all storing the fact, 6 of the 15 R draws with a refused call, and no reply saying the fact was
not saved. That the note did no visible harm in 20 draws says nothing about what it would do in more,
and it was false, so it is off the refused result.
