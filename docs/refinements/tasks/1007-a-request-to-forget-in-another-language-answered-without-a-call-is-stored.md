# A request to forget in another language answered without a call is stored

**Status:** done 2026-11-08
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`memory_withheld` (`memory_claim.py`) keeps a turn out of memory when its message `asks_not_kept`
reads, because the model can answer a forget request without calling `forget_memories` and the
message names the value. `asks_not_kept` (`memory_request.py`) reads `forget`, `erase` and
`unlearn` in English only, and in French, German, Spanish and Romanian only a negative imperative of
a keep verb. On 2026-11-07 it returned false for `Oublie le code de mon casier 7731.`,
`Vergiss meinen Code 4402.`, `Olvida mi PIN 1234.`, `Uită codul meu 7788.` and
`Efface mon code 7731 de ta mémoire.`, and true for `Forget my locker code 7731.`. A turn on one of
those messages that makes no forget call is therefore stored with the value it asked to forget.
This is read from the code; no draw has shown such a turn yet.

Reproduction: send `Oublie le code de mon casier 7731.` in new chats until a draw makes no
`forget_memories` call, then read `memories` for that chat's `session_id`: the row is there.

## What to do

1. Write near-miss statements first as tests in each language: a habit (`j'oublie toujours mes
   clés`, `ich vergesse das immer`), a past report (`j'ai oublié`, `olvidé`, `am uitat`), a
   question (`tu as oublié ?`) and a reminder (`n'oublie pas de`, `nu uita să`). Then the
   imperatives (`oublie`, `efface`, `vergiss`, `lösche`, `olvida`, `borra`, `uită`, `șterge`) at
   a clause start, read the same way the negative imperatives are.
2. `asks_not_kept` decides whether a turn is stored, so a statement read wrongly loses a fact the
   person asked to keep: replay every recorded message through the old and new reader, and list
   each change before shipping.

## History

- 2026-11-07: filed from the requests to remember in four more languages on the shared stack.
- 2026-11-07: drew the French, German, Spanish and Romanian messages above once each on the
  rebuilt stack brain with the card denied: all four called `forget_memories` (three matched
  nothing, one was declined) and none was stored, so the path with no call occurred in 0 of 4.
- 2026-11-08: done. `asks_not_kept` reads an imperative to forget or erase at a clause start in the
  four languages, and 23 near misses (habits, past reports, questions, `n'oublie pas`, `oublie pas`,
  `vergiss es nicht`, `uită-te`) stay unread. Of 13,259 replayed strings, 31 became requests not to
  keep, each a forget request; a third person statement after `et` or `y` is withheld
  ([readings](../../readings/claim-reader-replays.md#a-forget-in-four-more-languages-and-an-english-keep-idiom-2026-11-08)).
  Filed [R-1034](1034-a-third-person-statement-after-a-conjunction-reads-as-a-request-to-forget.md)
  for that statement and
  [R-1035](1035-a-request-to-forget-in-romanian-searched-the-files-and-made-no-forget-call.md) for
  a Romanian draw that made no forget call.
