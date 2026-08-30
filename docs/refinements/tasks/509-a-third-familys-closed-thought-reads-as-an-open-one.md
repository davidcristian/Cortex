# A closed thought spelled a third way reads here as an open one

**Status:** open, actionable
**Area:** inference
**Trigger:** a pick entering the lineup whose chat template is neither the native family's nor
gemma-4's, which is one `.env` line away and needs no code change to happen.
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-30 by the close of
[R-499](499-the-rendering-predictor-is-asserted-nowhere.md), which moved the rendering rule into a
covered reader and gave it exactly two families' vocabulary to read with.

`scripts/switchtail.py` decides whether a rendered prompt closed its thought by looking for the
last thought marker in the prompt's tail, and it knows two pairs: `<think>`/`</think>` on the
native family and `<|channel>thought`/`<channel|>` on gemma-4. Those are the two families
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s lineup resolves to today. A tail carrying **no**
marker is read as an open thought, deliberately, because that is precisely the failing pick's own
answer to the switch: drop the block, add nothing. The two cases are therefore indistinguishable
from the outside, and the second one is a guess wearing a verdict's clothes.

So a pick whose template closes a thought in a third spelling reads as open, predicts "does
nothing", and is refused as a broken prediction the moment its constrained cell holds. The refusal
prints the tail it read, which is what makes this recoverable by a person in about ten seconds
rather than a mystery; it is still a red aimed at the wrong thing, and the entry it would send a
reader to is the record's eleven rows rather than this module's two pairs.

**Why it was left.** Every pick this repo has ever measured is one of the two families, and a third
one arriving is a lineup decision that comes with a person looking at it. Inventing a third state
now, before there is a template to read, would be designing against an imagined spelling; the
honest version of it needs a real one.

**What would close it.** A third state, `unknown`, entered when the tail carries no marker of any
known pair **and** the two renderings differ in a way that says the template did read the key, and
published as a refusal to predict rather than as a prediction of "does nothing". The awkward part
is exactly the case above: the failing pick's switched tail carries no marker either, so the state
cannot be read off the tail alone and needs something more, most likely the **unswitched** tail as
the comparison (on the failing pick that tail is identical, on a third family it would not be).
That is a rule with two readings behind it rather than eleven, so it wants a real third-family
template to be measured against before it is written.

## Trail

- 2026-08-30: opened by the close of
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md), whose ADR-0005 rendered-tail
  addendum put the rendering rule in `scripts/switchtail.py` with the vocabulary of the two
  families the lineup holds.
