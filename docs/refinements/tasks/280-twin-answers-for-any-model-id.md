# The inference fake answers for a model id no deployment serves

**Status:** done 2026-08-17
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)

Opened 2026-08-16 by the shared streaming contract list for `InferenceBackend`
([R-018](018-ports-without-contract-suite.md)), which found it while deciding what belongs in the
list.

`LlamaCppBackend` refuses a model its `ModelManager` cannot lease: `acquire` raises
`ModelUnavailableError` for anything but the resident id and the adapter re-raises it as
`InferenceError`. `ScriptedInferenceBackend` answered any id at all, recording it in `calls` and
streaming its script, so a core test could watch a turn get a reply for a model production would
have refused. That is the fake being more permissive than the adapter it stands in for, which hides
defects rather than inventing them.

It was left out of the streaming list because of a real question rather than scope. Which ids a
backend serves is `ModelManager`'s subject, not the stream's: this adapter refuses because its
manager does, a backend in front of a router would legitimately serve any id it recognises and fail
on the wire for the rest, and the port's own words are about a completion "against a loaded model"
rather than about who checks.

## History

- 2026-08-17: Both halves of the claim were checked against the code first and held. Asked for
  `'scribe'`, `LlamaCppBackend` over a one-resident manager raised `InferenceError: model manager
  could not lease 'scribe' for inference` before any request left the process, while the fake
  streamed its whole script and recorded the id. Built as the entry described: the port now says an
  implementation answers only for the ids it serves and leaves who checks and when open, the fake
  takes `serves=[...]` and refuses anything outside it after recording the call, and the shared
  streaming list gained a ninth check that needs no fifth builder, since every world it already
  arranges stands for a deployment serving `CONTRACT_MODEL` alone. Written up as
  [ADR-0068 decision 8](../../adr/ADR-0068-port-contract-lists.md), with two mutations proving the
  check reachable from each side: making the fake's refusal a no-op fails it on the scripted side
  alone (1 of 2625), and a manager that stops checking residency fails it on the adapter side (3 of
  2625, the other two being that manager's own test and the adapter's wrapping test). The entry's
  count of "fifty-odd existing scripts" was wrong: `ScriptedInferenceBackend` has exactly three
  call sites, all contract fixtures, and the scripts that ignore a model id are the hand-written
  backends in `core/tests` and `orchestrator/tests`. That, and the opt-in default the change kept,
  is [R-298](298-served-ids-are-opt-in-everywhere.md).
