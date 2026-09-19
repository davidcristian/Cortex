# A judge that falls back to geometry logs nothing

**Status:** done 2026-08-19
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`JudgeRecallPolicy.select` (`brain/packages/core/src/cortex_core/rerank_judge.py`) has three
fallback paths, and the module imported no logger, so all three were silent. The pool came back
ranked by geometry and nothing recorded that the model had been asked and had not answered. The
three are different failures: an empty pool (a legitimate no-op), an `InferenceError` from the
backend, and `parse_order` returning `None` for a reply that is not the expected envelope.

The judge is the shipped default recall policy, so it is the path most turns take, and a deployment
whose judge has never once answered looked the same as one where it answers every turn.

The work is a logger and the call sites, plus deciding what each line contains. `parse_order`
already separates a failure from a refusal (the empty tuple), and that difference should reach the
log.

## History

- 2026-08-18: Opened by the close of [R-277](277-a-cut-fold-reads-like-a-wandering-one.md), which
  gave the recap fold its diagnosis and found the other `drain_text` caller with a fallback had
  none.
- 2026-08-19: Fixed as two warnings rather than three. `rerank_judge.py` gained a module logger;
  the `InferenceError` and the unreadable reply each log a line naming the pool and the `k`. An
  empty pool logs nothing, there being nothing to judge. A refusal logs nothing either: it is the
  model judging and declining, it is already on the recall trail as the `demur` basis, and a line
  for it would add a second per-recall stream beside the one the audit environment variable
  controls. So every line from the module means the configured rank did not run. The
  unreadable-reply line includes `capped`, which separates a rank the bound cut short from a model
  that ended in the wrong form, and `chars`, which separates a model that emitted no assistant text
  from one whose text was not the envelope. It cost no signature change, since the fold had already
  given `drain_text` its optional record. Both values go into the message as well as the structured
  record, because the brain's shipped handler prints the message alone. Opened
  [R-316](316-a-rank-fallback-cannot-name-its-turn.md), the session the port cannot pass through,
  and [R-317](317-shipped-handler-drops-every-field.md), the handler that drops every field this
  repo attaches.
