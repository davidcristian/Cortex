# The inference twin answers for a model id no deployment serves

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)

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

## Trail

- 2026-08-17: Both halves of the claim re-derived from the code before anything was written, and
  both held. Asked for `'scribe'`, `LlamaCppBackend` over a one-resident manager raised
  `InferenceError: model manager could not lease 'scribe' for inference` before any request left the
  process, while the twin streamed its whole script and recorded the id. Landed as the entry
  described it: the port now says an implementation answers only for the ids it serves and leaves
  who checks and when open, the twin takes `serves=[...]` and refuses anything outside it after
  recording the call, and the shared streaming list gained a ninth check that needs no fifth
  builder, since every world it already arranges stands for a deployment serving `CONTRACT_MODEL`
  alone. Written up at the [ADR-0001 served-model addendum](../../adr/ADR-0001-architecture.md),
  which also carries the two mutations that prove the check reachable from each leg: the twin's
  refusal made a no-op fails the check on the scripted leg alone (1 of 2625), and a manager that
  stops checking residency fails it on the adapter leg (3 of 2625, the other two being that
  manager's own test and the adapter's wrapping test). The entry's own count of "fifty-odd existing
  scripts" was the one thing it got wrong: `ScriptedInferenceBackend` has exactly three call sites,
  all of them contract fixtures, and the scripts that ignore a model id are the hand-rolled backends
  in `core/tests` and `orchestrator/tests`. That, and the opt-in default the widening kept, is
  [R-298](298-served-ids-are-opt-in-everywhere.md).
