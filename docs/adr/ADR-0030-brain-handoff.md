# ADR-0030: Brain handoff (the real model swap)

**Status:** Accepted (2026-09-17)

## Context

The one hard rule in [AGENTS.md](../../AGENTS.md) says state must survive a model swap. This record
turns that rule into a mechanism: the cortex escalates mid-turn, its context is serialized to a
store, the model host evicts the cortex and loads the deep model, the deep model reads the store,
works and stores its results, and the cortex comes back and resumes from the store.

Most of a turn already lives in a store (history, tasks, schedules, memory). What does not,
mid-turn, is the tool loop's tail (the assistant tool-call messages and fenced `Role.TOOL` results,
which are never stored), the `TaintLedger`, the fence nonce, the turn-wide `DispatchBudget` and the
round count. The GPU lease is held across one inference round, not one turn, and the body opens one
`Converse` stream per turn, so what the user sees during a handoff is sent on that turn's stream.
The deep model (gemma-4-31B QAT q4_0, about 18.7 GiB at an 8K context) does not fit beside the
cortex (about 8.4 GiB at its peak) on the 24 GB card this repo targets, so a handoff is an eviction.

The supervisor sidecar is [ADR-0053](ADR-0053-model-host-supervisor.md); the residency report and
the cortex's peers [ADR-0054](ADR-0054-baseline-residency.md); co-residency, the fit check and the
spill watch [ADR-0055](ADR-0055-co-residency-and-spill-watch.md).

## Decision

### 1. Escalation is an explicit `escalate_to_brain` built-in tool that needs confirmation

The cortex calls `escalate_to_brain(brief)` (`cortex_core/escalate.py`) when it finds mid-turn that
the task is beyond it; mid-turn is where the evidence is. The tool writes only `slot.brief` (stripped,
at most `MAX_BRIEF_CHARS`, 4,000, refused whole rather than cut) and tells the model to finish without
further tools. It is registered only when the escalating wrapper is configured, since a tool that
could only refuse would be a misleading advertisement.

The tool **needs confirmation**: an untainted turn confirms through the ADR-0022 card, whose reason
is the tool's own (`DispatchPolicy.confirm_reasons`, configured as `CORTEX_TOOLS_GATE_REASONS__<name>`),
and a tainted turn is denied outright with the confirmer never consulted. Of the deny's two reasons,
the deep tier's unmeasured injection resistance no longer applies (the model obeyed 0 of 10 framed
injections, [ADR-0013](ADR-0013-untrusted-content.md)); the other still holds, since no model
measurement addresses it: injected content must never force an eviction that claims the GPU for
minutes. The deny is the dispatcher's generic branch for tools needing confirmation, unconditional by
[ADR-0022](ADR-0022-email-write-confirmer.md) decision 2, so relaxing it means an explicit exception
rather than a configuration change.

A turn that has seen screen-capture pixels cannot escalate, pixels being turn-local
([ADR-0029](ADR-0029-vision-screen-capture.md)): the confirmation rule closes capture-then-escalate
(an opaque turn is tainted), and the conductor refuses the reverse order on the ledger's `opaque`
bit (`OPAQUE_TURN_NOTE`). A pre-turn policy would be a producer of the existing `RoutingHints`.

### 2. The handoff record and the `HandoffStore` port

`HandoffRecord` (`cortex_core/handoff.py`) holds only what is not already in a store:
`handoff_id` (the escalating turn's id, [ADR-0046](ADR-0046-work-identities-on-log-lines.md)
decision 4), `session_id`, a timezone-aware `requested_at`, `state`, `brief`, the fence `nonce`,
the whole ledger (`tainted`, `opaque`, `sources`, `untrusted_urls`), `budget_remaining` and
`budget_closed` (so a swap never refills the allowance; `DispatchBudget.resume` rebuilds the pool),
`rounds_used`, the text-only `loop_tail`, and `failure` (decision 10). `opaque` is defence in depth:
no record has it set today, but both its consumers (the URL guardrail's strict mode and the
tainted-memory policy) relax on `False`, so a rebuilt ledger must never invent one.

