# A closed thought spelled a third way reads here as an open one

**Status:** landed 2026-08-30
**Area:** inference
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
from the outside, and the second one is a guess reported as a verdict.

So a pick whose template closes a thought with a third pair of markers reads as open, predicts
"does nothing", and is reported as a broken prediction the moment its constrained cell holds. The refusal
prints the tail it read, which is what makes this recoverable by a person in about ten seconds
rather than a mystery; it is still a failure aimed at the wrong thing, and the entry it would send a
reader to is the record's eleven rows rather than this module's two pairs.

**Why it was left.** Every pick this repo has ever measured is one of the two families, and a third
one arriving is a lineup decision that comes with a person looking at it. Inventing a third state
now, before there is a template to read, would be designing against an imagined marker; the
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

- 2026-08-30: closed. Re-derived first, and this entry was right about the reader and wrong about
  what closing it would cost: the comparison it names as the missing input, the unswitched tail,
  is already read on every run and the fact it turns on is already asserted, since the failing
  pick moves a system turn at the **front** and leaves its tail byte identical. So no third-family
  template had to be measured. `scripts/switchtail.py` gained `marked`, and an unmarked switched
  tail that differs from the unswitched one is now reported as a third marker pair rather
  than published as an open thought. Opened
  [R-517](517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md), the case the
  discriminator cannot see. Recorded as the ADR-0005 third-spelling addendum.
