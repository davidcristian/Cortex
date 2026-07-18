# ADR-0030: Brain handoff (the real model swap)

- **Status:** Accepted (2026-07-17)
- **Date:** 2026-07-17

## Context

Slice 11 (docs/ROADMAP.md) is the capstone: the one hard rule proven end to end. The full
handoff is cortex escalates → context serialized → the model manager evicts cortex/subagents
and loads the brain (stops their `llama-server` processes, starts the brain's, per ADR-0005
decision 3) → the brain rehydrates from the store, works, persists → swap back → cortex
resumes from the store. It includes a chaos test (kill a model mid-handoff; the system resumes
from the store) and the runbook `docs/runbooks/model-swap.md`.

The design sits on what exists, not on guesses. The load-bearing facts, each read from the
tree at the commit this ADR lands on:

- **Almost everything is already in the stores.** The engine is a stateless function over
  `SessionStore` ([engine.py](../../brain/packages/core/src/cortex_core/engine.py): the module
  docstring and `handle_turn`); tasks live in the Redis `TaskStore`, schedules in the
  `ScheduleStore`, durable memory in pgvector
  ([ports_stores.py](../../brain/packages/core/src/cortex_core/ports_stores.py)). What is NOT
  in any store mid-turn: the tool loop's `working` tail (the `Role.ASSISTANT` tool-call and
  fenced `Role.TOOL` messages the loop appends are never persisted; only the user message and
  the final reply are), the `TaintLedger` (tainted bit, `sources`, `untrusted_urls`;
  [untrusted.py:90](../../brain/packages/core/src/cortex_core/untrusted.py)), the per-turn
  fence `nonce`, the `DispatchBudget`, and the loop's round position.
- **The GPU lease is a non-reentrant `asyncio.Lock` held across one inference round, not one
  turn.** `SingleResidentModelManager` serializes callers on `self._lock`
  ([model.py:41](../../brain/packages/core/src/cortex_core/model.py)) and raises
  `ModelUnavailableError` for any non-resident model (model.py:51). `LlamaCppBackend.stream`
  holds the lease across the whole SSE stream
  ([backend.py:185](../../brain/packages/inference/src/cortex_inference/backend.py)), but each
  tool-loop round is its own `backend.stream` call
  ([tool_loop.py:211](../../brain/packages/core/src/cortex_core/tool_loop.py)), closed before
  any dispatch runs (tool_loop.py:224), so the GPU is free while a tool executes.
- **The tier seam already exists and always answers cortex.** `route_turn(RoutingHints())`
  with default hints selects `Tier.CORTEX`
  ([engine.py:155](../../brain/packages/core/src/cortex_core/engine.py),
  [routing.py:24](../../brain/packages/core/src/cortex_core/routing.py)); `Tier.BRAIN` and
  `needs_deep_reasoning` are shaped but nothing produces them.
- **Processes are compose services today, started declaratively.** The resident cortex is the
  `llama-cortex` service ([docker-compose.gpu.yml:24](../../docker/docker-compose.gpu.yml))
  with `restart: unless-stopped`; the subagent tier is one CPU `llama-server` serving BOTH
  placement targets ([docker-compose.subagents.yml:39](../../docker/docker-compose.subagents.yml)),
  the real GPU sidecar being an ADR-0012 host-half deferral. Nothing in the running system can
  stop or start a model process.
- **The swap's composition contract is already written.** ADR-0007 decision 3 defers the
  `cortex_model_manager` package (process lifecycle behind the unchanged `ModelManager` port)
  to this slice; ADR-0012 decision 1 pins `acquire(model) -> ModelLease` to zero change and its
  consequences defer `SubagentScheduler.drain()` as an additive method composed "at the swap
  orchestrator, never merging the ports". The scheduler and placer are ONE object across roster
  entries ([subagent_builders.py:106](../../brain/packages/orchestrator/src/cortex_orchestrator/subagent_builders.py)).
- **`Health` is unconditionally ready.** The servicer answers `ready=True` always
  ([server.py:102](../../brain/packages/orchestrator/src/cortex_orchestrator/server.py));
  `HealthReply` already carries `ready` + `detail`
  ([body.proto:138](../../proto/body.proto)). The overlay indicator already classifies a
  future `ready=false` as amber Degraded, and the streamed-status deferral names this slice as
  the producer that makes it real ([body-overlay.md](../refinements/body-overlay.md)).
- **The body is one turn per `Converse` call.** The overlay opens a fresh stream per submit
  and the transport sends exactly one `UserTurn`
  ([body-overlay.md](../refinements/body-overlay.md), read against
  `body/crates/rpc/src/converse.rs`). Anything the user must see during a handoff therefore
  has to ride the escalating turn's own event stream, or wait for a body seam change.
- **VRAM (ADR-0004, measured):** 24 GB GPU, soft cap 14 GB (`CORTEX_VRAM_SOFT_CAP_GB`), cortex
  gemma-4-12B at ~11.3 GB incl. vision at 16K ctx, subagent E4B VRAM ask 5.5 GB (deliberately
  above the ~2.7 GB headroom, so every spawn overflows to CPU today), brain candidates 15-18 GB
  of weights that "all fit alone in 24 GB". The brain pick itself is still open and lands with
  this slice.
- **Sequencing and the line cap.** ADR-0029 (Slice 10, designed, not yet implemented) records
  `engine.py` at 299 of 300 lines and `tool_loop.py` at 297. This slice lands after the vision
  slice; its engine-adjacent additions live in new modules and any residual cap pressure is
  resolved by a mechanical split planned up front, per the same ADR's precedent.

## Decisions

Each decision names the alternatives considered and why they lost.

### 1. Escalation is an explicit, gated `escalate_to_brain` built-in tool

The cortex decides mid-turn that it is out of its depth by calling a new built-in tool,
`escalate_to_brain(brief)`, advertised like the volume and spawn built-ins and dispatched
through the audited `ToolDispatcher`. `brief` is the cortex-authored statement of what the
deep model should do and what has been learned so far. The tool is marked **gated**, which
buys both existing protections at zero new mechanism: on an untainted turn the user confirms
via the ADR-0022 card (a swap takes minutes and claims the whole GPU; that consent surface
already exists), and on a tainted turn the call is hard-denied with the confirmer never
consulted ([dispatch.py](../../brain/packages/core/src/cortex_core/dispatch.py)), so injected
content can never force an eviction. Because the brain tier's injection robustness is
unmeasured until the harness runs (decision 9 / the backlog section), refusing to hand
attacker-influenced context to a stronger tools-holding model is the only honest v1 default.

