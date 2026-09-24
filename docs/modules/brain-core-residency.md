# brain/packages/core: model residency and the swap

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers which model is on the GPU: the values and ports that
describe it, the record a mid-turn handoff is rebuilt from, and the sequence that evicts the cortex
for the deep model and puts it back. The `escalate_to_brain` tool that asks for one is in
[brain-core-tools.md](brain-core-tools.md) and the subagent tiers a swap stops are in
[brain-core-subagents.md](brain-core-subagents.md). The decision is ADR-0030, extended by ADR-0053,
ADR-0054 and ADR-0055; the runbook is [model-swap](../runbooks/model-swap.md).

## Model residency

The deep model needs the whole GPU, so serving it means evicting the cortex and putting it back.
**The normal residency** is the cortex plus every `plan.evict_models` tier: the state every exit
path returns the card to. Measurements are in [model-swap](../readings/model-swap.md) and
[co-residency](../readings/co-residency.md).

- `ModelLease(endpoint)` is a live claim on the GPU for one model, valid only inside the `acquire`
  block that yields it. `ModelHostState` is `STOPPED`, `LOADING`, `READY` or `FAILED`: what one
  logical model's process is doing. `start` only begins loading, so readiness is observed through
  `status` and nowhere else.
- `DeviceMemory(free_mib, total_mib)` is how much of the GPU is free now and how big it is, in MiB.
  **A reading is evidence before an allocation and never after one**: measured 2026-08-07, a pair
  of tiers that genuinely fit a 24 GB card and a pair overcommitted by 4676 MiB both read about
  23.6 GB used with about 0.5 GB free, the driver having paged the excess to system memory.
- `ControlBounds(probe_timeout_s, stop_grace_s, reap_timeout_s)` is the three deadlines one control
  call can spend, with `worst_case_stop_s` their sum and `clears(deadline_s)` the strict comparison
  a caller's own deadline must pass. Three terms rather than two because a `status` takes the same
  per-model lock a `stop` does, so a queued stop pays that probe's deadline first, measured at
  15.70 s against 10.89 s with the lock free. `pairing_fields(deadline_s)` renders the five numbers
  of that comparison as log fields.
- `ResidencyPlan(cortex_model, brain_model, evict_models=(), coresident=False, brain_vram_mib=0,
  brain_decode_tps=0.0, drain_timeout_s=60.0, load_timeout_s=300.0, poll_interval_s=1.0,
  control_deadline_s=0.0)` is the composition-root value the manager, the conductor and boot
  recovery all read, so they cannot disagree about the topology; construction raises `ValueError`
  when `evict_models` names either other model. `coresident` reverses one rule and nothing else: a
  swap then stops only the cortex and the conductor never drains, so delegation runs through the
  handoff. `brain_vram_mib` is the free device memory the deep model needs, compared against the
  host's own reading immediately before the load, and zero means no check. `control_deadline_s`
  (`CORTEX_MODELHOST_TIMEOUT_S`) is compared against the host's worst stop by two readers, so it
  lives here rather than being passed twice. `DEFAULT_SWAP_DRAIN_TIMEOUT_S` (60 s, a bound on the
  user's wait: a whole CPU subtask measures 200 to 300 s, so a drain that meets one in flight
  usually elapses and aborts the handoff before anything is evicted),
  `DEFAULT_SWAP_LOAD_TIMEOUT_S` (300 s, an 18 GB GGUF off the mount being minutes) and
  `DEFAULT_HEALTH_POLL_INTERVAL_S` (1 s) are the exported defaults.
- `await_model_ready(host, model, *, clock, sleeper, plan)` (`model_ready.py`) is the one readiness
  check, shared by the swap in, the restore and boot recovery. It polls `status` until it settles
  or `plan.load_timeout_s` elapses and returns the last state seen when the bound elapses, so a
  caller can tell a load still running from a start that never took. The deadline is taken once
  before the first poll, so a zero bound is already expired.

### Residency ports

- `ModelManager` provides `acquire(model)`, which owns the GPU, queues for access and yields a
  `ModelLease`. It is unchanged by the swap: residency is a separate port.
- `ModelHost` (`ports_models.py`) provides `start`, `stop`, `status`, `device_memory`,
  `control_bounds` and `boot_id`. The last three are readings only the host can take, and each
  returns `None` as a normal answer, meaning it can see no card, has no stop of its own to bound,
  or will not name which boot it is; a boot id is compared for equality only. Both lifecycle verbs
  are idempotent, and `model` is a logical id, so artifact paths, ports and engine flags never
  cross this port. Failures are `ModelHostError`, with `ModelNotHostedError` for an id the host
  does not serve at all. Fake: `ScriptedModelHost`; real adapter: `cortex_model_manager`.
