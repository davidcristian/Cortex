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
messages the same way the session stores do, and the user is told to ask again in a fresh message.
Escalating an `opaque` turn would otherwise quietly widen pixel persistence, which that ADR
explicitly reserved as its own deliberate decision. (Where that refusal belongs was corrected on
2026-07-19; see this ADR's addendum. It is the gate plus the conductor, not the tool.)

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

**Closed 2026-07-18** with the vision slice's pixel-taint increment. `TaintLedger` carries an
`opaque` bit, and `EscalationSlot.snapshot` raises on an image-bearing loop tail exactly as both
session stores do. One correction to what this ADR's decision 1 assumed: the refusal keys on the
bit rather than on image-bearing messages, because the handoff record's message codec enumerates
fields by name and would have dropped `Message.images` on encode, so a check that hunted for
images in the tail would have been checking the one thing that cannot survive a swap.

**Corrected 2026-07-19** by the vision slice's audit, because the refusal had been put in the
wrong place and closed the deferral with the very defect it was recorded to avoid. Inside
`EscalateToBrainTool` it could never fire: `TaintLedger.observe` cannot mark a turn opaque without
marking it tainted, this spec is `gated=True`, and the dispatcher hard-denies a gated call on a
tainted turn before `invoke` runs, so **the taint gate this ADR already leaned on is what closes
the capture-then-escalate ordering**, with `DENIED_MSG` and the confirmer unconsulted. The
ordering nothing handled was the reverse one, which is reachable and was not: the handoff is
approved while the turn is still clean and the ungated capture lands afterwards, so the tail
carried an image by the time `snapshot` ran and the invariant's `ValueError` escaped
`SwapConductor._prepare`, propagated through `run_handoff` and the escalating engine, and killed
the Converse stream with no record written and nothing in a terminal state. The refusal now lives
in the conductor, on the same bit, answering `OPAQUE_TURN_NOTE` beside `ALREADY_ACTIVE_NOTE` and
`STORE_FAILED_NOTE`, so the turn ends with an honest sentence and a serving cortex; the dead check
in the tool is gone, and the snapshot raise is documented as the unreachable invariant behind it
rather than as a mechanism. The refusal is pinned end to end through the real tool loop, the real
tools and the real conductor, and deleting it (or moving a word of the note) reddens that test.
What the record still does **not** carry is the `opaque` bit itself, so `taint_ledger()` rebuilds
it at `False`: sound only because no opaque turn can reach a record now, and recorded as a
deferral in `docs/refinements/vision.md` with its index line, beside the pixels-across-a-swap
entry this ADR's sibling named.

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

## Addendum (2026-07-18): the swap back is uninterruptible, and a status is pinned to its work

A settling pass found one live defect and two places where the gate agreed with the code instead
of constraining it. Nothing about decisions 1 to 9 changes. **Still no real model swap has been
validated:** the scripted host starts no process, and the dev GPU cannot hold these tiers.

**One shielded wait is not "a cancellation waits for the restore".** The previous addendum
decided that the swap back runs as a shielded task a cancellation waits for, because the restore
is the recovery path. The implementation waited for exactly one delivery: it caught the first
`CancelledError`, awaited the restore, and re-raised. A second delivery lands on that await and
abandons the restore mid flight, which returns the residency scope while the cortex is still
stopped, and the conductor's `finally` then reopens subagent admission onto a GPU with nothing on
it and a subagent tier nobody has restarted. Two deliveries are what the seam actually produces:
`ConverseStream` cancels the in-flight turn from its pump when the client asks to stop, and again
from `events()`'s own teardown when the stream goes away, and a swap back takes minutes, so the
second arrives while the first is still unwinding. The contract is now what it always said:
`_restore_uninterruptibly` waits **per cancellation**, remembering the first and re-raising it
once the restore is genuinely done, so the ordering the scope promises (restored, then released)
holds however many times the turn is cancelled. The bound is the restore itself, not the number
of cancellations, and the cost is the one already recorded in
[seam-transport.md](../refinements/seam-transport.md): a teardown mid handoff waits for the
cortex. The conductor's `undrain` keeps its single `finally`, which already runs after the swap
generator's `aclose` and therefore after the restore; what was missing was never that ordering
but the guarantee underneath it, and the gate now holds both (hoisting the `undrain` above that
`aclose` reddens the close case).

**An order among four strings is not four true statements.** The window's statuses were asserted
as an ordered prefix of the four, which constrains them only against each other: three of them
could be emitted at any moment relative to the work they name and the suite stayed green, while
the helper's own docstring claimed a step could not be reordered. Each status now carries a
witness taken at the yield (the drains asked for, the host's op log, the record's written states,
the deep model's call count), and each is checked against the work it announces: the drain is
announced before the pool is quiesced, the load before the deep model is started, "working on
this" only after the health gate passed and the record reached `BRAIN_ACTIVE` and before the
model has been asked anything, and the restore after the deep model answered and before the
cortex is asked back. All four misplacements redden, in both swap suites; none of them changes
the order the old assertion read.

**The innermost teardown had no witness at all.** The conductor closes three generators on a
consumer that walks away, and the case named for that teardown asserted only the outermost two.
The deep model's own round is now asserted through the backend's `closed` flag, and the close
case runs with the deep model mid answer so all three are outstanding at once. Dropping that
`aclose` reddens it and nothing else in the suite.

## Addendum (2026-07-18): the proof claims only what was measured

A pass over the settled conductor for honesty rather than correctness. No production behaviour
changed with this note, nothing about decisions 1 to 9 changes, and **still no real model swap has
been validated**, for the reason every addendum above gives.

**Two assertions that could not fail.** The boot-recovery case asserted that recovery had neither
asked the deep model anything nor appended to the session, over a `recover_handoffs` that is
handed the store, the host and the plan and nothing at all it could run a turn with. No
implementation of that function could have made either line fail, so the "without double running"
half of the case's name was unbacked. Non-resumption is a property of the signature, recorded
here and in the refinement that would undo it, not something a runtime assertion adds to. What
the case proves instead is the consequence a crash-stranded record really threatens and that can
fail: it now escalates the same turn again after recovery and requires it to answer, having asked
the deep model exactly once, which reddens under a conductor that refuses a handoff because the
store still holds a record under that turn id. The case is renamed for that. The second assertion
was decorative, a `not in` on a value the preceding line had already pinned whole by equality to a
constant that does not contain it; the equality is what rules the note out, and the comment says
so rather than a line that cannot fail.

**A preamble that claimed more precision than it had.** The chaos suite's distrust-green block
said each mutation "reddened exactly the cases named". Re-measured one mutation at a time across
the whole `packages/core` suite, nine of the bullets understated, reddening cases they did not
name, either elsewhere in the chaos suite or in the conductor, residency, recovery and
drain-contract suites over the same production code; two of the four swap-window sub-claims
overstated instead, naming a wider population than actually reddens (a drain that timed out emits
no status at all under the "draining" mutation, a case killed between the deep model's answer and
the "restoring" status never emits that one, and four cases in the suite never check the window
at all). No proof is weaker than it was cited for, every
mutation still reddening the case it exists to pin, but "exactly" would have told a future agent
that a case is unconstrained when it is not. Each bullet now carries its measured package-wide
failure count and names the cases in its own file, and "and nothing else" where it appears was
measured across the package. Two counts had also drifted with the repairs above: dropping
`undrain` now reddens the mid-drain kill as well, the window's release being witnessed against
the residency running at that instant, and restarting nothing after the cortex comes back now
reddens the second-cancellation case too, that case evicting a tier.

**One piece of harness the suite does not pin.** The mid-drain straggler waits on the pool's own
condition until the real `drain` closes admission around it. Removing that wait leaves the whole
suite green, because the loop resumes the handoff into `drain` before the case can look either
way. It stays, a boundary that holds only by ready-queue order being no boundary, but its
docstring now says plainly that it is scaffolding rather than something the assertions pin.

## Addendum (2026-07-18): the reopening deferral is recorded where it was created

A closing pass over the conductor sub-slice. No production behaviour changed with this note,
nothing about decisions 1 to 9 changes, and **still no real model swap has been validated**, for
the reason every addendum above gives.

**A deferral with two of its three records is a gate violation.** The doc-first Definition of Done
asks for three: the area doc under `docs/refinements/`, its line in the refinements index, and a
dated addendum at the origin ADR. The last deferral this sub-slice opened, **admission reopening
even onto a tier the best-effort restart could not bring back**, had the first two and not the
third. It belongs here and not at ADR-0012 because both halves that create it are decisions of
this ADR: decision 4 makes restarting each `CORTEX_SWAP_EVICT_MODELS` tier deliberately best
effort, since a tier that will not come back must not be reported as the cortex being gone, so a
`ModelHostError` on that start is logged and swallowed; and the same decision's ordering runs
`undrain` after the swap generator's `aclose`, so admission reopens the moment the restore
returns, whether or not the tier came back with it. The `SubagentScheduler` port is untouched by
either half (`drain` and `undrain` behave exactly as the ADR-0012 addendum landed them) and the
fix below is residency state rather than a scheduler change. The sibling deferral this sub-slice
opened into the same area doc, the drain bound sitting under a fired task's schedule lease, is
recorded at this ADR for the same reason.

**What is actually true.** The drain window now lifts only after the residency scope has restored
the cortex and asked every evicted tier back, and each reopening is witnessed in the chaos suite
against what the host was really running at that instant. What the best-effort restart leaves is
the narrower case: the cortex is back, one tier is not, its failure is in the log, and the pool
starts admitting delegated work onto a subagent server that is not running. That run then fails at
its backend and degrades to an `ok=False` "refused before running" result, which is honest but
wasteful, and nothing retries the tier until the next handoff or a restart.

**Why nothing is at stake today.** `CORTEX_SWAP_EVICT_MODELS` is empty by default and no
GPU-placed subagent tier is hosted until the model-host sub-slice, so no tier is ever evicted and
there is nothing that can fail to come back.

**What would close it.** Not keeping the pool drained after a failed restart, which trades every
delegated run for the ones that would have gone to that one tier. It wants the residency state the
honesty-surfaces sub-slice introduces: a tier known to be down, so the placer skips it while
something retries the start, after which `undrain` can reopen unconditionally because admission no
longer implies that every tier is serving. **Trigger:** a deployment that evicts a tier at all
(`CORTEX_SWAP_EVICT_MODELS` non-empty over the real model host) and sees one refuse to restart.
Recorded in [docs/refinements/resource-governance.md](../refinements/resource-governance.md) and
its [index](../refinements/index.md).

**Two more assertions that could not fail, and one comment that read as a claim.** The species this
sub-slice kept producing, an assertion satisfied by the harness rather than by the code, cost two
more lines. The pool-less deployment case asserted that the harness's scheduler had admitted
nothing and drained nothing, over a conductor constructed with `scheduler=None`, so no
implementation could have moved either number. What that deployment really constrains is asserted
instead: the sequence still reaches a deep answer and a `DONE` record, which is the drain step
answering "nothing to quiesce" rather than aborting, and the window still announces the quiescing
it has nothing to perform, as all four details whole rather than as the prefix the per-status
witness checks (dropping the last status reddens that case and the clean one, and nothing else in
the package). The mid-drain boundary case asserted that its straggler task was still running, which
its own harness holds at a gate; the case now asserts what the conductor owes at that boundary and
had not been asked for, that the record is written and `READY` before anything touches the pool
(persisting the snapshot after the drain instead reddens it there, and nothing else in the suite
sees the ordering while the drain is still running), and the straggler lines stay as the stated
premise of the boundary rather than as a finding about the code. The conductor suite's drain-timeout
case has the same premise line and now says so too.

## Addendum (2026-07-18): the real model host landed, and the swap mechanism is validated

The last engineering sub-slice of decision 9 item 5 has landed: the `model-host` supervisor sidecar,
the `HttpModelHost` adapter, the compose revision that retires `llama-cortex`, the ADR-0012 host
half, and the CUDA-OOM re-place (recorded at ADR-0012, whose entry it closes). The sentence every
addendum above ends with changes, and this is the only place it may:

**The swap mechanism is validated. Tier scale is not, and cannot be here.** Real `llama-server`
processes were started, health-gated, evicted, swapped, killed under the daemon and restarted over
their own corpses, in Docker on the dev GPU, with two small artifacts standing in for the tiers
(`Qwen3.5-0.8B-Q8_0` as the cortex tier, `Qwen3.5-2B-Q4_K_M` as the deep one, both at
`--ctx-size 4096`), which is exactly what decision 7 authorizes and no more. The eviction half is
sub-second (SIGTERM to reaped in 0.10 to 0.40 s, VRAM back to baseline within the sampling
resolution), the load half is the whole cost (11.3 s and 18.0 s for those two artifacts), and one
`Converse` turn streamed its reply off the supervised child through the brain container. gemma-4-12B
alone takes 7715 of this card's 8188 MiB, so the real cortex and any deep candidate cannot be
swapped between here; that half, and the deep-model pick itself, stay host-side. Commands, timings
and failure modes: [docs/runbooks/model-swap.md](../runbooks/model-swap.md).

Decision 3's shape landed as written, with the fixed per-model ports, the roster from the daemon's
own env, requests carrying a logical id and nothing else, and the cortex started at boot. What
follows is where this ADR was silent or wrong, decided here rather than left to the next reader.

**`status` proxying the child's `/health` is not enough, and this is the sub-slice's
highest-value correction.** Decision 3 says "`status` proxies the child's `/health`, so READY means
what the compose healthcheck means today". Taken literally that defeats the swap. Measured: a second
`llama-server` on a port an incumbent still holds dies in 0.24 s with exit code 1 and
`couldn't bind HTTP server socket`, while `/health` on that port keeps answering
`200 {"status":"ok"}` from the incumbent. A status that only probed would report the dead start
READY, the health gate would pass, and the previous weights would go on serving under the new
model's name, which is the hard rule's premise silently broken. So the supervisor reads the child's
**exit code first** and only probes a process it knows is alive; a child that exited unasked is
FAILED with its code in `detail` until the next `start` replaces it. `build_roster` closes the same
hole at boot by refusing two tiers on one port, where an operator can still fix it. Both halves are
pinned by tests that redden under mutation, and the FAILED case was observed live twice (a missing
artifact, exit code 1; a `kill -9`, code -9).

**The control API is not published to the host, and that cost a second override file.** Decision 3
says compose-network-only; every other sidecar publishes `127.0.0.1:<port>` so host-side integration
tests can reach it. This API starts and stops processes on the container holding the GPU and the
models mount, and on WSL2 a `127.0.0.1` publish is reachable from Windows' own localhost too, so the
security argument outranks the convenience precedent. The gpu override publishes only the cortex
tier's `127.0.0.1:8080`, exactly as the service it replaces did, which keeps
`just brain-inference-live` and the GPU runbook working unchanged.
`docker/docker-compose.modelhost-loopback.yml` is the opt-in override that adds the control API and
the two other tiers, and it maps them to **different** host ports (9300, 9081, 9083) because this
ADR's chosen container ports collide with two existing publishes: `:8081` is `llama-embed` and
`:8083` is `llama-subagent-qwen`, so a stack layering memory or subagents-roster with an
equal-ports publish would fail to start. In-network nothing changes and this ADR's port assignment
stands.

**The healthcheck asserts the boot resident is READY, not that the daemon answers.** The obvious
reading (a healthcheck on the control API) would let `brain`'s `depends_on: service_healthy` pass
while the cortex was still loading, so the first turn would fail at the backend, where today's
`llama-cortex` check means "the model serves". The check therefore reads
`GET /models/{cortex}` and greps for `ready`, preserving that meaning exactly.

**The image, and one shortcut that does not work.** `brain/Dockerfile.modelhost` bases on
`ghcr.io/ggml-org/llama.cpp:server-cuda` and copies `uv` in as the static binary it is, installing
the workspace against the image's own `/usr/bin/python3`. Transplanting the brain image's prebuilt
venv fails: it points at `/usr/local/bin/python3.12`, which Ubuntu 24.04 does not have. `WORKDIR` is
`/srv/brain`, because `/app` is where the base keeps the binary the supervisor spawns, and the base
image's `llama-server` entrypoint is cleared. The brain image ships this package too (it imports the
adapter) and therefore ships the daemon's modules, which nothing there runs; that breaks no part of
decision 3's argument, whose blast radius is the GPU reservation, the models mount and the
`llama-server` binary, none of which the brain container has.

**One package, not two.** `cortex_model_manager` holds both halves even though they run in different
containers and never import each other, because this ADR names one package. The adapter imports
`cortex_core` (the four state words and the typed error), which is what keeps the wire's vocabulary
from drifting between the two sides.

**The cgroup caps are per supervisor, not per model, and that is a real loss.** ADR-0012's host half
asked for `--cpus`/`--memory`/`--memory-swap` on two `llama-server` sidecars; decision 3 collapsed
the GPU one into this container, so the cortex, the deep model and the GPU subagent are **processes
in one cgroup** and no per-model CPU or RAM cap exists, only one cap set covering all three
(`CORTEX_MODELHOST_{CPUS,MEMORY,MEMSWAP}`), plus a separate set on the CPU subagent container whose
defaults are the hard twin of the brain's soft admission budgets. This ADR wins as the later and
more specific decision, and its own security argument is what buys it: a per-model cap wants a
container per model, which wants something that can start containers, which is the docker-socket
shape decision 3 rejected. The values ship as user-tunable placeholders, because the 8 GB dev GPU
cannot hold a real tier pair; note that llama.cpp mmaps the GGUF, so mapped model pages count
against the memory cap and a cap below the artifact size makes a load thrash rather than fail.

**The other decisions this ADR left open, each with the reason.** The SIGTERM grace is 10 s and the
post-SIGKILL reap bound 30 s, both env knobs, and `stop` does not return until the child is reaped
because `swap_in` starts the next model with nothing in between; a still-dying cortex holding
~11.3 GB would CUDA-OOM the load. Their sum must stay below the brain's new
`CORTEX_MODELHOST_TIMEOUT_S` (60 s), which is a **real** deadline unlike the generation clients'
deliberate `read=None`, since a hung control call would hang a swap step under no bound at all; the
pairing is documented in the runbook rather than validated in code, the two sides being separate
processes' env. A momentarily unreachable supervisor raises `ModelHostError` with no retry, so the
swap fails safe and the scope restores. The new backend value is `supervisor`, and selecting it
requires `CORTEX_MODELHOST_ENDPOINT` or boot fails, mirroring the fail-closed validator this ADR's
previous addendum added. `SwapRuntime.close` widened to release the control client as well as the
handoff store, the client even when the store's own release raises. And the GPU subagent tier is
opt-in behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`, with `CORTEX_SWAP_EVICT_MODELS` still empty by
default: a tier with no artifact file is not in the roster at all, so a stock stack answers 404 for
it rather than spawning a doomed process.

**Every process hazard the recon for this sub-slice enumerated, and where each went.** A start that
has not finished loading is LOADING and the health gate is the only readiness authority (`start`
returns in ~7 ms, a spawn and not a load). A stop racing a start is serialized by one lock per
logical model. Zombie reaping needs no collector: asyncio's child watcher reaps on its own, which is
what makes `returncode` authoritative for a child nobody awaited. Orphans cannot outlive the
container: children inherit the daemon's process group, and killing the daemon was observed to end
the container, kill both children and return VRAM to baseline. VRAM not freeing instantly is why
`stop` waits for the reap, and at this scale no lag was observable; at tier scale it is the user's
to re-measure. Children inherit the daemon's stdout and stderr rather than a pipe, so nothing can
wedge when llama.cpp's loading log outruns a buffer nobody drains, at the cost of a failed child's
reason living in `docker logs` while the API's `detail` carries the exit code.

**One deferral opened, with its three records.** A restarted sidecar reconverges itself (its boot
default starts the cortex) but **nothing reconverges the brain**: `SwappingModelManager` keeps
`_resident`, `_scope_model` and `_handoff_claimed` as instance attributes and `recover_handoffs`
runs only at startup, so a sidecar restart mid handoff leaves the brain believing the deep model is
resident while the fresh sidecar serves the cortex. It is invisible with escalation off (the plain
`SingleResidentModelManager` holds no residency state, confirmed live by a turn answered straight
after a restart) and self-limiting with it on (the handoff fails at the backend and releases its
claim in the conductor's `finally`). Closing it is a wire addition plus a caller, not a port change:
a boot id or generation counter on `GET /health` that the manager compares, and `converge_residency`
called from somewhere other than startup, which pairs naturally with the residency state the
honesty-surfaces sub-slice introduces. **Trigger:** a sidecar that restarts under a live handoff more
than once. Recorded in
[docs/refinements/inference-model-manager.md](../refinements/inference-model-manager.md) and its
[index](../refinements/index.md).

**Two claims elsewhere that this landing falsified, corrected rather than left.**
Placement-aware CPU charging said it reopened with the GPU-placed runtime; the runtime is here and
did not reopen it, because one hosted GPU tier is still one backend object per target per roster
entry and the measured serialization argument stands, so its condition is now decision 8's own, a
**second** GPU-capable executor. And admission reopening onto a tier that would not restart said
nothing was at stake because no deployment evicts a tier; a deployment can now name a GPU subagent
artifact and list that tier in `CORTEX_SWAP_EVICT_MODELS`, so it is reachable by configuration for
the first time, though the shipped defaults still leave both empty and its cost fell with the
re-place (a spawn on a dead tier re-runs on the CPU rather than only reporting).

**One defect found in the previous sub-slice's own work, by running its live suite.** The
integration-marked test for the SIGTERM-then-SIGKILL escalation signalled the child before the
trapping shell had installed its trap, so the child died on the default disposition with -15 and the
case tested the opposite of its name. It never ran in the gate by design (`integration`-marked), and
running it is what found it; the child now writes a marker when it is armed and the test waits for
that, under a timeout so a poll cannot become a hang.

What remains of decision 9: the honesty surfaces (item 6) and the host-side capstone (item 7,
which now also owns the tier-scale swap, its chaos kill, and the deep-model pick). The first of
those landed later the same day; the last addendum below is what it decided.

## Addendum (2026-07-18): the audit round on the real model host, and what it corrected

Three adversarial audits of the sub-slice above found real defects. The repairs are recorded here
because two of them change what this ADR's previous addendum says, and one of them corrects a
measurement that addendum publishes.

**The healthcheck asserts the cortex tier OR the deep tier is READY, not the cortex alone.** The
addendum above says the check "reads `GET /models/{cortex}` and greps for `ready`, preserving that
meaning exactly". That reading is what a handoff breaks: `swap_in` stops the cortex first, so a
**working** escalation marked the container unhealthy for as long as it ran (`interval: 30s` times
`retries: 5`, about 150 s, against a 300 s load bound), and the runbook's own diagnosis line then
read that as "the model is not serving" and sent the operator to start the cortex onto a GPU the
deep model was already resident on. Nothing in compose acts on unhealthy, so the harm was the
scripted human action rather than an automated one, which is why it is a docs-and-predicate fix
rather than a redesign. The predicate now accepts either tier. `brain`'s `depends_on:
service_healthy` is unchanged in effect, because at cold boot the daemon starts only the cortex.
Measured on the dev GPU with the small stand-ins, watching docker's own `State.Health.Status`:
cortex stopped with the deep tier READY reads **healthy** (it read unhealthy before), both stopped
reads unhealthy, and the deep model's load window still reads unhealthy because nothing is serving
then, which the runbook now states as expected rather than as a fault.

**The eviction half is sub-second only while the child is idle, and the addendum above overstates
it.** That addendum says "the eviction half is sub-second (SIGTERM to reaped in 0.10 to 0.40 s)".
Re-measured on the dev GPU with a stream in flight against the stand-in: `llama-server` logs
`cleaning up before exit` and then does **not** exit, because the shipped tiers run `--parallel 1`
and one in-flight request blocks the graceful exit, so the whole `CORTEX_MODELHOST_STOP_GRACE_S` is
paid and the child is SIGKILLed: **10.09 s** end to end, and 10.90 s in a second run. The idle
number (0.40 s) is real and is what a swap-back eviction of a quiet tier costs; the busy number is
what the paths that evict a tier which was answering cost (the cancellation restore, and the
shutdown sweep). Nothing is unsafe, since 10 s of grace plus 30 s of reap still clears the brain's
60 s control deadline, but two things followed from it: the grace must not be tuned down on the
strength of the idle number, and the container's `stop_grace_period` was sized by one stop rather
than by the sequential sweep, so it is now 45 s (three tiers times the grace, plus slack) instead
of 30 s. A sweep cut short is not a leak either way, because the runtime's kill of the container
takes the children with it.

**The timeout pairing has three terms, not two.** The addendum above states the rule as the SIGTERM
grace plus the reap bound below `CORTEX_MODELHOST_TIMEOUT_S`. It omits `probe_timeout_s`:
`ModelSupervisor.status` takes the **same per-model lock** as `stop` and probes the child inside it,
and the compose healthcheck asks for a status every 30 s on exactly the tier `swap_in` stops first,
so a stop queued behind a status is the normal case. Measured against a SIGSTOPped child on the
shipped grace: the stop took 10.89 s with the lock free and 15.70 s when issued 0.2 s behind a
status, the status itself taking 5.80 s. The shipped defaults are safe (5 + 10 + 30 = 45 < 60), but
a user tuning by the two-term rule to a compliant-looking 20 + 35 would reach the deadline and
abort a working handoff, so the rule is now written with all three terms in the runbook and at
`DEFAULT_MODELHOST_TIMEOUT_S`. Moving the probe out from under the lock was rejected: a status that
read the child, released the lock, then probed could report READY for a tier a concurrent stop had
already ended, which is the readiness lie the lock exists to prevent. `GET /health` now reports the
two stop bounds the daemon was actually given, so the pairing can be checked against a running
container rather than against its env.

**The daemon's own log was empty, which mattered more than it looks.** `uvicorn.run` configures
uvicorn's loggers and leaves root alone, so every INFO lifecycle line the sidecar logged was
dropped and the one WARNING that escaped went through logging's last-resort handler. Measured in
the image before the fix: twenty start and stop calls produced twenty access-log lines and not one
line naming which tier was started or stopped. This ADR's own decision 3 tradeoff (children inherit
the daemon's streams, so a failed child's reason lives in `docker logs` rather than in the API's
`detail`) and the runbook's diagnosis step both depend on that log, so the trail was the diagnosis
and it was not there. `main` now configures the root logger, and each line carries its tier, pid and
port in the message as well as in `extra`, because a plain stdlib formatter renders no `extra`
(the tool audit sink documents the same pattern).

**Hosting the GPU subagent tier and routing to it are two settings, and decision 3 above says
otherwise.** That decision reads "the real GPU subagent `llama-server` (`-ngl 99`) becomes a hosted
model, `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at it". The tier landed; the variable does not point
at it. It still defaults to the CPU subagent server, which is the safe default and the one ADR-0012's
re-place addendum already described: a deployment that has named no GPU subagent artifact would
otherwise route every GPU-placed spawn at a tier that answers nothing. So opting in is three
settings together (`CORTEX_MODEL_FILE_SUBAGENT_GPU`,
`CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`, and the tier's id in
`CORTEX_SWAP_EVICT_MODELS`), now written in the gpu override's own checklist, in
[docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md), and in the backlog entry that had
claimed the wiring existed.

**One deferral opened, with its three records.** The timeout pairing stays **documented rather
than enforced**, which is what the landing addendum already said, but the reason is now weaker in
one direction: `GET /health` reports the two stop bounds the daemon was actually given, so the
brain could read them at wiring time and refuse to boot when its own deadline does not clear their
sum plus the probe timeout. Closing it needs the probe timeout on that same body (it belongs to the
health probe's client, not to the supervisor) and a fail-closed check in `build_control_client`,
and it costs the brain a wiring-time dependency on the sidecar answering, which today it
deliberately does not have. **Trigger:** a user tuning either side's timing, or any report of a
handoff aborting with `ModelHostError` on an eviction that in fact completed. Recorded in
[docs/refinements/inference-model-manager.md](../refinements/inference-model-manager.md) and its
[index](../refinements/index.md).

**And the records the landing left stale, now correct.** ADR-0012's host half was declared landed
with two of its three required places (the area doc and the backlog index, both pointing here for the
decision that relocated it) while its own origin ADR got nothing, unlike the `drain()` and re-place
landings in that same file; it now has a dated host-half addendum there. `docs/ROADMAP.md` still
named the real process lifecycle as outstanding and the swap's mechanism as validated only over
fakes. The subagents override and its runbook still called the GPU sidecar and the cgroup caps
pending, in the file that carries those caps. None of that changes a decision; all of it was a
reader being told the opposite of the tree.

## Addendum (2026-07-18): `Health` tells the truth about residency, and the last producer is whole

Decision 9 item 6's remaining half has landed: the servicer answers `ready=false` with a truthful
detail whenever the standing residency is not serving. The swapping `StatusUpdate`s landed with the
conductor (the slicing correction two addenda above), so the honesty surfaces are now complete and
**the overlay was not touched**, exactly as decision 6 says: the landed indicator classifies a
not-ready reply as amber `Degraded`, shows the brain's own line verbatim, and its
visible-and-unhealthy recheck turns it green again on its own. No proto change either;
`HealthReply` has carried `ready` and `detail` since the first proto commit. **Tier scale is still
not validated and cannot be here**, for the reason every addendum above gives.

**The source of truth is the manager's own published residency, and the alternatives lose for
reasons worth keeping.** The `HandoffStore` record survives a restart, which this does not, but it
answers a different question: it is live through the drain, while the cortex is still resident and
still answering turns, so a probe reading it would call a working machine not-ready. It is also
Redis I/O on a probe that arrives every 5 s while a swap runs, and it is already the conductor's
own precondition, so reading it here would make two answers to one question. `ModelHost.status` is
ground truth and restart-proof, and it is the worst of the three for this: it is an HTTP call per
probe into the supervisor's per-model lock, measured at up to 5.80 s under contention against a
5 s recheck. So the report is in-process, published by the one object that changes residency, and
its staleness is recorded rather than hidden (below).

**Five decisions this ADR left open, made here.**

- **The direction of a swap is published, not inferred.** Decision 6 names three details, but a
  swap in and a swap back both leave nothing resident, so no reading of `_resident` can tell them
  apart. `_set_resident` therefore writes the resident and a `ResidencyReport` together, under the
  same condition and with nothing awaited between them, and the five values are the states a swap
  can actually be in: serving, loading the deep model (eviction included, nothing serving for
  either), the deep task in progress, bringing the usual assistant back, and one this ADR's
  decision 4 step 3 demanded but never named, a restore that **gave up**. That last one is why the
  report is not merely three strings: without it the manager would go on announcing a restore that
  stopped happening, which is the one lie the honesty surface exists to prevent. That also retires
  the conductor addendum's "the loud log alone for now": step 3 now surfaces both halves.
- **The drain window stays ready.** Decision 6 keys not-ready on the cortex not serving, and
  through the drain it is resident and leasable; the claim is taken before anything is unloaded.
  So the dot is green while the stream's own "pausing delegated work" chip is showing. That
  asymmetry is deliberate and pinned by a test, because it looks like a bug to anyone who assumes
  a handoff and a not-ready brain are the same window.
- **The reader is a port, not the concrete manager.** `ResidencyReporter` (`residency()`) joins
  `ModelHost` and `ResidencyController` in `ports_models.py`, segregated for the opposite reason
  the controller is: its holder is a readiness RPC that must only ever look, so it cannot reach a
  swap through what it is given. It is **synchronous by contract**, and that is the port's whole
  content: a coroutine that took the GPU lease would hang the indicator for the entire load, which
  is precisely when the honest answer matters, so the signature makes that unrepresentable rather
  than merely discouraged. The strings live beside the value in `residency_state.py` rather than in
  `swap_notes.py`, whose stated scope is the escalating turn's own stream: a `StatusUpdate` is
  progress on one turn, while a report answers a probe any client may make between turns.
- **The ready detail is unchanged** (`cortex-orchestrator <version>`), so nothing that asserts it
  moved, and the brain's optional residency is `None` with escalation off, where the plain manager
  holds no residency state and readiness stays unconditional.
- **The brain container's compose healthcheck now asserts that the RPC answered, not that the
  reply says ready.** An honest `ready=false` under the old predicate would have marked the
  container unhealthy after about 90 s of any handoff and permanently after a failed restore,
  which is the identical defect the model-host check was corrected for on this same slice, and the
  runbook's own step 1 told the operator both containers should read healthy. The check's purpose
  is catching a broken gRPC server, which a successful reply of either kind disproves. Verified
  live on the dev GPU: the real container reads healthy under the new predicate, and the same
  command against a port with no server exits 1. What that costs is real and recorded: a
  permanently not-ready brain (a restore that gave up) no longer shows in `docker compose ps`, so
  the runbook now points at the overlay's dot and the logs for residency, which is where it
  belongs. Nothing in compose gates on `brain` being healthy, so no automated behaviour changed.

**What this deliberately did not build, and the two entries that were about to imply otherwise.**
The state is one report about what the GPU is serving. It carries no per-tier health and no
staleness generation, so neither **admission reopening onto a tier that would not restart**
(resource-governance.md) nor **reconverging the brain's residency when the sidecar restarts under
it** (inference-model-manager.md) is closed by it; both entries said the fix wanted "the residency
state the honesty-surfaces sub-slice introduces", and both now say what actually landed instead.
The second gained a sibling case with the same fix: after a restore that gave up, an operator who
brings the cortex back by hand leaves the report saying it could not be reloaded until the brain
restarts, which is the one place the honest answer can outlive the truth. It is accepted rather
than papered over, because boot recovery is what re-reads the machine and the runbook's manual
recovery already ends by restarting the brain; the runbook now says why that step is not optional.

**What the gate holds, proven by mutation** (each applied to production code alone with the whole
brain workspace re-run): answering ready unconditionally again reddens three cases and nothing
else, two at the seam and one through the whole composition root; reading `_resident` instead of
the published report reddens five; dropping the give-up report reddens one; dropping `residency=`
from the root's `serve` call reddens exactly the wiring case, which is what keeps the knob from
being silently droppable; publishing not-ready at the claim reddens the drain-window case; and
making the report a coroutine that takes the lease fails the stalled-swap case by its own timeout
rather than hanging the suite. The last of those is the non-blocking proof: the case pauses a swap
inside the host's `start`, where the lease is held for the whole move, and requires a bounded
`Health` RPC to answer `loading` anyway. Agent-validated in Docker as well, over the real
supervisor and two small stand-ins: inside a real residency scope the deep child was READY, the
standing one STOPPED, and the report at that instant said a deep task was in progress, with a
report that always claims serving reddening it.

## Addendum (2026-07-18): the audit round on the honest `Health`, and the boot it still lied about

Two adversarial passes over the sub-slice above. No decision changed; one real hole was closed,
two proof holes were filled, and one prose defect was corrected. What follows is what was
measured, because three of the four looked correct on the page.

**The hole: decision 6 keys not-ready on "the cortex is not the serving resident", and a failed
boot is exactly that.** `SwappingModelManager` seeds its report `RESIDENCY_SERVING` in the
constructor, which is unavoidable (a constructor cannot see a GPU), and only a swap ever wrote it
afterwards. Boot recovery is the code that actually looks, and it is deliberately allowed to fail
without raising: an unreachable model host is caught and logged, and a cortex that never gates
`READY` inside the load bound is logged too. Neither told anyone. So a brain whose cortex could
not be brought up logged "the cortex is not serving after boot recovery; turns will fail until it
is" and then answered `ready=true` from the same process, for as long as it ran. Reproduced
before fixing, over the real objects in the composition root's own order: with the host refusing
to start the cortex, `Health` answered ready with the cortex `STOPPED`; with the cortex stuck
loading, ready again with it `LOADING`. This is reachable through the runbook's own mandatory
step: a `docker compose restart brain` after a restore gave up does not re-evaluate the GPU
override's `depends_on`, so in precisely the case that step exists for (the cortex will not load,
which is why the restore gave up twice) the restart converted a truthful amber into a green lie,
on the one surface the same sub-slice had just designated for residency after taking `reply.ready`
out of the brain's compose healthcheck.

**The fix, and the one thing it deliberately does not do.** `converge_residency` and
`recover_handoffs` now answer whether the cortex was **observed** `READY`, and the composition
root publishes that with `publish_boot_residency(serving=…)` before `serve`. A sixth published
value, `RESIDENCY_BOOT_FAILED`, carries it, distinct from `RESIDENCY_LOST` because no deep task
need have happened and the wording must not claim one. That publish is the only writer that
touches the report **without** touching `_resident`, which is a deliberate exception to the
otherwise absolute "the two are written together" rule of the sub-slice above, and the reason is
that failing to confirm is not the same as knowing: an unreachable supervisor says nothing about
the process it supervises, and a load that outran its bound may finish a minute later. Clearing
the resident would have turned one unanswered probe into a brain that refuses every turn until
someone restarts it, which is worse than the amber dot it would have justified. So the lease keeps
the forgiving posture boot recovery has always had, the report goes amber, and the cost is a false
amber rather than a false green: a cortex that comes good on its own leaves the dot wrong until a
swap or a restart re-reads the machine. That staleness is the same shape as the hand-fixed-GPU one
the previous addendum recorded, it has the same fix (a generation the manager can compare), and it
is filed with it rather than invented as a new entry.

**The proof holes, both measured rather than argued.** First: the `serving` flag of
`RESIDENCY_RESTORING` and `RESIDENCY_LOST` was pinned by nothing. Flipping either constant to
`serving=True` left the entire brain workspace green while `Health` answered ready for the whole
swap-back window and, after a restore gave up, permanently. The cases covering those two windows
compared `manager.residency()` against production's own constant, which proves which value was
published and nothing whatsoever about what that value claims; the two windows that *were* pinned
were pinned only incidentally, by seam cases that happen to read `reply.ready is False` as a
literal. Second, the same species: every not-serving `detail` could be blanked with the workspace
still green, and blanking them also collapsed four distinct reports into one equal value, so the
case named for tracking the swap's direction could no longer tell its direction apart. Both are
now pinned by one case that compares all six published values against literal `ResidencyReport`s,
which is where the user-facing strings live under the gate, plus two new seam cases that drive the
restoring and gave-up windows through `BrainService.Health` and assert `ready is False` as the
literal it has to be.

**Measured mutations for the repair** (each applied to production code alone, whole brain
workspace re-run, then restored): `serving=True` on `RESIDENCY_RESTORING` reddens 2, the constants
case plus the seam's swap-back case; the same on `RESIDENCY_LOST` reddens the constants case plus
the seam's gave-up case; on `RESIDENCY_BOOT_FAILED`, the constants case plus the composition
root's boot case. Blanking all five not-serving details reddens exactly 1, the constants case.
Dropping the root's `publish_boot_residency` call reddens exactly 1, and passing it a constant
`serving=True` reddens the same one, so neither half of that knob is silently droppable. Making
`converge_residency` return `True` unconditionally reddens 3, both recovery cases that observe a
cortex which is not serving plus that same root case. Dropping the not-serving branch of the
publish reddens 2. Clearing `_resident` inside it reddens exactly 1, the case that pins a
still-leasable cortex, which is the guard on the exception described above. `Health` answering
ready unconditionally now reddens 6 where it reddened 3 before this round.

**Two smaller corrections.** `create_server` and `serve` were threading the three optional seam
ports one keyword at a time and had reached `max-args = 6`, the dependency ceiling ruff.toml sets,
while the constructor one layer down had already bundled them as `SeamPorts`; both now take the
bundle, which drops them to 4 and removes the second place that must learn about every new
optional port. And `SwappingModelManager`'s handoff claim moved to `residency_claim.py` as
`HandoffClaim` over the same condition, a pure move made **before** adding to `residency.py`
rather than after tripping the 300-line cap: 277 lines plus the boot publish would have left 8 of
headroom on the file every swap feature grows. Dropping the claim's refusal reddens 2, its own
case and the chaos suite's race, so the move is proven behaviour-preserving where it matters.

**Validated live in Docker, and the boot path needs no GPU to be real.** The brain container was
brought up with escalation on and `CORTEX_MODELHOST_BACKEND=supervisor` pointed at a port nothing
listens on, which is the unreachable-host branch through the real `HttpModelHost` adapter rather
than a fake. `Health` over the real seam answered `ready=false` with "the usual assistant did not
come up at startup; the model host needs attention", the boot-recovery ERROR was in the container's
own log, and the container still read **healthy**, which is the corrected predicate doing its job
(the RPC answered). Restoring the base stack, where escalation is off and no residency is wired,
answered `ready=true` with the version detail, so the check discriminates rather than always
reddening. **Tier scale is still not validated and cannot be here**, for the reason every addendum
above gives: the dev GPU is 8 GB.

## Addendum (2026-07-19): the host-only half has a home, and an 8 GB card does not fail loudly

**Where the host-only half is tracked.** The three things this ADR leaves to the 24 GB machine, the
tier-scale swap, the chaos kill against a real deep-model process, and the measured swap timings,
now have a written home with a bring-up, a pass, a fail, and a "record it" line pointing back here:
items 2, 3 and 4 of [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md), indexed at
[docs/host/](../host/index.md). The five risks this ADR flags for maintainer review stay here, which is
where a decision belongs, and are listed on that index as pointers so they survive the ROADMAP
slimming. Nothing about the work changed.

**The bring-up the user needs was not derivable from the docs, and now is.** Enabling escalation
takes three settings on the `brain` service (`CORTEX_ESCALATION`, `CORTEX_MODELHOST_BACKEND`,
`CORTEX_BRAIN_ENDPOINT`), and **no compose file interpolates any of them**, so a `.env` entry or an
exported shell variable reaches nothing and the stack comes up with escalation quietly off
(verified against a running container on 2026-07-19). Omitting the endpoint is a restart loop on
`CORTEX_BRAIN_ENDPOINT is required when CORTEX_ESCALATION=1`, which is `config_swap.py` behaving
exactly as decision-level fail-closed intends. They belong in the `brain` environment block of
`docker/docker-compose.gpu.yml` or in a local override layered after it, which that file's own
header says and the user prerequisites now repeat.

**An undersized card produces a green swap, which is the surprise worth recording.** Every addendum
above says the dev GPU is 8 GB and cannot hold the cortex beside a deep candidate, which is true
and unchanged. What was assumed and is false is that trying anyway fails loudly. Measured here on
2026-07-19 with the cortex evicted first and the deep tier pointed at a 17 GB
`gemma-4-31B-it-qat-q4_0` artifact: llama.cpp logged `failed to fit params to free device memory:
n_gpu_layers already set by user to 99, abort`, kept every layer assigned to the GPU, and the tier
reached READY after **373 s** with `nvidia-smi` pinned at about 7.7 of 8188 MiB, then generated 16
tokens in 36 s, roughly half a token per second, which is consistent with the WSL2 driver spilling
into host memory rather than refusing the allocation. So an 8 GB run of the tier-scale swap would
look like a pass and every number in it would be meaningless, and the 373 s load would already blow
through the 300 s `CORTEX_SWAP_LOAD_TIMEOUT_S` default for a reason that has nothing to do with the
mount. The user doc carries this warning at the top of its bring-up.

No code changed here; this addendum records a records fix and one measurement.
