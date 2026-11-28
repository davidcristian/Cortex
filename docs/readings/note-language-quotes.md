# Readings: quoted words in the note language pick

These readings replay `message_language` (`note_language.py`) before and after it leaves quoted
words out of the pick: a word inside `«»`, `»«`, `""`, `“”`, `„“`, `„”`, `‘’` or `''` at a
word's edge counts for no language, and a message whose words outside quotes score nothing is
read whole. The decision is [ADR-0076](../adr/ADR-0076-closing-note-language.md). The forget
readers read with `forget_language`, which still reads every word of the message, so no forget
reader changes.

## Why the Spanish message read as English, 2026-11-28

`Quiero un recordatorio a las 9 para decirle «tak for i går» a Søren.` scores two Spanish words
(`las`, `para`) and two English ones from the quoted Danish (`for`, `i`). It holds no Spanish
letter, so the tie fell to English. The form came from a generator of reminder messages, the
`gen.py` of the `c2` scratch directory of the 2026-11-28 run, where it was 48 of the 3,456 Spanish
messages ([readings](cortex-sampling-broken-words.md#the-replay-and-the-generated-replies)).

A person plausibly types the form. A reminder to say or write a phrase in another language, such
as a greeting for a friend abroad or the text of a card, quotes that phrase, and a message in one
language often quotes the title of a film, a song or a book in another (`Recuérdame ver «The
Office»`). The quoted words then count for the quote's language, and when they score as many as
the message's own words, the note falls to English or to the quote's language.

## The rule and its near misses

Words inside a quote do not count. A straight single quote opens a quote only where no letter or
digit is before it and closes one only where none follows it, and a single quote between two
letters inside the quote stays part of it, so `don't`, `kids'` and `d'appeler` are words and `'I don't
know'` is one quote. When the words outside quotes score nothing, the whole message is read, so a
message that is only a quote keeps the pick it had. The tests, written before the code, in
`test_note_language.py`:

| Message | Pick before | Pick after |
| --- | --- | --- |
| `Quiero un recordatorio a las 9 para decirle «tak for i går» a Søren.` and the same with `""`, `“”` and `''` | English | Spanish |
| `Recuérdame decir 'I don't know' a Ana.` | English | Spanish |
| `Je veux dire « thank you for the help » à Ana.` | English | French |
| `«tak for i går»` | English | English |
| `"Rappelle-moi demain"`, `'Erinnere mich morgen'`, `Dile «gracias por todo» a Ana.` | French, German, Spanish | the same |
| `Remind me to tell Bob "the meeting is at 9".` | English | English |
| `Rappelle-moi de dire « merci pour tout » à Claire.` | French | French |
| `Recuérdame escribir “feliz cumpleaños” en la tarjeta.` | Spanish | Spanish |
| `Don't forget the kids' party, por favor.` | English | English |
| `Remind me 'cause it's the kid's party, gracias y hola.` | English | English |
| `Rappelle-moi d'appeler l'école.` | French | French |

`forget_language` reads the task's message as English before and after. The 97 tests written
before this change pass unchanged.

## The replay, 2026-11-28

Seven sets of distinct strings, each read by both picks before and after the change. A string
holds a quote when the rule finds one in it; of those, the pick reads the words outside quotes
when they score, and the whole string when they do not.

| Set | Strings | Holding a quote | Read outside quotes | Note pick changed | Forget pick changed |
| --- | --- | --- | --- | --- | --- |
| backticked strings of [closing-note-language.md](closing-note-language.md) | 146 | 0 | 0 | 0 | 0 |
| backticked strings of [note-language-letter-tie.md](note-language-letter-tie.md) | 63 | 0 | 0 | 0 | 0 |
| backticked strings of the `forget-*.md` readings | 2,792 | 10 | 6 | 0 | 0 |
| backticked strings of `docs/readings/` | 8,132 | 114 | 39 | 0 | 0 |
| turn messages in the run records under `~/.cache/cortex-run/` | 1,529 | 103 | 103 | 0 | 0 |
| backticked strings of `docs/` | 18,964 | 506 | 60 | 0 | 0 |
| distinct generated reminder messages | 2,160 | 648 | 648 | 6 | 0 |

The six changed strings are the task's form, each read by eye as Spanish and moved from English
to Spanish: `Quiero un recordatorio a las 9 para decirle «tak for i går» a Søren.` and
`Quiero un recordatorio a las 9 para escribir «tak for i går» en la tarjeta de Søren.`, each at
the hours 9, 18 and 7.
Over the generator's 3,456 messages per language, the pick now reads every message of all five
languages in its own language. No quoted string lost a language: a string whose words outside
quotes score nothing is read whole, so its pick is the one it had.

Method: `replay1391.py` (c1's replay with the generated set added), `spans.py`, `misread.py`,
`note_language.old.py` and their logs in `~/.cache/cortex-run/2026-11-28/c4/`.

## The German, Romanian and curly single quotes, 2026-11-28

The rule above first read only `«»`, `""`, `“”` and `''`, so a quote in the marks German and
Romanian write was read as words. `Erinnere mich, „thank you for the help“ zu sagen.` scores two
German words (`mich`, `zu`) and three English ones from the quote, and read as English. The
Romanian `Amintește-mi să-i spun „thank you for the help” lui Ana.` and the Spanish
`Recuérdame decir ‘thank you for the help’ a Ana.` read as English the same way.

The pick now also leaves out the words inside `»«`, inside `„` closed by `“` or `”`, and inside
`‘’`. German closes `„` with the `“` English opens with, so a `„` quote ends at the first `“` or
`”` and never runs past another `„`. `’` is also the typographic apostrophe, so it closes a quote
only where no letter or digit follows it, and one between two letters inside the quote stays
part of it. `‘` opens a quote anywhere: no recorded string below holds it after a letter.
The tests, written before the code, in `test_note_language.py`:

| Message | Pick before | Pick after |
| --- | --- | --- |
| `Erinnere mich, „thank you for the help“ zu sagen.` | English | German |
| `Amintește-mi să-i spun „thank you for the help” lui Ana.` | English | Romanian |
| `Recuérdame decir ‘thank you for the help’ a Ana.`, `Recuérdame decir ‘I don’t know’ a Ana.` | English | Spanish |
| `Erinnere mich an »Thank you for the music« von ABBA.`, `„Thank you“ und „see you“` | English | German |
| `Rappelle-moi d’envoyer ‘thank you for the help’ à l’équipe.` | English | French |
| `„thank you for the help“` | English | English |
| `„Erinnere mich morgen“`, `»Rappelle-moi demain«`, `‘Recuérdame mañana’` | German, French, Spanish | the same |
| `Erinnere mich, „danke für die Hilfe“ zu sagen.`, `Amintește-mi să spun „mulțumesc pentru tot” Anei.` | German, Romanian | the same |
| `Remind me to tell Bob ‘the meeting is at 9’.`, `Remind me to say “danke für alles” to Jürgen.` | English | English |
| `Rappelle-moi d’appeler l’école.` | French | French |
| `Don’t forget the kids’ party, por favor.`, `Remind me ‘cause it’s the kid’s party, gracias y hola.` | English | English |

The 114 tests written before this change pass unchanged.

The replay reads the sets of the first replay with both picks before and after. A new span is a
quote only the new marks find. The last set is every generated message holding a `«»` quote with
that quote written in each of the four new marks.

| Set | Strings | New span | Read outside quotes | Note pick changed | Forget pick changed |
| --- | --- | --- | --- | --- | --- |
| backticked strings of [closing-note-language.md](closing-note-language.md) | 146 | 0 | 0 | 0 | 0 |
| backticked strings of [note-language-letter-tie.md](note-language-letter-tie.md) | 63 | 0 | 0 | 0 | 0 |
| backticked strings of the `forget-*.md` readings | 2,792 | 0 | 0 | 0 | 0 |
| backticked strings of `docs/readings/` | 8,162 | 1 | 1 | 1 | 0 |
| turn messages in the run records under `~/.cache/cortex-run/` | 1,529 | 31 | 31 | 0 | 0 |
| backticked strings of `docs/` | 18,996 | 6 | 4 | 3 | 0 |
| distinct generated reminder messages | 2,160 | 432 | 432 | 0 | 0 |
| generated `«»` messages in the four new marks | 1,728 | 1,728 | 1,728 | 24 | 0 |

The changed strings of the recorded sets are the three messages above, each moved from English
to its own language. The 24 generated ones are the Spanish form of the first replay,
`Quiero un recordatorio a las 9 para decirle ‘tak for i går’ a Søren.` and its card variant at
the three hours, in each new mark, moved from English to Spanish. After the change each of the
1,728 picks equals the pick of the same message in `«»`; before it, 1,704 did. The 432
generated German and Romanian messages already quoted in `„“` and `„”` and keep their picks. No
quoted string lost a language, since a string whose words outside quotes score nothing is still
read whole.

Method: `replay1394.py` (the first replay with the re-marked set added), `spans.py`,
`mutate.py`, `note_language.old.py` and their logs in `~/.cache/cortex-run/2026-11-28/c5/`.