- `ResidencyController` provides `swap_scope(model)`, `handoff_claim()` and `unhosted(model)`.
  `swap_scope` waits for the GPU lease to fall free, performs the swap, serves `model` for the
  scope, and in a `finally` restores the normal residency; entering may raise `SwapFailedError`
  with the cortex already restored by that same `finally`, and a restore that fails even after its
  one retry raises `ResidencyRestoreError` naming both the tier the last attempt failed on and the
  cortex. `handoff_claim` takes the one-GPU-one-handoff rule before anything is drained or evicted
  and raises `HandoffInProgressError` at once rather than queuing, with nothing awaited between the
  check and the claim. `unhosted` returns `True` only on an explicit refusal, and is asked every
  time rather than remembered.
- `ResidencyQueue` provides `blocks(model)`, synchronous, whether another model's residency scope
  is active so a lease of `model` would wait, and `await_scope_end(model)`, which waits until none
  is and leaves the check of what is resident to the lease. A turn uses it to announce the wait
  before it reads its history and before each model call (ADR-0069 decision 9).
- `ResidencyReporter` provides `residency() -> ResidencyReport`, what the GPU is serving right now,
  for the wire's `Health`. It is **synchronous and free of I/O by contract**, because a probe
  arrives every few seconds precisely while a swap is in flight and one that queued behind the GPU
  lease would hang for the whole load; an implementation answers from a cache it publishes into.
- `PaceSink` provides `note_pace(*, spilled)`, where the deep phase says whether the tier it just
  ran held the rate its deployment measured for it. Also synchronous and free of I/O, being called
  after the reply has streamed and before it is persisted. What crosses is a judgement and never a
  reading, and a phase with no judgement calls it not at all. Implementation: `HandoffPace`; fake:
  `RecordingPaceSink`.
- `HandoffStore` holds the one in-flight handoff: `put`, `get`, `transition(handoff_id, state, *,
  failure=None)`, `delete` and `active()`. State and reason move in one read-modify-write, so a
  transition naming no reason clears the field. Fake: `InMemoryHandoffStore`; adapter:
  `cortex_session`.

### The handoff record

`HandoffState` is `PENDING`, `READY`, `BRAIN_ACTIVE`, `DONE` or `FAILED`, and `terminal` is `True`
for the last two: a terminal record stops being `active()` and may expire. `HandoffRecord` holds
`handoff_id` (the escalating `turn_id`, which is why every log line on this path names its work
`turn_id`), `session_id`, `requested_at`, `state`, `brief`, `nonce`, the whole serialized
`TaintLedger` (`tainted`, `opaque`, `sources`, `untrusted_urls`), `budget_remaining`,
`budget_closed`, `rounds_used` and `loop_tail`. It contains only what is not already in a store,
per the one hard rule, and `taint_ledger()` rebuilds an exact detached ledger for the deep phase.
`opaque` is there as defence in depth: the conductor refuses an opaque turn before it snapshots, so
every record written today says `False` truthfully, but both readers of the field open up on a
`False`, so the schema must never manufacture one. `failure` is the one field that is not turn
state: what a `FAILED` record says about itself, written by the settling transition.

`EscalationSlot(refs=None, brief=None)` is the mutable turn-local handle through which in-flight
state reaches the record. It is built empty by whoever orchestrates the turn and serves exactly one
turn; the engine fills `refs` at turn start with an `EscalationRefs` (the live `working` list,
taint ledger, nonce, shared allowance, and `base_len`, how many messages `working` held when the
loop began, so everything past it is the tail), and the `escalate_to_brain` tool writes only
`brief`. `snapshot(*, turn_id, session_id, requested_at)` freezes it into a `READY` record by
copying, and raises `ValueError` on a slot no tool filled, one no engine filled, or a tail
containing images, the record being durable and its schema having no field for pixels.

### Running the swap

- `SwapConductor(handoffs, residency, brain_phase, plan, clock, scheduler=None)`
  (`swap_conductor.py`) runs one handoff end to end as a stream of turn events. `run_handoff(slot,
  *, session_id, turn_id)` refuses before anything moves in three cases: another handoff holds the
  claim, which is taken first so nothing is read, written, drained or evicted; the turn's ledger is
  `opaque`; or the host does not serve the deep tier at all. It then snapshots the slot, drains the
  subagent pool (a timeout aborts before anything is evicted), enters the residency scope, marks
  the record `BRAIN_ACTIVE` only once the deep model is serving, streams `BrainPhase`, and settles
  the record `DONE` or `FAILED`. `undrain` is owed in a `finally` on every path and **after** the
  swap generator's teardown, never beside it. Every failure, cancellation and stream teardown
  leaves the record terminal and the normal residency back.
