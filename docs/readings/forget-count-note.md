# Readings: a note counting what a forget deleted

What the brain appends when a turn's approved `forget_memories` deletes removed rows and the reply
names no removal. In one of 8 `n1v` draws of
[forget-shared-number.md](forget-shared-number.md#the-fixed-draws-2026-11-09), `Forget my gym
locker number, it is 5521.` deleted the gym row and the reply was `I've updated your gym locker
number to 5521.`, so the person was not told the fact was deleted. The note is `FORGOT_COUNT_NOTE`
in `forget_count_note.py`, and the decision is
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The reply reader, 2026-11-09

`says_forgotten` (`numbers_left_claim.py`) reads a removal in the five note languages. Of the 49
reply strings in `docs/readings/` that name a forget, change or save, `names_removal` alone reads
no removal in 9, three of which name it in Romanian, German and French (`Am uitat codul.`, `Ich
habe das vergessen.`, `j'ai oublié`); `says_forgotten` reads those three. The unit tests
`test_forget_count_note.py` show the note on `updated`, `changed`, `saved`, a question, a negation
and `OK.`, and on no reply naming the removal in any note language. Script `replies.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot12/`.

## Rows and rule

Written before the first draw. The `n1v` rig of
[forget-shared-number.md](forget-shared-number.md#a-value-named-beside-a-label-rows-and-rule-2026-11-09)
on the `cortexn17` stack: two seed rows holding 5521 (gym locker, shed padlock) stored again by two
seed turns and put back under new ids before each draw, then `Forget my gym locker number, it is
5521.` in a new chat with every card approved.

| Build | Draws | What it is |
| --- | --- | --- |
| fixed | up to 12 minutes | the stack brain, rebuilt from the working tree: after a turn whose approved forget deleted rows, a reply that `says_forgotten` does not read ends with `FORGOT_COUNT_NOTE`, followed by `NUMBERS_LEFT_NOTE` when rows still hold the number |

Counted per draw: rows deleted, whether the reply names the removal (`says_forgotten`), whether
the note shows, and the **form** (a reply naming no removal after a delete).

**Rule.** The note ships when it shows on every draw with the form and on no draw whose reply
names the removal. The form's count is recorded and does not decide: a draw set within the cap
with no form passes on the second item and the unit tests, since the form occurred in 1 of 8 base
draws and its requests matched the base build's.

## The draws, 2026-11-09

Ten draws on the stack brain from 05:50 to 05:53, every card approved, the SM clock at 0.57 to 0.58
of its maximum (`clocks.sm` over `clocks.max.sm`) before each. The seed replies were `I've
remembered that your gym locker number is 5521.` and `OK. I've noted that the shed padlock code is
5521.`.

| First call | Draws | Gym row left | Padlock row left | Reply names the removal | Count note |
| --- | --- | --- | --- | --- | --- |
| `5521` | 6 | 0 | 6 | 6 | 0 |
| `gym locker number` | 3 | 0 | 3 | 3 | 0 |
| `gym locker number is 5521` | 1 | 0 | 1 | 1 | 0 |

The form occurred in none of the 10 draws. Every reply named the removal by `says_forgotten`, and
no reply showed the count note; one, `I've processed your request to forget your gym locker
number.`, is read as naming it by the word `forget`. Each value first card listed the gym row to
delete and the padlock row under `KEPT_LINE`. The rule passes on its second item and the unit
tests, so the note ships. Driver and records: `seed.sh`, `draw.sh`, `fixed.log`, `fixed.jsonl`
and `tally.py` in the slot directory above.

## Second audit probes, 2026-11-09

Unit calls through `ForgetChosenTool` and `limit_notes` (`probe2.py` and `probe3.py`, logs beside
them in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot13/`).
A delete whose rows outlast it, because rows written since the card still hold the text or more
than the card's limit hold the value, deleted its listed row and reported a count of 0, so a reply
saying nothing was forgotten got no note. Those results now count their rows (tests in
`test_forget_count_note.py`). A count of 0 shows no note. Over a reply naming no removal, the
count, numbers left and kept rows notes agree and take the message's language (`KEPT_NOTES`,
tested in `test_forget_just_said.py`). The kept rows note and the count never contradict each other,
but two other notes do. Over `Done, I've forgotten your bike lock code and kept the shed one.`,
`UNKEPT_CLAIM_NOTE` says nothing was kept ([task 1090](../refinements/tasks/1090-the-unkept-note-follows-a-forget-reply-that-kept-the-fact-asked-to-keep.md)), and `NUMBERS_LEFT_NOTE` asks the person
to forget the number the message asked to keep ([task 1091](../refinements/tasks/1091-the-numbers-left-note-asks-to-forget-a-number-the-message-asked-to-keep.md)). A store failure after the delete still
counts nothing ([task 1092](../refinements/tasks/1092-a-store-failure-after-a-forget-deleted-rows-counts-nothing.md)). `Amintirea a fost ștearsă.` names the removal in a form the reader
lacks, so a second, Romanian count note follows it ([task 1095](../refinements/tasks/1095-a-romanian-removal-in-a-feminine-plural-or-cedilla-form-gets-a-second-count.md)). A forget turn stores no exchange
row, so none of these notes reaches memory; they stay in the chat's transcript.
