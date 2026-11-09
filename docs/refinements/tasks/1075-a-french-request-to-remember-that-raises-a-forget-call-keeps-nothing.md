# A French request to remember that raises a forget call keeps nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

On a request to remember, a stray `forget_memories` call that matches nothing leaves the turn kept
only when `asks_kept` (`memory_request.py`) reads the message as a request to remember, through
`_unmatched_keep` (`memory_claim.py`). `asks_kept("Le code de mon cadenas de vélo est 5937,
retiens-le.")` is false. In 1 of 8 f1 draws of
[the readings](../../readings/forget-what-was-just-said.md) that first turn called
`forget_memories` with `5937` (its thinking planned a `remember_memory` call, a tool that does not
exist), the call matched nothing, no row was stored, and the reply said "C'est noté, je retiendrai
que le code de votre cadenas de vélo est 5937." with no note. The English requests to remember in
R-952's draws kept the fact in every such draw.

## What to do

1. Write near-miss statements in French, German and Spanish (a question, a negation, "remember"
   naming another person) as tests first, replay every recorded draw message through the old and
   new reader, then decide between widening `asks_kept` and a brain-appended note naming that
   nothing was kept, with rows and a rule written before any draw.

## History

- 2026-11-09: filed from an f1 draw of
  [R-1061](1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md).
