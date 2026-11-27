# Readings: a tie in the note language broken by letters

These readings replay `message_language` (`note_language.py`) before and after it breaks a tie
by letters: of the languages tied for the most words, the one whose own letters the message holds
most is picked, and a tie the letters do not break stays English. The decision is
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
No draw showed a card. On q2, 4 of 8 draws made the same call and `FORGET_UNSAID` refused it, a
refusal the note does not cover, so those replies say the number was noted as wrong while the
row still holds it
([R-1379](../refinements/tasks/1379-a-forget-call-refused-for-words-a-request-to-remember-lacks-gets-no-held-note.md)).
On q3 the cortex made no forget call and asked for the new code. Logs and notes:
`~/.cache/cortex-run/2026-11-27/a2/`.
