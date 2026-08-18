# A judge that falls back to geometry says nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`JudgeRecallPolicy.select` (`brain/packages/core/src/cortex_core/rerank_judge.py`) has three
fallback sites, and `rerank_judge.py` imports no logger at all, so every one of them is silent.
The pool comes back ranked by geometry and nothing anywhere says the model was asked and did not
answer. The three are not one failure either: an empty pool (a legitimate no-op), an
`InferenceError` (the backend), and `parse_order` returning `None` (a reply that is not the
envelope). Only the first is uninteresting.

This is the same blindness the recap fold just had, and it is worse here for two reasons. The
fold's fallback at least logged a line, so a reader knew a fold had been attempted and rejected;
this one leaves no trace whatever, and a deployment whose judge has never once answered is
indistinguishable from one where it answers every turn. And the judge is the shipped default
recall policy, so it is the path most turns take.

The work is a logger and three call sites, plus the question of what each line carries.
`parse_order` already distinguishes a failure from a refusal (the empty tuple), and that
distinction should survive into the log rather than being flattened back. Whether the stop reason
is worth carrying here as well is a real question rather than a given: the judge decodes under
`ORDER_ENVELOPE`, so a cut envelope fails to parse and is structurally caught, which is the
argument ADR-0005 made for not making this path a consumer. What that argument does not give is
the *reason*, which is the same gap that reopened it for the fold.

## Trail

- 2026-08-18: Opened by the close of [R-277](277-a-cut-fold-reads-like-a-wandering-one.md), which
  gave the fold its diagnosis and found the other `drain_text` caller with a fallback has none.