States run `READY`, `BRAIN_ACTIVE`, then terminal `DONE` or `FAILED`; `PENDING` has no producer.
`HandoffStore` (`put`, `get`, `transition(id, state, *, failure=None)`, `delete`, `active()`) sits in
`ports_stores.py` with a core fake and a Redis adapter in `cortex_session`. The codec reads every
field strictly: a missing taint key is a corrupt record (`HandoffStoreError`), never a default. At
most one handoff is active; `active()` treats a dangling pointer, or one naming a terminal record, as
no handoff. A clean handoff ends `DONE` and is deleted, which frees the pointer, so success leaves no
record; a failed one is kept for one hour (`_TERMINAL_TTL_SECONDS`); a live one has no TTL, so boot
recovery finds it.

The in-flight state reaches the serializer through an `EscalationSlot`, built empty by the wrapper,
filled by the engine at turn start with `EscalationRefs` (working list, ledger, nonce, budget,
pre-loop length), and snapshotted by the conductor after the cortex phase has finished.

### 3. The process-lifecycle port: `ModelHost`, adapted by a supervisor sidecar

`ModelHost` (`ports_models.py`) has `start`, `stop` and `status` (`STOPPED`, `LOADING`, `READY`,
`FAILED`) over a **logical** model id, and three reads (`device_memory`, `control_bounds`,
`boot_id`). Model file paths, ports and layer counts never cross it. It raises `ModelHostError`, or
its subclass `ModelNotHostedError` when the host has no such id. `ScriptedModelHost` is the core
twin CI drives. The real adapter drives the `model-host` sidecar, which holds the GPU reservation
and runs one `llama-server` child per logical model on a fixed port (cortex `:8080`, deep `:8081`,
GPU subagent `:8083`), starting the cortex at boot; killing a child loses nothing, by design
([ADR-0005](ADR-0005-llamacpp-engine.md) decision 3).

### 4. The swap sequence, its ordering guarantees, and every failure's direction

Every exit path converges back to a serving cortex; the swap back is the recovery path.

