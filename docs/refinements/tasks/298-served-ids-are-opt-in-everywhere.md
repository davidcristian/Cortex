# A test backend serves every model id unless it is told otherwise

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Trigger:** the first turn, fold, delegation or handoff that reaches a real deployment with a model id its wiring never had, having passed every test that covers that path.

Opened 2026-08-17 by the served-model answer ([R-280](280-twin-answers-for-any-model-id.md)), which
closed the port's silence and left the default where it found it.

`InferenceBackend` now says an implementation answers only for the ids it serves, and
`ScriptedInferenceBackend` keeps that promise when it is constructed `serves=[...]`. The default is
still `None`, which answers for anything, and the three fixtures in
`brain/packages/inference/tests` are the only places that pass the keyword. Everywhere else the id
is discarded outright: `del model` appears 53 times across 18 test files under `core/tests` and
`orchestrator/tests`, in backends hand-rolled per file rather than shared. So the exposure the
closed entry described is narrowed rather than removed. What is covered is that an implementation
told about a deployment refuses an id outside it; what is not is that any test in the tree would
notice a caller asking for the wrong one, because `TurnEngine`'s config, the subagent roster and
the handoff plan all supply the id and none of the fakes reading it care what it says.

The default was kept deliberately and the argument still stands: a twin told nothing about a
deployment has made no claim to violate, and a check about events rather than wiring should not
have to invent one. So this is not "flip the default", which would cost every hand-rolled backend a
served set it has no opinion about. The shapes worth weighing when it bites are narrower. The fakes
could take the id from the wiring under test rather than from the test author, which means the
config-driven callers grow a fixture that reads the same value the production root reads. The
hand-rolled backends could collapse onto the twin, which is a larger cleanup with a real payoff
(one place to teach, `serves` included) and a real cost (each of the eighteen files scripts its own
shape, and some assert on `bounds` or on messages the twin ignores). Or the exposure could be
covered once end to end, a single test per configured caller pinning that the id it asks for is the
id its deployment hosts, which is the cheapest of the three and the only one that would fail today
if a wiring change went wrong.

Nothing mis-wires an id in the tree right now, so this is filed by shape rather than by symptom:
the failure it guards against is silent in tests and loud on the first real turn, which is what
makes it worth a trigger rather than a fix.