- `HandoffSettler` (`swap_settle.py`, held by the conductor and not exported) has two verbs:
  `advance(record, state)` for the two writes that owe no reason, and `fail(record, reason)` for
  the one that does, so no path can settle a handoff failed without saying why. `fail` writes the
  reason onto the record and into one warning, each covering the other's failure. Settling also
  releases the store's active pointer, so a settling write the store rejects is followed by
  deleting the record anyway.
- `BrainPhase(store, backend, clock, brain_model, capabilities, cadence=NO_CADENCE_TERMS)`
  (`brain_phase.py`) rehydrates from the stores and the record alone: history from `SessionStore`,
  the working set as preamble plus recalled context plus history plus the record's `loop_tail`, the
  taint ledger and nonce from the record, and the dispatch allowance resumed at its recorded
  position. It runs the shared tool loop with a fresh rounds allowance, no escalation slot and no
  `capture_screen`, then persists its reply as a second assistant message under the same `turn_id`.
  A mid-work `InferenceError` persists the partial text with a note and re-raises, so the conductor
  fails the record, with the same `MalformedToolCallError` exception the cortex turn makes. It is
  the only caller that watches decode rate, logging the tier's rate once after the stream and
  before persisting and handing the same judgement to `cadence.sink`.
- `CadenceWatch(floor=0.0, *, min_tokens=MIN_CADENCE_TOKENS)` (`cadence.py`, ADR-0055 decision 4)
  is the policy behind that: `observe(sample)` takes one completion's `DecodeCadence` and
  `reading()` settles them into a `CadenceReading(observed, floor, samples, judged)` or `None`. A
  sample under `MIN_CADENCE_TOKENS` (32) is counted and never judged, and the fastest qualifying
  sample decides, a spill being a ceiling that holds for every completion while it lasts. A zero
  `floor` means this deployment measured no rate and has no opinion, a third answer rather than a
  pass. `CadenceTerms(floor_tps=0.0, sink=None)` is the pair a phase is built with and
  `NO_CADENCE_TERMS` the empty one. Nothing is persisted: one watch serves one handoff.
- `EscalatingTurnEngine(make_inner, conductor)` (`escalating_engine.py`) is the `TurnRunner` a
  deployment with escalation enabled serves turns through. Per turn it builds an `EscalationSlot`,
  constructs the inner engine around it, passes every event through, suppresses the inner
  `TurnCompleted`, and, only when the cortex asked to escalate, runs the conductor on the same
  stream before emitting one real `TurnCompleted` whose text is the whole turn's. Both the handoff
  and the completion are named by the `turn_id` it was handed.
- `recover_handoffs(...)` and `converge_residency(...)` (`swap_recovery.py`) are boot recovery. The
  composition root calls the first once at startup: it marks any non-terminal record `FAILED` with
  `STRANDED_REASON`, then converges the GPU back onto the normal residency in the conductor's own
  order. It never raises, and what it returns is whether the cortex was observed `READY`, which the
  root publishes onto the manager: without that, a boot that could not settle the cortex answers
  `Health` ready off the manager's seed.
- `SWAPPING_STATE` and the swap window's status and reply texts (`swap_notes.py`) are every
  brain-written string a handoff can put on a turn's stream. Status details are progress; notes are
  reply text, streamed but not persisted, except `BRAIN_FAILED_NOTE`, appended to the deep model's
  partial reply and persisted with it. `note_for(error)` maps a `ModelManagerError` to the note
  that is true of the GPU at that moment. `DRAIN_TIMEOUT_REASON`, `TORN_DOWN_REASON` and
  `STRANDED_REASON` (`swap_reasons.py`) are the opposite: a note is what the user is told and
  describes the GPU, a reason is what the record keeps and describes the fault. The two families
  never share a string, and none of it is model text.

### The manager

`SingleResidentModelManager(resident_model, endpoint)` is the `ModelManager` for a deployment that
never escalates: `acquire` serializes callers with one lock and refuses any other model with
`ModelUnavailableError`. `SwappingModelManager(host, endpoints, plan, clock, sleeper)`
(`residency.py`) implements the lease port, `ResidencyController`, `ResidencyQueue` and
`ResidencyReporter` together,
still as pure policy with no I/O of its own. A scope rather than a swapping `acquire`, because the
deep model's tool loop re-acquires once per round and a swapping `acquire` would thrash minutes
each way whenever a queued cortex turn interleaved. Its parts are split along the boundary the
manager already draws, it owning when and who may, they owning what the host is asked to do:
`residency_claim.py` (`HandoffClaim`, the non-blocking claim over the whole sequence);
`residency_moves.py` (the two host-facing moves, with the fit check between the last `stop` and the
`start`, the only instant at which free memory means anything); `residency_restore.py` (the swap
back's retry policy and its uninterruptible wait, where every cancellation waits for the shielded
restore, not merely the first); `residency_board.py` (`ResidencyBoard`, holding which model the GPU
serves, what a user is told, whether a scope owns the card, and the one condition all three are
published under, with `report` and `scope_active` as lock-free reads so `Health` answers during a
load); `residency_probe.py` (`ResidencyProbeMixin`, which composes the answer as it is read,
annotating the published record first by the peers that are missing and then by how the last
handoff ran, and whose `publish_boot_residency(*, serving)` touches display alone); and
`residency_charge.py` (which tells the optional `SubagentPlacer`, at the swap's two edges, which
model holds the card, written before the swap in and reversed only once the cortex serves again).