1. **Snapshot**: store the record `READY` before anything touches the pool.
2. **Drain**: `SubagentScheduler.drain()` stops admitting and waits for in-flight admissions,
   bounded by `CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s); `admit` refuses (`SubagentAdmissionError`)
   rather than queues for the whole handoff, since a queued deep-phase spawn would deadlock the turn
   against its own drain. On timeout the handoff aborts **before anything is evicted**. The drain
   waits on admissions, never on a schedule lease, and a whole CPU subtask takes 3 to 5 times the
   bound ([ADR-0005](ADR-0005-llamacpp-engine.md) decision 7), so meeting one usually aborts, which
   is the intended direction. Raising the setting trades handoff latency for handoff success.
3. **Swap in**: wait for the lease to fall free (no mid-stream preemption), stop the cortex and
   every `CORTEX_SWAP_EVICT_MODELS` tier, start the deep model and wait for it to report `READY`
   within `CORTEX_SWAP_LOAD_TIMEOUT_S` (300 s), store `BRAIN_ACTIVE`. A failed load stops it and
   restores the cortex.
4. **Read the state back and run** the shared `stream_tool_loop` on the deep model over windowed
   history, recall and the record's tail, with the rebuilt ledger, the resumed budget, the same
   audited dispatcher and the guardrail seeded with the stored URLs; the rounds allowance is fresh.
   The deep model judges that recall and writes any recap, the one model its scope can lease.
5. **Store** the deep reply as a second assistant message under the same `turn_id`, and memory
   under the engine's taint policy; a deep model that dies mid-answer has its partial text stored
   with its failure note.
6. **Swap back**, in the scope's `finally`: stop the deep model, start the cortex and wait for it to
   report `READY` (one retry, then a logged failure), then start every evicted tier back, best
   effort. The restore is a shielded task that waits out **every** cancellation and re-raises the
   first once done, because the gRPC layer cancels a torn-down turn twice; `undrain` runs after it.

**Boot recovery** fails any non-terminal record with `STRANDED_REASON` and brings residency back to
plan ([ADR-0054](ADR-0054-baseline-residency.md) decision 2). A crashed deep phase is **not** resumed:
a resumed phase would re-run every tool the deep model had dispatched, which only a request-identity
and deduplication design prevents, and it would be a conductor entry point started beside the gRPC
server, never a step of boot recovery, which runs first.

### 5. Who orchestrates: a core conductor over an added residency scope; `acquire` unchanged

- **`SwappingModelManager`** implements the unchanged `ModelManager` (`acquire` leases the resident
  model under one lock) and the separate **`ResidencyController`**: `swap_scope(model)`,
  `handoff_claim()` (non-blocking, nothing awaited between its check and set) and `unhosted(model)`
  (decision 11). While a scope is active, `acquire` of another model waits, but raises
  `ModelUnavailableError` at once from the task holding the scope, whose wait could never end.
- **`SwapConductor`** runs decision 4 over the store, the drain, the controller, a `Clock` and a
  `Sleeper` port (so the health check never polls in real time under test). `HandoffSettler`
  (`swap_settle.py`) owns the settling writes; `BrainPhase` bundles step 4, built per stream so the
  deep model runs that stream's dispatcher; `turn_output.py` is the output half both phases share.
- **`EscalatingTurnEngine`**, behind the `TurnRunner` port, builds the slot, runs the plain engine,
  suppresses its `TurnCompleted` when the slot was filled, runs the handoff and emits one
  `TurnCompleted` for the whole turn. It is wired only under `CORTEX_ESCALATION`, which requires
  `CORTEX_MODELHOST_BACKEND` (`scripted` or `supervisor`) and `CORTEX_BRAIN_ENDPOINT` or boot fails.

The claim is taken before anything is read, written, drained or evicted; a second handoff is refused
with `ALREADY_ACTIVE_NOTE`, and `HandoffInProgressError` says one is running rather than that a swap
failed. The store's `active()` check is the second line of defence, and the deep phase has no slot, so
it cannot escalate to itself. **Every guard is in-process**, and the deployment runs one brain: the
lease, the claim, the residency board, the peer record and the placer's ledger are instance state, so
a second process that can swap needs a distributed-residency decision over all five.

### 6. What the user sees: one turn, one stream, and an accurate `Health`

The cortex's pre-handoff text is stored as its assistant message; the wrapper yields
`StatusUpdate(state="swapping")` for the drain, the load, the deep work and the restore, each only when
its work is next; the deep reply streams as the same turn's `TextDelta`s; `TurnComplete` is sent once.
A refusal or failure streams a fixed note from `swap_notes.py` describing the GPU, never the fault, and
is not stored except for the deep model's failure note beside its partial text. `Health` returns
`ready=false` with a truthful detail while the cortex is not serving, and ready through the drain
([ADR-0054](ADR-0054-baseline-residency.md) decision 1). No proto change was needed.

### 7. The failure test: kill points over fakes in CI, the real kill on the host

A parameterized suite over the scripted host, fake stores and the real conductor kills at every
boundary of decision 4, including inside the real drain, a store refusing either settle, and a closed
stream at the conductor, the wrapper and the deep phase. Every case asserts the cortex is the only
model running with the evicted tiers asked back, the pool admits again, no partial reply is stored as
complete, memory holds the exchange or nothing, the record is terminal and `active()` is `None`, a
later escalation still runs, and the stream ends with an accurate sentence or a `SeamError`. Every
property is proven able to fail by mutation. The host half (`kill -9` on the deep child) needs the
24 GB card **and** a Windows desktop, since only the overlay shows the confirm card.

### 8. VRAM: the deep model runs alone by default

A handoff evicts the cortex and every `CORTEX_SWAP_EVICT_MODELS` tier and drains the pool, so
admission never reopens onto an evicted tier. The window suspends the 14 GB soft cap, the user
having confirmed a handoff that takes the card; `CORTEX_NGL_BRAIN` and `CORTEX_CTX_SIZE_BRAIN` bring
the deep tier under a budget. In normal operation the card holds the cortex and one GPU-placed
subagent tier ([ADR-0012](ADR-0012-resource-governance.md)), which a deployment hosting it lists for
eviction.

The evict list names peers of the cortex only: `ResidencyPlan` raises `ValueError` at boot when it
names the deep model or the cortex, reporting `CORTEX_SWAP_EVICT_MODELS` and the setting the id
belongs to, because every reader of the list starts a listed tier that is not running (a listed deep
model would start beside the cortex; a listed cortex would reload at every boot). Keeping peers
resident through a handoff is the opt-in of [ADR-0055](ADR-0055-co-residency-and-spill-watch.md).

### 9. What remains on the host

The mechanism is validated in Docker with small stand-in tiers and with the real cortex on the 24 GB
card; the tier-scale swap through the overlay is in [docs/host/](../host/index.md#gpu-tier-scale).

### 10. A handoff that failed says why, on the record

`HandoffSettler.fail(record, reason)` is the only writer of `FAILED`, so no path settles a failure
without a reason. The reason is written in the state's own read-modify-write, and a transition naming
none clears it. It is written by the application or taken from an error's message, never from model
text: `swap_reasons.py` holds `DRAIN_TIMEOUT_REASON`, `TORN_DOWN_REASON` and `STRANDED_REASON`, and
the swap's `ModelManagerError` and the deep server's `InferenceError` include their own message,
which is how the model host's status reaches the brain. `fail` writes one `WARNING` (`a handoff ended
failed`) before asking the store. A terminal write the store refuses is followed by deleting the
record, since a stuck active pointer would refuse every later escalation; a refused intermediate
write keeps it for boot recovery. The reason stays off the residency report, whose detail the user
reads word for word and which is not serving on every path that leaves the machine wrong.

### 11. A handoff the host cannot run is refused before the drain

`SwapConductor._prepare` calls `unhosted(deep model)`, one `status` call, after the `opaque` check
and before the store is touched. Only `ModelNotHostedError` means yes: a model host with no deep tier
(`CORTEX_ESCALATION=1` without `CORTEX_MODEL_FILE_BRAIN`) gets `UNHOSTED_TIER_NOTE`, no record, no
drain and a cortex that never stopped. Any other failure means no and the handoff fails where it
really fails. The result is not cached, because the fix is restarting the sidecar, not the brain.
Each refused attempt logs one line naming `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION`; the
confirm card still comes first. Behind that, the swap in names the missing tier, and the swap back
tolerates `ModelNotHostedError` from stopping the model it swapped in, so a missing tier never leaves
the cortex unloaded.

## Consequences

- The hard rule made real: all mid-turn state is in the record or a store before anything is
  evicted, the deep phase is a function over them, and a failed record outlives the process that
  ran it. Facts about the machine are read again from the model host, never stored
  ([ADR-0054](ADR-0054-baseline-residency.md) decision 6).
- A turn can hold its stream for minutes, and a teardown mid-handoff waits for the cortex. Swap-path
  log lines name their work `turn_id`, and the handoff still in the store `active_turn_id`
  ([ADR-0046](ADR-0046-work-identities-on-log-lines.md)). CI stays GPU-less, and the failure suite
  must pass.

## Risks flagged for maintainer review

1. **The tainted-turn deny** rests on the eviction argument alone, with 0 of 10 measured beside it.
2. **The model-host sidecar** is privileged (GPU, models mount, process control), on the compose
   network only.
3. **Swap latency** is the loads: an eviction costs about 1% of the deep load, and the whole swap
   about 1.5 times that load warm ([model swap](../readings/model-swap.md)).
4. **Two assistant messages share one turn id**, and **the deep phase uses the cortex's
   dispatcher**, spawn included; narrowing it is wiring.

## Alternatives rejected

- **A pre-turn policy, a user-only trigger, or a tool without confirmation plus a taint check**:
  nothing accurate computes the first, the second cannot express depth found mid-turn, the third
  loses the consent.
- **Reusing `TaskStore`, the tail in `SessionStore`, or a wider `TurnStamp`**: each muddies a
  contract that already means something else.
- **The Docker API, a compose controller, or subprocesses in the brain**: host root in the process
  running model-influenced code, or CUDA in the brain.
- **`acquire` performing the swap**: the deep loop re-acquires per round, so an interleaved cortex
  `acquire` would swap back mid-task. **Answering in a new turn**: one turn per call.
- **Hiding `escalate_to_brain` when the deep tier is missing**: an absent tool says nothing, so
  nobody learns why no handoff happens. The per-turn cost first argued against it is not prohibitive
  (a live capability read per turn exists at about 1.5 ms); the lost sentence is the reason.
- **A cross-process claim with a fence** (`SET NX`): it breaks `active()`'s ability to recover on
  its own and would be one cross-process guard above four in-process ones.

## Related

[brain-core](../modules/brain-core.md), [brain-orchestrator](../modules/brain-orchestrator.md),
[brain-session](../modules/brain-session.md), the [model-swap](../runbooks/model-swap.md) runbook and
its [measurements](../readings/model-swap.md), [ADR-0012](ADR-0012-resource-governance.md) (the drain
and the placer), [ADR-0013](ADR-0013-untrusted-content.md) (taint and the injection measurements).