Two consequences are named rather than hidden. First, the generic gate reason ("outbound or
irreversible", dispatch.py:42) would be false on this card, the same falsehood argument
ADR-0029 used against gating capture; the gate therefore grows an optional per-tool reason
(config beside `CORTEX_TOOLS_GATED`, flowing into `ConfirmationRequest.reason`), an additive
change, and the escalate card says what is true: the deep model will take over and the machine
will be busy for a while. Second, a turn carrying screen-capture pixels cannot escalate:
pixels are turn-local by ADR-0029's store invariant, the handoff record refuses image-bearing
messages the same way the session stores do, and the tool answers with a typed refusal telling
the model to ask the user to retry in a fresh message. Escalating an `opaque` turn would
otherwise quietly widen pixel persistence, which that ADR explicitly reserved as its own
deliberate decision.

Smarter policies slot in later without new seams: `route_turn` already accepts
`needs_deep_reasoning` and `explicit_tier` (routing.py:16), so a pre-turn heuristic or a
user-invoked "think deeper" affordance becomes a producer of `RoutingHints`, not a new
mechanism. The tool is the v1 because mid-turn is where the evidence lives: the cortex
discovers it needs depth after reading, not before.

Rejected: **a pre-turn core policy** (nothing honest to compute it from yet; it would be a
heuristic pretending to be a decision); **user-invoked only** (it cannot express the common
case, the cortex discovering mid-turn that the task is deep, and it needs body/proto surface
this slice does not otherwise touch); **an ungated tool with an internal taint check** (loses
the user-consent card for a machine-wide disruption, and re-implements half the gate).

### 2. The handoff record: schema, and the `HandoffStore` port

Per the hard rule, the record carries only what is NOT already in a store. Frozen dataclass
`HandoffRecord` (new `cortex_core/handoff.py`):

- `handoff_id` (= the escalating `turn_id`), `session_id`, `requested_at`;
- `state`: `PENDING` → `READY` → `BRAIN_ACTIVE` → terminal `DONE` | `FAILED`;
- `brief`: the cortex's escalation ask (model-authored text, same trust domain as the
  conversation);
- `nonce`: the turn's fence id, carried so the fenced blocks in the tail stay explained by the
  preamble's "markers carry a random id per turn" rule instead of becoming unexplained
  markers under a fresh nonce;
