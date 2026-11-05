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

## A reply saying it kept and removed, 2026-10-31

`claims_kept` reads `Noted your new code and removed the old one.`, and `unforgotten_claim` does not,
since it needs `I` and a named memory, so that reply after a refused call had no note and the old row
stayed. `names_removal` (`forget_claim.py`) now also shows the note on a statement naming a removal in
any words with no negation in its clause. A message holding one of those words is not refused, so on
a refused call the reply did not read the word back from the message.

The reader's tests decide this, with no row drawn: the note is true on any turn with a refused call.
The replay of the 532 replies in the run logs still on disk: `claims_kept` reads 325, and 19 of those
also name a removal. All 19 answer a message giving a new value (M01, M02, T1); 18 say the old
value went and one offers to remove it. No reply on an R, S or P row is among them.

A reply `claims_kept` does not read still shows the note on a plain request
([R-975](../refinements/tasks/975-a-refused-forget-call-shows-its-note-on-a-reply-the-claim-reader-does-not-read.md)).

## Facts holding a wish word, 2026-10-31

`_WISH` leaves the tool callable on a fact holding a wish word, so these rows ask whether such a fact
reaches an approved card. Written before the draw, with the rig above and cards approved, the fact
stored first by the same message in a new chat: W1 `Please remember this: I want a window seat.`, W2
`Please remember this: my bank's name is Askari.`, W3 `Please remember this: I need a window seat on
flights.`, W4 `Remember that my son can swim.`, 3 draws each. A draw with a card and the row gone is the
defect. Null result: no card in the 12 draws.

Run log `d1.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot9/`,
the SM clock at 0.21 of its maximum at the end. All 12 draws made no forget call, showed no card and
kept the row, and each reply says the fact was noted. That is the null result on 12 draws, which cannot
rule out a low rate
([R-968](../refinements/tasks/968-a-request-to-remember-holding-a-negation-or-a-full-stop-can-still-show-a-forget-card.md)).

## A reply saying it will make sure to keep, 2026-11-05

`claims_kept` did not read `Understood. I'll make sure to keep your vegetarian preference in mind for
any recipes.`, the reply in 3 of the 259 recorded replies to R and P rows with no forget card, so after
a refused call that reply would have ended with `UNFORGOTTEN_CLAIM_NOTE`. Its `I'll` form now also
reads `make sure to` before the verb. The near misses stay unread: `I'll make sure not to keep that in
memory.`, `I'll not keep that in memory.`, `I'll make sure you keep it in mind.` and a question.
`Got it, your locker code is 8426.` says nothing kept and still shows the note.

The readers' tests decide this, since no recorded draw has both the wording and a refused
call. The replay of the 27,162 quoted strings in `docs/readings/`, the task files and the brain tests
changes `claims_kept` on 4, all `I'll make sure to keep` or `save` in mind or memory, three of them the
new tests. Replay script and log `replay.py` and `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot2/`.

Real turns on a brain built from the change, written before the draw as a check that it runs and not
as a rule: V1 `Keep in mind that I am vegetarian.` and V2 `Please remember this: I am vegetarian, so
keep that in mind for any recipes.`, 2 draws each on an empty pool, cards approved. Null result: an
error, a lost row, or a note on a reply saying it kept the fact. All 4 draws stored the fact, made no
call, refused none and ended with no note; 2 replies said `I'll make sure to keep`. Run log
`rows.jsonl` beside `replay.log`, the SM clock at 0.52 of its maximum at the end.

## The unkept note on a forget worded as a note, 2026-11-05

`Note that 8426 should be zapped.` and `Note that I mean the locker code.` end with
`UNKEPT_CLAIM_NOTE` when their forget call deletes the row, since `asks_kept` reads them. A message
reading that hides the note there also hides it where a new value is lost. On a turn with a forget
call, replayed over the 27,176 quoted strings read the same way, 384 are read as a request to
keep. Requiring `_STATES_A_FACT` with no `_WISH` word, as the refusal does, hides the note on 181 of
them, among them `Note that the new PIN is 8426, the old one can go.` and `Please remember this: my
bank's name is Askari.` (`ask` in the name). `_STATES_A_FACT` alone hides it on 98, among them
`Remember the code 7319 and wipe the PIN.`, and still shows it on `Note that I mean the locker code.`.

The note is true on every such turn. Shown on a forget request it costs one line the person did not
need; hidden on a new value it leaves a lost fact unsaid. So the message reading stays as it is, and
two tests show the note on the two lost new values above. Replay log `replay974b.log` beside
`replay.log`.

## A wish word's own forms and a title's full stop, 2026-11-05

`_WISH` read any longer word it starts (`ask` in `Askari`, `need` in `needles`, `tell` in `teller`),
and the second sentence branch of `_CAN_RETRACT` read the full stop of `Mr.`, so both left the forget
tool callable on a stated fact. `_WISH` now reads only each word's own forms, and `saying` or
`telling` only after a form of `be` or `keep`, so `my favourite saying` states a fact and
`I'm saying 8426 is dead` keeps the tool. A full stop after `Mr`, `Mrs`, `Ms`, `Dr` or `St` ends no
sentence. Near misses in `test_unasked_tools.py` keep the tool on `I asked you to zap 8426`, `I keep
saying`, `I was telling you`, `I needed`, `I wanted`, `I wished` and a real second sentence after a title.

The replay of the 27,175 quoted strings in `docs/readings/`, the task files and the brain tests, with
the test file as it was before the change: of the 408 read as requests to remember, the old reader
refuses the forget tool on 103 and the new one on 105. The two added are `Please remember this: my
bank's name is Askari.` and `Please remember this: my landlord is called Mr. Weber.`, and none is
newly kept. Replay script and log `replay.py` and `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot3/`.

A negation, a question and a real second sentence still keep the tool. They are how a forget request
reads (`Remember I don't need the locker code anymore.`), a refused forget costs a second message, and
a fact read wrongly costs a card the person can reject, which the 12 draws on facts holding a wish word
never showed.

Real turns on a brain built with this change, written before the draw as a check that it runs and not
as a rule: the Askari and Mr. Weber messages above, one draw each on an empty pool, cards approved.
Null result: an error, a card, or no stored row. Both stored the fact with no card, no error and no
forget call. Run log `rows.jsonl` beside `replay.log`, the SM clock at 0.51 of its maximum at the end.
