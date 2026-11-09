# Readings: a second clause beside a request to remember

Which clauses beside a request to remember keep `set_volume` and `schedule_task` offered, since
a second clause can ask for them in words the reminder and sound readers do not name. The
refusal itself and its rows are in [side-effect-tools-on-remember.md](side-effect-tools-on-remember.md).

## A second clause in another language, 2026-11-07

Once `asks_kept` read requests to remember in French, German, Spanish and Romanian, a request
that also asked for a reminder or the sound in words `_REMINDER` and `_SOUND` do not name lost
the tool (`préviens-moi`, `sag mir Bescheid`, `anunță-mă`, `sube la música`). In those four
languages `unasked_tools` now leaves the tools out only when no comma, semicolon, conjunction or
second sentence follows the request to remember (`asks_kept_alone`, `memory_request.py`), so a
message read wrongly keeps both tools offered. English keeps its word lists. Replayed through the
old and new readers, 2 of the 94 distinct messages recorded that night changed: the two French
requests to remember with `rappelle-moi`, which now keep `set_volume` offered. Of 22,008 distinct
strings in the brain's other test files and the readings records, the only other changes were
two stored exchange texts that quote a French request.

On the stack brain rebuilt at 06:59 (SM clock 0.57 of `clocks.max.sm`), each message below ran
once in a new chat `s14-*` with every card approved:

| Message | Tool calls |
| --- | --- |
| `Souviens-toi que j'ai rendez-vous chez le coiffeur demain et préviens-moi à 15h.` | `schedule_task` ran |
| `Merk dir, dass ich morgen zum Friseur gehe, und sag mir um 15 Uhr Bescheid.` | `list_scheduled`, `schedule_task` ran |
| `Ține minte că mâine merg la frizer și anunță-mă la 15.` | `schedule_task` ran |
| `Recuerda que me gusta así y sube la música.` | `get_volume`, `set_volume`, both failed (no `pactl` for the shell) |

The same requests about a dentist at 9 called no `schedule_task`: the schedule store already held
a German dentist reminder for 9 the next day, and each reply said so. A first Romanian draw
recalled the stored exchange of the two draws before it and said the reminder was already set;
with those rows deleted, the draw above ran `schedule_task`. The French call used `at_time`, a
daily item, and its reply had the daily note appended
([one-time and daily times](schedule-one-time-and-daily.md)). Every `memories` row and schedule
item of the `s14-*` chats was deleted afterwards. Run logs: `flows.log` to `flows4.log`,
`replay.log` and `mut2.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot14/`.

## A second clause in English, and a plain fact in the other four, 2026-11-08

An English request to remember kept its word lists, so a second clause asking for the tool in
other words lost it (`and give me a shout at 9`, `and crank up the music`). `actions_asked`
(`memory_request.py`) now reads each clause beside an English request that opens with a verb and
its object: after a comma, semicolon, colon, `and`, `so`, `then`, `but` or a sentence start, a
first word that is no pronoun, determiner, preposition or auxiliary, then `me` or `us` (also after
`at`, `to`, `for` or `with`), a pronoun or a determiner. A verb with no object and a time is
read too ([below](#a-verb-and-a-time-2026-11-09)).
When `_REMINDER` and `_SOUND` read none of such a clause, `unasked_tools` keeps both tools; a
clause they read (`and remind me the day before`) keeps the old refusal of the other one.
`Remember that the remote is under the couch, and turn the heating down.` now keeps both tools: it
asks for an action, and the rows that measured the refusal
([side-effect-tools-on-remember.md](side-effect-tools-on-remember.md)) hold only plain facts. In the
four other languages `asks_kept_alone` no longer reads a comma before a digit (`72,5 kg`) or a
closing thanks (`Gracias.`, `Merci beaucoup !`) as a second clause. A conjunction inside the fact
(`Retiens que mon vélo est rouge et bleu.`) still keeps both tools offered, since no word list
tells it from a second clause; that cost is on the safe side.

Replayed through the old and new reader, 57 of 13,291 distinct strings changed (the night's turn
records, the brain's test strings and the backticked text of the docs), all from both tools
refused to both kept. Of the 11 in draws or docs, every one asks for an action (a forget, a
delete, a file listing, `crank up the music`). Two fact-only test strings changed, on the safe
side: `Remember that I feed the cat and walk the dog.` and `Remember that my cat, Mia, sleeps on
the sofa.` No string changed toward a refusal.
Reading `me` or `us` after `at`, `to`, `for` or `with` changed none of 13,332 distinct strings.

On the stack brain rebuilt at 02:38 (SM clock 0.57 of `clocks.max.sm`), with the rows written in
`expect.txt` first, each message ran once in a new chat with every card approved:

| Message | Tool calls | Row |
| --- | --- | --- |
| `Remember that I have the dentist tomorrow and give me a shout at 9.` | `schedule_task` ran | passes |
| `Remember that I like it like this and crank up the music.` | `get_volume`, `set_volume`, both failed (no `pactl` for the shell) | passes |
| `Remember that I have the barber on Tuesday. Give me a shout at 8 that morning.` | `schedule_task` ran, a weekly rule | passes |
| `Remember that I am vegetarian and allergic to nuts.` | none | passes |
| `Merke dir: mein Gewicht ist 72,5 kg.` | none | passes |
| `Retiens que mon code est 4512. Merci beaucoup !` | none | passes |

The barber call stored a reminder for every Tuesday, which the message did not ask for
([one-time weekday readings](schedule-one-time-weekday.md)).
Every `memories` row and schedule item of the draws was deleted afterwards. Run logs `draws.log`,
`replay.log` and `mut.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot3/`.

## A verb and a time, 2026-11-09

`actions_asked` also reads a clause whose verb has no object and is followed by `at`, `around`,
`by`, `before` or `in` and a digit (`and ring at 9`, `then call in 5 minutes`), unless the first
word is a day or frequency word (`tomorrow at 10`, `Friday at 3`) or the number is a year from
1900 to 2099 (`married in 2015`). A tool refusal keeps the tool when unsure, so a fact of that
shape (`Remember that I start at 9 and finish at 5.`) keeps both tools, a cost on the safe side.
Near misses written first: `Remember that I swim and run on Mondays.`, `Remember that my sister
sings and dances at weddings.`, `Remember that I was born in 1990 and married in 2015.` and
`Remember my dentist appointment, tomorrow at 10.` keep both tools refused.

Replay over the 28,058 distinct strings of `docs/readings/` (every line, table cell, quoted and
backticked text), of which `asks_kept_alone` reads 355: `unasked_tools` changes for none of them.
`actions_asked` reads one more clause in 61 strings, all prose outside a request to remember, and
one fewer in none. No turn was drawn. Scripts `replay.py` and `replay1037.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot7/`.
