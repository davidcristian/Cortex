# An idiom with a keep verb in another language withholds the turn from memory

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`asks_not_kept` (`memory_request.py`) returns true for any sentence where `_DONT_KEEP_OTHER`
matches a negative imperative of a keep verb at a clause start, and `memory_withheld` then stores
nothing of the turn. Common idioms use the same verbs and are not requests about memory, so the
fact the message states is lost. Each of these returns true:

- `Ne garde pas rancune à Paul, il a déménagé à Lyon.` (do not hold a grudge)
- `Ne le retiens pas contre moi, mais mon nouveau numéro est 0176 5550 1234.`
- `Ne le garde pas pour toi, dis-le à ta sœur.`
- `Behalt das nicht für dich, mein neuer Job beginnt am 1. Dezember.`
- `No guardes rencor, mi jefe se llama Luis.`
- `No lo guardes para ti: mi hermana se casa el 12 de mayo.`
- `Nu ține minte răul, fratele meu se mută la Cluj.`

The English reader returns false for `Don't hold a grudge, my boss is called Luis.` and true for
`Don't keep it to yourself, my sister is getting married on 12 May.`, so the English form of the
last idiom has the same defect. The branch also returns true before the English logic that keeps
the words after a request to remember, so `Merk dir nicht alles, aber merk dir, dass mein Code 4512
ist.` is withheld; the English `Don't note everything, but remember that my code is 4512.` is
withheld too.

## What to do

1. Write the idioms above as tests first, beside `test_memory_request_languages.py`, and replay
   every recorded draw message of the language flows through the old and the new reader.
2. Require the negated verb to name memory or the message: an object such as `ça`, `das`, `esto`,
   `asta` with no complement (`pour toi`, `für dich`, `para ti`, `contre moi`, `rancune`,
   `rencor`, `răul`), or no object at all at the end of the clause.
3. Apply the same clause rule to the English `keep it to yourself`.

## History

- 2026-11-07: filed by the audit of the readers that withhold a request not to keep in four more
  languages.
