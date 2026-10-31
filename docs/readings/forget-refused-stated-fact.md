# Readings: refusing a forget call on a stated fact only

[The first record](forget-refused-on-remember.md) holds the refusal of `forget_memories` on a request to
remember, and the rig named here as "the rig above" is its rows' rig. This record holds its narrowing to a
message that states a fact, and the note a reply gets after such a refusal.

## Refusing a stated fact only, 2026-10-31

The list reads a word. It cannot read a request with no such word: `Note that 8426 should be zapped.`,
or `Note that I mean the locker code.` after `Which one would you like me to forget?`. The call's text
does not separate them either. All 4 forget cards drawn on R and S rows named the stated fact
(`my bank closes at four on Fridays`), so a text found in the message is the harm, yet `8426` is in
`Note that 8426 should be zapped.` too. A text outside the message is no safer: on
`Remember my new locker code is 5555.` a call naming the old value and an approved card would delete
it and keep neither.

So the shape of the request decides. The refusal now also needs `_STATES_A_FACT` to read the message
(`my`, `our`, `I`, `we`, or a subject that is no value or pronoun before `is`, `are`, `was`, `were`) and
`_WISH` not to (a modal, a verb of wanting or saying), and the chat's last assistant message not to hold
a question naming forgetting. A question about something else changes nothing: most replies end in one.
`UNASKED_MSG` stays as it is, since it tells the model to ask when the person may want the action, and
the reply is covered by the note in the next section.

The replay of the 875 recorded messages: the old reader refuses 85 and the new one 72, with none newly
refused. The 13 it no longer refuses were read by hand. None is a plain fact at risk of a forget
call except `Note that the heads of the team meet on Monday.` and `Note that I need to take my pills at 8
every day`; the rest ask for a reminder or a tool, or state nothing (`Please remember`). All 15 R messages
are still refused, so the reader returns the same on R and S rows and they are not drawn again.

Rows, written before the draw, on a brain built from the change with the rig above, cards approved:
F1 is the forget question of `t3.jsonl` and its answer (2 draws), Z1 `Note that 8426 should be zapped.`
(3 draws), and P1 `Please remember this: my locker code is 8426.` with that fact stored (3 draws). The
change ships when no F1 or Z1 draw has a refused forget call, and no P1 draw shows a card or loses the
row. The reader's tests decide the rest, as the last section says. Null result: a refused call on F1
or Z1, or a P1 draw that loses the row.

Run log `d971.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot8/`, the
SM clock at 0.21 of its maximum at the end of the first run and 0.10 at the end of the second. No draw
ended in an error.

| Row | Draws | Refused | Card and row deleted | Row left | Reply |
| --- | --- | --- | --- | --- | --- |
| F1 | 2 | 0 | 2 | 0 | says forgotten |
| Z1 | 3 | 0 | 2 | 1 | `OK.`, `I've processed that request.`, and in the third, whose call matched nothing, says so |
| P1 | 3 | 0 | 0 | 3 | says noted, with no card |

**The change ships.** The two F1 and Z1 replies that deleted the row also end with `UNKEPT_CLAIM_NOTE`,
which is true and says nothing useful there
([R-974](../refinements/tasks/974-a-forget-worded-as-a-note-shows-the-unkept-note.md)).

## A note on a refused call, 2026-10-31

`unforgotten_claim` reads English forms of "forgotten" and "removed", so a reply after a refused call
could say `gelöscht` or `processed your request to forget` with no note. A note with no reading of the
reply fails on the recorded draws alone: all 7 refused draws of `draw961b.jsonl` said the fact was noted,
on messages that never asked to forget, so it would close 7 of 27 plain requests with a statement about
forgetting. So the reading is turned around: the note shows on a turn with a call refused as unasked
unless `claims_kept` reads the reply. Written before the draw, with the rig above and cards approved:
R01 to R15 once on an empty pool, P1 3 draws, and D1 `Remember my code 8426 is dead to me.` 3 draws with
that code stored. The change ships when at least 3 draws make a refused call (fewer is no result, and R01
to R15 are drawn once more), at most 1 R or P draw with a refused call shows the note, no draw with a
refused call says something was removed with no note, and R01 to R15 all store the fact. Null result: 2
or more R or P draws show it, which reverts the change.

Run log `d973.jsonl` beside `d971.jsonl`, the SM clock at 0.16 of its maximum at the end of the R rows.
No draw ended in an error, and every R draw stored its fact.

| Row | Draws | With a refused call | Refused and showing the note | Reply when refused |
| --- | --- | --- | --- | --- |
| R01 to R15 | 15 | 3 | 0 | says noted |
| P1 | 2, the third cut off by the run's time limit | 0 | 0 | none |
| D1 | 3 | 2 | 2 | says noted and asks whether to remove the old information; the row stays |

**The change ships.** The D1 note is true, since nothing was removed, and the message asked for that.
