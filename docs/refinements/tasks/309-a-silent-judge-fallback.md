# A judge that falls back to geometry says nothing

**Status:** landed 2026-08-19
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
- 2026-08-19: Landed as two warnings rather than three, which is the one place this entry's own
  count was overtaken by its argument. `rerank_judge.py` gained a module logger; the
  `InferenceError` and the unreadable reply each log their own line, naming the pool and the `k`,
  and the empty pool logs nothing, a no-op with nothing to judge being the same silence the
  summarizing window keeps when its inner window dropped nothing. The refusal logs nothing either,
  which is how the failure-against-refusal distinction survives: a refusal is the model judging and
  declining, it is already on the recall trail as the `demur` basis, and a line for it would put a
  second ungated per-recall stream beside the one the audit env var deliberately gates. So every
  line from the module means the configured rank did not run. The open question about the stop
  reason is answered the way the fold answered it, since the argument for declining it was about
  the behaviour and the gap is about the reading: the unreadable-reply line carries `capped`, which
  is the only thing separating a rank the bound cut from a model that ended in the wrong shape, and
  `chars`, which separates a model that emitted no assistant text from one whose text was not the
  envelope. It cost no signature at all, the fold having already given `drain_text` its optional
  ledger. Both readings ride the message as well as the record, because the brain's shipped handler
  prints the message alone. Opened
  [R-316](316-a-rank-fallback-cannot-name-its-turn.md), the session the port cannot carry, and
  [R-317](317-shipped-handler-drops-every-field.md), the handler that drops every field this repo
  attaches.
