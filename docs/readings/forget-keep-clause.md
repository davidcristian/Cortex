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

Three forms keep a row the person asked to forget, each declined 2026-11-09 (unit calls in
`probe2.py`, log beside it in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot14/`). `Forget 7319, no need to keep
the shed one.` keeps the shed row, since a negation that opens a clause asks to keep unless a keep
verb follows it at once. `Vergiss 7319 und behalte den vom Schuppen auch nicht.`, with German
`nicht` after the keep verb, keeps the shed row. `Forget 7319 and do not keep the shed one.` keeps
the bike row, which `Forget 7319.` deletes, because the negated keep names the shed row as the
one to forget; `ne garde pas celui du cabanon non plus`, `no guardes el del shed tampoco` and
`nu păstra nici pe cel de la shed` do the same. Each fails toward keeping, the destructive card's
safe direction: the card lists each kept row under `KEPT_LINE` before the person approves, and a
call that keeps every row closes the reply with the kept rows note. Reading them needs another
widening of the keep and negation parsing in each language, and the build of this reader and its
first widening were each followed by an audit that found more forms it misread.

## Function words of the other languages, 2026-11-09

The common words were English only, so an article, preposition or pronoun of another language
named every row holding it. Over two German rows sharing 7319, `Vergiss 7319, behalte den vom
Schuppen.` kept both through `den`, and `Vergiss den Code von meinem Fahrradschloss, 7319.` listed
the shed row for deletion. Now the articles, prepositions, pronouns, auxiliaries and forget verbs
of French, German, Spanish and Romanian (`_FUNCTION`) name no fact in a message that
`message_language` reads as that language. Each list is read only there, since an English fact
can be named by `den`, `son` or `care`: `Forget the den code 7319.` still names the den row. The
tests are `test_forget_function_words.py`.

Replay: every distinct string of `docs/readings/` holding a forget verb of the five languages
(1,802) went through the old and new reader over twelve rows holding its value (the seven above,
plus German, Spanish and Romanian rows, a French pool locker row and a German dog row), with and
without the calling chat's row. 112 cases changed, all French, German or Romanian, none English.
87 keep more rows, where a function word had named a row of its language. 9 now delete only the
calling chat's newest row, since no function word names a row in `Oublie ce que je viens de te
dire.` or `Vergiss bitte, was ich dir gerade gesagt habe.`, which ask to forget what was just said.
16, from `Uită codul meu 7788.` and `Vergiss den Fahrradcode 7319, alles andere bleibt.`, name no
row by another word and now ask for every row holding the value, as the same message in English
does; before, `meu` or `den` named the one row of that language. The second names its fact only by
the code word `Fahrradcode`, as `Forget the doorcode 7319, keep everything else.` did in English.
No case deletes a row outside those two rules. Script `replay2.py` and log `replay2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot14/`.

The part of a compound code word before its code word (`door` of `doorcode`, `fahrrad` of
`Fahrradcode`, from `code_stem`) now names each row word it starts, so both messages keep every
row they do not name, while `Forget 7319.`, `Forget the code 7319.`, `Forget my passcode 7319.`
and `Forget my pincode 7319.` still ask for every row. A replay of the 1,854 recorded forget
strings through the reader before and after that change moved 9 cases, each holding one of those
two messages and each toward keeping rows. Script `replay2.py` and log `replay-compound.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot16/`.

One live draw on the stack brain rebuilt with this reader, after two chats stored
`Merke dir bitte: Mein Fahrradschloss hat den Code 7319.` and `Merke dir bitte: Der Schuppen hat
auch den Code 7319.`: `Vergiss 7319, behalte aber den vom Schuppen.` drew a `forget_memories`
call with the text `7319`, and the card listed the bike row to delete and the shed row under
`KEPT_LINE`. The card was refused and both rows stayed. The SM clock read 0.57 to 0.63 of
`clocks.max.sm`. Script `live.sh`, records `live.jsonl` and `live.log` in the same directory.

## A call text that holds no value, 2026-11-09

`unnamed` returned no row when the call's text held no value, before it read the keep clause.
With the text `bike lock code`, `Forget my bike lock code, keep the shed one.` listed the shed
row, which holds 7319 and the word `code`, under `Listed because they also hold 7319:`. A row a
keep clause names is now kept whatever the text holds, while `Forget my bike lock code.` and
`Forget my bike lock code, keep it.` still list it (tests in `test_forget_keep_clause.py`).
Replay: the 1,858 recorded forget strings went through the reader before and after over the
twelve rows above, with the texts `7319`, `code`, `lock code` and `number`, with and without the
calling chat's row. 174 cases from 29 strings changed, none with the value as the text, and each
keeps more rows. Script `replay1098.py` and log `replay1098.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot17/`.

## The third audit's probes, 2026-11-09

Unit calls of `unnamed` and `asks_to_keep` over rows that each hold 7319. A row that writes its
fact only as a compound code word gave no row word: `Forget 7319 but keep the Postleitzahl.` and
`Vergiss meinen Türcode, aber behalte die Postleitzahl.` kept nothing, so the kept row also
counted as holding the number and the result and `NUMBERS_LEFT_NOTE` asked to forget the number
itself. A row's own compound now gives its part (`postleit`, `fahrrad`) as a row word, and both
messages keep the row, while `keep my passport` still keeps no `passcode` row and `keep the pin`
no `pincode` row (tests in `test_forget_compound_code.py`). Replay: the 1,874 recorded forget
strings went through the reader before and after over the twelve rows above with the same four
texts, and no case changed.

Still open: a short stem names unrelated words (`passcode` lists a `passport` row, task 1102);
a fact named only by a code word such as `PIN` names no row (task 1103); a message in capitals
reads as English, so German `DEN` names a row (task 1071); and in a mixed German and English
message `den` and `hat` name nothing (task 1104). No moved forget result text changed in the
split into `forget_results.py`, and no exemption names either module. Scripts `probe2.py`,
`probe4.py`, `probe6.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`.

One live turn on the stack brain rebuilt with this reader (`Vergiss meinen Türcode, aber behalte
die Postleitzahl.`, after two chats stored a Postleitzahl row and a Türcode row, both 7319) drew a
call with the text `Türcode`, so the card listed the door row alone and never reached the value
path. The card was denied and both rows stayed, and the reply called the Türcode never stored
(task 1106). The SM clock read 0.57 to 0.58 of its maximum.
