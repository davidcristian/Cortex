# Readings: a forget whose message asks to keep a fact

How `unnamed` (`forget_unnamed.py`) reads a forget message that names a fact to keep, such as
`Forget my bike lock code 7319, keep the shed padlock one.`, when two stored rows share the call's
value. The rows and the reader before this change are in
[forget-shared-number.md](forget-shared-number.md#audit-probes-of-the-keep-reader-2026-11-09).
The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The reader before, 2026-11-09

Unit calls over a bike lock row and a shed padlock row, both holding 7319, with the call text
7319. The reader read every word of the message as naming a fact to forget, so a word of a clause
asking to keep named that row too, and the card listed it. Each of these kept no row:
`Forget my bike lock code 7319, keep the shed padlock one.`,
`Forget my bike lock code 7319 but not the shed one.` and
`Forget my bike lock code, not the shed one.`. `Forget 7319, keep the shed one.` kept the bike
row and listed the shed row, the reverse of the request.

## The reader now

A clause asks to keep from a keep verb that no negation precedes within two words (`keep`,
`garde`, `behalte`, `guarda`, `păstrează` and their verb forms, never a noun such as `guardian`,
`keepsake`, `conservatory` or `mantenimiento`), or from a negation such as `not`, `n't`, `pas`,
`nicht`, `no` or `nu` that opens the clause or follows `but`, `and`, `do`, `is`, `mais`, `aber`,
`pero` or `dar`, unless a keep verb follows it or a naming word (`the`, `a`, `my`, `your` and the
other possessives) comes before that word, as in `my do not disturb PIN`. The clause ends at its mark or at a forget verb
that no negation precedes, so `don't forget the shed one` keeps the shed row. A word of such a
clause, other than the keep verb, names a fact to keep unless the message also names it outside
one. A matched row naming a fact to keep is listed under `KEPT_LINE` and kept, even beside a word
to forget or a word for all, and even when it holds the value only in its reply. The other words
decide the rest as before.

Near misses, each still reading its words as facts to forget: `the not so new shed padlock code`
(a negation inside a label), `Don't keep my bike lock code 7319.`, `Do not keep ...`,
`Ne garde pas ...`, `I keep forgetting it, forget my bike lock code 7319.` and `keep everything
else` (a keep clause naming no fact). The tests are `test_forget_keep_clause.py`.

## Replay, 2026-11-09

Every distinct string of `docs/readings/` holding a forget verb (1,710) went through the old and
new reader over seven rows holding the string's value (six other chats' rows and one of the
calling chat), with and without the calling chat's row: 16 cases changed, all prose that holds
`keep`, `kept`, `keeps` or `don't`, and no recorded draw message. Each changed case keeps at
least one more row. In two of them, with the calling chat's row, that row is now listed: the words
naming the shed row are in a keep clause, so no word names a fact to forget and the newest row the
chat stored is read as just said, as `Forget it, but keep the shed padlock code.` asks. Script
`replay.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot9/`,
log `replay.log` in the `slot12/` directory beside it. No turn was drawn.

## Second audit probes, 2026-11-09

Unit calls (`probe1.py`, log `probe1.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot13/`)
over a bike row and a second row sharing 7319. A keep verb read in all five languages
(`garde`, `behalte`, `mantén`, `păstrează`), and `don't keep the shed one either` names the
shed row to forget. Two forms read a fact's own name as a request to keep, so the asked row was
kept and the bike row, which the message does not name, was listed: a negation after `do` inside
the name (`Forget my do not disturb PIN 7319.`) and a noun the keep verb list matched (`guardian`,
`keepsake`, `conservatory`, `mantenimiento`). Both now name the fact (tests in
`test_forget_keep_clause.py`). The replay above, run again with the reader before this change
(`replay.log` in the same directory), changed none of 1,766 strings in either condition.

Still open, each filed with its reproduction: `no need to keep the shed one` reads as a keep
([task 1086](../refinements/tasks/1086-a-forget-reads-no-need-to-keep-as-a-request-to-keep.md)); function words such as `den`, `del` or `celui` name rows in the other four languages
([task 1087](../refinements/tasks/1087-function-words-of-the-other-languages-name-rows-in-a-forget.md)); a German negation after the keep verb is not read ([task 1088](../refinements/tasks/1088-a-german-negation-after-the-keep-verb-reads-as-a-keep.md)); and `Forget 7319 and
do not keep the shed one` keeps the bike row, which `Forget 7319.` alone deletes ([task 1096](../refinements/tasks/1096-a-forget-of-a-value-beside-do-not-keep-the-other-one-keeps-the-unnamed-rows.md)).
