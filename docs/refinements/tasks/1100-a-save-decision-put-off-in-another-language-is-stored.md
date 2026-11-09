# A save decision put off in another language is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

`asks_not_kept` in `memory_request.py` reads an English save decision the person puts off
(`I'll tell you later whether to save it`) as a request not to keep, and reads none in French,
German, Spanish or Romanian. Unit calls on 2026-11-09: `Retiens-le pour l'instant, je te dirai plus
tard s'il faut l'enregistrer.`, `Merk es dir erst mal, ich sage dir später, ob du es speichern
sollst.`, `Recuérdalo por ahora, te diré luego si debes guardarlo.` and `Ține minte deocamdată, îți
spun mai târziu dacă să-l salvezi.` each return `asks_kept` true and `asks_not_kept` false, so the
exchange is stored while the person put off the decision to save it
([readings](../../readings/chat-only-limit-words.md#second-audit-probes-of-keep-it-in-mind-2026-11-09)).

## What to do

A do-not-keep reader withholds when unsure. Write near misses in each language first (`je te dirai
plus tard quoi faire`, `ich sage dir später, ob ich mich erinnere`, a question asking whether it was
saved), then read a first person `tell you`, `let you know` or `decide` verb with `si`, `ob`,
`dacă` before a keep verb as a request not to keep, and replay every recorded draw message.

## History

- 2026-11-09: filed by the fix of the English form, from unit probes (`probe-later.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot16/`).
