# A finish reason the port does not carry

**Status:** landed 2026-08-16
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

The `InferenceBackend` port carries no finish reason, so a capped completion looks like a finished
one. Opened 2026-08-11 by the close above, which records the need for it. llama-server ends a capped
completion and reports it on the wire, `finish_reason: "length"`, and the adapter surfaces text,
reasoning, tool calls and a decode cadence and no finish reason at all, so the core cannot tell a
model that stopped from one that was stopped. The deadline half of that close reports itself, being
the core's own bound; the token half does not. On the constrained tool-less path the gap is closed
structurally, since a cut envelope fails to parse and arrives as `MALFORMED`, a correct `ok=False`
with a less useful reason; on the unconstrained path a truncation reads as a short answer. What
holds today instead of a mechanism is the sizing: at roughly five times the longest reply the
shipped tier has been measured writing, what the cap cuts was already not an answer, and this repo's
own precedent for the same problem, `clean_recap`, reads the reply's shape rather than the
transport.
**The trigger is the first capped delegated reply that a reader mistakes for a finished one**, or
the same distinction being wanted by any other caller, the recap fold being the obvious second. The
fix is a port change and is priced as one: a finish reason has to cross `InferenceBackend`, either
as a field on the closing `DecodeCadence` (which already arrives once, whole, at the end of the
completion it describes) or as an event of its own, and every backend including
`EchoInferenceBackend` owes the new answer. `DecodeCadence.tokens` is the near miss worth naming,
since a completion whose decoded count reached the cap did reach the cap: it is an inference rather
than a statement, it says nothing on a build that reports no timings, and the loop absorbs the event
into a `CadenceWatch` whose contract is about rates, so reading it here would be a second consumer
of a value shaped for another question.

## Trail

- 2026-08-11: Opened by the total generation cap's close, which records the need for it: the
  deadline half of that close reports itself, being the core's own bound, and the token half does
  not. Its fix really is a port change and is priced as one.
- 2026-08-16: Landed as the port change it was priced as, ahead of a trigger that cannot fire, a
  truncation read as an answer leaving nothing behind for anyone to notice. `InferenceEvent` gained
  `DecodeStop(reason)` carrying a closed `StopReason` of `FINISHED`, `CAPPED`, `CALLED` or
  `UNKNOWN`, its own event rather than a field on the closing `DecodeCadence` because the two ride
  one llama.cpp chunk while coming off different parts of it, so a build reporting no timings still
  reports why it stopped. The adapter translates `stop`, `length` and `tool_calls`, all three read
  off a live server, and files anything else under `UNKNOWN` rather than dropping it. The loop
  absorbs the event into a `StopLedger` on `ToolLoopContext` exactly as it absorbs the cadence into
  a `CadenceWatch`, and the delegated run is the consumer: a capped completion is now
  `AttemptFailure.TRUNCATED` with a refusal naming the cap, read ahead of the envelope check and
  never re-placed. `EchoInferenceBackend` reports one too, correctly, which is where the cadence's
  own absence stops applying. Proved end to end against the shipped CPU tier: a request capped at
  eight tokens came back `CAPPED` and the shipped attempt turned it into `ok=False`, where the same
  run used to return the cut title as an answer. ([ADR-0005 finish-reason
  addendum](../../adr/ADR-0005-llamacpp-engine.md).) It opened two narrower entries: the diagnosis
  half the recap fold still lacks ([R-277](277-a-cut-fold-reads-like-a-wandering-one.md)) and the
  one path where a capped run is still reported as a dead backend
  ([R-278](278-capped-tool-call-reads-as-a-dead-backend.md)).
