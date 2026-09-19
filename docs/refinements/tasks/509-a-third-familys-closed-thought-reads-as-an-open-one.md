# A closed thought written a third way reads here as an open one

**Status:** done 2026-08-30
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

`scripts/switchtail.py` decides whether a rendered prompt closed its thought by looking for the last
thought marker in the prompt's tail, and it knows two pairs: `<think>`/`</think>` on the native
family and `<|channel>thought`/`<channel|>` on gemma-4. Those are the two families
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s lineup resolves to today. A tail with no marker is
read as an open thought, deliberately, because that is the failing pick's own response to the
switch: drop the block, add nothing. The two cases are indistinguishable from the outside, and the
second is a guess reported as a result.

So a pick whose template closes a thought with a third pair of markers reads as open, predicts "does
nothing", and is reported as a broken prediction the moment its constrained cell works. The refusal
prints the tail it read, which makes this recoverable by a person in about ten seconds.

## History

- 2026-08-30: opened by the close of
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md), whose ADR-0050 put the rendering rule
  in `scripts/switchtail.py` with the vocabulary of the two families the lineup has.
- 2026-08-30: closed. Checked first, and this entry was right about the reader and wrong about what
  closing it would cost: the comparison it names as the missing input, the unswitched tail, is
  already read on every run and the fact it turns on is already asserted, since the failing pick
  moves a system turn at the front and leaves its tail byte identical. So no third-family template
  had to be measured. `scripts/switchtail.py` gained `marked`, and an unmarked switched tail that
  differs from the unswitched one is now reported as a third marker pair rather than published as an
  open thought. Opened
  [R-517](517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md), the case the
  test cannot see. Recorded as ADR-0050.
