# A forget of a fact never stored asks for the value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, a new chat said "Please forget my passport number." No
passport number was stored. The cortex did not call `forget_memories`; it replied that it had no
way to list its memories and asked for the passport number "to ensure I remove it correctly". So a
person who wants a fact forgotten is asked to type it again, and the reply wrongly says the cortex
cannot see its memories. Row F5 of
[forget-chosen-memories.md](../../readings/forget-chosen-memories.md) fails its pass rule: the reply
does not say that nothing was found to forget.

The tool takes the literal text the memories contain, so the model calls it only when it knows the
value, which it does when a recall brought the fact into the turn and not otherwise.

## What to do

1. Replicate F5 with five draws, and F3 with five draws, before any change, and write the counts
   into the readings.
2. If F5 fails again, decide between a tool description that tells the model to search with a word
   from the request ("passport") when it does not know the value, and a recall of the named subject
   before the reply. Write the pass rule for the change first.

## History

- 2026-10-28: filed from row F5 of the forget rows on the `cortexn9` stack.
