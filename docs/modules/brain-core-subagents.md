# brain/packages/core: delegated work

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers a subtask the cortex delegates to a subagent: the
values and ports it is placed and admitted through, and the runner that performs it. The
`spawn_subagents` tool that starts one is in [brain-core-tools.md](brain-core-tools.md), and the
GPU it competes for is in [brain-core-residency.md](brain-core-residency.md). The decisions are
ADR-0010, ADR-0012, ADR-0017, ADR-0018, ADR-0028 and ADR-0048.

## Subagent values and ports

- `TaskStore` provides `put_task`, `get_task`, `put_result` and `get_result`: the hot store a
  subagent is a stateless function over. Unknown ids return `None`, and `get_result` has no
  production caller, so the result key is the operator's record and what a resume path would read.
  Fake: `InMemoryTaskStore`; real adapter: `cortex_session`.
- `SubagentTask(id, instruction, context, at, model="", tainted=False, session_id="", turn_id="",
  item_id="")` is one delegated task, persisted before it runs. `context` is the material the
  subagent works from; the cortex conversation is never shared. All of these travel on the record
  rather than as parameters, so the runner resolves and audits from the store alone.
  `SubagentResult(task_id, output, ok=True, detail="", tainted=False)` is the outcome, where
  `ok=False` is a failure the cortex consumes as a value. `tainted` is true when the task was
  tainted or the attempt read an untrusted tool result (ADR-0013 decision 3).
- `PlacementTarget` is `GPU` or `CPU`, where a subagent's whole model runs, never split across
  both; `.ngl` maps it to the llama.cpp offload flag (`GPU` to 99, `CPU` to 0).
  `PlacementRequest(model, vram_gb, cpus, memory_gb)` is one subagent's resource ask and rejects a
  non-positive value. `Placement(target, reserved_gb)` is what a `SubagentPlacer` returns, with
  `reserved_gb` the request's `vram_gb` on GPU and `0.0` on CPU, so a release is exact.
- `SubagentResources(backends, scheduler, placer, request)` bundles one roster entry's placement
  collaborators and `SubagentProfile(resources, description)` is one entry, the description being
  the trade-off text the spawn spec advertises. In a multi-entry roster the scheduler and placer
  are the same objects in every entry, so there is one CPU budget and one VRAM ledger. A profile
  contains no measured rate and no per-entry wording, both declined because an entry names an
  endpoint and not a model artifact (ADR-0018 decisions 10 and 11, ADR-0028 decision 8).
- `SubagentRoster(entries, default)` rejects an empty roster and a default outside it.
  `resolve(requested, *, tainted, tools_enabled)` is where ADR-0017 runs: a tainted or
  tools-enabled path takes the `default` whatever was requested; any other path takes the requested
  entry, `""` meaning the default; an unknown name on a clean tool-less path returns `None`, which
  the runner fails closed on.
- `SubagentPlacer` provides `place(request)`, `release(placement)`, `close_gpu()` and
  `open_gpu()`, all synchronous. `place` fit-tests `request.vram_gb` against the live headroom
  (`soft_cap − resident − placed`) and reserves it on the GPU or spills to the CPU. While closed,
  `place` must return CPU whatever the headroom says, which is the one question no number about
  free memory answers: whether the server a GPU placement would use is running at all. The last
  two leave the ledger alone and are idempotent. Implementation: `VramBudgetPlacer(*, soft_cap_gb,
  cortex_reservation_gb)`, pure policy whose ledger is rebuilt from zero at boot.
- `SubagentScheduler` provides `admit(request)`, `drain(*, timeout_s)` and `undrain()`: a soft
  two-dimensional CPU and RAM budget for spawns, deliberately not the GPU lease. A charge larger
  than the whole budget can never be admitted and raises `SubagentAdmissionError`, and an
  implementation that queues owes a bound on that queue and the same typed refusal when it elapses.
  `drain` stops admission at once and waits for in-flight admissions to release; `True` means it
  drained clean and `False` that the bound elapsed with work still running and nothing killed, so
  the swap must abort before evicting anything. Implementation:
  `ResourceBudgetScheduler(cpu_budget, mem_budget_gb, *, wait_timeout_s=DEFAULT_ADMISSION_WAIT_S)`;
  fake: `AdmitAllScheduler`, which grants every admission at once and still implements the drain
  contract. `DEFAULT_ADMISSION_WAIT_S` is 7200.0, three run deadlines, which clears both twice the
  1624.6 s the last spawn of a full `MAX_SPAWN_BATCH` was measured waiting when an entry's admitted
  pair runs one after the other on one placement target (893.2 s when that pair overlaps, the
  shipped placement) and the `ATTEMPTS_PER_ADMISSION` whole deadlines one task can hold the room.

