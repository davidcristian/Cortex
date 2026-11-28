# Readings: a tie in the note language broken by letters

These readings replay `message_language` (`note_language.py`) before and after it breaks a tie
by letters: of the languages tied for the most words, the one whose own letters the message holds
most is picked, and a tie the letters do not break stays English. The last section replays a second
change, in which the letters also decide a lone word that two languages write. The decision is
[ADR-0076](../adr/ADR-0076-closing-note-language.md). The forget readers read with
`forget_language`, the pick without letters, so no forget reader changes.

## Why the French message read as English, 2026-11-27

`Retiens que ce code est périmé.` scores one French word (`est`) and one Romanian word (`ce`), and
a tie fell to English. `Retiens que mon adresse est périmée.` and `Oublie mon code.` score two
French words and none of another list. Taking `ce` out of the Romanian list would also fix the
message, but `Uită ce am spus.` would then tie Romanian `uită` with English `am` and lose its
Romanian note, so the lists stay as they are.

## The replay, 2026-11-27

Three sets of distinct strings, each read by the pick before and after the change
(`replay1375.py`, `replay1375c.log` and the earlier `note_language.old.py` in
`~/.cache/cortex-run/2026-11-27/c6/`):

| Set | Strings | Pick changed | Forget pick changed |
| --- | --- | --- | --- |
| backticked strings of [closing-note-language.md](closing-note-language.md) | 146 | 0 | 0 |
| backticked strings of `docs/readings/` | 7,956 | 10 | 0 |
| turn messages in the run records under `~/.cache/cortex-run/` | 1,440 | 2 | 0 |

The 749 messages of the first replays are no longer on disk. Every changed string, read by eye:

| Before | After | String | Read by eye |
| --- | --- | --- | --- |
| English | French | `Retiens que ce code est périmé.` | French |
| English | French | `règle un rappel pour 2h du matin` | French |
| English | Romanian | `Am uitat să te întreb` | Romanian |
| English | Romanian | `Am șters codul, dacă vrei să știi.` | Romanian |
| English | Romanian | `Am programat un întunecire pentru astăzi la orele 17:30 [...]` | Romanian |
| English | Romanian | `el nu reține` | Romanian |
| English | Romanian | `nu am găsit` | Romanian |
| English | German | `Der Hund des Benutzers heißt Bello.` | German |
| English | Spanish | a recorded exchange opening `User: Recuerda que soy vegetariano.` | Spanish |
| English | Spanish | `Guarda o meu número 0721 555 019.` | Portuguese |
| English | Spanish | `Meu código mudou para 4862.` | Portuguese |

Nine of the eleven moved from English to the language they are written in. The two Portuguese
strings tie Spanish with Romanian (`guarda` or `para` against `meu`) and get the Spanish note in
place of the English one; Portuguese is none of the five languages. The one changed string with a
recorded reply, the Spanish exchange, now matches its reply's language, so the rule of the first
replay (no message given a language other than its reply's) still passes. In the unit tests
`Fiesta mañana at 9` moved from English to Spanish.

## The live draw, 2026-11-27

The brain built from the tree with the change, project `cortexn32`, the model host on compose
defaults (the argv read off the container: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context 16,384,
the default cache type, the MTP drafter at a draft length of 3, no reasoning flag, build b12375).
Each label seeds one old row from its own new chat, put back before every draw; each draw is one
turn in a new chat, every card approved. All three messages tie under `forget_language`.

**The rule, written before the first launch.** It passes when every closing note of every draw is
in the message's language and the seeded row is present and unchanged after every draw. No
closing note on any draw is a null result for the language half.

| label | seed | message | draws with a note | notes in the message's language | seeded row unchanged |
| --- | --- | --- | --- | --- | --- |
| q1 | `Retiens que mon code est 5528.` | `Retiens que ce code est périmé.` | 2 of 8 | 2 of 2 | 8 of 8 |
| q2 | the same | `Retiens que ce numéro est faux.` | 0 of 8 | none | 8 of 8 |
| q3 | `Ține minte că codul meu este 5528.` | `Reține că am schimbat codul.` | 0 of 8 | none | 8 of 8 |

The rule passes, and its language half rests on q1 alone: both notes are the French
`REFUSED_HELD_NOTES` text, after a forget call naming `5528` that `FORGET_UNREQUESTED` refused.
No draw showed a card. On q2, 4 of 8 draws made the same call and `FORGET_UNSAID` refused it.
The turn kept no call text for that refusal when these draws were taken, so those replies say the
number was noted as wrong while the row still holds it, with no note. It keeps the text now, and
the q2 call replayed through the tree ends with the French note
(`test_forget_refused_held.py`).
On q3 the cortex made no forget call and asked for the new code. Logs and notes:
`~/.cache/cortex-run/2026-11-27/a2/`.

## A lone `ce`, 2026-11-28

`Retiens bien ce code périmé.`, `Retiens que ce code a changé.` and `Note ce code: 5530.` count
one word, the Romanian `ce`: `retiens` and `changé` are in no list, `bien` is Spanish too, and
`que`, `note` and `code` are words of two of the five languages. Each read as Romanian alone, with
no tie for the letters to break.

The first rule tried let the letters decide whenever one language scores a single word, between
it and every language whose letters the message holds. It read both accented messages as
English, because `é` is a French and a Spanish letter, and it moved two unit test messages on a
name's letters beside one English word: `Call José María García López tomorrow` to Spanish and
`Book the Champs-Élysées crème brûlée place` to French. The rule built is narrower: the letters
decide only between the language that scored and a language that also writes its one word
(`_ALSO_WRITTEN`, French for `ce`), and a letter tie keeps the language that scored.
`Note ce code: 5530.` holds no letter outside ASCII and reads the way `Ce faci?` does, so it keeps
the Romanian note ([R-1386](../refinements/tasks/1386-a-french-message-with-no-accent-whose-one-word-is-ce-gets-romanian-notes.md)).

Six sets of distinct strings, each read by both picks before and after the change
(`replay1380.py`, `replay1380.log` and `note_language.old.py` in
`~/.cache/cortex-run/2026-11-28/c1/`):

| Set | Strings | Note pick changed | Forget pick changed |
| --- | --- | --- | --- |
| backticked strings of [closing-note-language.md](closing-note-language.md) | 146 | 0 | 0 |
| backticked strings of this file | 63 | 3 | 0 |
| backticked strings of the `forget-*.md` readings | 2,780 | 0 | 0 |
| backticked strings of `docs/readings/` | 8,042 | 3 | 0 |
| turn messages in the run records under `~/.cache/cortex-run/` | 1,467 | 0 | 0 |
| backticked strings of `docs/` | 18,872 | 3 | 0 |

Every changed string, read by eye:

| Before | After | String | Read by eye |
| --- | --- | --- | --- |
| Romanian | French | `Retiens bien ce code périmé.` | French |
| Romanian | French | `Retiens que ce code a changé.` | French |
| Romanian | French | `Ce face José?` | Romanian |

The two French messages are the task's own. `Ce face José?` is quoted only here and in the
decision record, as the cost of the rule: a Romanian message whose one counted word is `ce`
beside a name holding a French letter. No recorded run message changed, and no string in any set
changed its `forget_language` pick.