- the serialized `TaintLedger`: `tainted` bit, `sources` (the kind-tagged ADR-0027
  `Provenance` values), and `untrusted_urls` (the ADR-0015 laundering evidence, without which
  the brain phase's guardrail would forget every URL read before the swap);
- `budget_remaining` + `budget_closed` (the turn-wide dispatch pool survives the swap; a swap
  must not refill the turn's allowance);
- `rounds_used`, and `loop_tail`: every message the tool loop appended this turn (the
  assistant tool-call messages and the fenced `Role.TOOL` results, in order), text-only by the
  same invariant the session stores enforce (ADR-0029).

This is the schema the untrusted-content backlog flagged: the tainted bit AND the sources
survive a mid-turn swap because they are IN the record, and provenance rides the serialized
tool-step context. The contract test pins an exact round trip of a tainted ledger (bit,
sources order, URL set) through the store and back into a reconstructed `TaintLedger`.

It lives behind a new port, `HandoffStore` (`put`, `get`, `transition(id, state)`, `delete`,
`active() -> HandoffRecord | None`), in `ports_stores.py` beside the four existing store
ports, with the in-memory fake in core and a Redis adapter in `cortex_session` (hot state,
exactly the `TaskStore` precedent; terminal records get a TTL). At most one handoff is active
at a time (one GPU), which `active()` makes checkable and boot recovery (decision 5) relies
on. Failures surface as a typed `HandoffStoreError`.

Mechanically, the turn's in-flight state reaches the serializer through an `EscalationSlot`:
a mutable turn-local object created next to the ledger and nonce, holding references to
`working`, the ledger, the nonce, and the budget, and threaded to the tool the same way
`budget` and `progress` already ride `ToolLoopContext`/`TurnStamp` (tool_loop.py:271). The
tool writes only `slot.brief`; the conductor snapshots everything else at the loop boundary,
after the cortex phase's generator has finished, so nothing is copied mid-flight.

Rejected: **reusing `TaskStore`** (a handoff is not a subagent task; overloading the port
muddies both contracts and the fake); **persisting the tail into `SessionStore`** (it would
make half-finished tool rounds part of durable history and every reader would need to learn
to skip them); **widening `TurnStamp` to carry the whole ledger and working list** (the stamp
is a frozen per-dispatch value; hanging the turn's mutable state off it inverts its meaning).

### 3. The process-lifecycle port: `ModelHost`, adapted by a supervisor sidecar

The deferred `cortex_model_manager` package arrives, split into a port and a deliberately
boring adapter pair.

**The port** (in `cortex_core`, beside `ModelManager`):

```python
class ModelHost(Protocol):
    async def start(self, model: str) -> None: ...      # idempotent; begins loading
    async def stop(self, model: str) -> None: ...       # idempotent; SIGTERM then SIGKILL
    async def status(self, model: str) -> ModelHostState: ...  # STOPPED|LOADING|READY|FAILED
```

`model` is a logical id (ADR-0004 decision 2); artifact paths, ports, `-ngl`, and ctx flags
never cross the port. Failures surface as a typed `ModelHostError`. The fake in core is
scriptable (delays, failures, kill-at-step) and is what CI and the chaos test drive; the real
adapter's live tests are `integration`-marked, per gate 3.

**The real mechanism** is a new `model-host` supervisor sidecar replacing the always-on
`llama-cortex` service in `docker/docker-compose.gpu.yml`: one container holding the GPU
device reservation and the read-only models mount, running a small daemon (shipped from the
new `cortex_model_manager` workspace package, the standalone-sidecar precedent set by
`cortex_email`) that spawns and kills one `llama-server` child process per logical model on a
fixed per-model port (cortex :8080, brain :8081, GPU subagent :8083), each with argv built
from its own env (`CORTEX_MODEL_FILE_BRAIN`, `CORTEX_NGL_BRAIN`, `CORTEX_CTX_SIZE_BRAIN`, and
the existing cortex knobs). Its HTTP control API is the wire behind the `ModelHost` adapter
(`CORTEX_MODELHOST_ENDPOINT`), reachable only on the compose network. `status` proxies the
child's `/health`, so "READY" means what the compose healthcheck means today. At boot the
daemon starts the cortex (its default residency), so a stack that never escalates behaves
byte-for-byte as the current one. Killing a child loses nothing by construction: that is
ADR-0005 decision 3 made literal.

This container is also where the ADR-0012 host-half lands: the real GPU subagent
`llama-server` (`-ngl 99`) becomes a hosted model, `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at
it, and the per-container cgroup caps ride the compose revision.

Rejected: **the Docker API from the brain container** (mounting `docker.sock` into the
process that runs model-influenced code is host-root in the hands of whatever compromises
it); **a socket-holding controller sidecar driving `docker compose stop/start`** (still
host-root somewhere, plus compose-file awareness inside a container; the blast radius of a
child-process supervisor is its own container); **subprocesses inside the brain container**
(the brain image would need CUDA and the GPU reservation, coupling orchestration restarts to
model residency and fattening the attack surface of the one container that talks to
sidecars).

### 4. The swap sequence, its ordering guarantees, and every failure's direction

The conductor runs the sequence inside the escalating turn (decision 6), after the cortex
phase ends. Fail-safe direction throughout: **every exit path converges back to a serving
cortex**; the swap back is the recovery path, not an optimization.

1. **Snapshot.** Build the `HandoffRecord` from the slot, persist it `READY`. Nothing has
   been stopped yet; a crash here leaves a record that boot recovery marks `FAILED` and a
   fully working cortex.
2. **Drain subagents.** `SubagentScheduler.drain()` (the ADR-0012 deferral, additive on the
   port): stop admitting, wait for in-flight admissions to release, bounded by
   `CORTEX_SWAP_DRAIN_TIMEOUT_S` (default 60 s). While draining and for the whole handoff,
   `admit` refuses with the typed `SubagentAdmissionError` ("pool draining for a model
   handoff") instead of queuing; the runner already degrades that to an `ok=False` result
   ([runner.py:152](../../brain/packages/core/src/cortex_core/runner.py)). Refuse, not queue,
   because a brain-phase spawn queuing on a drained pool until swap-back would deadlock the
   turn against its own drain. On timeout (one wedged CPU stream is a real hazard, given the
   deliberate `read=None` client): **abort the handoff before anything is evicted**, mark the
   record `FAILED`, tell the user, and continue on the cortex.
3. **Swap in.** Enter the residency scope (decision 5): wait for the GPU lease to fall free
   (the swap never preempts a mid-stream round in v1), then `stop(cortex)`, `stop(gpu
   subagent)` if hosted, `start(brain)`, and health-gate by polling `status(brain)` until
   `READY`, bounded by `CORTEX_SWAP_LOAD_TIMEOUT_S` (default 300 s; an 18 GB GGUF off the
   drvfs mount at the measured ~150-180 MB/s is minutes, ADR-0004). Record state →
   `BRAIN_ACTIVE`. On `FAILED` status or timeout (VRAM short, CUDA OOM at load, dead
   sidecar): best-effort `stop(brain)`, `start(cortex)`, health-gate, mark `FAILED`, report
   honestly on the stream. If the cortex restore itself fails: retry once, then surface
   `ready=false` on `Health` with a loud log; the runbook owns manual recovery, and the
   compose `restart` policy revives a dead sidecar whose boot default is cortex-up.
4. **Rehydrate and run.** Reload history from `SessionStore` (windowed as usual), rebuild the
   working set as preamble + recalled context + history + the record's `loop_tail`,
   reconstruct the `TaintLedger` from the record, resume the carried budget, and run the
   shared `stream_tool_loop` against model id `brain` with the same audited dispatcher, the
   guardrail seeded with the record's URL evidence, and a fresh rounds allowance (the budget
   is the spend bound and it carried; salience is per-loop by design, and a cross-swap repeat
   costs budget but is not refused, a bounded residual this ADR accepts).
5. **Persist.** The brain's reply is appended as an assistant message under the same
   `turn_id`; a brain-phase memory record is written under the same taint policy the engine
   applies.
6. **Swap back.** Scope exit (a `finally`, so crash-or-success): `stop(brain)`,
   `start(cortex)`, health-gate, record → `DONE`, then delete. A mid-work brain crash
   (`InferenceError` from a dead server) persists the partial text with an honest failure
   note, exactly the runner's parts-so-far discipline, then converges the same way.

**Boot recovery** (wiring startup): read `HandoffStore.active()`; any non-terminal record is
marked `FAILED` (kept under TTL for diagnosis), and residency is converged: `status` each
hosted model, stop a running brain, ensure the cortex is `READY`. v1 deliberately does **not**
auto-resume a brain phase after a crash: without a request-identity/dedup design, replaying
risks double-running side-effectful work, the exact hazard the seam-transport reconnect entry
sharpened. Resume-from-record is the recorded refinement, unlocked by that same dedup design.

### 5. Who orchestrates: a core conductor over an additive residency scope; `acquire` unchanged

Three pieces, all explicit typed code in the core, composed at the orchestrator's root:

- **`SwappingModelManager`** (core, pure policy over the injected `ModelHost` port) implements
  the unchanged `ModelManager` protocol: `acquire(model)` leases the resident model's endpoint
  under the same single `asyncio.Lock` discipline as today. It additionally implements a new,
  segregated **`ResidencyController`** protocol: `swap_scope(model)` is an async context
  manager that waits for the lease to fall free, performs the process swap via `ModelHost`,
  serves the new resident for the scope's duration, and on exit (in a `finally`) restores the
  cortex. While a scope is active, `acquire` of a non-scope model **waits** instead of
  raising, so a queued cortex turn on another stream blocks until restoration rather than
  failing; outside any scope, non-resident `acquire` raises `ModelUnavailableError` exactly as
  v1 does. The endpoint map (logical id → URL) is composition-root config.
- **`SwapConductor`** (core) owns decision 4's sequence, composing `HandoffStore` +
  `SubagentScheduler.drain` + `ResidencyController` + `ModelHost` status polling + a `Clock`
  for the two timeouts. Per ADR-0012, drain is composed here, never merged into a port.
- **`EscalatingTurnEngine`** (core) wraps the plain engine: per turn it builds the
  `EscalationSlot`, constructs the inner `TurnEngine` (engines are stateless and per-stream
  construction is free, [converse.py:61](../../brain/packages/orchestrator/src/cortex_orchestrator/converse.py)),
  delegates `handle_turn`, suppresses the inner `TurnCompleted` when the slot was filled, runs
  the conductor's phase 2, and emits the real `TurnCompleted`. The servicer's `EngineFactory`
  wires the wrapper only when escalation is enabled (`CORTEX_ESCALATION`, default off), so CI
  and the GPU-less loop are byte-identical to today.

The rejected alternative is the one ADR-0012's consequences sketched in passing: **`acquire`
itself performs the swap** (acquiring a non-resident model evicts and loads). It thrashes by
construction: the brain's tool loop re-acquires per round, so any interleaved cortex `acquire`
(a queued turn on a second stream, a ticker-driven pass) would swap back mid-task and the
brain's next round would swap again, minutes each way. The scope is the second coordination
primitive that makes eviction interact with in-flight streams safely: swaps happen only at
lease-free boundaries, exactly once per handoff, and mid-stream preemption stays a recorded
refinement (it is also the named trigger for the reconnect-dedup and real-abort backlog
entries, which this ADR leaves where they are). `acquire`'s signature and its
one-lock-per-GPU semantics survive untouched, which is what ADR-0012 decision 1 requires.
Also rejected: **the conductor in the orchestrator package** (it is orchestration policy, the
exact thing AGENTS.md pins to the core; the orchestrator contributes only wiring), and
**widening the `ModelManager` port itself with `swap_scope`** (every existing implementation
and fake would grow a method only one object meaningfully implements; interface segregation,
same argument as ADR-0012 decision 1).

### 6. What the user sees: one turn, one stream, and an honest `Health`

The handoff happens **inside the escalating turn**, on the stream the user already holds.
The cortex's short pre-handoff text (whatever it streamed before calling the tool, plus its
wrap-up after the confirmed call) arrives as normal deltas and persists as its assistant
message; the wrapper then yields `StatusUpdate` events (`state="swapping"`, with the wire
`state` being a free string the overlay already renders as a chip) through drain, load, and
health-gate; the brain's reply streams as the same turn's continued `TextDelta`s and persists
as a second assistant message under the same `turn_id`; `TurnComplete` fires once, at the
true end. No proto change: every event shape already exists on the seam. The confirm card
rode the existing ADR-0022 flow during the cortex phase. This fits the body's
one-turn-per-call reality: the stream stays open because the turn genuinely is not finished.

`Health` becomes honest, the producer the streamed-brain-status deferral waits on:
the servicer reads the manager's synchronously-cached residency state and answers
`ready=false` with a truthful `detail` ("swapping: loading the deep model", "deep task in
progress", "restoring the cortex") whenever the cortex is not the serving resident;
`ready=true` otherwise, unchanged. The overlay's landed indicator already classifies that
as amber Degraded with zero overlay work. The **push** half (a server-streamed status RPC)
stays deferred: the probe-on-summon plus the escalating stream's own `StatusUpdate`s cover
personal scale, and a push channel is a seam change that should be designed with its
consumer. Its blocker is now met, so it graduates from "blocked on Slice 11" to actionable
in its area doc when this lands.

Rejected: **ending the cortex turn and having the brain answer in a new turn** (there is no
stream to carry a server-initiated second turn on a one-turn-per-call body; it would push a
body/proto change into the capstone for no user-visible gain); **swapping inside the
`escalate_to_brain` dispatch itself** (the loop would resume the cortex model mid-loop with
the brain resident; the loop boundary is where the model id can change cleanly).

### 7. The chaos test: parameterized kill points over fakes in CI, the real kill on the host

**CI half (the gate).** A parameterized suite over the fake `ModelHost`, fake stores, and the
scriptable conductor, with a kill injected at every step boundary of decision 4:
after-snapshot, mid-drain, after-drain, after-cortex-stop, brain-start-fails,
health-gate-times-out, mid-brain-stream (task cancellation, the process-death analogue for
the consumer side), after-brain-persist, cortex-restore-fails-once, and during-swap-back.
For every kill point it asserts convergence and no state loss:

- the conductor's exit path requested `start(cortex)` and the fake host ends with the cortex
  as the only running model;
- the scheduler is admitting again (drain always released);
- the stores are intact: the user message and every persisted result are present, no partial
  brain reply is persisted as a completed one, and the handoff record is terminal
  (`DONE`/`FAILED`), never live;
- the stream ended honestly: either a completed turn whose text says what happened, or a
  terminal `SeamError`; never silence.

Distrust-green, per AGENTS.md: after wiring, the suite is proven fallible by mutation
(removing the scope's `finally` restore, or skipping the record transition before the swap,
must redden named cases; the proofs are noted in the tests as the lease-release test did).

**Host half (host-side, runbook-driven).** On the 24 GB machine: `docker exec` into
`model-host` and `kill -9` the brain's `llama-server` child mid-handoff (and once mid-load),
then verify from the overlay that the turn fails honestly, the cortex comes back, and the
next turn works; procedure and expected timings recorded in `docs/runbooks/model-swap.md`.
Stated plainly: **CI has no GPU and the dev machine's 8 GB card cannot hold the 12B cortex
and a ~31B brain, so the tier-scale swap can only be validated host-side; the CI chaos test
over fakes is the gate.** The mechanism itself (real processes started, killed, health-gated,
swapped) is agent-validated in Docker on the dev GPU with two small artifacts standing in
for the tiers, which exercises every code path except the VRAM arithmetic.

### 8. VRAM arithmetic: the brain runs alone, and the handoff window suspends the soft cap

From ADR-0004's measurements: the cortex is ~11.3 GB at 16K ctx (11.0 weights + 0.3 mmproj);
the soft cap is 14 GB, leaving ~2.7 GB headroom, which the E4B's 5.5 GB ask deliberately
overflows, so today's GPU carries the cortex and nothing else. Every brain candidate is
15-18 GB of weights plus KV: **no candidate fits beside the cortex in 24 GB (11.3 + 15 > 24),
and none fits under the 14 GB soft cap alone at full offload.** Therefore the swap evicts
BOTH the cortex and any GPU-placed subagent, and the v1 co-residency rule is: **while the
brain is resident, it is alone on the GPU.** CPU subagents hold no VRAM but are drained
anyway (decision 4): the brain's hybrid-offload fallback and its KV want the host RAM/CPU
headroom, and "brain runs alone" is one invariant instead of three special cases.

The handoff window is a deliberate, user-confirmed exception to the 14 GB soft cap: the brain
takes the whole GPU for the duration (the cap governs the standing AI stack the user games
beside, and nobody games mid-handoff having just clicked the card). `CORTEX_NGL_BRAIN` and
`CORTEX_CTX_SIZE_BRAIN` remain the deployment levers to pull it under any budget, costing
zero core change (ADR-0004's placement logic). Recorded refinements, not v1: co-residency
(keeping CPU subagents serving through a swap; brain + tiny GPU subagent on a larger card),
and placement-aware charging, which reopens with a second GPU-capable executor per its
ADR-0012 addendum.

### 9. Implementation slicing: seven vertical slices, each green and committable

1. **S11.a, the record.** `HandoffRecord` + `HandoffStore` port + core fake + contract test +
   Redis adapter in `cortex_session`; the tainted-ledger round trip pinned. No behavior
   change anywhere.
2. **S11.b, drain.** `SubagentScheduler.drain()` on the port, implemented by
   `ResourceBudgetScheduler` (drain-refuses-admission semantics + timeout), contract-tested
   against fake and real impl alike.
3. **S11.c, the trigger.** `escalate_to_brain` + `EscalationSlot` threading through
   `ToolLoopContext`/`TurnStamp` + the per-tool gate reason + the opaque-turn and
   tainted-turn refusals; any engine line-cap pressure resolved by the planned mechanical
   split of the turn-context assembly.
4. **S11.d, the conductor.** `SwappingModelManager` + `ResidencyController` +
   `SwapConductor` + `EscalatingTurnEngine`, all pure over the fake host, plus the full
   chaos suite (decision 7). The hard rule is CI-proven here, before any real process exists.
5. **S11.e, the real lifecycle.** The `cortex_model_manager` package (daemon + HTTP
   `ModelHost` adapter), the compose revision (model-host supersedes `llama-cortex`; the GPU
   subagent sidecar + cgroup caps land per ADR-0012's host half), `integration`-marked live
   tests, the CUDA-OOM one-shot CPU re-run in the runner, and the agent-side two-small-models
   swap validation on the dev GPU.
6. **S11.f, honesty surfaces.** `Health` residency state + the swapping `StatusUpdate`s;
   overlay untouched by design.
7. **S11.g, host-side capstone.** The brain pick (ADR-0004 gains its addendum), the live
   tier-scale swap + chaos kill on the 24 GB machine, measured swap timings,
   `docs/runbooks/model-swap.md`, and the ~31B injection-harness run
   (`CORTEX_PROBE_BRAIN=1`), whose result feeds back into decision 1's tainted-escalation
   stance.

## Where each "Blocked on Slice 11" backlog entry lands

The four entries under "Blocked on Slice 11" in
[docs/refinements/index.md](../refinements/index.md), mapped; none is closed by this ADR
(nothing lands with a design), and the area docs are updated only as slices deliver.

- **Model-manager process lifecycle, co-residency, and the real swap**
  ([inference-model-manager.md](../refinements/inference-model-manager.md)): lifecycle and
  the real swap are decisions 3-5 (S11.d/e). **Co-residency stays deferred** (decision 8
  records the v1 brain-runs-alone rule and the refinement's shape).
- **`SubagentScheduler.drain()`, CUDA-OOM re-place, the real GPU-placed runtime**
  ([resource-governance.md](../refinements/resource-governance.md)): drain is decision 4 /
  S11.b with refuse-not-queue semantics; the GPU-placed runtime and cgroup caps land in
  S11.e inside the model-host; CUDA-OOM re-place lands in S11.e as a single CPU re-run after
  a GPU-placed failure, recorded in the result's detail. **Placement-aware CPU charging stays
  declined-as-recorded**; its reopening condition (a second GPU-capable executor) is noted in
  decision 8 but not built.
- **Taint/provenance persistence across a mid-turn swap, and the ~31B injection-harness run**
  ([untrusted-content.md](../refinements/untrusted-content.md)): the persistence is decision
  2's record schema (S11.a) exactly as the entry flagged ("provenance rides on the stored
  tool-step context"); the harness run is S11.g, user-hardware, and gates any future
  relaxation of the tainted-turn escalation denial.
- **Streamed brain status** ([body-overlay.md](../refinements/body-overlay.md)): decision 6
  delivers the *producer* (`Health` earns `ready=false` between turns, with truthful detail),
  which is the entry's named blocker. **The push stream itself stays deferred**: the landed
  probe-on-summon indicator plus the escalating stream's own status events cover personal
  scale, and a push RPC is a seam change to be designed with its consumer. When S11.f lands,
  the entry moves from "blocked" to actionable in its area doc.

Adjacent entries this slice deliberately does not deliver, but whose recorded triggers it
meets: safe `converse` reconnect dedup and the real Stop/abort
([seam-transport.md](../refinements/seam-transport.md),
[body-overlay.md](../refinements/body-overlay.md)) both name "mid-turn compute becomes
expensive/evictable under the real swap" as their trigger. v1 never evicts mid-stream
(decision 5), so the pressure arrives with usage, not with this design; they stay
fix-when-it-bites with their triggers now live.

## Consequences

- New core modules: `handoff.py` (record + slot), the `ModelHost`/`ResidencyController`
  ports + `SwappingModelManager`, `SwapConductor`, `EscalatingTurnEngine`, and their fakes;
  new `cortex_model_manager` workspace package (daemon + adapter); `cortex_session` gains the
  Redis `HandoffStore`; compose gains the model-host revision. Module contract docs land with
  each slice, per the doc-first DoD.
- Config gains, all at the composition root: `CORTEX_ESCALATION`, `CORTEX_MODEL_BRAIN`,
  `CORTEX_MODELHOST_ENDPOINT`, `CORTEX_BRAIN_ENDPOINT`, `CORTEX_SWAP_DRAIN_TIMEOUT_S`,
  `CORTEX_SWAP_LOAD_TIMEOUT_S`, `CORTEX_MODEL_FILE_BRAIN` / `CORTEX_NGL_BRAIN` /
  `CORTEX_CTX_SIZE_BRAIN` (model-host env), and the per-tool gate reason knob.
- CI stays GPU-less and green at 100% both toolchains: everything real is behind `ModelHost`
  and `integration`-marked; the chaos suite over fakes is the gate that proves the hard rule.
- The escalating turn makes long-lived `Converse` streams normal (minutes, not seconds);
  the loopback seam and the credit-bounded buffer already tolerate that, and no timeout on
  the seam path assumes short turns today.

## Risks flagged for maintainer review

1. **The gated-escalation default** trades away "escalate about untrusted content" until the
   ~31B harness run exists. If that is too restrictive in practice, the alternative (ungated
   tool + internal taint refusal + card kept for consent) weakens nothing else; it is a
   config-plus-one-check change by design.
2. **The model-host sidecar** is a new privileged-ish component (GPU + models mount + process
   control). Its API is compose-network-only and it holds no secrets, but the user may
   prefer the docker-socket controller shape despite the host-root argument in decision 3.
3. **Swap latency is unmeasured for the brain tier.** The 300 s default load timeout is an
   estimate from ADR-0004's mount-read numbers; if the real figure is worse, the
   fix is the recorded WSL-side model mirror lever (ADR-0005 consequences), not a design
   change.
4. **Two assistant messages under one turn id** (cortex wrap-up + brain reply) is new for
   history readers; the stores append happily and the overlay renders sequential messages,
   but any future per-turn aggregation must not assume one reply per turn.
5. **Brain-phase tools carry the cortex's dispatcher unchanged**, including spawn (which
   drain refuses for the window). If the user prefers a tool-less or narrower brain phase
   for v1, it is a wiring choice at the composition root, not a design change.

## Addendum (2026-07-17): the trigger sub-slice landed; the opaque-turn refusal moved to the vision slice

The escalation trigger landed as designed with one sequencing correction. This ADR's context
said "this slice lands after the vision slice", but the repo sequenced the handoff sub-slices
ahead of ADR-0029, which remains designed and unimplemented: `Message` carries no pixels and no
`opaque` bit exists. The trigger sub-slice's opaque-turn refusal therefore has nothing to check
today, and a stand-in check would be a gate that cannot fail (AGENTS.md, distrust green). It is
recorded as a deferred refinement in `docs/refinements/untrusted-content.md` (indexed under
"actionable, but a seam change comes first") and lands with the vision slice's pixel-taint
increment, as decision 1 specifies: the handoff record already refuses what the session stores
refuse, and the tool then answers an image-bearing turn with a typed refusal telling the model
to ask the user to retry in a fresh message.

What landed, versus this ADR's shape, with no other deviation:

- `escalate_to_brain` (`cortex_core/escalate.py`) is a stateless gated built-in; the slot rides
  each dispatch's `TurnStamp` (the spawn progress-sink isolation discipline), the tool writes
  only `slot.brief` (stripped, bounded at `MAX_BRIEF_CHARS` 4000, refused whole rather than
  truncated), and its success text tells the model the handoff is queued for the loop boundary
  and to wrap up without further tools, which is exactly decision 6's cortex wrap-up phase.
- `EscalationSlot` grew the armable shape decisions 2 and 5 jointly require: the wrapper builds
  it empty before the turn exists, and the engine arms `refs` (an `EscalationRefs` bundle:
  working list, ledger, nonce, shared budget, pre-loop `base_len`) at turn start, threaded via
  `TurnCapabilities.escalation` and `ToolLoopContext`/`TurnStamp`. `snapshot()` refuses an
  unarmed or unfilled slot. The conductor sub-slice consumes this seam unchanged.
- The per-tool gate reason landed as `DispatchPolicy.gate_reasons` flowing into
  `ConfirmationRequest.reason`, with the config knob (`CORTEX_TOOLS_GATE_REASONS__<name>`)
  beside `CORTEX_TOOLS_GATED` as decision 1 specified, the built-in escalate card text merged
  under the user's (the cost-policy merge precedent), and `escalate_to_brain` added to the
  default gated backstop (the `send_email` fail-closed pairing).
- The tool is deliberately not yet registered in the wiring's built-in set: without the
  escalating wrapper (the conductor sub-slice, which builds the per-turn slot and is gated by
  `CORTEX_ESCALATION`), an advertised escalate tool could only ever refuse, a dishonest
  advertisement. Registration arrives with that wrapper.

## Addendum (2026-07-17): the conductor sub-slice landed; what it decided where this ADR was silent

The conductor sub-slice (decision 9 item 4) landed as designed: the `ModelHost` port and its
scriptable twin, `SwappingModelManager` with the segregated `ResidencyController`, the
`SwapConductor` running decision 4's sequence, the deep model's phase, boot recovery, and the
`EscalatingTurnEngine` behind `CORTEX_ESCALATION`, plus the full chaos suite of decision 7. The
hard rule is now CI-proven before any real process exists, which is what this sub-slice was for.
Stated plainly, because the ADR already says it and it stays true: **no real model swap has been
validated.** Everything here runs over the scripted host, which starts no process and moves no
weights, and the dev GPU (8 GB) cannot hold the 12B cortex beside a ~31B brain, so tier-scale
validation remains host-side and the real supervisor adapter remains the next sub-slice.

Decision 4's sequence, decision 5's three objects, and decision 6's one-turn shape landed
unchanged. What follows is the decisions this ADR left open, made here rather than left to
whoever reads the code next.

**Two additions to the ports.** A `Sleeper` port (`async sleep(seconds)`) joins `Clock`, because
decision 4's health gate polls and `Clock` can bound a wait but cannot perform one; the core may
not reach for `asyncio.sleep` itself, or every test of the gate would be a real-time test. The
body side has had the same port since the transport's retry backoff, so this is a seam the repo
already speaks. And `EngineFactory` widens from the concrete `TurnEngine` to a new `TurnRunner`
port, because the escalating wrapper is the other implementation; the alternative was subclassing
the engine, which would have made a wrapper pretend to be the thing it wraps.

**One additive change to a landed value type.** `DispatchBudget.resume(*, remaining, closed)`
rebuilds a pool at a persisted position, which decision 4 step 4 requires ("resume the carried
budget") and the constructor could not express. What was already spent is deliberately not
carried as a number: nothing reads it, since a refusal depends only on whether the next call fits
and whether the pool is closed.

**Where the sequence's collaborators live.** Decision 5 lists the conductor's collaborators, but
steps 4 and 5 need more than that list (a session store, a backend, the audited dispatcher, the
window, the guardrail, the recaller). They are bundled into a `BrainPhase` use-case the conductor
drives, built per stream at the composition root so the deep model runs THIS stream's dispatcher.
The engine's output half (delta-to-event mapping, channel flushing, the tainted-memory policy)
moved into a shared `turn_output.py` that both phases use, so the two cannot drift apart.

**Six interpretations, each chosen for the fail-safe direction.** A second concurrent handoff is
refused with an honest note and no eviction (decision 2 makes `active()` checkable; one GPU means
one handoff). The deep phase carries **no** escalation slot, so the deep model cannot escalate to
itself and the built-in refuses honestly. The outer `TurnCompleted` carries the whole turn's text
(cortex wrap-up plus deep answer), which nothing on the wire reads but which is the only honest
answer for an in-process consumer. Failure notes are streamed but not persisted as messages of
their own, with one exception: the deep model's partial text and its failure note are persisted
together, because there the note explains text the user can see in their history. A clean handoff
ends `DONE` then deleted, every failure ends `FAILED` and is kept under the store's TTL, so "the
record is terminal, never live" is asserted as `active() is None` plus a terminal last write. And
`HandoffState.PENDING` still has no producer: `snapshot()` emits `READY` directly, and inventing
a `PENDING` write to exercise the enum would have been a test that proves nothing.

**The model-host backend is named for what it is.** Enabling `CORTEX_ESCALATION` requires
`CORTEX_MODELHOST_BACKEND` and `CORTEX_BRAIN_ENDPOINT`, or boot fails: without a host nothing can
evict or load a model, so the escalate tool could only ever refuse, which is the same dishonest
advertisement the trigger sub-slice withheld registration over. Today the only backend is
`scripted`, the in-core fake, documented as starting no process; the real supervisor adapter
arrives as a second value. `CORTEX_SWAP_EVICT_MODELS` exists but is empty by default, since no
GPU-placed subagent is hosted until that same sub-slice.

**Two defects the chaos suite found before anything shipped**, which is what it is for. A kill
during the record's first write stranded a live record, and `active()` would then have refused
every later handoff until a restart; the record's failure guard now covers that write too. And a
cancellation during the swap back abandoned the restore midway, leaving the process with no
resident model and every later turn failing; the restore now runs as a shielded task that a
cancellation waits for, because the swap back is the recovery path and not an optimization. The
cost of that fix (a disconnect mid handoff holds the stream's teardown until the cortex is back)
is recorded in `docs/refinements/seam-transport.md`.

**Slicing correction, and one deferral this creates.** Decision 9 item 6 bundles the swapping
`StatusUpdate`s with the honest `Health` into the honesty-surfaces sub-slice, but decision 6
describes the wrapper yielding them and decision 7 asks the stream to say what happened, so they
landed here: they need no proto change and the alternative was a swap window that says nothing.
The `Health` half is untouched (the servicer still answers `ready=true` unconditionally), which
is what that sub-slice now delivers on its own; decision 4 step 3's "surface `ready=false` with a
loud log" is therefore the loud log alone for now. The streamed-brain-status backlog entry is
updated to say exactly that. Two further deferrals are recorded with it: resuming a crashed
handoff from its record (`docs/refinements/inference-model-manager.md`), which this ADR names and
which needs the request-identity design the reconnect entry also needs, and the drain bound
sitting below a fired task's schedule lease (`docs/refinements/resource-governance.md`), which
makes an escalation during scheduled work abort every time under the shipped defaults.

## Addendum (2026-07-18): what the chaos proof was not proving, and the two contracts that fixes

An adversarial review of the landed conductor found the proof weaker than its own docstring
claimed, and one real concurrency defect behind it. Nothing about decisions 1 to 9 changes; what
follows is the two places this ADR was silent, decided here rather than left to the next reader,
plus the holes closed in the gate itself. **Still no real model swap has been validated:**
everything below runs over the scripted host on an 8 GB dev GPU, exactly as the previous
addendum says, and tier-scale validation remains host-side.

**The single-handoff precondition is a claim, not a read.** Decision 2 makes `active()`
checkable and the previous addendum said a second concurrent handoff is refused with an honest
note. The conductor implemented that as a store read followed, two awaits later, by a write.
Over a store whose verbs suspend (Redis's do; the in-memory fake structurally cannot exhibit it)
two escalating turns on separate streams both pass, and the loser then runs the drain prologue
and reopens subagent admission in its own `finally` while the winner's deep model is resident,
contradicting decision 4 step 2 and decision 8 at once. The rule therefore moves to where the
GPU's other invariants already live: `ResidencyController` gains `handoff_claim()`, a
non-blocking claim the conductor takes **before** anything is read, written, drained, or
evicted, whose check and set have nothing awaited between them. The store check stays as the
second line of defence, for a record the store still holds after a failed settle or from
another process. Losing the claim is not a swap failure and must not be reported as one: the
new `HandoffInProgressError` (a `ModelManagerError`, raised by the claim and by a second scope
entry, which previously raised `SwapFailedError`) carries the note that says a handoff is
already running, because at that moment the deep model IS loaded and the usual assistant is
NOT back, which is the opposite of what the swap-failure note asserts.

**Convergence means the standing residency, not the cortex alone.** Decision 8 has a swap evict
the cortex and every other hosted tier, and decision 4 step 6 restores "the cortex". Nothing
restarted the evicted tiers, ever, while `undrain` reopened the pool to spawns that would be
placed on them. The contract is now explicit and pinned: the standing residency is the cortex
plus every `evict_models` tier, the residency scope's `finally` restores all of it (the cortex
gated first, the tiers started back after, best effort, since a tier that will not come back
must not be reported as the cortex being gone), and boot recovery converges the same way,
clearing the GPU first and starting the tiers back last. This changes no shipped deployment,
`CORTEX_SWAP_EVICT_MODELS` being empty until the real lifecycle sub-slice, which is exactly why
it had to be decided now rather than discovered then.

**What the gate was not proving**, each now closed and each proven fallible by mutation:

- the "mid-drain" kill point never killed during a drain: it paused before the refusal window
  opened, so it tested the same system state as "after-snapshot". It now parks an admission,
  opens the real window, and pauses inside it, with a separate case asserting the boundary
  (admission refused, work in flight, nothing evicted) so it cannot silently regress again;
- the fourth invariant ("the stream ended honestly") asserted nothing at all for a cancelled
  case, and justified that with a citation to a cancellation proof that does not exist. Status
  details are now asserted as an ordered prefix of the swap window, with "the deep model is
  working on this" witnessed against the record and the host's op log, so a status yielded
  before the residency scope is entered reddens; the false citation is replaced by a plain
  statement of what a cancelled case does not prove;
- "the stores are intact" never covered durable memory (the harness's capabilities carried no
  recaller, so the memory write was a no-op in every case). It does now, strictly for a
  completed handoff and as "either the exchange or nothing" for a killed one;
- teardown by **closing** the stream, which is how the seam tears a turn down when a client
  goes away, was untested at three of its four sites, all of which a cancellation-only suite
  cannot discriminate. There is now a close case at the conductor, at the wrapper, and at the
  deep phase;
- the rehydrated fence nonce, the resumed budget, and the carried taint ledger are now asserted
  on what the run did rather than on values recomputed beside it;
- the swap window's four status strings were asserted by a count; they are asserted in order;
- taint through a swap, and the lease-free swap boundary, are now inside the chaos suite rather
  than only in unit tests elsewhere.

## Addendum (2026-07-18): settling a handoff and releasing its claim are two different writes

A second adversarial pass over the repaired conductor found three defects, two of them in the
places the previous addendum had just declared fixed. Nothing about decisions 1 to 9 changes.
**Still no real model swap has been validated**, for the same reason as before: the scripted
host starts no process, and the dev GPU cannot hold these tiers.

**The honest note was only half wired, and the docs were the half that lied.** The previous
addendum decided that `HandoffInProgressError` carries the note saying a handoff is already
running, and the error's own docstring, the port, and the module doc all said so. The
conductor's mapping did not: it answered the swap-failure note for everything that was not a
failed restore. So the one path that error can still reach, the residency scope's backstop guard
for a caller that swapped without claiming first, told the user that the deep model could not be
loaded and the usual assistant was back, at the exact moment when the deep model WAS loaded and
the cortex was NOT back. Both halves of that sentence were false. The mapping now names the
refusal, and it moved to `swap_notes.note_for` so it lives beside the strings it chooses
between; the test drives the backstop path itself (a scope held open while a handoff runs)
rather than asserting the mapping in isolation.

**The claim's release is not conditional on the settling write landing.** The store's active
pointer is taken by the `READY` write and given back by the settling write or by a delete, and
the conductor did both inside one `try`. One transient refusal of the write that settles a
finished handoff therefore skipped the delete, and the finished handoff went on holding the
pointer: `active()` answered it, and every later escalation in that process was refused with a
note claiming a handoff was in flight when none was, until a restart. Non-terminal records carry
no TTL by design (boot recovery must find them), so nothing expired it either. The contract is
now explicit: a **terminal** state the store refuses is followed by deleting the record, because
a diagnosis copy the store would not update is worth less than the escalation path it wedges,
and the refusal is logged loudly with the handoff id and state, which is where that diagnosis
now lives. A refused **intermediate** write keeps its record, the handoff being genuinely still
live there, and boot recovery settles it. When the delete is refused as well, nothing in the
process can free the pointer, so the log says exactly that and `docs/runbooks/model-swap.md`
carries the recovery. The chaos suite gained the kill point it had at no boundary at all, a
store that fails, at both settles, and its last assertion is the one that catches the wedge: a
LATER escalation still runs.

**A kill point the harness opened for itself.** The mid-drain case parked an admission and then
set the pool's own draining flag by hand before pausing, and the case's headline assertion read
that same flag back. It constrained nothing: with the pool's `drain` mutated to stop opening the
refusal window at all, the case still passed. The straggler now waits on the pool's condition
until the real `drain` closes admission around it, and only then fires the gate, so the handoff
is suspended inside the real drain and every assertion at that boundary reads state the pool set.
The same mutation now reddens both mid-drain cases. This is the third instance in this sub-slice
of an assertion satisfied by its own harness, which is worth naming as a species: a kill point
whose boundary is staged rather than reached proves nothing about the code that reaches it.

## Addendum (2026-07-18): the single-handoff claim binds one process, and that is now recorded

A verification pass over the repaired conductor found no new correctness defect but did find an
undocumented deferral, which under the doc-first Definition of Done is itself a gate violation.
Nothing about decisions 1 to 9 changes, no behaviour changed with this note, and **still no real
model swap has been validated**.

**What is actually true.** The one-handoff rule the previous addenda lean on is
`SwappingModelManager.handoff_claim`, and its state is `self._handoff_claimed`, an attribute on
one manager instance; `_begin_scope`'s backstop is the same object's `_scope_model`. Both
therefore bind exactly one process. The store-side check this ADR describes as the cross-process
guard is `active()` read in `SwapConductor._prepare` and the record written by `_persist_snapshot`
two awaits later, which is a check followed by an act, not a claim: two brain processes sharing
one Redis could both read "no handoff in flight" and both proceed to evict the cortex. The Redis
adapter says as much in its own module docstring (the read-then-write verbs are unfenced
"because the conductor is the store's one writer by construction"), so the design knew; the
backlog did not, and that is what is fixed here.

**Why it is not a live defect.** The deployment runs exactly one brain process (one `brain`
service in `docker/docker-compose.yml`, no replicas) holding one manager, so the in-process claim
covers the entire population of claimants and the store check is a backstop for a second process
that does not exist yet. Every consequence of losing either guard also stays honest: the loser is
refused before anything is drained or evicted, and it is told a handoff is already running rather
than that the swap broke.

**What would close it**, and it is not a small change behind the unchanged port. `put` cannot
express "write this record only if no handoff is active", so the port gains a fenced claim verb
answering whether it took the pointer. The Redis side is an atomic `SET cortex:handoff:active
<id> NX`, issued before the record write or as a Lua script, because a MULTI/EXEC transaction
cannot branch on an intermediate reply. It also needs an expiry story: a fenced claim held by a
process that then dies would wedge every other process's escalation until someone cleared the key
by hand, where today a stranded non-terminal record is deliberately TTL-free and settled by the
next boot recovery. So the claim wants a lease (a TTL plus a heartbeat while the handoff runs) or
a user id that lets recovery tell its own strand from another process's live handoff. Then the
in-memory fake carries the same semantics, the contract suite gains a two-concurrent-claimants
case, and `_prepare` calls the claim instead of `active()`, keeping the refusal note it has now.

**Trigger:** a second process that can swap. A second brain replica, a CLI or worker sharing the
same Redis, or a supervisor sidecar that performs swaps itself. Recorded in
[docs/refinements/inference-model-manager.md](../refinements/inference-model-manager.md) and its
[index](../refinements/index.md).
