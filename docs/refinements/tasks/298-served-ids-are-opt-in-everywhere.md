# A test backend serves every model id unless it is told otherwise

**Status:** landed 2026-08-20
**Area:** repo-gates
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)

Opened 2026-08-17 by the served-model answer ([R-280](280-twin-answers-for-any-model-id.md)), which
closed the port's silence and left the default where it found it.

`InferenceBackend` says an implementation answers only for the ids it serves, and
`ScriptedInferenceBackend` meets that requirement when it is constructed `serves=[...]`. The default
is still `None`, which answers for anything. Everywhere else the id is discarded outright: `del
model` appears 53 times across 18 test files under `core/tests` and `orchestrator/tests`, in
backends hand-rolled per file rather than shared. So what was covered was that an implementation
told about a deployment refuses an id outside it; what was not is that any test in the tree would
notice a caller asking for the wrong one.

Of the three shapes this weighed, the cheapest landed: one test per configured caller, pinning that
the id it asks for is the id its deployment hosts. There are three, and each renames its tiers,
which is what makes the pin a pin. Under the shipped ids the deployment's value and the module's
own constant are the same string, so a root reaching for the constant is indistinguishable from one
reading the config, and every case that already existed left the defaults in place.

- The resident tier a turn asks for. `run_from_env` reads `CORTEX_MODEL_CORTEX` into
  `TurnEngine(cortex_model=...)` and again into the backend whose manager grants the lease, and
  those two reads meet nowhere below the root. Driven over the llama.cpp backend, the echo one
  taking no lease at all, and against a refused loopback port, the assertion being on which failure
  comes back rather than on a reply.
- The deep tier a handoff swaps in. `build_swap_runtime` keys its endpoint map by the plan's ids
  while the deep phase asks for `plan.brain_model` by name.
- The subagent entry every untrusted spawn is forced onto. `config.model` is declared apart from
  the entries `named_roster` keys, and `SubagentRoster` refuses to be built when they disagree.

Nothing in production changed and the default stays `None`, for the reason it was kept: a twin told
nothing about a deployment states nothing a call could contradict, and flipping it would cost every
hand-rolled backend a served set none of them needs. The two heavier shapes stay unchosen, and the
entry that carries what is left of the exposure carries them too.

One correction to the record this was filed with. It said three fixtures in
`brain/packages/inference/tests` pass `serves=`; there is exactly one, the shared list's own
builder in `test_stream_contract.py`. The count of 53 across 18 files is exact.

## Trail

- 2026-08-20: Landed as three pins, each proved by mis-wiring an id to the module constant it
  reads like and watching the whole `packages` suite. Recorded in the ADR-0001
  configured-caller addendum, with the fourth caller it does not reach filed as
  [R-332](332-the-recall-judge-asks-for-an-unpinned-model.md).
