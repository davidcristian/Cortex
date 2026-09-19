# A test backend serves every model id unless it is told otherwise

**Status:** done 2026-08-20
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)

Opened 2026-08-17 by the served-model answer ([R-280](280-twin-answers-for-any-model-id.md)), which
closed the port's silence and left the default as it was.

`InferenceBackend` says an implementation answers only for the ids it serves, and
`ScriptedInferenceBackend` meets that when it is constructed with `serves=[...]`. The default is
still `None`, which answers for anything, and everywhere else the id is discarded outright: `del
model` appears 53 times across 18 test files under `core/tests` and `orchestrator/tests`, in
backends written per file rather than shared. So what was covered is that an implementation told
about a deployment refuses an id outside it; what was not is whether any test in the tree would
notice a caller asking for the wrong one.

The cheapest of three shapes was built: one test per configured caller, asserting that the id it
asks for is the id its deployment hosts. There are three, and each renames its tiers in the test,
which is what makes the assertion real, since under the shipped ids the deployment's value and the
module's own constant are the same string.

- The resident tier a turn asks for. `run_from_env` reads `CORTEX_MODEL_CORTEX` into
  `TurnEngine(cortex_model=...)` and again into the backend whose manager grants the lease, and
  those two reads meet nowhere below the root. Driven over the llama.cpp backend, the echo one
  taking no lease at all, and against a refused loopback port, asserting on which failure comes
  back rather than on a reply.
- The deep tier a handoff swaps in. `build_swap_runtime` keys its endpoint map by the plan's ids
  while the deep phase asks for `plan.brain_model` by name.
- The subagent entry every untrusted spawn is forced onto. `config.model` is declared apart from
  the entries `named_roster` keys, and `SubagentRoster` refuses to be built when they disagree.

Nothing in production changed and the default stays `None`: a fake told nothing about a deployment
states nothing a call could contradict, and changing it would cost every hand-written backend a
served set none of them needs.

One correction to the record this was filed with: it said three fixtures in
`brain/packages/inference/tests` pass `serves=`; there is exactly one, the shared list's own
builder in `test_stream_contract.py`. The count of 53 across 18 files is exact.

## History

- 2026-08-20: Done as three tests, each proved by mis-wiring an id to the module constant it reads
  like and watching the whole `packages` suite. Recorded as ADR-0068 decision 9, with the fourth
  caller it does not reach filed as [R-332](332-the-recall-judge-asks-for-an-unpinned-model.md).
