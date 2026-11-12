# The other-language not found readers read an opinion or a quote as a claim

**Status:** declined 2026-11-12
**Area:** cross-cutting
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)

`claims_not_found_other` (`access_claim_other.py`) and `says_not_stored_other`
(`forget_unfound_other.py`) read a find verb with a negation. Called on each sentence below in the
brain venv on 2026-11-11, both return true (the first column is the not-found reader, the second
the not-stored reader), though no sentence says a file or a fact was not found:

| Sentence | Not found | Not stored |
| --- | --- | --- |
| `Je ne trouve pas ça drôle.` | 1 | 1 |
| `Je ne trouve pas cette idée mauvaise.` | 1 | 1 |
| `Ich finde das nicht gut.` | 0 | 1 |
| `Ich finde nichts Schlimmes daran.` | 1 | 1 |
| `No encuentro las palabras para agradecerte.` | 1 | 1 |
| `Nu găsesc cuvintele potrivite.` | 1 | 1 |
| `Il m'a écrit : « je ne trouve pas mes clés ».` | 1 | 1 |
| `Er schrieb: „Ich habe nichts gefunden.“` | 1 | 1 |
| `Ella dijo: «no encuentro mis llaves».` | 1 | 1 |

Each shows a note that was not needed, the readers' safe side. An opinion (`trouver` or `finden`
with an object and an adjective) and a quote of someone else's words need a reader shape rather
than more excluded words, since `je ne trouve pas votre numéro` is a claim. The phrases saying
what is meant is unclear (`je ne vois pas ce que vous voulez dire`) were excluded the same night.

Both readers act only in narrow turns: `unsearched_files_claim` (`access_claim.py`) after a refused
file call, and `unfound_claim` (`forget_unfound_claim.py`) after a forget that matched nothing
beside one that deleted rows. A replay on 2026-11-11 of 7,452 strings (the backticked spans of
`docs/readings/` and every distinct reply in tonight's proxy log, French, German, Spanish and
Romanian chats included) found no proxy reply matching either reader. Of 6 not found and 11 not
stored matches, all in readings, one is a quote only (a table cell holding `"nicht dauerhaft
gespeichert"`). `je ne trouve pas que` matches the not stored reader and not the not found reader,
which excludes `que` after the verb. Narrowing either reader moves it off its safe side, so a
build should first show such a note reaching a person on a turn that needed none.

## What to do

1. Write the rows above as near misses, beside claims of the same verbs (`Je ne trouve pas votre
   fichier.`, `Ich finde die Datei nicht.`).
2. Decide whether a quoted span (`« »`, `„ “`, `" "`) is read at all, using the quote reader in
   `schedule_quoted.py`, and whether an adjective after the object marks an opinion.
3. Replay `docs/readings/` and the proxy logs through the old and new readers.

## History

- 2026-11-11: filed from the first audit of the other-language readers; reproduced with a unit
  call of each reader.
- 2026-11-11: replayed the readings and the proxy log through both readers, with no proxy
  reply matching; left open.
- 2026-11-12: declined, since each note a false read shows is true on the turn it reaches.
  `UNSEARCHED_FILES_NOTE` says no file was searched and the message asked only to remember, which
  the refused file call alone makes true. `DELETED_UNFOUND_NOTE` says one forget call deleted
  rows and another matched none, which the calls alone make true, and then only that what the
  reply calls not found may be among them. Neither needs rewording. Narrowing would move both
  readers off their safe side for no recorded harm: none of the 14 replies and tool results in
  tonight's proxy log matches either reader.
