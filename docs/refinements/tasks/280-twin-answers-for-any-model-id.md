# The inference twin answers for a model id no deployment serves

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Trigger:** the first test that passes against a model id the wiring it stands for could not have leased, or the second implementation of `InferenceBackend` that has to decide what an unservable id means.

Opened 2026-08-16 by the shared streaming list for `InferenceBackend`
([R-018](018-ports-without-contract-suite.md)), which found it while deciding what belongs in the
list and what does not.

`LlamaCppBackend` refuses a model its `ModelManager` cannot lease: `acquire` raises
`ModelUnavailableError` for anything but the resident id and the adapter re-raises it as
`InferenceError`. `ScriptedInferenceBackend` answers any id at all, recording it in `calls` and
streaming its script. So a core test can watch a turn get a reply for a model production would have
refused, which is the fake being more permissive than the adapter it stands in for, the direction
that hides defects rather than inventing them. It is the same shape the `BodyGateway` list found in
its capture bounds, one layer further out.

**It was left out of the streaming list on purpose, and the reason is a real question rather than
scope.** Which ids a backend serves is `ModelManager`'s subject, not the stream's: this adapter
refuses because its manager does, a backend fronting a router would legitimately serve any id it
recognises and fail on the wire for the rest, and the port's own words are about a completion
"against a loaded model" rather than about who checks. Deciding costs a sentence in the port and,
if the answer is that an implementation owes a refusal, a widening of the twin comparable to
`InMemoryToolRegistry.serve`: something naming the ids it stands for, defaulting to all of them so
the fifty-odd existing scripts keep working.

The cheap half is knowing whether it bites. Nothing in the tree mis-wires a model id today, since
`TurnEngine` reads its own config and the subagent runner reads the roster, so the exposure is a
future wiring change landing green against the twin and failing on the first real turn.
