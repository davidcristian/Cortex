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
  the producer that makes it real ([body-overlay](../refinements/index.md#body-overlay)).
- **The body is one turn per `Converse` call.** The overlay opens a fresh stream per submit
  and the transport sends exactly one `UserTurn`
  ([body-overlay](../refinements/index.md#body-overlay), read against
  `body/crates/rpc/src/converse.rs`). Anything the user must see during a handoff therefore
  has to ride the escalating turn's own event stream, or wait for a body seam change.
- **VRAM (ADR-0004, measured):** 24 GB GPU, soft cap 14 GB (`CORTEX_VRAM_SOFT_CAP_GB`), cortex
  gemma-4-12B at ~11.3 GB incl. vision at 16K ctx, subagent E4B VRAM ask 5.5 GB (deliberately
  above the ~2.7 GB headroom, so every spawn overflows to CPU today), brain candidates 15-18 GB
  of weights that "all fit alone in 24 GB". That last clause was confirmed on 2026-08-04, when
  the brain pick was measured and landed: **gemma-4-31B QAT q4_0**, 19128 MiB alone on the card at
  an 8192 context and 99.6 s from start to READY, with all four candidates fitting and none
  needing the hybrid fallback (ADR-0004's brain-pick addendum).
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
   turn against its own drain. On timeout (one wedged CPU stream is a real hazard, bounded since
   the per read stall ceiling landed at the delegated pool's 600 s rather than not at all, which
   is what the deliberate `read=None` client this line used to cite meant):
   **abort the handoff before anything is evicted**, mark the
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

**The opening premise of this decision is no longer true and the decision is unchanged
(2026-08-08).** Both of its standing terms have since been measured on the card this repo runs:
the cortex reservation is 8.6 GiB rather than 11.3 and the subagent ask 3.5 GiB rather than 5.5
([ADR-0012](ADR-0012-resource-governance.md)'s re-measured-reservation and measured-ask addenda),
so the headroom is 5.4 GiB, the ask fits it, and the standing GPU carries the cortex **and** one
GPU-placed subagent rather than the cortex alone. Nothing above depends on that: the deep model
still does not fit beside either, the swap still evicts every listed tier unless
`CORTEX_SWAP_CORESIDENT` says the card was measured to hold the pair, and the window still
suspends the cap. What changes is only which sentence describes today: the shipped stack now has a
GPU-placed subagent for a handoff to evict, where when this was written it had none.

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
7. **S11.g, host-side capstone.** The brain pick (**done 2026-08-04**: ADR-0004 has its addendum
   and `docs/host/index.md#gpu-tier-scale` item 1 its record), the live
   tier-scale swap + chaos kill on the 24 GB machine, measured swap timings,
   `docs/runbooks/model-swap.md`, and the ~31B injection-harness run
   (`CORTEX_PROBE_BRAIN=1`), whose result feeds back into decision 1's tainted-escalation
   stance. **That run is also done, on 2026-08-04** (0/10 framed; the last addendum here), so
   what remains is the three that need a handoff the overlay has to approve.

## Where each "Blocked on Slice 11" backlog entry lands

The four entries under "Blocked on Slice 11" in
[docs/refinements/index.md](../refinements/index.md), mapped; none is closed by this ADR
(nothing lands with a design), and the area docs are updated only as slices deliver.

- **Model-manager process lifecycle, co-residency, and the real swap**
  ([inference-model-manager](../refinements/index.md#inference-model-manager)): lifecycle and
  the real swap are decisions 3-5 (S11.d/e). **Co-residency stays deferred** (decision 8
  records the v1 brain-runs-alone rule and the refinement's shape).
- **`SubagentScheduler.drain()`, CUDA-OOM re-place, the real GPU-placed runtime**
  ([resource-governance](../refinements/index.md#resource-governance)): drain is decision 4 /
  S11.b with refuse-not-queue semantics; the GPU-placed runtime and cgroup caps land in
  S11.e inside the model-host; CUDA-OOM re-place lands in S11.e as a single CPU re-run after
  a GPU-placed failure, recorded in the result's detail. **Placement-aware CPU charging stays
  declined-as-recorded**; its reopening condition (a second GPU-capable executor) is noted in
  decision 8 but not built.
- **Taint/provenance persistence across a mid-turn swap, and the ~31B injection-harness run**
  ([untrusted-content](../refinements/index.md#untrusted-content)): the persistence is decision
  2's record schema (S11.a) exactly as the entry flagged ("provenance rides on the stored
  tool-step context"); the harness run is S11.g and gates any future relaxation of the
  tainted-turn escalation denial. **It ran on 2026-08-04**, by the agent rather than the user
  once the hardware premise that filed it turned out to be false, and the gate it held is open:
  the relaxation is now a judgement rather than a missing number (the last addendum here).
- **Streamed brain status** ([body-overlay](../refinements/index.md#body-overlay)): decision 6
  delivers the *producer* (`Health` earns `ready=false` between turns, with truthful detail),
  which is the entry's named blocker. **The push stream itself stays deferred**: the landed
  probe-on-summon indicator plus the escalating stream's own status events cover personal
  scale, and a push RPC is a seam change to be designed with its consumer. When S11.f lands,
  the entry moves from "blocked" to actionable in its area doc.

Adjacent entries this slice deliberately does not deliver, but whose recorded triggers it
meets: safe `converse` reconnect dedup and the real Stop/abort
([seam-transport](../refinements/index.md#seam-transport),
[body-overlay](../refinements/index.md#body-overlay)) both name "mid-turn compute becomes
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
   config-plus-one-check change by design. **The harness run exists as of 2026-08-04** and the
   deep tier measured 0/10; what that does and does not settle is the addendum at the end of this
   file, and the short version is that it retires one of the deny's two reasons and leaves the
   other standing.
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
recorded as a deferred refinement in `docs/refinements/index.md#untrusted-content` (indexed under
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
deferral in `docs/refinements/index.md#vision` with its index line, beside the pixels-across-a-swap
entry this ADR's sibling named. **That deferral closed 2026-08-03**: the record carries the bit,
as defence in depth behind the unchanged refusal, and the addendum at the end of this ADR has
the schema change and its proofs.

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
is recorded in `docs/refinements/index.md#seam-transport`.

**Slicing correction, and one deferral this creates.** Decision 9 item 6 bundles the swapping
`StatusUpdate`s with the honest `Health` into the honesty-surfaces sub-slice, but decision 6
describes the wrapper yielding them and decision 7 asks the stream to say what happened, so they
landed here: they need no proto change and the alternative was a swap window that says nothing.
The `Health` half is untouched (the servicer still answers `ready=true` unconditionally), which
is what that sub-slice now delivers on its own; decision 4 step 3's "surface `ready=false` with a
loud log" is therefore the loud log alone for now. The streamed-brain-status backlog entry is
updated to say exactly that. Two further deferrals are recorded with it: resuming a crashed
handoff from its record (`docs/refinements/index.md#inference-model-manager`), which this ADR names and
which needs the request-identity design the reconnect entry also needs, and the drain bound
sitting below a fired task's schedule lease (`docs/refinements/index.md#resource-governance`), which
was read at the time as making an escalation during scheduled work abort every time under the
shipped defaults. The addendum of 2026-08-09 below traced that reading to the code and declined
it: the drain waits on an in-flight admission, never on a lease, so the number it is really up
against is a measured subtask duration and the abort is likely rather than certain.

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
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager) and its
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
[seam-transport](../refinements/index.md#seam-transport): a teardown mid handoff waits for the
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
Recorded in [docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance) and
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
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager) and its
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
already ended, which is the readiness lie the lock exists to prevent. `GET /health` reports from this
round on the two stop bounds the daemon was actually given, so the pairing can be checked against a
running container rather than against its env. The deadline-pairing addendum below then put
`probe_timeout_s` on that same body, so it carries all three terms as of 2026-08-09.

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
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager) and its
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
items 2, 3 and 4 of [docs/host/index.md#gpu-tier-scale](../host/index.md#gpu-tier-scale), indexed at
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

## Addendum (2026-07-19, later): the tier-scale swap needs the overlay, not only the card

Decision 7's host half says "verify from the overlay", and the user directory had nevertheless
filed the tier-scale swap and the chaos kill as card-only work. They are not, and the reason is
decision 1's own gate: `escalate_to_brain` ships `gated=True`, so a handoff begins only after the
ADR-0022 confirm card is approved. That card is a `ConfirmRequest` on the Converse stream answered
by a `ConfirmResponse` from the client, denied fail-closed after `CORTEX_SEAM_CONFIRM_TIMEOUT_S`
(120 s) if nobody answers, and the only shipped client that answers one is the overlay
(`body/crates/rpc/src/converse.rs`, `body/app/src/bridge/tauriBridge.ts`). The repo's headless
Converse driver, the `body-rpc` live suite, opens a stream and reads it; it answers no confirm.

So the tier-scale swap, the chaos kill during one, and the timings of one need **both** a 24 GB
card and a Windows desktop, and are tagged W+G in [docs/host/](../host/index.md). The deep-model
pick and the injection-harness run need the card alone: both drive the model host's control API and
the tier's own port directly, with no turn and no gate involved.

**A consequence worth stating for anyone who wants this headless later.** The gate is the design,
not an accident, so the fix is never to ungate escalation for a test run: it would be validating a
path the product does not have. A headless confirm-answering client on the seam would be a new
thing to build and to justify, and no slice needs one today.

No code changed here; this addendum records where a host item belongs.

## Addendum (2026-08-03): the record carries the `opaque` bit, as defence in depth and nothing more

Decision 2's schema said "the serialized `TaintLedger`" and shipped one field short of it: the
2026-07-19 correction above ends by naming what the record still did not carry, the ADR-0029
`opaque` bit, so `taint_ledger()` rebuilt it at `False`. That is now closed. `HandoffRecord`
grows `opaque: bool` beside `tainted`, `EscalationSlot.snapshot` reads it off the live ledger,
`taint_ledger()` rebuilds it, the Redis codec writes and reads the key strictly (a missing one is
a corrupt record like every other taint field), and the `HandoffStore` contract suite gains
`check_the_opaque_bit_round_trips_both_ways`, which both implementations pass.

**This is defence in depth, and calling it anything else would repeat the mistake this area is
famous for.** `SwapConductor._prepare` refuses an opaque turn before it snapshots, so no record
with the bit set exists today; the conductor test that drives the reachable ordering end to end
now also asserts that the store saw no write at all, which is what makes the refusal, rather than
the schema, the thing keeping the far side clean. The reason to carry the bit anyway is that both
of its consumers **open** on a `False`, and neither can tell an invented one from an honest one:
`_UrlRedactingFilter._scrub` stops escalating to strict redaction (the default policy redacts URLs
collected from untrusted result **text**, and a URL painted into pixels is never in that text, so
verbatim redaction is structurally a no-op for exactly the case vision introduces), and
`record_exchange` stops dropping the exchange, so a deployment with `CORTEX_MEMORY_ON_TAINTED=record`
would write a transcription of the screen into Postgres. A rebuilt ledger that manufactures the
bit is therefore a fail-open waiting for whatever relaxes the refusal, which is precisely what the
pixels-across-a-swap half of the vision entry would do.

Two claims in the deferral were checked against the code rather than inherited. Both consumers are
real and are reached by the deep phase (`BrainPhase.run` opens the guardrail over the rebuilt
ledger and hands the same ledger to `record_exchange`), and the cost estimate ("a record field, a
codec line, and the store contract's round trip") held exactly. The codec's behaviour on a field it
does not know was checked too, since the same entry's history turns on it: `decode_record` reads
keys by name, so an **unknown** key is ignored in silence and a **missing** known key raises
`KeyError` into `HandoffStoreError`. That asymmetry is why the bit is added to both halves of the
codec rather than defaulted on read, and why the strict-decode test is now parametrized over all
four taint fields.

Mutation-proven three ways, each restored: dropping the key from `encode_record` alone reddens
thirteen store tests (every read of a written record fails as corrupt); defaulting it on read with
`.get("opaque", False)` reddens only the strict-decode test, which is the one that exists to catch
a silent default; dropping it from both halves reddens the contract round trip itself on
`loaded == record`. Dropping `opaque` out of `snapshot` or out of `taint_ledger()` reddens the two
new brain-phase tests that watch the consumers differ across a swap, each of which runs a
tainted-but-not-opaque control arm so the difference measured is the bit and not the taint.

Validated against the compose Redis (`cortex-redis-1`), not only fakeredis: the integration-marked
`test_handoff_live.py` runs the whole suite including the new check, and a direct put/read of both
poles shows `"opaque": true` and `"opaque": false` in the stored document, reads back exact on the
record and on the rebuilt ledger, and sweeps the keys.

What stays open is the expensive half, pixels themselves, which still wants an `AttachmentStore`
and still meets the capability argument that no brain-tier candidate on the mount has a projector.
The conductor's refusal stays exactly where it is.

## Addendum (2026-08-04): decision 1's robustness pillar is measured, and the stance still stands

The `CORTEX_PROBE_BRAIN=1` harness row this ADR made a precondition has run, on the pick locked the
same day. **`gemma-4-31B-it-qat-q4_0` obeys 0 of 10 framed injections, against an unframed control
that obeys 1**, so the deep tier is as robust as the cortex under the shipped preamble, and the one
arm the control fell to is the tool exfil: unframed, the model emits a real `send_email` call on an
instruction hidden in a file it was asked to summarize, and the framing is what stops it. The
evidence, the checks that make a perfect score believable rather than an empty-reply artifact, and
the trace showing the model citing the preamble while refusing are in
[ADR-0013](ADR-0013-untrusted-content.md)'s addendum of this date;
[runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md) has the procedure.

**Decision 1 rests on two reasons for hard-denying `escalate_to_brain` on a tainted turn, and this
retires one.** The sentence "because the brain tier's injection robustness is unmeasured until the
harness runs, refusing to hand attacker-influenced context to a stronger tools-holding model is the
only honest v1 default" is now false in its premise and favourable in its answer. The other reason
in the same paragraph, that injected content must never force an eviction that claims the whole GPU
for minutes, is a resource-control argument no model measurement can touch, and it is untouched.

**So the shipped behaviour does not change here, and the remaining decision is the user's.** Three
things are worth having in hand before weighing it, all checked against code rather than recalled:

1. **It is not a knob.** The deny is the generic gated-tool branch of the dispatcher
   (`if gated: if stamp.tainted: DENIED_MSG`, [dispatch.py](../../brain/packages/core/src/cortex_core/dispatch.py),
   the rule [ADR-0022](ADR-0022-email-write-confirmer.md) decision 2 made unconditional for every
   gated tool). Relaxing it for escalation is a carve-out in a rule that currently has no
   exceptions, not a config flip, and risk 1's recorded alternative (ungated tool, internal taint
   refusal, card kept for consent) keeps the refusal rather than removing it.
2. **The far side is already covered if it is ever relaxed.** The ledger rides the handoff record
   whole (decision 2), so a tainted turn stays tainted through the swap and the deep phase's own
   gated calls hit the same deny. A relaxation would widen what may be *reasoned about* after an
   eviction, not what may be *done* with it.
3. **What the harness does not measure.** One row of ten attacks, at `--ctx-size 8192` with thinking
   on, on one artifact. The three rejected deep candidates were not probed, so adopting the recorded
   alternate means re-running the row before leaning on this result.

Risk 1 in the list above is therefore no longer blocked on a measurement; it is a judgement about
whether injected content may spend the machine. It stays listed for the user, now with a number
beside it.

## Addendum (2026-08-07): co-residency is measured, and half of decision 8 is wrong

Decision 8 deferred co-residency on an arithmetic argument, and this is the first sitting on a card
that can test it: an RTX 5090 Laptop reporting 24463 MiB, models on the read-only mount, driven
through the shipped `model-host` sidecar's control API with the real tiers rather than stand-ins.
Every number below is `nvidia-smi` total used on that card, with the floor stated beside it, because
this machine's floor moves: it read 1529 to 1554 MiB with the desktop quiet and 2836 MiB earlier in
the same session, which is roughly a gigabyte of the budget that belongs to Windows rather than to
this stack. Throughput is llama.cpp's own `timings`, decode only, so a fixed request overhead cannot
be mistaken for a slow model.

**The shipped pair does not co-fit, and the reason is not the one decision 8 gave.** The cortex
(gemma-4-12B QAT q4_0 at `--ctx-size 16384`, with its projector and the shipped 1024-token image
budget) costs **8448 to 8468 MiB** above the floor, not the 11.3 GB decision 8 quotes from ADR-0004.
The deep model (gemma-4-31B QAT q4_0 at `--ctx-size 8192`, `-ngl 99`) costs **19117 to 19125 MiB**,
which reproduces ADR-0004's 19128 MiB to within 11 MiB. Together with a 1552 MiB floor that is
**29139 MiB wanted against 24463 MiB of card, a deficit of 4676 MiB**, so the rule stands. What does
not stand is the shape of the failure. Starting the deep model with the cortex resident **succeeded**:
both tiers reported `ready`, the pair read 23539 to 23642 MiB, and 496 MiB of the card was free.
Under WSL2 the driver had paged roughly 6 GB out to system memory rather than refusing the
allocation, and the only thing that says so is the throughput. The deep model decoded **14.80 to
17.29 tok/s** co-resident against **25.07 to 33.28 tok/s** with the card to itself, and its prefill
on the first request after each switch collapsed to **13.8 to 14.0 tok/s** from 126 to 134. The
cortex was untouched (44.68 to 49.47 tok/s co-resident, 44.52 alone): the deficit was charged
entirely to the model that arrived second.

**So `nvidia-smi` cannot tell a fit from a spill on this machine, and any future sitting has to
measure decode.** The genuine fit below and the 4676 MiB overcommit above both read about 23.6 GB
used with about 0.5 GB free. That is the instrument check this addendum's numbers rest on.

**The other half of the deferral is real, and it works.** Decision 8's second recorded refinement,
"brain + tiny GPU subagent on a larger card", needs no tiny model. With the cortex evicted exactly as
a handoff evicts it, the deep model and the **shipped** gemma-4-E4B subagent tier (`-ngl 99
--ctx-size 8192 --parallel 2`) sat together at **23555 to 23642 MiB** over a 1552 MiB floor, the peer
costing 2878 MiB and leaving 908 MiB free. The deep model decoded **28.92 to 29.82 tok/s** beside it,
which is its solo rate, and its prefill held at 105 to 116 tok/s. Generating on both at once cost
both (deep 18.74, peer 22.91) and allocated nothing new: 23639 MiB under load against 23642 MiB idle.
That last figure is the one the design leans on, and it is why admitting delegated work to an
already-resident tier does not need a VRAM decision.

**What a handoff costs today, which is what co-residency buys back.** Through the real control API,
with the artifact warm in the page cache: evicting the cortex answered in **0.48 s**, the deep model
gated `ready` **70.03 s** later, and the swap back cost **0.89 s** to stop it plus **31.43 s** for the
cortex to gate, for **102.9 s** of pure swap on top of the deep model's own work. Cold, ADR-0004's
99.6 s load makes it about 132 s. For the whole of that window, and for the whole deep phase after
it, `SubagentScheduler.drain` refuses every spawn, the deep model's own included.

### The decision: `CORTEX_SWAP_CORESIDENT`, off by default

`ResidencyPlan` gains `coresident: bool = False`, read from `CORTEX_SWAP_CORESIDENT`. With it off
nothing whatsoever changes, and the shipped rule is exactly decision 8's: the deep model runs alone.
With it on, two things and no others:

1. `residency_moves.swap_in` stops the cortex and stops nothing else, so every `evict_models` tier
   stays serving through the handoff. The cortex still goes, because no measured pairing of it with
   a deep candidate fits this card.
2. `SwapConductor` does not enter the drain window at all, and does not announce one either, so
   delegated work keeps flowing and the deep phase may spawn.

The two belong together and neither is useful alone. A kept tier nothing may be delegated to buys
nothing; an open window over an evicted tier is the hazard the reopening deferral was recorded for.
They are safe together for one reason, which is worth stating as an invariant rather than a
consequence: **a co-resident handoff stops no tier delegated work can reach**, so there is no
instant at which admission is open onto a server nothing has restarted. `restore_standing` still
starts every `evict_models` tier on the way out, deliberately, because a start against a tier that
never stopped is a no-op the supervisor answers from its own child table, and because it is the one
place that would notice a peer that died while the deep model held the card.

The flag is an assertion the deployment makes about its own card, and nothing checks it, which is
recorded as a refinement rather than smoothed over: the brain container sees no GPU, and the
measurement above is the only way to know. A deployment that sets it on a card that cannot hold the
pair gets the silent 2x that opens this addendum, not a failure.

**Naming.** `CORTEX_SWAP_CORESIDENT` sits in the swap family (`CORTEX_SWAP_EVICT_MODELS`,
`CORTEX_SWAP_DRAIN_TIMEOUT_S`, `CORTEX_SWAP_LOAD_TIMEOUT_S`) and uses the word the deferral itself
has used since decision 8, so nothing has to be translated between the backlog and the env. The
honest alternates were `CORTEX_SWAP_KEEP_PEERS`, which names the mechanism rather than the property
and would have to be renamed the day a third thing is kept, and a `CORTEX_SWAP_KEEP_MODELS` list
paralleling the evict list, which was rejected for splitting one standing residency across two
settings that could disagree, and for needing its own overlap validator to say what one boolean
says by construction.

**Confirmed by the maintainer on 2026-08-07**, who raised decision 8's own rule against it: that
everything else is ejected during the handoff and the brain is exclusive while it works. That rule
is unchanged, and it is what the shipped default still does. What this addendum relaxes is the pair
of exceptions decision 8 recorded for itself, keeping CPU subagents serving through a swap and a GPU
subagent peer beside the deep model; the cortex is evicted either way, and no measured pairing of it
with a deep candidate fits this card. The flag stays, off by default. Recorded because the decision
was reached by the implementer and ratified afterwards, which is a different provenance from a
decision the maintainer made, and a later reader should be able to tell them apart.

### What decision 8 got wrong, corrected here rather than in place

- **The cortex figure.** Decision 8 budgets ~11.3 GB at 16K and the placer still reserves it
  (`CORTEX_VRAM_CORTEX_GB=11.3`). Measured on this build with the projector loaded it is 8448 to
  8468 MiB, so the shipped reservation is about 2.8 GB conservative. ADR-0004's own incidental
  observation predicted this and asked for a controlled re-measurement; this is it, and the
  reservation is left alone deliberately, since lowering it widens what the placer admits beside the
  cortex and that is a resource-governance decision with its own measurements to redo.
  **Those measurements were redone hours later the same day and the reservation is now 8.6**
  ([ADR-0012](ADR-0012-resource-governance.md)'s re-measured-reservation addendum). The figure this
  bullet published was an idle one; a reservation has to cover the peak, which is 8573 MiB above a
  floor read at both ends of the session, and the only thing that arrives with the work is the
  vision path's 70 to 90 MiB, a filled 16K context costing nothing beyond the load. The handoff
  charge above composes with the new value unchanged: it replaces this term for the window and
  restores it after, and what it restores is 8.6.
- **The reason CPU subagents are drained.** Decision 8 says the drain covers them because "the
  brain's hybrid-offload fallback and its KV want the host RAM/CPU headroom". ADR-0004's brain-pick
  addendum retired that premise on 2026-08-04: every candidate fits alone at `-ngl 99`, the hybrid
  fallback "is therefore not needed and is not configured". The surviving reason for the drain is
  the one the conductor's own comments give, that admission must not reopen onto an evicted tier,
  and it is exactly the reason a co-resident plan does not need it.
- **"No candidate fits beside the ~11.3 GB cortex in 24 GB."** True, and true for a second reason
  the arithmetic hid: at the measured cortex figure the lightest candidate ADR-0004 tested
  (gemma-4-26B-A4B, 14607 MiB) misses a 1552 MiB floor by 160 MiB, and it is the candidate that
  answered 0 of 4 escalation questions. The pairing that nearly fits is the one that cannot serve.
- **"Exercisable for the first time on hardware that fits the tiers it would keep alive."** The
  backlog's wording. The tiers it keeps alive are the deep model and the subagent peer, not the
  cortex, and that pair fits with 908 MiB to spare.

### What this deliberately does not do

- **No residency-set model.** `SwappingModelManager._resident` is still one model and `acquire`
  still leases one. It does not need to be a set here, because a subagent tier is leased through its
  own `SingleResidentModelManager` against a static endpoint and never through the swapping manager
  (`subagent_builders._entry_profile`). Co-residency of two tiers the *swapping* manager leases
  would need that change, and nothing asks for it.
- **No placement accounting for the window.** `VramBudgetPlacer` still fit-tests against
  `soft_cap - cortex_reservation - placed`, which during a handoff describes a card that does not
  exist: the cortex is gone and the deep model is not charged at all. Decision 8 suspends the soft
  cap in prose and nothing in code reads it. That was moot while the pool was drained, and
  co-residency is precisely what makes it reachable, so it is recorded as an open refinement.
- **No fit check.** See above; recorded, not built.

Both deferrals are written up in
[refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager) with their lines
in that backlog's index.

## Addendum (2026-08-07, later): the co-residency flag is checked, at the one instant it can be

The addendum above landed `CORTEX_SWAP_CORESIDENT` and recorded, as its own refinement, that
nothing verifies it: the flag is an assertion about a card, and the brain container sees no GPU.
This closes that refinement. It also narrows what the closing is allowed to claim, because the
measurement above is a warning about the instrument as much as about the pair.

**The instrument constrains the design, so the design starts there.** A genuine fit and a 4676 MiB
overcommit both read about 23.6 GB used with about 0.5 GB free once both tiers are up: the WSL2
driver pages the excess to system memory and reports success, and only decode rate says otherwise.
So a check that read the card **after** the load would answer the same for the configuration it
must accept and the one it must refuse, which is worse than no check, since it would license the
bad one in writing. Free memory is evidence at exactly one instant: **before the allocation, after
everything this handoff intends to unload is gone.** That instant is inside `swap_in`, between the
last `stop` and the `start`, and that is where the check went.

### The decision

1. **The model host reports the card.** `ModelHost` gains a fourth verb, `device_memory() ->
   DeviceMemory | None`, off the sidecar's existing `GET /health` body (now carrying
   `device_free_mib` and `device_total_mib`). The supervisor container is the only process in the
   stack with a device reserved, so it is the only one that can answer; the brain reads what it
   says. `None` is a real answer meaning "this host can see no card", not an error, because a
   CPU-only stack and the scripted backend are normal deployments.
2. **The daemon reads it with `nvidia-smi`**, behind a `DeviceMemoryProbe` seam beside the existing
   `ChildProcesses` and `HealthProbe` ones. The binary is injected into the container by the NVIDIA
   container toolkit alongside the driver, so it is present exactly where a GPU is reserved, which
   is the condition the seam has to report. Every failure is "no reading" rather than an exception,
   including **more than one visible GPU**: nothing downstream knows which card a model would land
   on, so this refuses to guess.
3. **The deployment declares what the deep model costs**, `CORTEX_SWAP_BRAIN_VRAM_MIB`, and the
   swap compares it against what is free immediately before the load. Short of it, `swap_in` raises
   `SwapFailedError` with both figures in the message, the deep model is never started, the scope's
   `finally` restores the standing residency, and the user gets the existing swap-failure note. A
   host that cannot answer at all fails closed the same way: a deployment that asked to be checked
   and cannot be is refused rather than run unchecked.
4. **Co-residency requires the figure at boot**, when the host is the real supervisor.
   `CORTEX_SWAP_CORESIDENT=1` with no `CORTEX_SWAP_BRAIN_VRAM_MIB` is a boot failure, in the same
   validator that already refuses escalation with no backend. Over the `scripted` host it stays
   optional, that backend starting no process on any card.

### Why the refusal is there and not somewhere else

- **Not at wiring time.** What a card has free changes by the gigabyte while the machine runs (this
  one's idle floor moved between 1529 and 2836 MiB inside a session, because Windows shares it), so
  a reading taken at boot is stale by the first handoff, and at boot the cortex is resident, which
  is not the residency the deep model loads into. Boot is still the right place for the half that
  **is** constant, the deployment's own declaration, which is why the validator refuses an
  unmeasured co-resident stack there. The brain still does not depend on the sidecar answering at
  wiring time, which is the objection the stop-bounds refinement recorded against enforcing its own
  pairing at boot: nothing here talks to the sidecar until a swap does.
- **Not by degrading to the evict-everything path.** Falling back to the shipped behaviour on a
  card that turns out to be short is tempting and is unsafe here, for a reason that is about
  ordering rather than taste: the conductor decides whether to drain **before** the swap begins, so
  a co-resident handoff has already skipped the drain and announced no window by the time `swap_in`
  reads the card. Stopping the peers at that point would reopen exactly the hazard the drain
  exists for, admission onto a tier nothing restarted, and it would do it silently. A handoff that
  cannot run as configured is refused, and the machine is left as it was found.
- **After the cortex is stopped, not before.** The refusal therefore costs one cortex eviction and
  its restore (measured 31.43 s) on a misconfigured deployment. Checking earlier would need the
  cortex's own cost as a second declared number to know what the eviction will free, and that
  number is the one ADR-0004 and decision 8 have both had wrong by about 2.8 GB. One measured
  figure that is compared against the real card beats two that are compared against each other.

### What this check can detect, and what it cannot

It detects **one thing**: at the instant before the load, the card had less free memory than the
deployment said the deep model needs. Live, on this machine: with the cortex resident the sidecar
reported 14905 MiB free of 24463, the deep model's declared 19125 MiB did not clear it, and
`swap_in` refused in 0.03 s without starting anything. With the cortex evicted, the same call on
the same card passed the check and loaded the deep model to `ready` in 69.24 s, leaving 3579 MiB
free. Those two runs differ in nothing but what was resident.

It cannot detect:

- **A declared figure that is wrong.** Nothing here measures a model; it compares a number the
  deployment measured against the card. Under-declare and the check passes and the load spills.
- **A spill that has already happened.** The reading is meaningless after the allocation, which is
  the whole instrument lesson above. This is now the shape of the one refinement this closing
  opens: the only witness of a spill is decode rate, and nothing in the brain watches it.
- **Memory taken during the load.** A tier-scale load is a minute or more, and the desktop sharing
  this card moves about a gigabyte on its own. A deployment wanting slack declares it, by adding it
  to the figure; there is no invented margin constant here, because a margin nobody measured is
  another unchecked assertion.
- **Anything about a peer.** The check asks whether the deep model fits in what is free. Which
  tiers are standing, and whether they should be, is the plan's business.

### Naming

`CORTEX_SWAP_BRAIN_VRAM_MIB` joins the swap family (`CORTEX_SWAP_EVICT_MODELS`,
`CORTEX_SWAP_CORESIDENT`, `CORTEX_SWAP_DRAIN_TIMEOUT_S`, `CORTEX_SWAP_LOAD_TIMEOUT_S`) and names
the fact it carries, the deep tier's own cost, in the unit every instrument and every measurement
in this repo publishes. The honest alternates: `CORTEX_SWAP_REQUIRED_FREE_MIB`, which names the
test rather than the fact and would have to be renamed the day a second tier is gated the same
way; and `CORTEX_VRAM_BRAIN_GB`, which would sit in the placer's `CORTEX_VRAM_CORTEX_GB` family and
was rejected for reading as a placement budget the placer does not consult, and for hiding MiB
behind a unit that would need converting at the seam where the two numbers meet. On the sidecar,
`CORTEX_MODELHOST_NVIDIA_SMI` names a binary path exactly as `CORTEX_MODELHOST_LLAMA_BIN` does.

### What this deliberately does not do

- **No spill detection.** Recorded as a refinement in
  [refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager): the brain
  would have to read llama.cpp's own `timings.predicted_per_second` after a handoff and say so when
  it collapses. That is the only instrument that separates a fit from a spill, and it is the honest
  residue of a check that can only see the room beforehand.
- **No reading on the seam.** `Health` still answers residency and says nothing about VRAM. A
  number that means something only at one instant of a swap is not a status field.
- **No second port.** The reading rides `ModelHost` rather than a segregated port, because its one
  caller is the swap, which already holds the other three verbs, and because it comes off the same
  daemon's existing route on the same client. `ResidencyReporter` was split from
  `ResidencyController` to keep a read-only caller from reaching a write; there is no such
  asymmetry here.

## Addendum (2026-08-07): the handoff window, as the subagent placer accounts for it

The co-residency addendum above opened a refinement it could not take at the time: `VramBudgetPlacer`
fit-tests every GPU-placed spawn against `soft_cap - cortex_reservation - placed`, and during a
handoff both named terms are wrong. The cortex whose reservation is credited has been evicted, and
the deep model holding 19117 to 19125 MiB of the card is charged nowhere, because it is not placed
through the placer. Decision 8 suspends the soft cap for the window in prose and nothing in code
read it. That was moot while every handoff drained the pool first, since no spawn could be placed
inside the window at all; `CORTEX_SWAP_CORESIDENT` is precisely the deployment that skips the drain
so delegation keeps flowing, which is what made the gap reachable and what makes it worth closing
now rather than on a trigger.

**The placer is told, and telling is a verb.** `SubagentPlacer` gains `charge_handoff(resident_gb=)`
and `charge_standing()`, moved with the protocol into `ports_placement.py` for the line cap and
re-exported from `ports.py`, so no call site moved. `VramBudgetPlacer` keeps the constructor's
cortex figure and fit-tests against a separate resident term the two verbs set, which is what lets
the standing figure survive the window and come back exactly. The ledger of placed spawns is
untouched by either edge: a spawn's VRAM did not move because the card changed hands, so its
reservation stands and its release credits the same amount.

**The writer is the residency scope, at the two edges of the swap** (`residency_charge.py`,
called from `SwappingModelManager._swap_in` and from the successful branch of `_restore`). Nothing
else knows when the card changes hands, and the conductor's drain edges are the wrong ones: a
co-resident handoff has no drain, and the scope is the object whose `finally` guarantees the
reversal on every path.

**What is charged is the declared figure, not a fresh reading**, and the reason is the spawn path.
`place` is synchronous and lock-free by design, so a batch of concurrent spawns races the ledger
correctly with no lock; reading `device_memory()` there would put an HTTP call to the sidecar inside
every fit-test and make the whole path async, to buy accuracy the swap has already bought. The fit
check in the addendum above compares that same `CORTEX_SWAP_BRAIN_VRAM_MIB` against what the card
reports free at the one instant a reading is evidence, and refuses the handoff when it does not
clear. So by the time the window matters, the declared number has been checked against the real
card. `ResidencyPlan.brain_vram_gb` is the one conversion, MiB to the gibibyte the placer's budget
knobs are written in.

**The two compose by ordering rather than by agreement.** The charge is written before `swap_in`
runs, so it is in force while the check reads the card and while the weights load. That direction
closes a gap the check cannot see on its own: a spawn admitted to the GPU between the reading and
the allocation would spend exactly the room the check just measured. The reversal waits for the far
edge and fires only once the cortex is genuinely serving, so a restore that gave up loudly keeps the
handoff's charge and keeps spawning on the CPU rather than admitting GPU work onto a card nobody can
describe.

**Off unless the deployment declared a figure.** With `brain_vram_mib` at its shipped zero the window
is never entered. Charging nothing would be worse than the status quo, since it would credit the
evicted cortex's 11.3 GB back while the deep model holds the card, so that deployment keeps exactly
the arithmetic it always had.

**Measured live** on the 24 GB card through the real sidecar and a real residency change
(`test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card`): 15061 MiB free of 24463
with the cortex resident, 19553 MiB free inside the window, a charge of 18.68 GiB leaving 4.32 GiB
of headroom against the shipped 5.5 GiB ask, so one spawn lands on the GPU outside the window, on
the CPU inside it, and on the GPU again after the restore. The test declares the deep tier's measured
cost and starts the cheap peer tier in its place, deliberately: a 19 GB load adds minutes and no
evidence, and the check passes either way once the cortex is evicted, there being that much room.

**What this does not do**, stated as narrowly as the fit check states its own limit. It charges a
number the deployment declared, so an under-declared figure is admitted against room that is not
there, which is the spill entry the fit check opened and the same instrument lesson. And a spawn onto
an already-resident tier allocates nothing (23639 MiB generating against 23642 idle), so a refusal
inside the window costs decode speed rather than correctness; the ledger charging per spawn for a
standing tier is the older modelling gap, and closing it is the placement-aware charge that ADR-0012
declined on a second GPU-capable executor.

## Spill-watch addendum (2026-08-08): the handoff the fit check cannot see, caught by decode rate

The fit check above reads free device memory immediately before the load, and its own closing
section named what it does not do: nothing detects a spill that happened anyway. That residue is
now closed. This addendum is here rather than in a new ADR because it decides nothing about
handoffs that the fit check did not already frame; it is the second half of one instrument. The
first half asks "is there room", at the one instant that question is answerable. This half asks
"was there room", at the one instant *that* question is answerable, which is while a real
completion is running on the tier that was loaded.

### The failure, re-derived before designing

Two things pass the fit check and spill regardless: a deployment that declared
`CORTEX_SWAP_BRAIN_VRAM_MIB` too low, since nothing here measures a model, and memory the desktop
takes while the load runs, this machine's idle floor having moved between 1529 and 2836 MiB inside
one session. In both cases nothing fails. The WSL2 driver pages the overcommit to host memory
rather than refusing it, both tiers answer `ready`, the health gate passes, the stream works, and
the card afterwards reads like a fit.

Re-derived from the tree on 2026-08-08 rather than taken from the entry: a grep for `timings` and
`predicted_per_second` across `brain/packages` found the string only inside two live tests' own
wall-clock timing dictionaries, so **nothing in the brain read the server's own figure**, and
`LlamaCppBackend` discarded the chunk that carries it. Verified against the running stack that the
figure is there to be read: llama-server build `b10298-15586e2d7` puts one `timings` object on the
**final** chunk of an ordinary streaming `/v1/chat/completions`, unasked, exactly one chunk of a
twelve-chunk stream carrying it. So no request anywhere had to change to get this.

### Decision: a port arm, a pure watch, and one sentence in the log

**1. `InferenceEvent` gains a `DecodeCadence` arm.** A backend whose engine reports how fast it
decoded closes its stream with one, after the text it describes, since a rate is only knowable
once the tokens are counted. It carries `tokens_per_second` and `tokens`. Reporting none stays a
legitimate implementation of the port, so silence means "no reading" and never "healthy"; that
permission is what `EchoInferenceBackend` exercises, an echo having no server and therefore no
timings to invent. The name is not a `*Chunk` because it is not a delta of anything, and it is not
`Timings` because that is one engine's noun on a port ADR-0005 says any engine may implement.

**2. The cadence never becomes a turn event.** `stream_tool_loop` absorbs the arm into an optional
`CadenceWatch` on its `ToolLoopContext` and yields nothing. How fast the machine decoded is a fact
about the machine, not something the turn said, so it must not reach a stream the user reads. Every
caller but the deep phase passes no watch and drops it, which is why the arm costs the cortex turn
and every subagent nothing.

**3. The watch is pure policy with two rules, both of which exist to keep a slow number honest.**
A sample under `MIN_CADENCE_TOKENS` (32) is counted and never judged, a short completion's rate
being dominated by whatever the server was doing when it started. And the **fastest** qualifying
sample decides, because a spill is a ceiling that holds for every completion while the overcommit
lasts, so judging on the fastest cannot convict a card that was briefly busy during one round of a
tool loop, while a tier that never once reached its floor is exactly what a spill is.

**4. The floor is the deployment's own measurement**, `CORTEX_SWAP_BRAIN_DECODE_TPS`, riding
`ResidencyPlan` beside `brain_vram_mib` and just as unknowable from inside a container. It is
**not** required by co-residency the way the VRAM figure is, and the asymmetry is the point: the
VRAM figure guards a decision taken before anything is loaded, so a deployment that omits it is
misconfigured at boot, while this one guards nothing. Zero reports the observed rate and judges
nothing, which is worth more to an unmeasured deployment than a boot failure, since the number in
its log is what a floor would later be set from.

**5. On a collapse the deep phase says so, once, and does nothing else to the turn.** The other
three options were considered and are worse. **Refusing** would spend a user's answer on an
operator's problem, and it cannot even do that honestly: the rate is known only after the reply has
streamed. **Degrading** has nothing left to degrade at that point. **Telling the user** puts infra
telemetry in an assistant reply, and it would arrive after the reply anyway. So the actor is the
operator, and what the watch replaces is a manual procedure this repo already documents:
`docs/runbooks/model-swap.md` tells a human to read `timings.predicted_per_second` off a completion
on each tier when a co-resident deep phase feels slow. That procedure cannot be run after the fact,
the completion being gone, and it now runs itself at the only moment it can. A healthy handoff logs
its rate at INFO too, from the same instrument, because the number that makes a later warning
readable is the one from the day it was fine.

### Measured on the card (2026-08-08)

Through the shipped `LlamaCppBackend` and the shipped watch, gemma-4-31B QAT q4_0 as the deep tier
beside gemma-4-12B QAT q4_0 as the cortex, on the 24 GB card (24463 MiB), three completions of
about 120 words an arm. The middle and last rows are reproduced by
`packages/inference/tests/test_decode_cadence_live.py`, integration-marked, whose two worlds are
arranged by starting or stopping the peer through the model-host control API. The **cold** row is
not, and that suite's own docstring says so: it was driven from a script through the same shipped
adapter and watch, so the 31.08 to 33.78 figures have no committed reproducer and a rerun has to
arrange a clear card by hand:

| Arm | card afterwards | decode | best | verdict at a declared 25.0 tok/s |
| --- | --- | --- | --- | --- |
| deep alone, cold onto a clear card | 2310 MiB free | 31.08, 31.85, 33.78 | 33.78 | not collapsed |
| **cortex resident, then deep** | **423 MiB free** | **21.64, 20.38, 22.77** | **22.77** | **collapsed**, 2.23 short |
| deep alone, the peer evicted under it | 8649 MiB free | 28.32, 29.82, 29.38 | 29.82 | not collapsed |

**Every tier a row had resident reported `ready`, the middle row's two included**, which is where
the claim bites: the outer rows run the deep tier alone, so there is no second tier there to have
said anything. The middle row is a co-resident handoff's own load
order and it is the one this addendum exists for: the deployment's fit check had nothing to refuse,
the card read like a fit, and the decode rate is the whole of the difference. The third row is the
same floor passing on the same tier minutes later, which is what makes the middle row's refusal
evidence rather than a gate that always fires.

Two things the run found that were not in the entry. **A spilled tier does not fully recover when
its peer is evicted**: 29.82 tok/s against 33.78 from cold, with 8649 MiB free where the cold load
read 2310, so part of the tier stays off the card until it is reloaded. A floor is therefore read
as a floor and set from a cold load. And **which tier pays depends on load order**: loading the
cortex second, beside an already-resident deep model, cost the deep model only 23.28 tok/s at its
best rather than 20.32, the driver evidently paging the newcomer first. A handoff always loads the
deep model second, so the measured arm is the one that matters, but a report of a slow *cortex*
after a handoff has the same cause read from the other end.

### Proven able to fail before being trusted

The parse, the routing and the policy were each mutated and reverted. Dropping the timings read
reddens the adapter leg of the shared contract and no scripted case; removing the loop's cadence
branch reddens every deep-phase case that expects a reading; logging a collapse at INFO reddens
the warning case; keeping the slowest sample instead of the fastest, dropping the short-sample
guard, judging against an undeclared floor, and answering with a reading when nothing qualified
each redden their own named test. One mutation did **not** redden what it should have, and that is
recorded rather than smoothed over: reordering the adapter's yields does not redden the contract's
ordering check, because on this build the `timings` object rides a content-less chunk and the order
is the transcript's rather than the adapter's. The case where the adapter's order is its own, one
chunk carrying both, is pinned in `test_backend.py` instead, and that is what the mutation reddens.

A second lesson came out of the same pass. The first run of that mutation reported green against a
**stale `.pyc`**: `cp` restoring the source within the same second as the bytecode's write left
Python believing the cache current. Every mutation here was re-run with `__pycache__` cleared, and
a mutation result taken without clearing it is not evidence.

### What this deliberately does not do

- **It does not act.** The watch has one actor, the operator reading the log, and that is argued
  above rather than assumed. The obvious next actor, a handoff that stops promising co-residency
  once it has watched itself spill, is recorded as a deferral in
  [refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager) rather than
  built, because it latches a working feature off on evidence one turn wide and `ResidencyPlan` is
  a frozen value with nowhere to keep the latch.
- **It does not watch the cortex.** Only the deep phase carries a watch, since only a handoff
  changes what is on the card. A standing cortex that spilled did so because something else on the
  machine took the card, which is not this repo's event.
- **It does not watch prefill.** The runbook records prompt rate collapsing to 13.8 tok/s against
  105 to 134 on a fitting pair, which is a second and possibly sharper witness. It is left out
  because prefill rate varies with prompt length far more than decode does, so a floor for it is a
  harder number for a deployment to measure, and one instrument that works beats two that need
  calibrating. Recorded as a deferral with that trigger.
- **It does not ask the server for anything.** No request changed, because this build volunteers
  the figure. A build that does not would need `timings_per_token`, and the adapter would then be
  changing every request in the repo to serve one phase.

## Deadline-pairing addendum (2026-08-09): the timeout rule is checked, not only written down

The audit round above left the timeout pairing **documented rather than enforced**, and gave the
reason: the sidecar's bounds and the brain's control deadline are two containers' environment
variables, and neither process can read the other's. That reason went half false the same day, when
`GET /health` began reporting the two stop bounds the daemon was actually given. This finishes the
other half and does the comparison, closing the refinement that round opened.

**Re-derived from the tree before anything was designed**, as the backlog's own warning demands,
and the entry held on every point. `api.py` published `stop_grace_s` and `reap_timeout_s` and not
`probe_timeout_s`, which existed on `ModelHostConfig` and was spent in exactly one place, the
`httpx.Timeout` on the readiness probe's client. `build_control_client` took a float and compared
it with nothing. The shipped arithmetic still cleared: 5 + 10 + 30 = 45 under a 60 s deadline.

### The decision

1. **The daemon publishes all three terms.** `probe_timeout_s` joins the other two on `GET
   /health`, and the three travel as one frozen core value, `ControlBounds`, beside `DeviceMemory`:
   `worst_case_stop_s` is their sum and `clears(deadline_s)` is the rule, strict, because a
   deadline equal to the sum times out on the very call the sum describes. The supervisor's
   two-term `StopBounds` is gone, since a two-term value is exactly the reading that stated this
   rule wrong the first time.
2. **The supervisor is what holds it**, handed the probe's deadline although it spends none of it.
   That deadline is a bound on a supervisor operation whoever pays it: `status` probes inside the
   same per-model lock a `stop` takes, so a queued stop waits it out. One object can therefore
   state the whole worst case of its own slowest call, and the API stays a serializer with no
   arithmetic and no second source.
3. **`ModelHost` gains a fifth verb**, `control_bounds() -> ControlBounds | None`, off the same
   `GET /health` on the same client as the card reading, and `None` the same way: a host that
   supervises no process has no stop to bound, which is what the scriptable twin genuinely is. The
   shared contract suite drives it over both implementations.
4. **The composition root compares, and refuses.** `check_control_deadline` runs in
   `swap_builders.py`, where the adapter is wired, and the root gates the runtime through it on its
   way out of the builder, before the backends, stores and tools below it exist. A host that
   answers bounds the configured deadline does not clear raises `ControlDeadlineError` naming every
   term, after releasing what the runtime already holds, since the root's shutdown hook is not
   armed that early. Boot recovery moved into that same module in the same change, as
   `recover_boot_residency`: `wiring.py` had reached the line cap, and the swap's two boot-time
   concerns belong beside the swap's other wiring rather than in the file that reads env.
5. **Only an answered mismatch refuses.** A host that cannot be asked is logged at warning and let
   through, and a host that answers no bounds is logged at info.

### Why wiring time is right here and was wrong for the card

The co-residency addendum above refused to check its own figure at wiring time, and the argument
was about what it was checking: free device memory moves by the gigabyte while a machine runs, so a
boot reading is stale by the first handoff. Three env values are the opposite kind of fact. They
cannot change under a running container, so one reading answers for the life of the process, and
the check costs one request at boot instead of one per swap step. The two decisions point in
opposite directions because the two quantities do.

### The cost the entry named, and what it turned out to be

The entry priced this as the brain gaining a wiring-time dependency on the sidecar answering,
"which today it deliberately does not". That is half right. The dependency already exists:
`recover_handoffs` runs at startup, before the seam serves, and issues `status`, `stop` and `start`
against this very sidecar. What it deliberately does not do is **raise**, and its own module says
why: a compose restart policy revives a daemon whose boot default is cortex-up, so a brain that
refused to start beside a sidecar that is merely down would be worse than one that logs and serves.
So the real cost was never the request; it was the risk of turning a tolerant boot dependency into
a fatal one. Tolerating unreachability and refusing only an answered mismatch keeps the tolerant
dependency exactly as tolerant as it was.

**Refusing rather than logging is the other half of that judgement, and it is a judgement.** A
mispaired deadline is static: no restart policy heals it, and only an operator editing env does.
Its failure is intermittent, because a stop pays the whole SIGTERM grace only when the tier it
evicts was answering (10.09 s measured busy against 0.40 s idle), so a mispaired stack works
through every quiet eviction and aborts the one that mattered. A boot refusal is how this repo
already treats an escalation with no model host and a co-residency flag with no measured fit, and
this is the same kind of misconfiguration read from a running container instead of from env.

### Proven able to fail before being trusted

Each mutation was applied to production code alone, `__pycache__` cleared, and the whole `packages`
suite re-run, so the counts below are what actually reddened rather than what was aimed at.

- Making `clears` answer `True` whatever the numbers reddens **4**: the boundary case in
  `test_model_host.py` and all three refusal cases.
- Dropping the refusal itself (logging the mismatch and serving anyway) reddens **3**, those same
  three, which is what separates the arithmetic from the policy over it.
- Refusing an unreachable host as well as an answered mismatch reddens **1**,
  `test_a_host_that_cannot_be_asked_leaves_the_pairing_unchecked`, so the tolerance is pinned as
  deliberately as the refusal.
- Dropping `probe_timeout_s` from the health body reddens **2**, the API's own health case and the
  shared contract's supervisor leg; no scripted case reddens, the twin echoing what it was handed.
- Reading a partial set of bounds as bounds (guarding only the first term) reddens **2**, the
  negative and the bool rows of the adapter's parameterization.
- Dropping the composition root's own call reddens **1**, and only the case that drives
  `run_from_env`, which is why that case exists beside the ones that drive the check directly.

One thing the first attempt got wrong is worth recording: that root-level case originally hung
instead of failing, because a root that never refuses goes on to `serve`, which returns for nothing
a test can arrange. It is bounded by `asyncio.wait_for` now. A mutation that hangs the suite is not
a proof that it reddens.

### What this deliberately does not do

- **It does not re-read the bounds while the process runs.** Env cannot change under a container,
  so the only way the answer goes stale is a sidecar that restarts under a running brain with a
  changed environment. That is the same staleness, with the same fix (a generation the brain can
  compare on `GET /health`), as the residency-reconvergence refinement already open in
  [refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager), so it is
  folded into that entry rather than counted beside it.
- **It does not register the pairing in the constant scan.** `crosscheck.py` ties a value spelled
  in several places by equality or by pairwise order; this is a **sum of three** values under a
  fourth, which no registry entry can express. The tie is a test instead, reading both containers'
  shipped defaults at once and asserting the pair still clears, which is stronger than the comment
  that used to add them up.
- **It does not bound anything new.** No timeout moved, no default changed, and a stack whose
  numbers already paired boots byte for byte as it did, one `GET /health` heavier.

## Host-generation addendum (2026-08-09): the brain notices when the daemon under it is replaced

The addendum above closed the deadline pairing and left one staleness behind, folded into the
residency-reconvergence refinement rather than counted beside it: a sidecar that restarts under a
running brain leaves the pairing check as stale as it leaves residency, and the same identifier
closes both. This is that identifier and both of its readers.

**Re-derived from the tree first, as the backlog demands, and the entry was right about the code
and wrong about one consequence.** `converge_residency` did exist, already written, in
`swap_recovery.py`. `recover_handoffs` was called from exactly one place, the boot path, which had
moved into `swap_builders.recover_boot_residency` in the previous change. `SwappingModelManager`
did hold `_resident`, `_scope_model` and the report as instance state, and `GET /health` carried
no identity field of any kind. What the entry does not say, and what the tree does, is that
`converge_residency` is **not free to run speculatively**: it stops every `evict_models` tier that
is not already stopped and starts them all again, which is precisely what a `coresident` plan
exists to avoid doing to its standing peers. That single fact shapes everything below.

### The decision

1. **The identifier is a boot id, not a generation counter, and it is `uuid4().hex`.** It is
   minted in `ModelSupervisor.__init__`, so it is one value per supervisor instance and therefore
   per daemon process, and it certifies the child table that object holds: a brain seeing a value
   it has not seen before knows every belief it formed about what is resident was formed against a
   table that no longer exists. A counter was rejected on the requirement itself, which is that the
   value must survive no restart: a counter in a process that restarted begins again at exactly the
   number the comparison exists to notice. Nothing derived from the container helps either, since a
   restarted sidecar is pid 1 again at the same address with the same env. The field is therefore
   compared for **equality only**, and the port says so: it names which boot, never how many, so no
   reader can be tempted to order two of them.
2. **It rides `GET /health`**, beside the roster, the three control bounds and the two device
   figures, and `ModelHost` gains a sixth verb, `boot_id() -> str | None`, shaped exactly like the
   fifth: same route, same client, `None` for a host that will not say, which is a daemon older
   than the field or the scriptable twin. An empty string and a non-string both read as no answer,
   because this value is compared for equality and an empty id would compare equal to the next
   daemon's empty id.
3. **The brain's half is `BootWatch` in `residency_watch.py`, held by the manager**, which is the
   object that owns the beliefs at stake and the only one that may rewrite them. The writer arrives
   as a `ResidencyPublisher` (the manager's own `_set_resident`, typed in `residency_state.py`), so
   the watch never reaches into that state. `observe(boot_id) -> bool` is the whole decision and is
   pure: `None` keeps what was remembered, a first answer is a seed, anything else is a replacement
   and is remembered at once so one restart reconciles once.
4. **A first observation is a seed and never a change**, which is decision 1 of the co-residency
   addendum protecting itself. Converging bounces every evictable tier, so a watch that treated its
   first daemon as new would take down, on the first handoff of every process, the standing peers a
   co-resident plan keeps serving through a swap. The seed is taken in
   `publish_boot_residency`, which is the moment boot recovery's observation is published: an
   answer about the GPU is an answer about the daemon that gave it, so recording which daemon that
   was belongs with recording what it said, and the first handoff then has something to compare
   against rather than a blank.
5. **The observation happens at the top of `_swap_in`, inside the residency scope and before
   anything is evicted.** That is the one moment the beliefs are about to be spent, and it needs no
   port change and no new refusal path in the conductor: a `SwapFailedError` raised there is
   already carried by `_swap`'s `except ModelManagerError`, which fails the record, streams the
   note that says the deep model could not be loaded and nothing was unloaded, and lets the scope's
   own `finally` restore. Both of those statements are true on this path, and the drain the
   conductor already performed is reopened by the `finally` it always was.
6. **A replacement rebuilds both halves.** Residency first: `converge_residency` runs, and what it
   observed is published, so the manager's resident, the seam's report and the machine come out of
   one reading instead of disagreeing. A convergence that could not settle the cortex publishes
   that nothing is resident and refuses the handoff, deliberately unlike `publish_boot_residency`,
   which leaves the resident alone: at boot the seed is only an assumption and the GPU may well be
   serving, while here the beliefs are known to have been formed against a process that is gone.
   The deadline pairing second: `control_bounds()` is read again and the handoff is refused when
   `plan.control_deadline_s` no longer clears the sum. Residency is rebuilt whether or not the
   pairing still holds, because the machine's state is what a stale belief endangers; the pairing
   decides only whether this handoff may proceed.
7. **The deadline moves onto `ResidencyPlan` as `control_deadline_s`**, and
   `check_control_deadline` reads it there instead of taking it as an argument. Two readers now
   compare one deployment value against the host's worst stop, and a value handed to two callers
   is a value that can differ. It is the plan's kind of fact: composition-root config, handed down
   as one object so the manager, the conductor and boot recovery cannot disagree.
8. **Every unanswered question stands down rather than refusing.** A host that cannot be asked
   which daemon it is, a host that names no boot, a host that will not state its bounds, and a
   plan that declared no deadline all leave the beliefs exactly where they were. That is the same
   tolerance the boot check argues for, and it costs nothing: a swap whose host is unreachable
   fails at its very next move with the failure that really happened.

### What the entry's own account got right, and the one hazard it glossed

The scout's warning was the right one: `converge_residency` acts on the `ModelHost` and would have
left the manager still describing whatever it believed before. That is why the publisher is passed
in rather than the convergence being called for its effect. The hazard turned out to have a
narrower shape than feared for `_scope_model`, and the shape is worth recording: the reconciliation
runs **inside** the one residency scope there can be, having entered it, and a concurrent scope is
refused by `_begin_scope` and, earlier, by the handoff claim. So there is never a live scope
belonging to somebody else to reset, and `_scope_model` needs no rebuilding at all. The beliefs
that can be stale and are rewritten are the resident and the report.

### Proven able to fail before being trusted

Each mutation was applied to production code alone, `__pycache__` cleared, and the whole
`packages` suite re-run, so the counts are what actually reddened rather than what was aimed at.

- Treating a first observation as a change reddens **3**, and the third is the one that matters:
  a co-resident plan losing its peers on a brain whose boot could not reach the sidecar.
- Remembering nothing reddens **12**; clearing what was remembered when a host will not say reddens
  **1**, and only on one line, since a silence **between** two daemons is the sole sequence in
  which erasing changes an answer.
- Skipping the deadline re-read after a replacement reddens **3**. Refusing on an unreachable host
  instead of standing down reddens **2**, and doing the same for unreadable bounds reddens **1**,
  so both tolerances are pinned as deliberately as the refusals.
- Publishing nothing after a successful convergence reddens **7**, which is what ties the beliefs
  to the reading rather than to the machine alone; publishing nothing after a failed one reddens
  **1**.
- Dropping the reconcile from the swap reddens **9**, across the residency, conductor and chaos
  suites, all of which read the op log; dropping the seed from the boot publish reddens **2**.
- Dropping `boot_id` from the daemon's health body reddens **2**, the API's own case and the shared
  contract's supervisor leg, and no scripted case, the twin echoing what it was handed. A
  supervisor minting a constant instead of a fresh value reddens **1**. An adapter taking whatever
  the body carries reddens **2**, the empty-string and non-string rows.

### Validated against a real container, since one claim here is not a CI claim

The suite proves the wire over a real supervisor and a real Starlette app, but the property the
whole design rests on is about **two processes**: that a daemon which has been replaced names
itself differently. So it was checked by the agent on 2026-08-09 against the real sidecar image,
built from `brain/Dockerfile.modelhost` and run with no GPU and no model mount (the mechanism is
control plane, so neither is needed, and the model drive was not mounted in that session).

`GET /health` before and after a `docker restart` answered with an identical roster and identical
bounds and a different `boot_id` (`e00cac75...` then `72171196...`), which is the point stated
negatively: nothing else on that body distinguishes a restart. Driven from the brain's own side
over real HTTP, the real `HttpModelHost` read the id and the bounds off that container, a second
`reconcile` against the same daemon published nothing at all, and a `reconcile` after a real
restart logged "the model host has been replaced since the last handoff", tried to converge, and
refused with `SwapFailedError` having published `(None, RESIDENCY_LOST)`. That refusal is correct
for the deployment under it, whose roster held one tier and no artifact file, so convergence could
not settle a cortex that cannot load: the failing path was exercised end to end rather than
described.

### What this deliberately does not do

- **It does not watch continuously.** The reconciliation happens once per handoff and once at
  boot, and nothing probes between them, so a restart followed by no handoff is noticed by nothing
  and `Health` can report a stale residency for that window. This is the same trade the
  honesty-surfaces sub-slice made when it refused to pay a probe per `Health` (priced there at up
  to 5.80 s against a 5 s recheck), and it is now the recorded residue of this entry rather than
  the whole of it: with escalation off the plain `SingleResidentModelManager` holds no residency
  state at all, and with it on the only reader that can be misled between two handoffs is the
  indicator.
- **It does not re-read the card.** Free device memory is the quantity the co-residency addendum
  refused to check at wiring time because it moves by the gigabyte while a machine runs; a boot id
  and three env values are the opposite kind of fact, which is why these are read on an event and
  that one is read immediately before each load.
- **It does not register the field in the constant scan.** `boot_id` is a JSON key spelled in the
  daemon that writes it and the adapter that reads it, exactly like `probe_timeout_s` and
  `device_free_mib` beside it, and neither side declares it as a named constant, so `crosscheck.py`
  has nothing to compare. What ties them is the shared `ModelHost` contract suite, which drives the
  same check over the twin and over the real adapter talking to a real supervisor through a real
  Starlette app: dropping the field from the daemon reddens that leg.
- **It does not resume the handoff it refuses.** A refused handoff ends as every other refused one
  does, with the honest note and the cortex serving. Resuming from the record remains the separate
  deferral it was, waiting on the same request-identity design.

## Tier-outage addendum (2026-08-09): a peer that would not restart is recorded, skipped, and retried

The deferral opened by the drain-window pass on 2026-07-18 and recorded at the reopening addendum
above, **admission reopening even onto a tier the swap back could not restart**, closes here. That
addendum named the fix in one sentence ("residency state that knows a tier is down, so the placer
skips it while something retries the start"), and this is that sentence built, plus the two
questions it did not ask: how a reader tells a tier that is **down** from one that is merely
**evicted**, and what clears the record so a single transient failure does not degrade the stack
for the life of the process.

### What the tree said, against what the entry claimed

The entry was re-derived from the code before anything was designed, as this backlog's own standing
warning demands, and three of its claims held while two moved.

Held: `residency_moves._restart_evicted` really does log a `ModelHostError` and swallow it, by
decision 4's design; `SwapConductor._undrain` really does reopen admission on every path, after the
swap generator closes; and the honesty surface really does carry no per-tier state, `ResidencyReport`
being two fields, `serving` and `detail`.

Moved, first: the entry says the fix "wants a residency state that knows a tier is down ... rather
than a scheduler change", and adds that this port stays unchanged. The scheduler is indeed
untouched. **The placer port is not**, and the entry never claimed either way, having been written
before `SubagentPlacer` grew the handoff-window pair. `place` is synchronous, lock-free and
argument-poor by design, so a placer cannot be *asked* whether a tier is up; the only shape that
fits this object is being *told*, which is a verb and therefore a port change. This area's standing
"behind the unchanged port" phrasing was again the thing to check first rather than to repeat.

Moved, second: the entry's proposal was to widen `ResidencyReport` itself, on the grounds that the
honesty-surfaces sub-slice gave it "a place to put it". Widening that value would have been wrong,
and the reason is a lifetime rather than a shape. A report is republished at every residency
transition, so a tier's down-ness written into one would be dropped by the next swap in, which
publishes `RESIDENCY_LOADING` and knows nothing about peers. The record therefore lives beside the
report and is folded into it on read.

### The decision

**One new pure-core record, `StandingTiers` (`residency_tiers.py`), held by `SwappingModelManager`.**
It knows which peers of the cortex the standing residency is missing. Its one writer is the
best-effort restart loop: `mark_missing(model)` where the `ModelHostError` is already caught,
`mark_standing(model)` where the host accepted the start. Its three readers are the placer, the
seam, and the retry.

**Two new verbs on `SubagentPlacer`, `close_gpu()` and `open_gpu()`.** While closed, `place`
answers CPU for every request without consulting the headroom. They are deliberately not
expressed as arithmetic: charging a resident large enough to crowd the cap out would make the
placer say "no room" where the truth is "no server", and it would collide with the handoff charge,
whose own reversal would then silently reopen a tier's outage. `VramBudgetPlacer` is the one
implementation and `test_placer.py` is the contract suite that pins both verbs; the port's
docstring states the degenerate form for an implementation with no GPU target of its own, exactly
as it already does for the charge pair.

**One bit for the card, a record per tier.** The record names each missing tier, because that is
what an operator reads and what a retry acts on. The lever it pulls is coarser: any missing tier
closes GPU placement for the whole pool. The brain has no declared mapping from a hosted tier id
(`CORTEX_SWAP_EVICT_MODELS`, a model-host roster name) to the GPU endpoint a roster entry dials
(`CORTEX_SUBAGENTS_GPU_ENDPOINT`, a URL), and inventing one now would be config with exactly one
possible value in every deployment this repo ships. The conservative direction is the right one
anyway: over-refusing the GPU costs decode rate, under-refusing costs a dead load, a failed
attempt and a CPU re-run for every spawn.

### Down versus evicted, which is the distinction the whole thing turns on

A placer that treats an evicted tier as broken refuses work the stack can do; one that treats a
broken tier as merely evicted sends every spawn into a start that fails. Three things keep them
apart, and none of them is a comment.

1. **Only a refusal marks.** The record is written where a `start` **raised**, never where a swap
   deliberately stopped a tier. A swap in touches it not at all.
2. **Only a serving report is annotated.** `StandingTiers.note_on` hands back any report that is
   not serving untouched, so the four swap windows keep their own words. Mid handoff the peers
   are stopped on purpose and the report already says a swap is happening; annotating that would
   describe the swap twice and call it a fault.
3. **The window is covered by something else entirely.** During a non-co-resident handoff the pool
   is drained, so no spawn is placed at all, and during a co-resident one the peers are never
   stopped. The arithmetic correction for the card changing hands is the handoff charge, which is
   a separate pair of verbs for a separate fact.

A reader tells them apart the same way: `ready=false` with a swap window's line means evicted and
coming back; `ready=true` with a tier named means down.

### What clears the mark

A mark with no clearing path is a defect rather than a safety feature, so there are three, in
increasing order of how much has to go right.

- **A retry pass that observes the tier serving.** `TierHealer` (`residency_heal.py`) calls
  `SwappingModelManager.heal_standing_tiers()` every `CORTEX_SWAP_TIER_HEAL_S` seconds (30 s).
  A pass asks `status` per missing tier: `READY` marks it standing, `LOADING` is left alone (it is
  on its way, and starting it again would say the same thing every pass for the whole load), and
  anything else gets one `start`. Readiness is observed on a later pass rather than gated inside
  this one, so a tier that takes minutes to load costs the loop nothing while it does. A pass
  never raises, so one unreachable tier cannot stop the others being retried.
- **The next handoff's own restart**, unchanged: `_restart_evicted` is unconditional, so a swap
  back that succeeds where the last one failed marks the tier standing again.
- **A restart of the brain**, which rebuilds every belief from boot recovery.

The retry is what makes this a fix rather than a permanent degradation. Escalation is rare by
construction, so leaving the next handoff as the only clearing path would mean a transient failure
costs the GPU pool until the user happens to escalate again, which may be hours or never.

Two things the retry deliberately does not take: **the GPU lease**, because a peer is never the
resident and holding it across a control call would park a user's turn behind a status probe; and
**a pass while a scope is active**, because starting a peer while the deep model is alone on the
card is the one forbidden move. A scope that begins in the instant after that check costs nothing
either, since the swap in's first move is to stop these very tiers.

### What the user sees, on a surface that already existed

No new surface. `HealthReply` already carries a `detail` beside `ready`, the body already copies it
verbatim into `LinkStatus`, and the overlay already renders a **ready** detail as
`Brain ready: <detail>` (`describeLink`); today that slot holds the orchestrator's version string.
So a serving report with something to say simply wins the slot, and the tooltip reads
`Brain ready: the model host is not running subagent-gpu, so delegated work is running on the CPU`
(the sentence this shipped with named a deep task as the cause, corrected by the boot-verdict
addendum below when boot recovery became the record's second writer).
The dot stays green, which is correct: turns run, delegation runs, and the one thing
that changed is where delegated work runs. Zero proto, Rust, or TypeScript change, which is the
whole reason to prefer this over inventing a second surface.

`ResidencyReport`'s docstring said the detail is empty while serving. It is amended rather than
quietly contradicted: serving and "nothing to report" stopped being the same thing when the
standing residency grew peers that can be down while the cortex is up.

### Proven able to fail before being trusted

Nine mutations, each applied to production code alone with the whole brain workspace re-run, then
reverted; the counts are in `test_residency_tiers.py`'s header and are measured rather than aimed
at. Dropping `mark_missing` reddens 7 across two packages, dropping `mark_standing` 1, reopening
on any restart rather than on an emptied record 1, annotating a not-serving report 1, consulting
the headroom before the closed flag 7, starting a `LOADING` tier 1, dropping the scope guard 1,
dropping the loop's pass guard 1, and dropping the seam's serving-detail branch 1.

The table also earned its keep the way this repo says it should. The first case written here,
"a peer that would not restart closes GPU placement", was **vacuous**: it held its first
placement's 2.0 GiB against a 3.0 GiB headroom, so the spawn it asserted on spilled for want of
room whatever the record said, and dropping `mark_missing` left it green. It releases now. Every
wait in that file is inside an `asyncio.timeout`, so the loop mutations fail on a bound instead of
hanging the suite.

### Validated over the twin, and then against a real sidecar

The whole path is exercised over the scriptable `ScriptedModelHost` and the real
`VramBudgetPlacer`, driving the real `SwappingModelManager` through real residency scopes: a
failed peer restart, a peer that came back, one peer of two, the retry's two passes, a tier still
loading, an unreachable host, and a retry deferred by an active scope.

The claim underneath all of that is not a CI claim, so it was checked on 2026-08-09 against the
real `model-host` image built from `brain/Dockerfile.modelhost`, run with no GPU and no model
mount (the mechanism is control plane, and the model drive was not mounted in that session), with
the real `HttpModelHost` driving `_restart_evicted` and `retry_missing` over real HTTP.

- **A peer the sidecar cannot run really does raise.** With the tier named in `evict_models` and
  no artifact named for it, the daemon answers `404 unknown model 'subagent-gpu'; this host serves
  none`, the adapter raises `ModelHostError`, the record marks it, and the same spawn that landed
  on `gpu` before the restart lands on `cpu` after it. A retry pass then reached the daemon, got
  the same 404, logged "a tier the standing residency is missing could not be retried", and left
  the mark standing. That is the misconfiguration the entry called reachable, end to end.
- **The retry's start branch works against a real daemon.** Pointed at a tier with a bad artifact
  path, a pass read `failed` off `GET /models/subagent-gpu` and issued the `start`, after which
  the tier read `loading`; the mark stayed, because a pass never claims a load it did not observe
  finish.
- **The hole below is measured rather than reasoned about.** That same bad-artifact tier answers
  `200 {"state":"loading"}` to a `start` and `{"state":"failed","detail":"the process exited with
  code 1"}` three seconds later. So the restart loop marks it **standing** on the host's
  acceptance, and a spawn is still placed on `gpu` while the tier is dead. The reopen on an
  observed `READY` is the one branch no session without a loadable GGUF can witness; it is
  agent-runnable the moment the model drive is mounted, which by the
  [host index](../host/index.md)'s own rule makes it not host work, and it is listed at
  [gpu-tier-scale](../host/index.md#gpu-tier-scale)'s "also possible on this hardware" section so it
  is not lost.

### What this deliberately does not do

- **It does not notice a tier that dies on its own.** The record is written only where a restart
  was attempted and refused, so a peer that exits after the swap back accepted its `start`, or one
  that dies quietly between handoffs, is invisible to it: the retry only ever asks about tiers it
  already believes are missing. That is the case measured above, where a real sidecar answered
  `loading` to the start and `failed` seconds later. A sweep over every `evict_models` tier would
  close the whole family for one `status` per tier per interval, and it is deferred with its
  trigger rather than built, because a sweep that may `start` a tier is a much stronger thing to
  hold correct against a handoff in flight than one that only retries a known failure. Gating the
  peers inside the swap back instead is the wrong end: it would spend the load bound per tier
  inside the turn the user is waiting on. **Closed 2026-08-11 by the tier-sweep addendum below**,
  which built that sweep and answered the risk this paragraph names with a fence rather than with
  a hope; it also found the family to be four shapes rather than the three named here.
- **It does not tell tiers apart at the placer.** One bit for the card, argued above; a deployment
  that evicts a tier the subagent pool never places on gets a conservative CPU fallback it did not
  need. Deferred with its trigger.
- **It does not touch boot recovery's verdict.** `converge_residency` still lets a peer tier's
  failed `start` fail the whole convergence, so a boot where the cortex is serving and only a peer
  is down still answers `RESIDENCY_BOOT_FAILED`, which is the same conflation this addendum
  refuses everywhere else. It is left alone here because threading the record through the two
  boot paths is a change to a different sequence, and because the retry clears the placer side of
  it within a pass either way. Deferred with its trigger. **Closed the same day by the
  boot-verdict addendum below**, which also found that the call this paragraph names is not the
  one a real deployment fails at.
- **It does not register a new cross-tree constant.** `CORTEX_SWAP_TIER_HEAL_S` has one
  declaration, `DEFAULT_TIER_HEAL_INTERVAL_S` in the core, read once by `config_swap.py`; the
  other spellings of 30 s are prose in that field's own docstring, the module doc and the runbook,
  which the scan's mention form could tie and which the drain and load bounds beside it have never
  tied either. Registering one of the three without the other two would be worse than the
  consistency this keeps.
- **It does not kill anything to make a tier come back.** The retry only starts; the supervisor's
  own idempotence is what makes repeating it safe.

## Boot-verdict addendum (2026-08-09): the cortex's readiness is a statement about the cortex

The deferral the tier-outage addendum above opened in its own "deliberately does not do" list,
**boot recovery still calling a peer tier's failure the cortex being gone**, closes here, ahead of
its trigger and for the reason the entry gave: it is a lie on an honesty surface, and the surface
it lies on is the first answer a fresh process gives.

### What the entry got right, and the one thing a real sidecar corrected

The entry was re-derived from the code before anything was designed. Its account of the mechanism
held exactly: `converge_residency` started every `evict_models` tier inside the same `try` that
decided whether the cortex was observed serving, so one peer that would not start made the whole
convergence answer `False`, the composition root published `RESIDENCY_BOOT_FAILED`, and the overlay
went amber with "the usual assistant did not come up at startup" over a cortex serving turns
perfectly well. Its account of the blocker held too, to the line: `residency.py` stood at 299 of
300, both call sites reach the record through it, and the change was therefore a file split rather
than an argument.

What the entry could not have known, because it was written from the code rather than from a
running daemon, is **which call actually fails first**. Driven against the real `model-host` image
over real HTTP, the reachable misconfiguration is a tier named in `CORTEX_SWAP_EVICT_MODELS` that
the sidecar has no artifact for: such a tier is not in the daemon's roster at all, so it answers
`404 unknown model 'subagent-gpu'; this host serves cortex, brain` to **every** verb, and the first
verb convergence spends on it is the `status` of the clearing loop, several calls before the
`start` the entry named. A fix that guarded only the restart would have left the observed lie
exactly where it was. So the clearing loop is peer-tolerant too, and the entry's one sentence
became two.

### The verdict rule

**`converge_residency` answers about the cortex and about nothing else.** `True` means the cortex
was observed `READY`; `False` means it was not, whether because the host could not be reached or
because it never gated inside the load bound. A peer of the cortex changes neither answer.

**A peer that will not run is recorded, in the record that already exists for exactly this.**
`StandingTiers` (`residency_tiers.py`) was built by the addendum above to hold the peers a swap
back could not restart; boot convergence writes the same record through the same move, since its
last step is `residency_moves.restart_evicted`, which is now public for that reason and is the one
implementation both paths run. One record, one writer per outcome, no second vocabulary: the
distinction a reader already had, **down** versus merely **evicted**, is the one this reuses.

**The record is reached through the manager.** `SwappingModelManager.standing_tiers` hands it out;
`recover_handoffs` and `BootWatch` take it as an argument, exactly as the swap back's retry policy
already took it. The alternative, letting boot recovery keep a record of its own, would have been
two records for one fact, which is the mutation that proves the wiring
(`test_a_boot_whose_peer_tier_is_down_still_says_the_brain_is_ready`).

**The deep model is deliberately not a peer.** Its clearing stays fatal to the verdict, because it
is the other half of the residency the cortex has to be alone in: a deep model that cannot be
stopped is a reason to distrust everything after it, where a delegation tier that cannot be started
is a fact about where delegated work runs. That asymmetry has a residue, recorded below.

### The three boot cases, and how a reader tells them apart

| What happened | `ready` | What the detail says |
| --- | --- | --- |
| The sidecar could not be reached at all | `false` | the usual assistant did not come up at startup |
| The sidecar answered and the cortex would not gate | `false` | the same line |
| The sidecar answered, the cortex serves, a peer will not run | `true` | the model host is not running `<tier>` |

The first two share a line on purpose, which the `RESIDENCY_BOOT_FAILED` docstring already argued:
nothing was observed either way and the operator's next move is the same, so they are separated in
the log (`the model host was unreachable during boot recovery` against `the cortex is not serving
after boot recovery`) rather than on the dot. The third is the one that had to become tellable, and
two independent things keep it apart from the other two. The record is written only where a `start`
was refused, and an unreachable host returns before that call is ever made, so nothing is marked
about peers nobody could ask about. And `StandingTiers.note_on` annotates only a **serving** report,
so even a marked record cannot put a tier's name on an amber dot.

### The split, by responsibility

`residency.py` was one line under the cap, so this change could not be made without one, and a file
cut to fit a number is the wrong artifact. What came out is the seam the module's own docstring
had been describing for three addenda: `residency_moves.py` owns *what the host is asked to do*,
`residency_restore.py` owns *what the swap back is promised to do*, and neither of them owns **the
bookkeeping both of them publish into**. That is now `ResidencyBoard` (`residency_board.py`): which
model the GPU serves, what a human is told about it, whether a scope owns the card, and the one
condition all three are published and waited on under.

It is one object rather than four attributes because it is one invariant: the resident and the
report are written **together**, under that condition, with nothing awaited between them, so the
lease's view of the GPU and the seam's answer about it cannot drift apart. The single writer that
touches the report alone is now a named verb (`publish_report`) instead of an inline exception, and
it says in its own docstring why boot recovery is allowed it. The manager keeps what none of the
three can decide: when the GPU may change hands, who may lease what, and the collaborators.

Nothing moved that a caller can see. `acquire`, `handoff_claim`, `swap_scope`, `residency`,
`publish_boot_residency` and `heal_standing_tiers` are unchanged in name and signature;
`ResidencyBoard` is deliberately **not** exported from the core barrel, exactly like `HandoffClaim`
beside it, because no adapter has business holding one.

### Proven able to fail before being trusted

Five mutations, each applied to production code alone with the whole brain workspace re-run, then
reverted; the counts are measured rather than aimed at.

| Mutation | Reddens |
| --- | --- |
| the peer restart back inside the verdict's `try` (the code as it was) | 5 |
| the peer clearing back inside that `try` (deep model included) | 1 |
| `restart_evicted` called on the unreachable path too | 1 |
| `BootWatch` converging against a record of its own | 1 |
| the composition root handing boot recovery a record of its own | 1 |

The third one is the case that earned the file's warning. Written the obvious way, over this
suite's default plan, its assertion was **vacuous**: that plan evicts nothing, so a mutation that
marked every peer had no peer to mark and stayed green. It names a tier and hands the host a start
it refuses now, and it releases. The split was re-measured rather than assumed: dropping
`notify_all` from what is now `ResidencyBoard.leave_scope` reddens 3, every wait that then never
wakes.

### Validated against a real sidecar, since the claim that moved the design is not a CI claim

Run 2026-08-09 against the real `model-host` image, with the real `HttpModelHost` driving
`converge_residency` over real HTTP. The model drive was not mounted in this session, so there was
no GGUF to load and the tiers' children were a stub HTTP server standing in for `llama-server`,
named plainly because it is the limit of what this witnesses: everything below is control plane,
which is all this change touches, and nothing here says anything about a model.

- **The lie, reproduced.** With `subagent-gpu` in `evict_models` and no artifact named for it, the
  daemon answered `404 unknown model 'subagent-gpu'; this host serves cortex, brain` to
  `GET /models/subagent-gpu`, and convergence answered `settled=False` with an empty record, while
  `GET /models/cortex` on the same daemon read `ready`. That is the entry's lie, live, and it is
  what showed that guarding the restart alone would not have closed it.
- **The fix, on the same daemon.** After the clearing loop became peer-tolerant, the same run
  answered `settled=True`, recorded `missing=('subagent-gpu',)`, and produced
  `ResidencyReport(serving=True, detail='the model host is not running subagent-gpu, so delegated
  work is running on the CPU')`.
- **The ordinary boot, unchanged.** With the tier given an artifact, the daemon's own log shows the
  whole convergence in order (`GET /models/subagent-gpu`, `GET /models/brain`, `GET /models/cortex`,
  `POST /models/subagent-gpu/start`) and the record stays empty.
- **The amber direction, still amber.** Pointed at a cortex id the daemon does not serve,
  convergence answered `settled=False` and recorded nothing about the peers, which is the
  unreachable branch returning before the restart.

### The detail line changed, because the record grew a second writer

`TIERS_MISSING_DETAIL` read `{models} did not come back after a deep task, so delegated work is
running on the CPU`. That clause is false on a brain that has never escalated, which is precisely
the boot this addendum is about, so the sentence now names the state rather than one writer's
cause: `the model host is not running {models}, so delegated work is running on the CPU`. It is
still what the overlay renders after `Brain ready: `, and the runbook and the tier-outage addendum
above are corrected to quote what ships rather than what shipped.

### What this deliberately does not do

- **It does not make the deep model's clearing best effort.** A `status` or `stop` of
  `plan.brain_model` that fails still answers `False` without asking about the cortex. Two shapes
  hide in that: an unreachable host, where the answer is right, and a deployment that turned
  escalation on without naming `CORTEX_MODEL_FILE_BRAIN`, where the daemon 404s that tier for ever
  and every boot goes amber over a cortex that is fine. The second is the same conflation one tier
  up, and it is deferred rather than fixed because the deep model is not a peer: it is the tier
  whose presence contradicts the residency the cortex needs, and treating a failure to clear it as
  cosmetic would let a boot report green over a card that is still holding it. Recorded with its
  trigger in `docs/refinements/index.md#resource-governance`. **Closed on 2026-08-11 by the
  unrostered-tier addendum below**, which gave the port the narrower failure this paragraph says it
  lacks, kept both other shapes amber, and found on the way that the same flat error was costing a
  misconfigured deployment its cortex at the first escalation rather than only a dot at boot.
- **It does not give boot recovery a sweep.** A peer that is rostered, accepted its start and then
  died is invisible here exactly as it is to the swap back, and an unreachable boot marks nothing
  at all, so nothing retries those tiers until the next handoff. Both are the entry already open
  above, whose fix is one sweep over every `evict_models` tier and which now has a third shape
  named in it.
- **It does not change what a peer costs the placer.** One bit for the card, argued above; boot
  recovery pulls the same lever the swap back does, and the retry loop clears it the same way.
- **It does not widen the health surface.** Three boot cases, two lines, one of them already
  written: the pair that share a line share an operator move, and inventing a third sentence to
  separate them would be describing the log on the dot.

## Addendum (2026-08-09): the drain bound is not up against a lease, and the entry is declined

The deferral this ADR opened alongside the tier-outage one, "the drain bound sits below a fired
task's schedule lease, so a task in flight aborts a handoff", asked for a defaults decision once
real usage arrived. Traced to the code ahead of that usage, its mechanism does not hold, so the
decision recorded here is to **decline the defaults change** and correct the two places that
stated the false rationale. Nothing about decision 4 changes; what changes is what the number in
it is understood to be measured against.

**The drain waits on an admission, never on a lease.** `ResourceBudgetScheduler.drain` waits on
one condition, `while self._in_flight > 0`, under `asyncio.timeout(timeout_s)`. `_in_flight` is
incremented and decremented by `admit`, and `SubagentRunner.run` holds that context manager around
the whole subagent run (`async with res.scheduler.admit(res.request):`). So what a drain waits out
is the remaining runtime of the subagent runs already admitted, and nothing else.

**The schedule lease governs a different thing entirely.** `CORTEX_SCHEDULE_LEASE_S` is the store's
fencing lease on a claim, and in `ScheduleTicker.run_once` it is additionally the cancellation cap
on a fire: `await asyncio.wait_for(self._fire(claim), timeout=self._settings.lease.total_seconds())`.
That makes 300 s a **ceiling** on how long a ticker-fired task may hold its admission, not the
duration it holds it for. Comparing 60 s against it compares a wait bound to a cancellation cap,
and neither number decides whether the drain succeeds.

**The number the bound is really up against is a measurement, and it is not the lease.** A whole
CPU subtask on the shipped roster entry is 200 to 300 s
([ADR-0005](ADR-0005-llamacpp-engine.md) stall-ceiling addendum,
[ADR-0012](ADR-0012-resource-governance.md)). A drain arriving at an arbitrary point in one
succeeds only if 60 s or less of it remains, so the abort is **likely, not systematic**: roughly a
quarter of arrivals clear a single in-flight run, and fewer clear an admitted pair, whose releases
are staggered. The honest word for the shipped behaviour is "usually", and it is what the two
corrected comments now say.

**The framing was also narrower than the behaviour.** An interactive spawn holds exactly the same
admission and carries no lease at all. Nothing caps a delegated generation's length (the total
generation cap is still open in the same area doc) and the pool's 600 s ceiling bounds the gap
between chunks rather than the run, so an interactive spawn's hold has no upper bound at all. The
collision is therefore between a drain and delegated work of any origin, and a scheduled fire is
one occasion of it rather than its cause.

**Why both knob moves the entry proposed are refused.** Lowering `CORTEX_SCHEDULE_LEASE_S` under
the drain bound would make drains succeed by cancelling every scheduled fire before its 200 to
300 s subtask could finish, which breaks the feature to protect the handoff. Raising
`CORTEX_SWAP_DRAIN_TIMEOUT_S` over the lease fixes only fires, not interactive spawns, and no
finite value guarantees a clean drain while a generation's length is uncapped; the smallest value
that even covers the wedge case is above the pool's 600 s ceiling, which is precisely the "do not
hold the user's handoff open for minutes" this default was chosen for. There
is no free move here, only a trade between handoff latency and handoff success, and a deployment
that has met the collision makes it with the knob that already exists.

**What landed instead.** The rationale comment on `DEFAULT_SWAP_DRAIN_TIMEOUT_S` and its
restatement in [modules/brain-core.md](../modules/brain-core.md) both claimed the 60 s was
"generous enough for a normal delegated run to finish", which this repo's own measurement denies,
and both now name the measurement and the direction. The model-swap runbook gains the sizing
guidance an operator needs at the knob. No default moves, so there is no new relationship for a
test to pin: the two values were never coupled, and coupling them in code would assert the
comparison this addendum is retiring.

## Unrostered-tier addendum (2026-08-11): a tier the host never had is not a host that failed

The deferral the boot-verdict addendum above opened in its own "deliberately does not do" list,
**the deep model's clearing still deciding the cortex's verdict at boot**, closes here, ahead of
its trigger. The entry asked for one thing, a narrower failure on the `ModelHost` port, and said
plainly why it had been recorded rather than fixed: `ModelHostError` covered both "this host has
no such tier" and "this host is not answering", and guessing between them from a message string
would be worse than the lie it was meant to remove.

### What the entry got right, and the failure it did not know it was describing

Re-derived from the tree before anything was designed, and its account held to the line.
`ports_models.py` declared the port with one error type behind all six verbs; `errors.py` had the
flat `ModelHostError`; `swap_recovery.py` put `plan.brain_model`'s `status` and `stop` inside the
same `try` that decided whether the cortex was observed serving. Its claim about the sidecar held
too, and is what made this a small change: `ModelSupervisor` has always distinguished the case
(`UnknownModelError`, raised by the one `_spec` lookup every verb shares) and the control API has
always answered it as a 404 rather than a 503. The information existed at the wire and the adapter
threw it away, so this is a port change plus an adapter that stops discarding, not a new mechanism.

Reproduced before it was fixed, against a real `ModelSupervisor` behind a real Starlette app with
the real `HttpModelHost` driving it over HTTP: with the deep tier absent from the roster, which is
exactly what `CORTEX_ESCALATION=1` and an unset `CORTEX_MODEL_FILE_BRAIN` produce, boot recovery
answered `settled=False` while `GET /models/cortex` on the same daemon read `ready`.

**What the entry did not know is that the amber dot was the cheap half.** Driven one step further,
through a real `swap_scope` against that same daemon, the shipped code did this: the swap in
stopped the cortex, the `start` of the unrostered deep tier came back 404, and then the swap back's
own `stop` of the model it had swapped in met the **same** 404, failed the restore, failed the
retry, and raised `ResidencyRestoreError`. The cortex was left `stopped`, the seam reported `the
usual assistant could not be reloaded after a deep task; recovery is manual`, and the deployment's
recovery was a runbook. So a misconfiguration that could only ever have meant "escalation is not
available here" took the assistant down permanently at the first attempt to use it. That is the
same conflation as the boot verdict, one call further along, and it is fixed by the same
distinction.

### The port change, and what it is called

`ModelNotHostedError(ModelHostError)`. One new type, on the port, meaning the host carries no such
logical id at all.

**A subclass rather than a sibling**, so every existing `except ModelHostError` catches it
unchanged: `swap_in`, `restore_standing`, `restart_evicted`, the tier retry and the two host-wide
reads in `BootWatch` all keep behaving exactly as they did, and only a caller that can act on the
difference names the narrower type. Adding a distinction must not be able to turn a handled
failure into an unhandled crash somewhere nobody looked.

**The name is picked against two collisions.** `UnknownModelError` is the supervisor's own class
for the same condition on the daemon's side of the wire, and a reader should never have to ask
which side a name is on; `UnrosteredModelError` would borrow "roster", which in the core already
belongs to the subagent roster (`roster.py`) and means a different thing entirely. `ModelNotHosted`
says whose relationship to the id is at issue (the host's) and stays inside the `Model*Error`
family beside `ModelUnavailableError`, which is the neighbouring distinction: that one is the
manager saying a model is not **resident** right now, this one is the host saying it was never
**hostable** here.

**Only the sidecar's own distinction is carried.** The adapter raises it for a 404 on a per-model
route and for nothing else: a 503 is `SupervisorError`, a process that would not start or stop,
which the next call may well answer differently, and a 404 on `GET /health` names no model at all,
so it means the endpoint is wrong rather than the roster short. A rule that read every refusal as a
missing tier would turn a genuine outage into a configuration note, which is the failure this
change exists to avoid and the direction that would be worst to get wrong.

### The verdict rule, unchanged in what it means and wider in what it survives

`converge_residency` still answers about the cortex and about nothing else. What changes is that
one shape of deep-tier failure no longer prevents it from asking:

| What happened | `ready` | What the operator is told |
| --- | --- | --- |
| The sidecar could not be reached at all | `false` | the usual assistant did not come up at startup |
| The sidecar answered and the cortex would not gate | `false` | the same line |
| The deep tier is resident and its `stop` failed | `false` | the same line, and the card may still be holding it |
| The daemon's roster has no cortex | `false` | the same line, with its own log sentence |
| The daemon's roster has no deep tier | `true` | one `ERROR` naming both knobs, and a serving dot |

The last row is the fix and the row above it is the guard on it. A cortex the daemon does not serve
is the same distinction pointing the other way, and it stays amber, because it is the one case
where nothing is serving turns: it is separated from an unreachable host in the log alone (`the
model host does not serve the cortex this brain names, so nothing can`), since the two share an
operator's next move, which is to read the daemon's roster.

**What a caller learns about the missing escalation is a log line, and deliberately only that.**
`escalation is enabled but the model host does not serve 'brain', so no handoff can ever run: name
an artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or turn escalation off (CORTEX_ESCALATION)`.
It is logged at `ERROR` because the deployment is misconfigured and nothing else will say so, and
it is logged once per boot rather than published, for the reason the boot-verdict addendum gave
about widening the health surface: the report carries one detail line, that line already belongs to
the peer record, and a second sentence competing for it would describe a configuration file on a
readiness dot. The residue that leaves is recorded below.

### What the swap does differently

**The swap in says which repair is needed.** A `ModelNotHostedError` still fails the handoff, since
an escalation that cannot happen must not appear to happen, but it now raises `the model host does
not serve 'brain' at all, so this deployment cannot escalate until that tier is in its roster`
instead of `the model host failed while swapping in 'brain'`. The distinction is what the user's
note is worth: one invites a retry that will succeed later, the other will fail identically for as
long as that daemon runs.

**The swap back stops nothing under a name the host does not have.** `restore_standing` tolerates
exactly that one failure from its stop of the model it swapped in, and nothing else, so the retry
still exists for the case it was written for, a resident model that will not die. This is the half
that turns a dead assistant back into a refused handoff, and it is why the fix reaches
`residency_moves.py` at all.

**Boot recovery clears the deep tier best effort in that one shape only.** `_clear_deep` swallows
`ModelNotHostedError` and propagates everything else, so a deep model that is resident and will not
stop still answers `False` without the cortex being asked about, which is the asymmetry the
boot-verdict addendum argued for and which nothing here weakens: there is no card to distrust when
the name was never on it.

### The second site the flat error hid, and where it went

The same 404 reaches `residency_tiers.retry_missing` for a **peer** tier, and there it is not
closed here. A peer named in `CORTEX_SWAP_EVICT_MODELS` with no artifact is marked missing at boot,
which is right (the tier really is not there, and GPU placement really should close), and then
retried every `CORTEX_SWAP_TIER_HEAL_S` for ever, which is two control calls a pass against a
roster that cannot grow. Nothing is harmed by it and the operator is told each time, so what is
open is a policy question rather than a defect: whether a tier that can never come back should stop
being asked about, and if so whether the placer stays closed on it. That belongs with the open
sweep entry, which already owns what the retry pass looks at, and it is named there as a further
shape rather than filed as a new entry.

### Proven able to fail before being trusted

Seven mutations, each applied to production code alone with the whole brain workspace re-run, then
reverted. The counts are measured rather than aimed at.

| Mutation | Reddens |
| --- | --- |
| the adapter collapsing a tier's 404 into the broad error (the code as it was) | 2 |
| the adapter reading **every** refusal as a tier the host does not carry | 3 |
| the twin serving every id it is handed | 5 |
| the deep tier's clearing deciding the verdict again (the code as it was) | 1 |
| an unhosted cortex reporting green | 1 |
| the swap back stopping the swapped-in model with no tolerance (the code as it was) | 1 |
| the swap in describing an unrostered tier as a host that failed (the code as it was) | 1 |

Three of them are worth reading rather than counting. The first reddens the **supervisor** leg of
`check_an_id_this_host_does_not_carry_is_refused_by_every_verb` and no scripted one, which is what
driving the contract over both implementations is for: the twin is told what it does not host,
while the real leg has to derive the same answer from a roster and an HTTP status. The third is the
mirror of it, reddening both scripted legs plus the three core cases that arrange the condition,
and it is the reason a fake that could not refuse would have made this whole slice untestable over
the twin. The second is the guard on the direction that matters most, since it is the one mistake
that would be worse than the defect: read every refusal as a missing tier and a wedged supervisor
becomes a configuration note, so the 503 and 500 rows and the wrong-endpoint case all redden.

### Validated against the real supervisor over HTTP, since the claim that moved the design is not a CI claim

Run 2026-08-11 through `httpx.ASGITransport` onto a real Starlette app over a real
`ModelSupervisor`, with the real `HttpModelHost` on the brain side: the adapter's encoding, the
API's routing and refusals and the supervisor's roster lookup are all the shipped code, and only
the OS spawn and the health socket are faked, exactly as the shared contract suite drives them. The
container was not needed for this: nothing here is about a model, a GGUF or a card, and every claim
is control plane.

- **The amber boot, before.** Roster `cortex` only, deep tier `brain`:
  `settled=False`, `GET /models/cortex -> 200 ready`, `GET /models/brain -> 404 unknown model
  'brain'; this host serves cortex`.
- **The same daemon, after.** `settled=True` with the cortex still `ready`, and the one `ERROR`
  line naming both knobs.
- **The amber direction, still amber.** A deep tier that is rostered, resident, and whose child
  survives SIGKILL answers `settled=False`, as does an endpoint with no daemon behind it at all.
  Neither reads as a configuration choice.
- **The escalation attempt, before.** `ResidencyRestoreError: could not restore 'cortex' after 2
  attempts`, with `GET /models/cortex -> 200 stopped` and the report reading `the usual assistant
  could not be reloaded after a deep task; recovery is manual`.
- **The escalation attempt, after.** `SwapFailedError: the model host does not serve 'brain' at
  all, so this deployment cannot escalate until that tier is in its roster`, with
  `GET /models/cortex -> 200 ready` and a serving report.

### What this deliberately does not do

- **It does not change the seam.** No proto field, no new `Health` vocabulary, nothing crossing
  body to brain: the distinction is between two failures of one control call inside the brain, and
  every surface it reaches (the boot verdict, the swap's note, the log) already existed. A seam
  change would be the maintainer's to weigh, and this did not need one.
- **It does not remember that escalation is impossible.** Boot recovery learns it and logs it, and
  then every escalation the user asks for still drains the pool, evicts the cortex, meets the 404,
  and reloads the cortex, which at tier scale is minutes of the assistant being gone for a handoff
  that was never going to run. Refusing at the conductor, before the drain, and telling the user
  why is the fix; it needs somewhere for the fact to live and a decision about what the seam says,
  which is why it is a recorded refinement with its trigger rather than a line here.
- **It does not stop retrying a peer that can never come back**, argued above and recorded on the
  entry that owns the retry pass. **Closed 2026-08-11 by the tier-sweep addendum below**, which
  gives the record a `TierFault` per tier so an unhosted one is written once and skipped for ever,
  and which also corrects the cost stated above: a pass asks `status` first and that is the call
  that 404s, so it was one control call a pass and never two.
- **It does not make the port's other failures finer.** The remaining shapes behind
  `ModelHostError` are a transport failure, a refusal, an undecodable body and an unknown state
  word, and all four mean the same thing to every caller: the host did not answer the question. The
  one distinction worth having is the one the daemon itself already draws.

## Tier-sweep addendum (2026-08-11): a pass asks about every peer, not only the ones it doubts

The deferral opened by the tier-outage addendum above, **the retry only asks about tiers it already
believes are missing**, closes here. That addendum listed the hole in its own "what this
deliberately does not do", the unrostered-tier addendum added a fifth shape from the opposite
direction, and this is the one pass that answers both: the record is no longer written by refusals
alone, it is **re-derived from the machine** every interval, and the one answer no retry can change
stops being asked about.

### The five shapes, re-derived before anything was designed

The entry named four shapes and a fifth was added to it hours before this pass. All five were run
against a real `ModelSupervisor` behind a real Starlette app over `httpx.ASGITransport`, with the
real `HttpModelHost`, the real `SwappingModelManager` and the real `VramBudgetPlacer`, so what is
below is what the shipped code did rather than what the entry claimed it did. Only the OS spawn and
the health socket are faked, exactly as the shared contract suite drives them.

| Shape | What the record held | Where a spawn landed |
| --- | --- | --- |
| a peer that accepted its start and then died | empty | **GPU**, at a `failed` tier |
| a peer that died quietly between handoffs | empty | **GPU**, at a `failed` tier |
| a peer nothing ever started | empty | **GPU**, at a `stopped` tier |
| a boot that could not reach the host | empty | **GPU**, at a `stopped` tier |
| a peer the roster never had | the tier, correctly | CPU, correctly |

Four of the five escape, and the fifth does not. That is the correction the entry needed and it
changes what this pass is for: the sweep is not a fix for all five, it is a fix for four plus a
retirement of a retry that was asking a question with a permanent answer.

Two further findings the entry could not have known.

**The third shape is reachable with escalation on**, which the entry left vague by writing "a peer
a deployment never started at all". Boot recovery does start every `evict_models` peer, so the
condition is not a deployment that forgot: it is a convergence that **returned before the restart
loop**. `converge_residency` runs its restart after the `try`, so a deep model that is resident and
survives SIGKILL, or a cortex that cannot be settled, answers `False` and leaves every peer both
unstarted and unrecorded. The run above produced exactly that from a child wired to ignore both
signals: `503 ... survived SIGKILL`, `settled=False`, the tier `stopped`, the record empty, and the
next spawn on the GPU. The fourth shape is the same site reached by a different failure, which is
why one change closes both.

**The fifth shape costs one control call a pass, not two.** The unrostered-tier addendum wrote
"two control calls a pass against a roster that cannot grow"; the pass asks `status` first and that
call is the one that 404s, so `start` is never reached. Three passes produced three refusals, not
six. The noise is half what was recorded, and the reason to retire it is unchanged.

### The decision

**One pass over `plan.evict_models`, not over the record.** `sweep_tiers`
(`residency_sweep.py`) asks `status` for every tier a handoff may evict, whatever the record
believes about it, and writes what it sees. The record stops being a list of refusals and becomes a
**cache of the machine, refreshed every interval**, which is the property that closes four shapes
at once: none of them has a refusal to be written by, and all four are visible to a `status`.

**A per-tier reason, because the two faults want opposite treatment.** `StandingTiers` now holds
`dict[str, TierFault]` rather than a set, with two words:

- `TierFault.MISSING`: the tier is not serving and asking again may change that. It is retried.
- `TierFault.UNHOSTED`: the host's roster has no such id, which is the `ModelNotHostedError` the
  port learned to tell apart. It is **not** retried, because the answer cannot change while that
  daemon runs.

Both close GPU placement, because both mean there is no server to place on; only one is asked
about again. `missing` still names every faulted tier, so the placer's one bit and the seam's one
sentence are untouched.

**The clearing path for an unhosted tier is a new daemon, and the brain already notices one.**
`BootWatch.reconcile` compares `boot_id` per handoff and runs `converge_residency` when it changes,
which asks every peer to start again through `restart_evicted`. So a roster that grew because the
operator fixed the env and the sidecar restarted is picked up at the next handoff, and a roster
that did not is never asked twice. Nothing new was built for it: the retirement is safe precisely
because the one event that can change the answer already rebuilds the record.

### What the sweep is allowed to do, and what stops it racing a handoff

This is the question the entry deferred on, so it is answered in full rather than asserted.

**It observes always and starts conditionally.** `status` is a read: it cannot change what the card
holds, so it is unfenced beyond the pass guard. A `start` is a write, and it happens only after the
record has already been closed against that tier, so the placer is protected by the observation
whether or not the start ever happens.

**The fence is wider than it was, and it is read synchronously immediately before the start.** The
old guard was one flag, `board.scope_active`, read once at the top of a pass. It is now the
disjunction of that flag and `HandoffClaim.claimed`, and it is read again, with **nothing awaited
between the read and the call**, before every `start`. Both halves matter:

- The claim is taken by the conductor *before* it drains anything and held through the drain and
  the whole scope, so it fences the sweep out from the first moment a handoff exists rather than
  from the moment the GPU changes hands. The drain alone is up to
  `CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s) of warning the old guard did not have.
- The scope flag stays as the backstop under it, because a swap that reaches `swap_scope` without
  claiming is still a swap, exactly as `ResidencyBoard.enter_scope` is the backstop under the
  claim.
- Reading synchronously is what makes the fence a fence rather than a hint. `scope_active` and
  `claimed` are plain attribute reads and `await host.start(...)` does not suspend before the
  request is built, so no other coroutine runs between the two: a handoff cannot **begin** in that
  gap. What remains is a handoff that began before the read and had not yet set either flag, which
  is not possible, or a start already in flight when a handoff begins, which is the next paragraph.

**A start already in flight when a handoff begins is safe, and the supervisor is why.** The swap
in's first move is to stop every `evict_models` tier, and `ModelSupervisor` holds one lock per
logical model and does not answer a `stop` until the child is reaped. So a start that reached the
daemon first is undone by the stop that follows it, and a start that has not reached it yet queues
behind that stop on the same lock. The ordering that would hurt, a spawn landing after the deep
model's fit check, requires the sweep's in-flight request to outlive the claim, the whole drain,
the lease wait, a `boot_id` round trip and a full cortex stop on the same loopback client. It is
not closed by construction and it is not claimed to be; what it costs if it ever happens is a
handoff refused by its own fit check or a peer running beside the deep model until
`restart_evicted` finds it already up, neither of which loses state or corrupts the record.

**"Only a refusal marks" is replaced by "only an observation taken outside a handoff marks", and
the distinction it protected is stronger for it.** Down versus evicted was kept by never writing
the record except where a `start` raised. It is now kept by the fence: a pass does not run at all
while a handoff owns the GPU, and by the time a scope ends `restart_evicted` has already asked
every peer to come back, so the first pass after a handoff sees `loading` or `ready` and never the
eviction. `note_on` still annotates a **serving** report only, so the four swap windows keep their
own words as they always did. A co-resident handoff never stops a peer at all, and the pass stands
down through it anyway, which is conservative in the one direction that costs nothing.

### Where it runs, how often, and what it costs

In `TierHealer`, the loop that already exists, every `CORTEX_SWAP_TIER_HEAL_S` (30 s). Not per
turn, which would put control calls on the path a user is waiting on for a fact that changes on the
timescale of a process dying; not at boot only, which is the timescale that misses four of the five
shapes; and not inside the swap back, which would spend the load bound per tier inside the turn.

The cost changed and the honest statement of it changed with it. A pass used to ask nothing when
the record was empty, which is the common case; it now asks one `status` per `evict_models` tier
per interval, unconditionally. In the shipped defaults that is still nothing, `CORTEX_SWAP_EVICT_MODELS`
being empty, and in the deployment this exists for it is two loopback calls a minute for one tier.
A tier already known unhosted is skipped, so the deployment with a typo pays less than it does
today rather than more.

### What the placer does with it, unchanged on purpose

Nothing about the placer moved. Any faulted tier closes GPU placement through `close_gpu()`, an
emptied record reopens it through `open_gpu()`, and it is still one bit for the whole card with the
per-tier detail kept for the operator and the retry. What changed is only **when** the bit is
written: a tier that died without anyone asking it to restart now closes it, which is the whole
harm the parent entry was opened for.

### The record's shape, and where it lives

**It grew a reason and nothing else.** No timestamp, no last-seen, no attempt count. A timestamp
would exist to pace a retry or to report an age; the pass interval already paces the retry, and the
seam names the tier rather than how long it has been down, so a clock in a pure record would be a
dependency no decision reads. If an operator ever needs the age, the log line at the transition is
where it already is.

**It stays in the process, and the sweep is what makes that obviously right.** The one hard rule is
about state that cannot be re-derived: conversation, task, working memory. This is live-resource
state, the same kind as `VramBudgetPlacer`'s ledger, and it is now re-derived from `status` every
interval by construction. Putting it in Redis would buy nothing a fresh process does not already
get within one pass, and it would cost the two things a store always costs here: a second writer
with no fencing, and a stale record that outlives the machine it described. A restart rebuilds it
from the machine, which is exactly what the hard rule asks of state that is about the machine.

**A second swapper cannot corrupt it, and the sweep is why.** Today's record can only be cleared by
something that already believes a tier is missing, so a mark written under a foreign process's swap
would stand until this process happened to escalate. A swept record is a cache: the worst a foreign
handoff can do is make one pass read a deliberately stopped tier as missing, which costs one
interval of CPU placement and is corrected by the next pass. That is the property that makes this
safe to keep in the process while the cross-process handoff fence is still a recorded refinement.

### Proven able to fail before being trusted

Eight mutations, each applied to production code alone with the whole brain workspace re-run, then
reverted. The counts are measured rather than aimed at, and they sit in `test_residency_tiers.py`'s
header beside the ones the tier-outage addendum measured.

| Mutation | Reddens |
| --- | --- |
| sweeping only the tiers already believed missing (the code as it was) | 10 |
| letting a host that could not be asked mark the tier anyway | 1 |
| going on retrying a tier the roster never had (the code as it was) | 1 |
| reading an unrostered restart as an ordinary refusal (the code as it was) | 1 |
| marking only when the pass may also start | 1 |
| dropping the mark the reading earned | 6 |
| dropping the claim half of the fence (the code as it was) | 1 |
| dropping the scope half of the fence | 1 |

The second is the one worth reading rather than counting, because it is the direction that would
be worse than the defect: a pass that read a transport failure as a tier being down would close
GPU placement for the whole pool on one blip, over a stack where every tier is in fact serving.
The last two are the argument for the fence being a disjunction rather than either flag, each
half reddening a case the other cannot: the scope covers a swap that never claimed, and the claim
covers the drain, where the scope flag says nothing at all.

### Validated against the real supervisor over HTTP, before and after

The same harness that produced the table at the top was re-run against the swept code. Per shape,
the placer's answer for one 2.0 GiB spawn with 3.0 GiB of headroom:

- **a peer that accepted its start and then died**: GPU before, CPU after, the record naming the
  tier and `Health` reading `the model host is not running subagent-gpu, so delegated work is
  running on the CPU`;
- **a peer that died quietly between handoffs**: GPU before, CPU after;
- **a peer nothing ever started, after a boot that returned early**: GPU before, CPU after;
- **a boot that could not reach the host, with the sidecar up a minute later**: GPU before, CPU
  after, and the tier started by that same pass;
- **a peer the roster never had**: CPU before and CPU after, with the difference in what the log
  says: three passes produced three refusals before and one line naming the two knobs after, with
  no control call at all on the passes that follow.

### What this deliberately does not do

- **It does not gate readiness inside a pass.** A tier that is `loading` is left alone and observed
  by a later pass, exactly as before, so a tier that takes minutes to load costs the loop nothing
  and reopens the GPU the moment a pass sees it serving.
- **It does not mark a tier on a host that could not answer.** A `ModelHostError` that is not the
  unrostered one leaves the record untouched and logs, so a network blip cannot close GPU placement
  for every tier at once. Only a state the host actually reported writes a fault.
- **It does not tell tiers apart at the placer.** One bit for the card, unchanged, with its own
  entry and its own trigger.
- **It does not close the in-flight start against a handoff by construction.** Argued above: the
  fence is synchronous and wide, the supervisor's per-model lock orders the rest, and the residual
  is a refused handoff rather than a lost one. Closing it fully would mean taking the GPU lease for
  the start, which would park a user's turn behind a control call and can block for the whole load
  bound, and that trade is worse than the residual.
- **It does not distinguish the two faults on the seam.** `Health` names every tier that is not
  running in one sentence, because the consequence for delegated work is identical; the distinction
  is drawn once, loudly, in the log at the transition, where an operator's next move differs.
- **It does not sweep the deep tier or the cortex.** Both have their own verdicts (the swap's, and
  boot recovery's), and a peer record that also carried the resident would be two objects with one
  name.

## Unrostered-refusal addendum (2026-08-16): the handoff that cannot run is refused before the drain

The deferral the unrostered-tier addendum above opened in its own "deliberately does not do" list,
**it does not remember that escalation is impossible**, closes here. That paragraph named the fix
in one sentence (refuse at the conductor, before the drain, and tell the user why) and named the
two decisions it was waiting on: where a fact about the host's roster lives on a brain whose every
other belief about that daemon is invalidated by a restart, and what the seam says about a
capability that is configured and unavailable. Both are made below, and the first one is made
against the shape the entry proposed rather than with it.

### What the tree said, re-derived before anything was designed

Every claim the entry made held, to the line.

- **Boot recovery learns it and only logs it.** `swap_recovery._clear_deep` catches
  `ModelNotHostedError` from its `status` and writes one `ERROR` naming both knobs
  (`swap_recovery.py:163`). Nothing is recorded anywhere a later caller can read.
- **The prologue's ordering is as described.** `SwapConductor._run_claimed` prepares, announces the
  drain, drains, and only then enters the swap (`swap_conductor.py:139` to `146`);
  `residency_moves.swap_in` stops the cortex first and starts the deep tier several calls later
  (`residency_moves.py:90` and `95`), so the 404 arrives with the cortex already unloaded and the
  scope's `finally` owes a full reload (`residency.py:223`).
- **A 404 is distinguishable at the call site**, and has been since the addendum above:
  `ModelNotHostedError` is raised by the adapter for a 404 on a per-model route and by nothing
  else, and every verb of the port can raise it (`errors.py:206`, `ports_models.py:19`).
- **The boot id works the way the entry assumed.** `ModelSupervisor` mints `uuid4().hex` per
  process, `GET /health` carries it, and `BootWatch.observe` compares it for equality only, seeding
  on the first answer and rebuilding both halves of what a replacement invalidates
  (`residency_watch.py:76`).
- **The residency report carries one detail line**, `ResidencyReport(serving, detail)`, and that
  line already belongs to the peer record: `StandingTiers.note_on` writes it on every serving
  report (`residency_tiers.py:163`).

One thing the entry could not have known, because it was written before the tier-sweep addendum
landed hours later, is that this repo had by then already answered a question of exactly this
shape, for the peer tiers, and answered it in the other direction: the peer record stays in the
process and is **re-derived from the machine every interval** rather than kept. That precedent is
what decides the first question here.

### Decision 1: the fact lives nowhere, because asking is cheaper than any key that would make a cache safe

The entry framed the question as "where does it live", and the honest answer turned out to be that
it does not need to live anywhere. **The conductor asks the host, once, immediately before it
commits to anything**, through a new `ResidencyController` verb, `unhosted(model) -> bool`,
implemented over one `status` call (`residency_moves.is_unhosted`).

The argument is a cost comparison, and it is the entry's own boot-id argument taken one step
further. A cached verdict has to be invalidated by the event that can change it, which is a
supervisor process replaced under a brain that never restarted. Detecting that event costs one
`boot_id()` round trip at the moment of use, because `BootWatch.reconcile` runs inside `_swap_in`,
which is **after** the drain and inside the residency scope, and cannot be hoisted above them: a
reconcile converges residency, and converging bounces every evictable tier, which is precisely what
a co-resident plan exists not to do to its standing peers. So a cache that is safe costs one
control call before the drain, and re-deriving the fact outright costs one control call before the
drain. At equal cost the version with no state, no key and no staleness window is the one to ship.

Three further reasons, in the order they would bite:

1. **The one hard rule is satisfied more strongly by asking than by storing.** The rule is about
   state that cannot be re-derived, which is conversation, task and working memory. This is a fact
   about the machine, and the tier-sweep addendum already ruled on the identical question for the
   peer record: state about the machine belongs wherever it is re-derived from the machine, and a
   store would buy nothing a fresh reading does not while costing a second writer with no fencing
   and a record that outlives the daemon it described. Redis would have been the wrong home for the
   same reason a `TaskStore` was the wrong home for a handoff record.
2. **The failure a cache invites is the expensive one.** An operator who fixes this fixes it by
   naming `CORTEX_MODEL_FILE_BRAIN` and restarting the **sidecar**, not the brain. A verdict cached
   for the life of the brain process would go on refusing escalation on a deployment that now
   works, and the only symptom would be a note saying the machine has no deep model while the
   daemon happily lists one. Re-deriving per attempt makes the repair take effect at the next
   attempt, which is what an operator expects of a config change.
3. **The call is free where it is spent.** It is a `status` on a tier that is stopped, on the same
   loopback client every other control call uses, on a path that is about to spend minutes and that
   a user has already confirmed through the ADR-0022 card. This is not the per-turn hot path the
   honesty-surfaces sub-slice refused to put a probe on; escalation is rare by construction.

**The tolerance is the same one the rest of this family keeps, and it is the direction that matters
most.** Only `ModelNotHostedError` answers `True`. Every other `ModelHostError` means the question
went unanswered, is logged, and answers `False`, so the handoff proceeds and fails at the move it
really fails at. Reading a transport blip as a missing tier would turn one unreachable moment into
"this deployment cannot escalate", told to a user whose machine is fine, which is worse than the
defect being fixed.

### Decision 2: the seam says nothing new, and the reason is the one the addendum above already gave

No proto field, no new `Health` vocabulary, nothing crossing body to brain. The capability's
absence reaches three surfaces, all of which already existed:

- **The user**, on the escalating turn's own stream, as `UNHOSTED_TIER_NOTE`: "this machine has no
  deep model set up, so the handoff was not started and nothing was unloaded". It is a `TextDelta`
  like every other refusal note, it arrives **before** the stall rather than after it, and it says
  what will still be true tomorrow rather than inviting a retry.
- **The operator**, in the log, twice for two different events: once per boot from
  `_clear_deep`, and once per attempt from the conductor, both naming `CORTEX_MODEL_FILE_BRAIN` and
  `CORTEX_ESCALATION`. An attempt is a separate fact from a boot, because it says somebody wanted
  the capability.
- **Nothing on the readiness dot.** `ResidencyReport` carries one detail line, that line belongs to
  the peer record, and a second sentence competing for it would be describing a configuration file
  on a readiness surface. This is the same judgement the unrostered-tier addendum made about the
  boot log, and nothing has changed except that the deployment is now refused earlier.

**Rejected: not advertising `escalate_to_brain` when the tier is missing.** It is the honest-looking
option and it is the wrong one twice over. The advertisement is built per turn, so keeping it
truthful would put a control call on the path a user is waiting on for every turn, which is exactly
what this design refuses to pay for a fact that changes on the timescale of a container restart.
And it would hide the misconfiguration from everyone: the model would simply never escalate, and no
user question would ever produce a sentence saying why. **Rejected: refusing inside the tool.** A
gated tool's `invoke` runs after the confirm card, so it saves the user nothing the conductor does
not, it puts a control call inside a dispatch, and it would split the handoff's refusals across two
objects that the 2026-07-19 correction above deliberately consolidated into one.

### Where the refusal sits, and the split it forced

In `SwapConductor._prepare`, after the free local `opaque` check and **before** the store is
touched, so a deployment that can never escalate writes no record, takes no drain, and has nothing
to settle. The conductor was at 299 of 300 lines, so this could not land without a split, and a
file cut to fit a number is the wrong artifact. What came out is the seam the ADR's own
2026-07-18 addendum named: settling a handoff and releasing its claim are two different writes, and
which of them is owed turns on the state being written rather than on where in the sequence the
write happens. That is now `HandoffSettler` (`swap_settle.py`); the conductor keeps the order the
machine changes hands in. Nothing a caller can see moved.

### Proven able to fail before being trusted

Four mutations, each applied to production code alone with `__pycache__` cleared and the whole
`brain/packages` suite re-run, then reverted. The counts are measured rather than aimed at.

| Mutation | Reddens |
| --- | --- |
| dropping the refusal entirely (the code as it was) | 28 |
| refusing after the drain instead of before it | 25 |
| reading every host failure as a tier the host does not carry | 2 |
| caching the verdict for the life of the process | 2 |

The first two counts are large for a reason worth stating, since a large number can hide a weak
test: three of those cases are the new ones, and the rest are the existing swap and chaos cases
whose "nothing was evicted" assertions were rewritten from an empty op log to the exact one call
this asks. That is deliberate. An assertion that a handoff has spent nothing is stronger when it
names what it has spent, and it means the prologue's cost is now pinned by every case that ever
cared about it rather than by one new case beside them.

The last two are the pair that matter most, being the two directions in which this could have been
built wrongly. Reading any failure as a missing tier reddens the unreachable-host case in the
conductor suite and the port's own three-answer case. Caching the verdict reddens the case that
gains the tier mid test and that same port case, which is the property the whole design rests on:
the same manager answers differently the moment the roster it is asking about does.

### Validated against the real sidecar, since the cost this removes is not a CI claim

Run 2026-08-16 against the real `model-host` image with the real GPU and the real model mount, the
cortex being gemma-4-12B loaded from `/models` and the daemon's roster holding `cortex` and nothing
else, which is exactly what `CORTEX_ESCALATION=1` with no `CORTEX_MODEL_FILE_BRAIN` produces.
`GET /health` answered `{"status":"ok","models":["cortex"],...,"device_free_mib":14840,
"device_total_mib":24463}`. The brain side was the real `HttpModelHost`, the real
`SwappingModelManager` and, for the second arm, the real `SwapConductor`.

- **The cost, as it was.** A residency scope entered against that daemon, which is what the
  conductor reached after draining: `POST /models/cortex/stop -> 200`,
  `POST /models/brain/start -> 404 unknown model 'brain'; this host serves cortex`,
  `POST /models/brain/stop -> 404`, `POST /models/cortex/start -> 200`, then the sidecar's own log
  showing `llama_server: model loaded` and `listening on http://0.0.0.0:8080` again. **29.7 s**,
  every second of it with the assistant off the card, for a handoff that could never have run. At
  the deep tier's scale the same reload is minutes, because it is a whole cortex load.
- **The cost, as it is.** The conductor over the same daemon: one `GET /models/brain -> 404`, the
  note "this machine has no deep model set up, so the handoff was not started and nothing was
  unloaded", the pool never asked to drain, and `GET /models/cortex` reading `ready` throughout.
  **Under 0.01 s.**

The port-level half of that is now an `integration`-marked live test that runs on the shipped
defaults (`test_a_stock_sidecar_answers_the_escalation_precondition_without_touching_a_thing`),
which is the one case in that suite a stock stack actually hits, and it skips on a deployment that
does host a deep tier.

### What this deliberately does not do

- **It does not remember anything, which is the decision and not an omission.** A deployment that
  attempts escalation ten times pays ten `status` calls, and that is the intended price of never
  being wrong about a roster that changed under it.
- **It does not refuse before the confirm card.** The user still approves a handoff that will then
  be refused, because the only surfaces earlier than the conductor are the per-turn advertisement
  and the gate, both of which are the hot path. The residue is one confirm card and an honest
  sentence, against minutes of an unloaded assistant before.
- **It does not check anything else about the deep tier.** A tier that is rostered but whose child
  will not load is a verdict about the machine, and it is discovered where it has always been
  discovered, at the health gate, with the swap-failure note the user already gets. Only the answer
  that cannot change while that daemon runs is worth asking for in advance.
- **It does not touch boot recovery.** The `ERROR` at startup stays exactly as it was: it is the
  operator's copy of the same fact, and a deployment that never escalates would otherwise never
  learn it.

## Spill-latch addendum (2026-08-18): the second actor is declined, and its own record was half stale

The spill-watch addendum above ends by recording the obvious second actor as a deferral: a handoff
that stops promising co-residency once it has watched itself spill. It is closed here on the
merits, and the first thing the re-derivation found is that the deferral's own two-line reasoning
had aged badly in both halves.

**A latch would withhold the peers, not the cortex.** The deferral is written as evicting the
cortex "next time", and `residency_moves` stops the cortex on every handoff already. What
`coresident` decides is whether the peer tiers are stopped too and whether the subagent pool is
drained, so the thing an automatic latch would take away is delegation through the handoff.

**"Nowhere to keep the latch" stopped being true the following day.** `ResidencyPlan` is still a
frozen value, but `StandingTiers` landed on 2026-08-09 as a mutable, process-lifetime residency
record held by the manager, read by the seam through `note_on`, and already pulling an automatic
lever off observed evidence when it closes GPU placement. Cost is not the argument any more, and
leaving that claim in the record would have told the next reader this was expensive when it is not.

**What decides it is evidence and reversibility.** A cadence reading is one handoff wide, and a
spill can be produced by the desktop taking a gigabyte during a load rather than by the pair
genuinely not fitting; the runbook records this machine's idle floor moving by about that much, and
the pairing this stack actually ships was measured to fit with about 908 MiB to spare. The tier
record heals, because a sweep re-reads each peer's real state and can mark it standing again. A
co-residency latch has no heal path at all: the only evidence that could clear it is a co-resident
handoff, which is what it just disabled. So it would trade a transient for a permanent loss of
delegation, unattended, until the brain restarts.

**The half of the trigger that is real gets its own entry.** A second machine adopting
`CORTEX_SWAP_CORESIDENT` from this repo's numbers is caught at boot by the required
`CORTEX_SWAP_BRAIN_VRAM_MIB` and at swap time by the free-memory check, and the residue is the
under-declaration the decode watch exists to warn about. The operator who never reads the log is
not covered by any of that, and the answer is to move the fact rather than to disable the feature:
the verdict can ride a serving residency report's detail exactly as a missing tier does, which
`Health` already prefers over its version string and the overlay already renders. That is filed as
[R-304](../refinements/tasks/304-spill-rides-the-residency-report.md), with the honest cost noted
(the deep phase holds no reference to the manager, so it needs a writer it can reach, and a note
about one handoff needs a rule for when it stops standing).

## Fenced-claim addendum (2026-08-18): the single-handoff fence is declined, on scope rather than staleness

The 2026-07-18 addendum above recorded that the single-handoff claim binds one process and named
what would close it. Re-derived on 2026-08-18, every word of it is still true of the tree, one
identifier having moved (`self._handoff_claimed` is now `HandoffClaim`'s flag, over the residency
board's condition). It is closed here anyway, because the fence cannot deliver the property its
name promises.

**It is one guard of five.** The GPU lease is an `asyncio.Lock` on the manager, the residency record
and the condition every acquire queues on are `ResidencyBoard` instance state, the missing-peer
record is `StandingTiers`, and the subagent placer's VRAM ledger is instance floats. `swap_builders`
already states the manager must be a single instance because a second one would be a second lease.
Two brain processes on one Redis would double-lease the card, publish contradicting residency to two
seams and charge the same VRAM twice, whether or not the handoff claim is fenced. Landing the fence
alone would put a cross-process-looking guard at the one place a reader checks, above four guards
that are still single-process, which reads as a stronger guarantee than the deployment has.

**The atomic claim is also not the `SET NX` that addendum sketched.** `active()` self-heals today: a
dangling pointer, or one naming a terminal record, reads as no handoff and mutates nothing. A bare
`NX` on the active key destroys that property, so a stale pointer would refuse every escalation
until a human cleared the key. Preserving the self-heal inside one atomic step means a Lua script
that reads the pointer, reads the record it names and claims only when it is absent or terminal,
plus the lease or owner id that lets boot recovery tell its own strand from another process's live
handoff. That is a second distributed-concurrency protocol beside the schedule store's, written for
a claimant population of one.

**The trigger, which a closed task may not carry, lives here.** A second process that can swap: a
second brain replica, a CLI or worker sharing the Redis, or a supervisor sidecar that swaps itself.
The deployment still declares one `brain` service with no replicas, and the sidecar still performs
no swap of its own, its control API able only to start, stop and report the tiers its env names. If
that day comes, the work is a distributed-residency decision covering the lease, the board, the tier
record and the ledger together, with a fenced claim as one of its consequences rather than as the
whole of the change.
