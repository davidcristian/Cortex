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
tested in `test_forget_just_said.py`). The kept rows note and the count never contradict each other.
`NUMBERS_LEFT_NOTE` and `UNKEPT_CLAIM_NOTE` did, over a row the message asked to keep; both are
fixed below. A store failure after the delete counted nothing; its result now says how many
rows were deleted and sets `ToolResult.forgot` (`failed_during`, `forget_results.py`, tested in
`test_forget_count_note.py`). `Amintirea a fost ștearsă.` named the removal in a form the reader
lacked, so a second, Romanian count note followed it (below). A forget turn stores no exchange
row, so none of these notes reaches memory; they stay in the chat's transcript.

## A row the message asked to keep, 2026-11-09

`NUMBERS_LEFT_NOTE` asks the person to forget the number itself, so the count behind it
(`_holding`) leaves out a row that `asks_to_keep` reads a keep clause of the message naming, and
every row when that clause holds a word for all or the rest (`everything`, `rest`, `tout`,
`reste`). A kept row the message did not ask to keep is still counted, so the note shows (tests in
`test_forget_keep_numbers_left.py`). Of 173 backticked strings in `docs/readings/` holding a forget
verb, the reader reads a keep in 21: 8 are prose a backtick pair split, 11 are real keep requests,
and 2 are the forms the keep reader is recorded as declining
([forget-keep-clause.md](forget-keep-clause.md)), `Forget 7319, no need to keep the shed one.` and
`Vergiss 7319 und behalte den vom Schuppen auch nicht.`, whose card lists the kept row. One live
turn on the rebuilt stack brain at 06:40 (SM clock 0.57 of its maximum), over a bike row and a shed
row stored by two seed turns, `Forget my bike lock code 7319, keep the shed one.` with the card
approved: the card listed the bike row and kept the shed row, the bike row was deleted, and the
reply `I've forgotten your bike lock code.` ended with no note (`live.jsonl`). Script
`replay1091.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot15/`.

## A reply that kept the row the forget kept, 2026-11-09

`UNKEPT_CLAIM_NOTE` said nothing was kept after `Done, I've forgotten your bike lock code and kept
the shed one.`, a correct reply. The forget tool now reports every row a call kept, on a card or
not (`ToolResult.spared`, kept in the handoff record), and the note is skipped when every keep
claim of the reply is `kept` or `keep` and names a word of such a row (`names_spared`,
`memory_claim.py`). A claim with any other verb, or naming anything else, keeps the note (tests in
`test_forget_spared_claim.py`). Of 9 backticked strings in `docs/readings/` that `claims_kept`
reads, replayed with the shed, padlock and gym rows as kept rows, `names_spared` reads only that
reply. Script `replay1090.py` in the slot directory above.

## Romanian removal forms, 2026-11-09

`_REMOVED` now reads the feminine and plural forms `ștearsă`, `șterse`, `uitată`, `uitate` and
`eliminată`, and the cedilla `ş`, so `Amintirea a fost ștearsă.` names the removal. It leaves out
`eliminate`, which is also an English verb. A negated form (`Amintirea nu a fost ștearsă.`), a
question and `I can eliminate it if you want.` still get the count (tests in
`test_forget_count_note.py`). Of 5591 backticked strings in `docs/readings/`, `says_forgotten`
reads 187 as a removal, and the only one the change moves is `Amintirea a fost ștearsă.`.
Script `replay1095.py` in the slot directory above.

## A removal offered under a condition, 2026-11-09

`says_forgotten` read a removal offered under a condition or as an ability as one done, so
`Poate fi șters dacă vrei.`, `Peut être supprimé si tu veux.`, `Kann gelöscht werden, wenn du
willst.` and `I can delete it if you want.` got no count note after a forget that deleted rows. A
removal word now names a removal only when no condition or ability word (`if`, `can`, `could`,
`si`, `peut`, `wenn`, `kann`, `puede`, `podría`, `dacă`, `poate`, `ar putea` and their forms)
comes before it in its sentence; the same words count as a hedge for another memory holding the
number. `Il a été supprimé.`, `Sie wurde gelöscht.` and `Am șters codul, dacă vrei să știi.`, with
the condition after the removal, still name it (tests in `test_numbers_left_note.py`). Replay of
40,146 strings (every distinct string of `docs/readings/` and every quoted string of the brain's
tests) through the reader before and after: `says_forgotten` moved 68, each from a removal to no
removal, so each now gets the note, among them the recorded replies `I can remove it from my memory
if you like.` and `If you previously provided it and would like me to ensure it's removed, please
let me know`. `names_still_held` moved none. Script `replay1099.py` and log `replay1099.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot17/`.

## A removal promised for later, 2026-11-09

`says_forgotten` read a removal the reply promises for later as one done, so `I will delete it.`,
`Il sera supprimé.`, `Es wird gelöscht.`, `Será borrado.` and `Va fi șters.` got no count note
after a forget that deleted rows. A future marker (`will`, `'ll`, `shall`, `going to`, `sera`,
`seront`, `wird`, `werde`, `werden`, `será`, `serán`, `va fi`, `vor fi`, `voi`) before a removal
word in its clause now reads as an offer. `I deleted it and it will not come back.`, `I'll confirm:
I deleted it.` and `Es wurde gelöscht.` still name the removal (tests in
`test_numbers_left_note.py`). Replay of 40,383 strings, built as in the section above, through the
reader before and after: `says_forgotten` moved 9, all of them the new test strings, and
`names_still_held` moved none. Log `replay1101.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot20/`.

## Third audit probe of the handoff record, 2026-11-09

Every field of `TaintLedger` but `forgotten` is a field of `HandoffRecord`, written by
`EscalationSlot`, restored by `taint_ledger()` and named by both `encode_record` and
`decode_record`, so `forget_spared` crosses a model swap, and a record without it reads as none
kept. `forgotten` stays off the record because a recall-tainted turn cannot escalate (ADR-0019
decision 9). The edit result's `was_once` is read in the same round into `made_repeating`, which
the record keeps. Script `probe1.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`.
