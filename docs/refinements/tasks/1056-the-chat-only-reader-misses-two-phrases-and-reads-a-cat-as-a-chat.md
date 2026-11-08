# The chat-only reader misses two phrases and reads a cat as a chat

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-08

`claims_chat_only` in `chat_only_claim.py` reads a keep verb beside a preposition and a chat noun.
It misses `Lo recordaré mientras dure esta conversación.` and `Je m'en souviendrai jusqu'à la fin
de notre échange.`, so `KEPT_BEYOND_CHAT_NOTE` does not follow either under the global scope. It
also matches replies that keep a fact and only mention a conversation or a cat: `J'ai noté
d'acheter des croquettes pour le chat.`, `Ich habe mir gemerkt, dass Sie im Gespräch mit Ihrem
Chef nervös waren.`, `Recordaré que en la conversación con tu jefe estabas nervioso.` and
`Am reținut ce ai spus în discuția cu Ana.` The note under those is true, since the fact is
stored, but not needed. The safe direction is that the note shows, so the misses matter more.

## What to do

1. Add `mientras dure` and `jusqu'à la fin de` as chat phrases, with near misses first, and replay
   the 749 recorded replies through the old and new reader.

## History

- 2026-11-08: filed by the second audit of the night's changes, from unit probes.