## Running one subtask

`AttemptBounds(max_tokens=None, timeout_s=None)` (`subagents.py`, ADR-0048) is how far one placed
attempt may go: `max_tokens` becomes the `GenerationBounds` on each of its completions and
`timeout_s` is the deadline on the whole attempt, tool dispatches included. They are one value
because the cap binds a fast tier and the deadline binds a slow one, where the pool's measured 0.18
to 1.35 tok/s makes a small token budget minutes of held admission; the two are deliberately not
ordered against each other. `DEFAULT_SUBAGENT_MAX_TOKENS` and `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` are
the shipped numbers, declared here and imported by `SubagentsConfig`, and one pair reaches every
roster entry and both placements of each.

`SubagentRunner(store, roster, clock, *, tools=None, constrain_output=False,
bounds=UNBOUNDED_ATTEMPT)` is a subagent's body, a stateless function over the `TaskStore`.
`run(task_id, *, budget=None, progress=None)` loads the task by id, resolves the roster entry,
admits against the scheduler, places on GPU or CPU, runs the attempt on that entry's backend for
the placement, persists and returns a `SubagentResult`, and always releases the VRAM in a
`finally`. A missing task, an unknown model and a `SubagentAdmissionError` all become `ok=False`
results rather than exceptions, which would cross the spawn tool's `gather` and fail the turn; a
refused spawn also writes one warning naming the task, the resolved entry and the scheduler's
reason, the only lasting record of it. A refused tainted task's result is tainted. `budget=None`
means the run is its own root, the ticker's fire.

**The CPU re-run**: a GPU-placed attempt that failed with `AttemptFailure.INFERENCE` is re-run once
on the CPU backend, and the outcome's `detail` says it happened. Only that failure kind and only a
GPU placement retry. The reservation is released before the re-run, so headroom is never
misreported to a concurrent spawn, and the re-run reuses the same admission and the same
`DispatchBudget`; the attempt deadline is the one bound it does not reuse, being set fresh per
attempt. The re-run's text and failure win, but the taint is the union of both attempts.

`PlacedAttempt(clock, tools, *, constrain_output, bounds=UNBOUNDED_ATTEMPT)`
(`subagent_attempt.py`) runs one attempt on an already-placed backend and returns an
`AttemptOutcome(text, failure, detail, tainted)` rather than storing anything. Every attempt is a
fresh function over the task, with its own working set, taint ledger and fence nonce; the shared
allowance is the deliberate exception. The ledger starts tainted when the task is, because the
task's context can quote what the spawning turn read, and a tool-holding attempt's dispatches are
stamped with it. The run sits inside `asyncio.timeout(bounds.timeout_s)`, so
the deadline covers every completion and every dispatch between them, and reaching it is
`AttemptFailure.TRUNCATED` with the fragment produced so far. Only an expired deadline counts, so a
`TimeoutError` raised from below is `AttemptFailure.INFERENCE` and stays eligible for the CPU
re-run. A completion the backend reports as cut at a token limit is also `TRUNCATED`; a cut inside
a tool call reaches that by a different path, reported as `TRUNCATED` only when the `StopLedger`
also saw a cap. The outcome vocabulary is in `subagent_outcome.py`.

`subagent_reply.py` holds the constrained-reply grammar (ADR-0028). `REPLY_ENVELOPE` is the schema
a constrained request asks for and `unwrap_envelope(text)` reads the answer back. A schema tells
the model nothing, which was measured: llama.cpp renders the same prompt with it and without it.
The repair is a sentence in the subtask, `REPLY_INSTRUCTION`, appended by
`instruct_reply(instruction)`; it is one wording for every roster entry, which the entries do not
agree about, and a per-entry wording was declined (measurements in
[reply envelope](../readings/reply-envelope.md)). The sentence is not a detector: a plan that still
arrives in `reply` is `ok=True`. `settle_reply(text, *, capped, max_tokens, constrain, tainted)` is
the ordered reading a finished run gets: capped first, then unconstrained text, then the envelope.
Constraining applies only on the tool-less path, a JSON grammar fighting tool calling.

**Invariants.**

- A subagent is a stateless function over the `TaskStore`: the runner reads the task by id and
  persists the result, keeping nothing between calls.
- One turn's dispatch allowance is shared with every subagent it spawns, and a tainted task or an
  attempt that read untrusted content taints its result whatever else happened to it, with or
  without tools and refused or not.
