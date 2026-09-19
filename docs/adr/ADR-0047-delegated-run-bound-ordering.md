# ADR-0047: Ordering the bounds on a delegated run

**Status:** Accepted (2026-09-19)

## Context

A delegated subagent run ([ADR-0010](ADR-0010-subagents.md)) has four time limits, each with its
own setting:

| limit | setting | what it limits | shipped |
| --- | --- | --- | --- |
| stall ceiling | `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` | one silent read of the model's stream (httpx's read timeout) | 600 s |
| tool call limit | `CORTEX_TOOLS_CALL_TIMEOUT_S` | one listing or call on a tool sidecar ([ADR-0009](ADR-0009-tools-mcp.md) decision 10) | 60 s |
| run deadline | `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` | one attempt of one subtask | 2400 s |
| admission wait | `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` | how long a queued spawn waits for room | 7200 s |

Each limit is only useful if it fits inside the one around it. When it does not, the failure is
reported as the wrong thing. A tool call limit above the run deadline turns a stuck sidecar into
`AttemptFailure.TRUNCATED` with no text, so the cortex is told the subtask "was still generating",
where the call limit would have returned a `ToolError` the model could recover from. A run that
outlasts the admission wait makes a queued peer give up on a pool that is working, and the refusal
it logs blames the queue.

## Decision

1. **Every ordering is strict and refused at startup, never clamped or only logged.** Equality
   leaves it to a race which limit ends the run first. A clamp would silently retune a number the
   operator typed, and a warning leaves the wrong ordering running with a diagnosis that names the
   wrong cause.
2. **The run deadline outlasts the stall ceiling.** `SubagentsConfig` refuses a `run_timeout_s` at
   or below `stall_timeout_s` (`_the_run_deadline_must_outlast_the_stall_ceiling`).
3. **A whole delegated dispatch fits inside the run deadline.** `check_tool_call_deadline`
   (`cortex_orchestrator/bounds.py`) multiplies the call limit by `delegated_call_bounds(tools)` and
   requires the product to be strictly under the run deadline. The limit applies per listing, not
   per dispatch: one advertisement listing, the live listing `UngatedToolRegistry` makes to strip
   the tools that need confirmation, the routing listing `AggregateToolRegistry` makes when there is
   more than one endpoint, and the call itself, each costing one limit per configured sidecar. That
   is 3 with one sidecar and 7 with two, so 700 s under 900 s, ordered as typed, is refused. The
   refusal names both settings, both values, the multiplier and the product, and the startup log
   line includes `call_bounds_per_dispatch`. The check runs only when `CORTEX_TOOLS_BACKEND=mcp` and
   `CORTEX_SUBAGENTS_BACKEND=llamacpp`, on the config as it comes out of the environment, before any
   adapter is built. Two settings classes read the two numbers, so the comparison lives in
   `bounds.py`, a module for orderings no single class can check.
4. **The admission wait outlasts everything one task can hold.** A GPU-placed attempt that fails on
   inference is re-run once on the CPU inside the same admission with a fresh deadline, so a task
   can hold its room for `ATTEMPTS_PER_ADMISSION` (2) deadlines. `SubagentsConfig` refuses
   `ATTEMPTS_PER_ADMISSION * run_timeout_s` at or above `admission_wait_s`
   (`_the_run_deadline_must_fit_inside_the_queue_for_it`), and the refusal names the product.
   `ATTEMPTS_PER_ADMISSION` is declared in `cortex_core.subagents` and tied to the runner by
   `test_runner.py::test_the_cpu_re_run_happens_exactly_once_and_both_failures_are_recorded`, so a
   third attempt fails that test rather than under-protecting the queue. A wait of zero means never
   queue, has nothing to outlast, and passes.
5. **The wait moved to 7200 s; the deadline did not.** The deadline is about four times the longest
   hold a fully serialized batch produced, and a whole subtask's time varies about twofold with what
   else the machine is doing, so lowering it would cut work that was going to finish. The wait had
   been derived from the measured batch alone (twice the serialized last admission, about 3250 s)
   and did not clear the doubled hold. `DEFAULT_ADMISSION_WAIT_S` is now three deadlines, the two a
   task can spend plus one of margin, and is computed from the larger of the relation and the
   measurement, so retuning the deadline moves the wait or fails at startup. The cost is that a
   spawn that will never be admitted is told so after two hours instead of one. The measurements are
   in [delegated run holds](../readings/delegated-run-holds.md).
6. **The cortex's own loop and the schedule ticker are outside the series.** A `Converse` turn
   declares no deadline for its calls to be ordered against
   ([ADR-0024](ADR-0024-transport-retry.md)), and the ticker has none either. Checking a whole run
   against every dispatch it could make, the call limit times `MAX_TOOL_DISPATCHES`, was rejected:
   the shipped pair does not clear it, and the failure worth preventing is a run cut off mid call,
   which only needs one dispatch to fit.
7. **Where the repo's own numbers are checked.** An ordering between two numbers that one settings
   class reads is checked by that class's validators: its defaults are the shipped constants, so
   every bare construction in the orchestrator test suite reads the shipped trio and an inverting
   retune fails on the commit that types it. An ordering across classes is checked by a test that
   imports the shipped defaults and runs the enforcing check over them:
   `test_the_shipped_pair_is_wired_and_says_so` and
   `test_a_second_sidecar_costs_the_same_bound_more` in `orchestrator/tests/test_bounds.py` enable
   both capabilities and fail with `ToolCallDeadlineError` when the pair inverts, including a call
   limit that is ordered as a bare pair rather than as a dispatch. The constant scan
   ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)) checks an ordering only when no single
   process reads both numbers, such as a pair across the language boundary or between brain packages
   deployed apart; its `ORDERED` relation compares integers non-strictly and is not widened for
   these decimals.

## Consequences

- A deployment whose limits do not nest fails at startup naming the settings and the product,
  instead of serving until the first stuck sidecar or the first CPU re-run and then blaming the
  model or the queue.
- Adding a second sidecar more than doubles what a stuck delegated dispatch costs without touching
  either setting; that multiplier is on the startup log line.
- The shipped stack clears every relation: a delegated dispatch costs 180 s of a 2400 s run with one
  sidecar and 420 s with both shipped sidecars, and the hold is 4800 s under a 7200 s wait.
- How often the CPU re-run actually happens is not counted, and every limit is a multiple of a
  subtask measured on an idle machine.

## Alternatives rejected

- **A fixed multiplier for the dispatch cost:** wrong above one sidecar or absurd at one, while the
  endpoint count is in the config the check is handed.
- **Comparing one attempt's deadline with the wait:** misses the doubled hold on the re-run path.
- **Lowering the run deadline to fit the old wait:** cuts subtasks that were going to finish.
- **Checking these orderings in the constant scan:** it would need decimal parsing, a strict
  relation and an exception to its rule that an entry spans more than one side of the boundary, to
  enforce a weaker copy of a check that already runs.

## Related

- [brain-orchestrator module contract](../modules/brain-orchestrator.md) (`bounds.py`, the config
  classes), [brain-core module contract](../modules/brain-core.md) (`subagents`, `scheduler`).
- Runbooks: [subagents-cpu](../runbooks/subagents-cpu.md), [tools-mcp](../runbooks/tools-mcp.md).
- Readings: [delegated run holds](../readings/delegated-run-holds.md).
- [ADR-0009](ADR-0009-tools-mcp.md), [ADR-0010](ADR-0010-subagents.md),
  [ADR-0012](ADR-0012-resource-governance.md) (admission), [ADR-0024](ADR-0024-transport-retry.md).
