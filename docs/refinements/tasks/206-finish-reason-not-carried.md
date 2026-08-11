# A finish reason the port does not carry

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** The first capped delegated reply that a reader mistakes for a finished one.

A finish reason the port does not carry, so a capped completion looks like a finished one.
Opened 2026-08-11 by the close above, which is honest about needing it.
llama-server ends a capped completion and says so on the wire, `finish_reason: "length"`, and the
adapter surfaces text, reasoning, tool calls and a decode cadence and no finish reason at all, so
the core cannot tell a model that stopped from one that was stopped. The deadline half of that
close reports itself, being the core's own bound; the token half does not. On the constrained
tool-less path the gap is closed structurally, since a cut envelope fails to parse and arrives as
`MALFORMED`, an honest `ok=False` with a less useful reason; on the unconstrained path a
truncation reads as a short answer. What holds today instead of a mechanism is the sizing: at
roughly five times the longest reply the shipped tier has been measured writing, what the cap
cuts was already not an answer, and this repo's own precedent for the same problem, `clean_recap`,
reads the reply's shape rather than the transport. **The trigger is the first capped delegated
reply that a reader mistakes for a finished one**, or the same distinction being wanted by any
other caller, the recap fold being the obvious second. The fix is a port change and is priced as
one: a finish reason has to cross `InferenceBackend`, either as a field on the closing
`DecodeCadence` (which already arrives once, whole, at the end of the completion it describes) or
as an event of its own, and every backend including `EchoInferenceBackend` owes the new answer.
`DecodeCadence.tokens` is the near miss worth naming, since a completion whose decoded count
reached the cap did reach the cap: it is an inference rather than a statement, it is silent on a
build that reports no timings, and the loop absorbs the event into a `CadenceWatch` whose
contract is about rates, so reading it here would be a second consumer of a value shaped for
another question.

## Trail

- 2026-08-11: Opened by the total generation cap's close, which is honest about needing it: the
  deadline half of that close reports itself, being the core's own bound, and the token half does
  not. Its fix really is a port change and is priced as one.
