# A finish reason the port does not report

**Status:** done 2026-08-16
**Area:** resource-governance
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

llama-server ends a capped completion and reports it on the wire as `finish_reason: "length"`, but
the adapter surfaced text, reasoning, tool calls and a decode rate and no finish reason, so the core
could not tell a model that stopped from one that was stopped. The deadline half of the generation
cap reports itself, being the core's own bound; the token half did not. On the constrained tool-less
path a cut reply fails to parse and arrives as `MALFORMED`, a correct `ok=False` with a less useful
reason; on the unconstrained path a truncation read as a short answer.

Fixed on 2026-08-16 as the port change it was priced as
([ADR-0048](../../adr/ADR-0048-generation-bounds.md)). `InferenceEvent` gained `DecodeStop(reason)`
with a closed `StopReason` of `FINISHED`, `CAPPED`, `CALLED` or `UNKNOWN`. It is its own event rather
than a field on the closing `DecodeCadence`, because the two come from one llama.cpp chunk but off
different parts of it, so a build reporting no timings still reports why it stopped. The adapter
translates `stop`, `length` and `tool_calls`, all three read off a live server, and files anything
else under `UNKNOWN` rather than dropping it. The loop absorbs the event into a `StopLedger` on
`ToolLoopContext` exactly as it absorbs the rate into a `CadenceWatch`, and the delegated run is the
consumer: a capped completion is now `AttemptFailure.TRUNCATED` with a refusal naming the cap, read
ahead of the envelope check and never re-run. `EchoInferenceBackend` reports one too.

`DecodeCadence.tokens` was the near miss worth naming, since a completion whose decoded count reached
the cap did reach the cap. It is an inference rather than a statement, it says nothing on a build
that reports no timings, and the loop absorbs it into a watch whose contract is about rates.

Proved end to end against the shipped CPU tier: a request capped at eight tokens came back `CAPPED`
and the attempt turned it into `ok=False`, where the same run used to return the cut title as an
answer.

## History

- 2026-08-11: Opened by the total generation cap's close, which records the need for it.
- 2026-08-16: Closed ahead of a trigger that cannot fire, since a truncation read as an answer leaves
  nothing for anyone to notice. It opened two narrower entries: the diagnosis the recap fold still
  lacks ([R-277](277-a-cut-fold-reads-like-a-wandering-one.md)) and the one path where a capped run
  is still reported as a dead backend
  ([R-278](278-capped-tool-call-reads-as-a-dead-backend.md)).
