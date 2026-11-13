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
`keepsake`, `conservatory` or `mantenimiento`), from a word for except or `but` after a word for
all ([forget-keep-except.md](forget-keep-except.md)), or from a negation such as `not`, `n't`, `pas`,
`nicht`, `no` or `nu` that opens the clause or follows `but`, `and`, `do`, `is`, `mais`, `aber`,
`pero` or `dar`, unless a keep verb follows it or a naming word (`the`, `a`, `my`, `your` and the
other possessives) comes before that word, as in `my do not disturb PIN`. The clause ends at its mark or at a forget verb
that no negation precedes, so `don't forget the shed one` keeps the shed row. A word of such a
clause, other than the keep verb, names a fact to keep unless the message also names it outside
one. A matched row naming a fact to keep is listed under `KEPT_LINE` and kept, even beside a word
to forget or a word for all, and even when it holds the value only in its reply. Beside such a
clause, a matched row is deleted only when a whole word outside it names the row
([below](#whole-words-to-forget-beside-a-keep-clause-2026-11-09)).

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

The probes also found a short stem naming unrelated words, a fact named only by a code word such
as `PIN` naming no row, and a mixed German and English message whose `den` and `hat` named
nothing, each read by the shape below. A message in capitals with one German list word reads as
English, and its forget verb now adds a German reading (the last section). No moved forget result text
changed in the split into `forget_results.py`, and no exemption names either module. Scripts `probe2.py`,
`probe4.py`, `probe6.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`.

One live turn on the stack brain rebuilt with this reader (`Vergiss meinen Türcode, aber behalte
die Postleitzahl.`, after two chats stored a Postleitzahl row and a Türcode row, both 7319) drew a
call with the text `Türcode`, so the card listed the door row alone and never reached the value
path. The card was denied and both rows stayed, and the reply called the Türcode never stored; a
reply after a denied forget card ends with `DECLINED_FORGET_NOTE`. The SM clock read 0.57 to 0.58 of its maximum.

## Whole words to forget beside a keep clause, 2026-11-09

The keep reader was widened six times in one night, and each audit found more word list misses,
each one listing a row the person asked to keep. Its shape now makes a miss keep the row. When a
clause asks to keep, a matched row is deleted only when a whole word of the rest of the message
names it and no word of the clause does. Every other row is kept, on the card under `KEPT_LINE`
or, when all are kept, in the kept rows note. The part of a compound code word (`code_stem`) names
only the same whole word or a row's same compound, so `passcode` names no `passport` row,
`carcode` no `card` row, `doorcode` no `doorbell` row and `Fahrradcode` no `Fahrradschloss` row.
A code word for one kind of value (`kind_word` in `memory_values.py`: `PIN`, `password`,
`Postleitzahl`, never `code` or `number`) names a row holding the same word, outside the clause
only when no other word names one, so `Forget my card PIN 7319, keep everything else.` lists no
phone `PIN` row. A word of the clause keeps the row it names whatever language the function word
list picked. Without a keep clause, a compound code word naming no row keeps every row rather
than asking for every row. The tests are `test_forget_keep_whole_words.py`.

Replay: the 1,888 recorded forget strings went through the reader before and after over seventeen
rows (the twelve above, plus a passport, card `PIN`, doorbell, Postleitzahl and den row, each
holding the string's value) with the four texts above, with and without the calling chat's row.
1,930 cases from 286 strings changed. None keeps fewer rows, and `asks_to_keep` turned no row from
kept to not kept. 1,922 are beside a keep clause. In `Forget 7319, keep the shed one.`, `Vergiss
7319, behalte aber den vom Schuppen.` and `Forget it, but keep the shed padlock code.` no word
outside the clause names a row, so every row is now kept and the reply ends with the kept rows
note, where before the other rows, or the newest row the calling chat stored, were deleted. With
the text `code`, `Forget my bike lock code 7319, keep everything else.` listed every row and now
lists the bike rows alone. The other 8 are `Forget my passcode 7319.` and `Bitte vergiss meine
Passnummer X4821937.`, which listed the passport row by its start and now keep every row. No draw
message of the n1, n1v, x6, x7 or f1 flows changed, and neither did `Forget 7319.`. Script
`replay.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot19/`.

One live turn on the stack brain rebuilt with this reader, after two chats stored `Remember that
my card PIN is 7319.` and `Remember that my door code is also 7319.`: `Forget my PIN 7319, keep
everything else.` drew a call with the text `7319`, and the card listed the card row alone, with
the door row under `KEPT_LINE`. The card was refused and both rows stayed. The SM clock read 0.57
to 0.59 of its maximum. Script `live.sh`, records `live.jsonl` and `live.log` in the same
directory.

## A forget verb of another language, 2026-11-10

A message in capitals is read by its words of four letters or more, and only when two are in one
language's list, so `VERGISS DEN TÜRCODE 7319, ALLES ANDERE BLEIBT.` read as English, its `DEN`
named a fact, and the card listed the den alarm row beside the door row. The forget reader now
also reads a message in each language whose forget verb it uses (`readings` in
`forget_languages.py`: `vergiss`, `lösche`, `oublie`, `olvida`, `uită` and the other forms), with
that language's function words, and keeps a row any reading keeps. A reading only adds kept rows,
so a misread keeps the row. `VERGISS DEN CODE 7319.` still lists only the den row, which the
English reading names, where the lowercase message lists every row holding 7319. An English verb
adds no reading, so `FORGET THE DEN ALARM CODE 7319, KEEP THE REST.`, `FORGET MY SON'S CODE 7319,
KEEP THE REST.` and `Jürgen: forget den code 7319, keep the rest` still list the den or son row.
The note picker is unchanged. The tests are `test_forget_verb_language.py`.

Replay: the 1,983 distinct recorded forget strings and each in capitals (3,932 strings) went
through the reader before and after over twenty-one rows holding the string's value (the seventeen
above, plus a German Türcode row and the hat, care home and son rows), with the four texts above,
with and without the calling chat's row. 170 cases from 40 strings changed. None keeps fewer rows,
and `asks_to_keep` changed for no row. 31 of the 40 have no lowercase letter, each a recorded
French or German message in capitals such as `OUBLIE LE CODE DE MON CASIER À LA PISCINE.`; the
other 9 are readings sentences quoting a French or German forget beside English prose.
Script `replay.py` and log `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot4/`.

## A keep verb after the words it keeps, 2026-11-14

A clause read from its keep verb onward left the words before the verb to forget, so beside a
card and a phone ending `4242`, `Vergiss die Karte 4242, mein Handy bleibt.`, `das Handy behalte
ich.` and `Forget the card 4242, my phone I keep.` listed and deleted the phone. A keep verb
can follow the words naming what it keeps: `bleibt` follows its subject, and `mon téléphone je le
garde` and `telefonul îl păstrez` put the object first. A keep verb now also keeps the words before it
in its clause, back to a forget verb or a joining word (`and`, `or`, `but`, `yet`, `et`, `ou`,
`mais`, `und`, `oder`, `aber`, `y`, `o`, `pero`, `și`, `sau`, `dar`), so `Vergiss die Karte 4242
aber mein Handy bleibt.` keeps the phone and deletes the card, and `Forget the card 4242, the
locker and my phone I keep.` deletes the locker code. The keep words are unchanged. In a clause
holding a forget verb and no joining word the keep verb takes every word after the forget verb, so
`Vergiss die Karte 4242 mein Handy bleibt.` keeps both rows: a misread keeps a row. `Vergiss die
Karte 4242, mein Handy vergiss auch.` still deletes the phone (`test_forget_side_clause.py`).

Replay: 5,206 distinct test, readings, task and recorded strings, over 27 sets of fourteen stored
card, phone and code exchanges in four languages, went through the card before and after (140,562
cases). No row is newly deleted. 204 rows are newly kept, from 16 strings: the phone of 14 strings
with a keep verb after the phone's words, such as those above, the card too beside the two of them
with no joining word, and the card of the reply text `... only your card number (4111 1111 1111
4242) is kept in my memory ...`, which says to keep it, and of its quote here. Script
`replay.py`, logs `replay2-old.jsonl`, `replay2-new.jsonl` and `compare2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/11450320-079c-401d-9f26-43a763a369b6/scratchpad/slot4/`.

Draws on a brain of the fix (cortex tier, `draw.log` in the folder above): in two draws each of the
German and English forms above the model called with the whole card number or made no call, so the
phone stayed and the fix was not reached. `Forget what I just told you`, `Forget 4242.` and `my
phone as well` beside a forget listed what they listed before.

A word for except, and `but` after a word for all, are in [forget-keep-except.md](forget-keep-except.md).