`ResidencyReport(serving, detail, notes)` and the six values a swap publishes are in `residency_state.py`:
`RESIDENCY_SERVING` (the normal residency, and the seed a fresh manager starts from),
`RESIDENCY_LOADING`, `RESIDENCY_DEEP`, `RESIDENCY_RESTORING`, `RESIDENCY_LOST` (a restore that gave
up) and `RESIDENCY_BOOT_FAILED` (boot recovery ran and did not leave the cortex serving). The drain
is deliberately `RESIDENCY_SERVING`, the cortex being resident and answering turns while delegated
work quiesces. `with_note(report, note)` is the one composition every annotator shares: a serving
report gains the note after any already in `notes`, and one that is not serving is unchanged.

### Keeping the normal residency

- `BaselineTiers(placer=None)` (`residency_tiers.py`, ADR-0054 decision 3) records which peers of
  the cortex are missing. `mark_missing`, `mark_unhosted` and `mark_serving` are written by the
  restore wherever it runs and by the pass below; `fault_of(model)` and `missing` read it back. A
  mark of either kind closes the placer's GPU and only an emptied record reopens it, and
  `note_on(report)` adds the detail naming what is down, which names the state and not the cause.
- `HandoffPace(clock, *, dwell_s=DEFAULT_SPILL_DWELL_S)` (`residency_pace.py`) is how the last
  handoff ran, for as long as that still describes now. `note_pace(spilled=True)` stamps the
  moment, `note_pace(spilled=False)` clears the note outright, and a second spill re-starts the
  dwell. The note lapses on its own after `DEFAULT_SPILL_DWELL_S` (3600 s), long enough to still be
  there when somebody who walked away from a minutes-long deep task comes back and short enough
  that a card left alone for an afternoon is not described by a judgement about the morning.
- `recheck_tiers(host, plan, tiers, fence)` (`residency_pass.py`) is one pass over **every**
  `plan.evict_models` tier rather than only the marked ones, because the ways a peer goes down with
  no refusal to record are exactly the ways a record written from refusals cannot see. Per tier: an
  unhosted one is skipped without a call, a `ModelNotHostedError` records that fault, any other
  `ModelHostError` leaves the record alone and logs, `READY` marks it present, `LOADING` is left
  alone, and `STOPPED` or `FAILED` marks it missing and then, if `fence()` still allows, issues one
  `start`. The mark is written before the fence is consulted. It never raises.
- `recheck_baseline_residency(host, plan, board, tiers, fence)` (`residency_regain.py`) is a whole
  pass: `recheck_tiers` for the peers, then `regain_residency` for the resident, in that order so
  the report the second publishes is composed over a record the first has just refreshed.
  `regain_residency` answers a state nothing else could leave, a restore that gave up refusing
  every `acquire`, so no turn runs, so no handoff starts, so the reconciliation inside the swap is
  unreachable; a serving report returns before any call, so a healthy deployment pays nothing.
  `TierRechecker(recheck, *, interval_s=DEFAULT_TIER_RECHECK_INTERVAL_S)` (`residency_recheck.py`)
  is the loop that keeps calling one such pass and owns its own task.
- `BootWatch(host, plan, tiers, *, clock, sleeper)` (`residency_watch.py`, ADR-0053 decision 12)
  records which supervisor daemon every belief above was formed against, and the manager calls
  `reconcile(publish)` as the first thing a swap does. `observe(boot_id)` is the whole decision and
  it is pure: `None` is no evidence and keeps what was remembered, a first answer is a seed, and
  anything else is a replacement, remembered at once so one restart reconciles once. A replacement
  runs `converge_residency` and publishes what it observed, then re-reads `control_bounds()` and
  refuses the handoff when `plan.control_deadline_s` no longer clears them. Both refusals happen
  with the cortex still serving and nothing unloaded.

**Invariants.**

- A handoff record contains only what no other store holds, and a swap never refills the turn's
  dispatch allowance.
- Every exit from a residency scope, cancellation and teardown included, restores the normal
  residency and leaves the handoff record terminal.
