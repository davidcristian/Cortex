# A French request not to keep with an elided ne is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`_DONT_KEEP_OTHER` in `memory_request.py` reads a French negative imperative only as `ne`, then an
optional object pronoun, then the verb. French writes `ne` as `n'` before a vowel, so the verbs
`enregistre` and `enregistrez` on its own list never match in the form a person writes, and
`asks_not_kept` is `False`, so the turn is stored.

Reproduction, unit level (`SCRATCH/slot20/probe_readers.py`): `asks_not_kept` is `False` for
"N'enregistre pas ça." and "N'enregistre pas mon code 7731.", and `True` for "Ne retiens pas ça,
s'il te plaît.".

## What to do

1. Write near misses first: "Je n'enregistre pas les appels" and "Il n'enregistre rien" state a
   fact and must stay unread.
2. Read `n'` or `n’` at a clause start before `enregistre`, `enregistrez`, and the other
   vowel verbs a person uses for this (`écris`, `écrivez`), then replay every recorded draw
   message through the old and new reader, as `SCRATCH/slot16/replay.py` did.

## History

- 2026-11-07: filed by the third audit of the night's changes.
