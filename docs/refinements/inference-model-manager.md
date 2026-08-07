# Inference & Model Manager

Deferrals from the Slice 4 inference work, whose origin decision is
[ADR-0007](../adr/ADR-0007-model-manager-inference.md); the reasoning-status entry carries its own
decision record in [ADR-0020](../adr/ADR-0020-reasoning-status.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** 7, counted by reading the entries below rather than by adjusting the last number.
Resume a crashed handoff from its record; fence the single-handoff claim across processes;
reconverge the brain's residency when the sidecar restarts under it; check the sidecar's stop
bounds against the brain's control deadline; MTP model variants; disable-thinking / token-budget
capping, **narrowed rather than closed on 2026-08-06**; and noticing a handoff that spilled, which
is what a fit check cannot see. Three entries closed on 2026-08-07 and this area's oldest was one
of them: **model-manager co-residency**, which opened two in its place, then **the fit its flag
asserted**, which closed as a real check and opened one, and then **the placer's budget describing
the standing residency rather than the handoff window**, which closed as a placement epoch and
opened nothing. So the count went 7 to 8 in the morning and back to 7 by the end of the day: three
out across three sittings and three in, every arrival something a landing made reachable rather
than something it broke, and the one that closed on the day it opened did so because its own
trigger turned out to be a setting a deployment can already turn.

On the narrowing of the capping entry, which is the one the count deliberately did not move
for: the lever shipped on 2026-08-06 as `GenerationBounds` on `InferenceBackend.stream`, and
all three passes whose deliberation `drain_text` throws away unread now take it: the history
recap's fold, the session title, and the model-based recall rank. What the entry still covers is
the case it was written for and the only one left, a user-facing reply, which sends no bounds
deliberately, so a runaway trace on a real answer is uncapped exactly as it always was and the
original trigger, a user who minds the wait, still stands for that case alone. **The count does
not move for this entry.** A count moved for a half-closed entry loses an open item exactly as
one that fails to move for a newly opened deferral does, which this backlog learned in the other
direction; what moves instead is this sentence and the entry's line in the index's
fix-when-it-bites bucket, so nobody picks it up expecting to build a lever that already exists.

**Inference / Model Manager in Slice 4 ([ADR-0007](../adr/ADR-0007-model-manager-inference.md)):**
- **`cortex_model_manager` process lifecycle and the real swap landed 2026-07-17 and 2026-07-18
  across the brain-handoff sub-slices ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decisions 3 to
  5); co-residency stays deferred.** The entry read: "**`cortex_model_manager` process lifecycle,
  co-residency, real swap.** The pure single-resident manager exists now; process I/O and swap land
  in **Slice 11** behind the unchanged `ModelManager` port (consequences)." It landed behind that
  port exactly as written, `acquire(model) -> ModelLease` untouched: the process half went behind a
  **new, segregated** `ModelHost` port rather than into `ModelManager`, and the swap behind a
  `ResidencyController` that only `SwappingModelManager` implements, which is what kept the
  original port unchanged rather than merely compatible. The real half is the `model-host`
  supervisor sidecar: one `llama-server` child per logical tier, an HTTP control API whose requests
  carry a logical id and nothing else, and the `HttpModelHost` adapter, all passing the same
  contract suite as the in-core scriptable twin. The mechanism is agent-validated in Docker on the
  8 GB dev GPU with two small artifacts standing in for the tiers (real processes started,
  health-gated, evicted, swapped, killed, restarted; see
  [runbooks/model-swap.md](../runbooks/model-swap.md)); **tier scale stays host-side**, the dev
  card being unable to hold the real cortex beside a deep model. **Co-residency remains open**, and
  its shape is now recorded rather than sketched: ADR-0030 decision 8's v1 rule is that while the
  deep model is resident it is **alone** on the GPU, since no candidate fits beside the ~11.3 GB
  cortex in 24 GB, so keeping CPU subagents serving through a swap, or a tiny GPU subagent beside
  the deep model on a larger card, is the thing still deferred. What this landing changes about it:
  the tiers it would need to keep alive are now real hosted models rather than hypothetical ones,
  so the deferral is exercisable for the first time on hardware that fits them.
  **Co-residency closed 2026-08-07** ([ADR-0030](../adr/ADR-0030-brain-handoff.md) co-residency
  addendum), measured first and designed second, on an RTX 5090 Laptop reporting 24463 MiB with the
  real tiers driven through the shipped sidecar. The paragraph above is wrong in three of its
  numbers and the ADR corrects them there; the ones that matter here are that the cortex costs
  **8448 to 8468 MiB** with its projector at 16K rather than the ~11.3 GB every doc quoted, and the
  deep model **19117 to 19125 MiB**, so the pair wants **29139 MiB against 24463** over a 1552 MiB
  floor and misses by **4676 MiB**. **That cortex figure is an idle one**, and a controlled
  re-measurement hours later the same day put the tier's peak at 8573 MiB above the floor and
  lowered `CORTEX_VRAM_CORTEX_GB` from 11.3 to 8.6, which this paragraph declined to do and was
  right to decline; the close is at [resource-governance.md](resource-governance.md), where the
  placer's budget lives, and it moves none of the pair arithmetic above. It does not miss loudly. Started with the cortex resident the
  deep tier reported `ready` at 23539 to 23642 MiB with 496 MiB free, because WSL2 pages the
  overcommit to system memory, and the only witness is decode: **14.80 to 17.29 tok/s co-resident
  against 25.07 to 33.28 alone**, with the cortex untouched at 44.68 to 49.47. So `nvidia-smi` alone
  cannot tell this deferral's answer either way, which is the methodological finding a later sitting
  should not have to rediscover. What **does** fit is the half decision 8 named second, and it needs
  no tiny model: the deep model and the **shipped** gemma-4-E4B subagent tier sat at 23555 to 23642
  MiB with 908 MiB free, the deep model decoding 28.92 to 29.82 tok/s beside it, which is its solo
  rate, and generating on both at once allocated nothing new (23639 MiB under load against 23642
  idle). Against that, a handoff costs 0.48 s to evict the cortex, 70.03 s for the deep model to
  gate warm, and 32.36 s to restore, **102.9 s** in which every spawn is refused, the deep phase's
  own included. What landed is `CORTEX_SWAP_CORESIDENT`, **off by default**, one flag doing two
  things that are useless apart: `swap_in` stops the cortex and nothing else, and the conductor
  never enters the drain window (nor announces one), so delegation runs through the handoff. It is
  safe because a co-resident handoff stops no tier delegated work can reach, which is the reopening
  deferral's own condition rather than a way around it. Two things it deliberately does not do are
  recorded below as this area's newest entries.
- **Check that a co-resident deployment's card really holds the pair, instead of trusting the
  flag.** Opened 2026-08-07 by the co-residency landing
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) co-residency addendum). `CORTEX_SWAP_CORESIDENT` is
  an assertion the deployment makes about its own hardware and nothing verifies it, because the
  brain container sees no GPU: the fit is a fact about one card's free VRAM at one moment, and the
  brain has no reading of it. The failure this leaves is the quiet one the same addendum measured:
  a card that cannot hold the pair does not refuse the second load, it pages the overcommit to
  system memory and serves the deep model at roughly **half** its decode rate, with `nvidia-smi`
  showing the same ~23.6 GB used and ~0.5 GB free as a genuine fit. **What would close it:** the
  sidecar reporting free and total device memory on `GET /health` (it is the process that can see
  the card, and that body already carries the two stop bounds), the adapter carrying it, and a
  check at wiring time or at swap-in that refuses, or logs loudly, when the deep tier's own measured
  cost will not clear what is free. The cost is the one the stop-bounds entry above already prices:
  the brain would then depend on the sidecar answering, which today it deliberately does not, and a
  VRAM reading taken at wiring time is stale by the time a handoff runs. **Trigger:** any report of
  a deep phase that is inexplicably slow on a co-resident deployment, or a second machine adopting
  the flag without redoing the measurement.
  **Closed 2026-08-07**, hours after it was opened
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) fit-check addendum), and the shape it landed in is
  not quite the one above, for a reason the entry's own text contains. The proposed check was "at
  wiring time or at swap-in", and only the second is honest: what a card has free changes by the
  gigabyte while the machine runs, and at boot the cortex is resident, which is not the residency
  the deep model loads into. **Free memory is evidence at one instant only, before the allocation
  and after everything the handoff means to unload is gone**, which is inside `swap_in` between the
  last `stop` and the `start`. That placement is what makes the check possible at all, since the
  same figure read after the load cannot tell a fit from a spill. What landed: `ModelHost` gains a
  fourth verb, `device_memory()`, answered off the sidecar's existing `GET /health` (a
  `DeviceMemoryProbe` seam over `nvidia-smi`, with every failure and any second visible GPU
  reported as no reading rather than a guess); the deployment declares the deep tier's cost as
  `CORTEX_SWAP_BRAIN_VRAM_MIB`; `swap_in` refuses with `SwapFailedError` when the card is short or
  when there is no reading at all; and `CORTEX_SWAP_CORESIDENT=1` without that figure is a boot
  failure on the real supervisor, which is the constant half of the claim caught where it is
  constant. The entry's own cost line is **wrong about the price**: the brain still does not depend
  on the sidecar answering at wiring time, because nothing asks it anything until a swap runs, so
  the stop-bounds entry's objection does not transfer. Measured live rather than argued: with the
  cortex resident the sidecar reported **14905 MiB free of 24463**, the declared 19125 MiB did not
  clear it, and the swap refused in **0.03 s** having started nothing; with the cortex evicted the
  same call passed and loaded the deep model to `ready` in **69.24 s**, leaving 3579 MiB free. What
  it does **not** detect is recorded as this area's newest entry, and it is the same instrument
  lesson from the other side: a declared figure nobody verified, and a spill that has already
  happened.
- **Notice a handoff that spilled, since a fit check can only see the room beforehand.** Opened
  2026-08-07 by the fit check's own landing
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) fit-check addendum). The check compares the deep
  tier's declared cost against what the card reports free immediately before the load, which is the
  only instant at which free memory means anything. Two things stay invisible to it. A deployment
  that **under-declares** passes the check and spills anyway, because nothing here measures a
  model. And memory taken **during** the load (this machine's idle floor moved between 1529 and
  2836 MiB inside one session, Windows owning the difference) can turn a fit into a spill after the
  check has already answered. In both cases the outcome is the measured one: both tiers report
  `ready`, `nvidia-smi` reads about 23.6 GB used and about 0.5 GB free exactly as a genuine fit
  does, and the deep model decodes at **14.80 to 17.29 tok/s** against **25.07 to 33.28** with the
  card to itself. **The only witness is decode rate, and nothing in the brain watches it.** What
  would close it: the deep phase reading llama.cpp's own `timings.predicted_per_second` off the
  completion it already streams, comparing it against a rate the deployment measured for that tier
  (the same shape as the VRAM figure, and the same honest limitation), and saying so loudly once
  per handoff when it collapses. The cost is a backend that surfaces its own timings, which
  `LlamaCppBackend` today discards, so it is a port question and not a one-line read. **Trigger:**
  any report of a deep phase that is slow rather than absent, on a deployment whose fit check
  passed.
- **Give the placer a model of the handoff window, instead of one that describes the standing
  residency.** *Fix when it bites.* Opened 2026-08-07 by the same landing. `VramBudgetPlacer`
  fit-tests every GPU-placed spawn against `soft_cap_gb - cortex_reservation_gb - placed_gb`
  ([placer.py](../../brain/packages/core/src/cortex_core/placer.py)), and during a handoff both
  named terms are wrong: the cortex whose 11.3 GB is reserved has been evicted, and the deep model
  holding 19 GB of the card is not charged at all, because it is not placed through the placer.
  ADR-0030 decision 8 suspends the soft cap for the handoff window in prose and **nothing in code
  reads it**. This was moot while the pool was drained, since no placement could happen inside the
  window; co-residency is exactly what makes it reachable. It is not a live defect and the reason is
  measured rather than argued: a spawn admitted to a tier that is already resident allocates no new
  VRAM (23639 MiB with both tiers generating against 23642 idle), so the ledger's answer changes
  nothing about the card either way, and its errors are in the safe direction anyway, a refusal
  falling back to the CPU backend. **What would close it:** a placement epoch, meaning the placer
  told which residency it is fit-testing against so the reservation names the model that is actually
  there, which is a `SubagentPlacer` port change plus a writer at the residency scope's two edges.
  Its natural companion is placement-aware charging, declined-as-recorded in
  [resource-governance.md](resource-governance.md) and reopening on the same second GPU-capable
  executor. **Trigger:** a co-resident deployment whose peer tier is started per spawn rather than
  standing (which would allocate), or a second GPU-placed tier, at which point the ledger stops
  being decorative.
  **Closed 2026-08-07**, the same day it opened
  ([ADR-0030](../adr/ADR-0030-brain-handoff.md) handoff-window addendum, with the port half at the
  [ADR-0012 handoff-window addendum](../adr/ADR-0012-resource-governance.md)), taken rather than
  left on its trigger because the trigger is a machine setting, not a code change: any deployment
  that raises `CORTEX_VRAM_SOFT_CAP_GB` far enough to admit a GPU-placed spawn at all reaches it,
  and the entry's own "fix when it bites" was written when nothing could bite. Two of its claims
  were checked against the code first and both held: `place` really does fit-test
  `soft_cap - cortex_reservation - placed`, and the port really did have to change, which this
  area's index warns is the claim entries get wrong. It landed as the placement epoch this text
  proposed, in the shape the text proposed it, and the naming is the only departure: the verbs are
  `charge_handoff(resident_gb=...)` and `charge_standing()` on `SubagentPlacer` (moved to
  `ports_placement.py` for the line cap and re-exported, so no call site moved), written by the
  residency scope at the two edges of the swap
  ([residency_charge.py](../../brain/packages/core/src/cortex_core/residency_charge.py)). What is
  charged is the deployment's declared `CORTEX_SWAP_BRAIN_VRAM_MIB`, converted once through
  `ResidencyPlan.brain_vram_gb`, and **not** a fresh reading through the `device_memory()` verb the
  fit check added, for a reason worth keeping: `place` is synchronous and lock-free by design, so a
  reading there would put an HTTP call to the sidecar inside every spawn's fit-test and would buy
  accuracy the swap has already bought, since the fit check compares that same declared figure
  against the real card at the one instant a reading is evidence. The two therefore compose in one
  direction: the charge is written **before** `swap_in` runs, so it is in force while the check
  reads the card and while the weights load, which closes the gap the check cannot see on its own,
  a spawn admitted into the very room the reading just measured. The reversal waits for the far
  edge and fires only once the cortex is genuinely serving again, so a restore that gave up loudly
  keeps charging the deep model and keeps spawning on the CPU rather than admitting GPU work onto a
  card nobody can describe. **Off unless the deployment declared a figure:** with
  `brain_vram_mib` at its shipped zero the window is never entered, because charging nothing would
  be worse than today, crediting the evicted cortex's 11.3 GB back while the deep model holds the
  card. Measured live rather than argued, through the real sidecar and a real residency change on
  the 24 GB card: 15061 MiB free of 24463 with the cortex resident, 19553 MiB free inside the
  window, the charge 18.68 GiB and the headroom 4.32 GiB against the shipped 5.5 GiB ask, so the
  same spawn lands on the GPU outside the window and on the CPU inside it and on the GPU again
  after the restore (`test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card`, which
  declares the deep tier's measured cost and starts the cheap peer tier in its place, since what a
  19 GB load would add is minutes rather than evidence). **What this does not do**, stated as
  narrowly as the fit check states its own limit: it charges a declared number, so a deployment
  that under-declares is admitted against room it does not have, which is the sibling entry above
  and the same instrument lesson; and a spawn onto an already-resident tier still allocates nothing
  (23639 MiB generating against 23642 idle), so refusing it costs decode speed rather than
  correctness, and the ledger charging per spawn for a standing tier is the older modelling gap
  this entry never claimed to close. Placement-aware charging stays declined-as-recorded in
  [resource-governance.md](resource-governance.md), on the same second-GPU-executor trigger.
- **Resume a crashed handoff from its record, instead of failing it.** Opened 2026-07-17 with the
  brain-handoff conductor sub-slice ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 4),
  which names it as the recorded refinement. Boot recovery marks any handoff a crash interrupted
  `FAILED` and converges the GPU back onto the cortex; it deliberately does **not** re-run the
  deep model's phase, even though the record holds everything needed to (that is the point of the
  record). Replaying it would risk double-running side-effectful work, because nothing carries
  request identity: the tail may contain tool calls whose results were fed back but whose effects
  are not idempotent, and the deep phase's own dispatches would run again. Unlocked by the same
  dedup design the seam-transport reconnect entry needs (a request id plus an
  idempotency/resume registry keyed by it), after which resuming is a small addition to
  `recover_handoffs`: read the record, re-enter the residency scope, and run `BrainPhase` against
  it, which is exactly what the conductor already does. Until then the honest failure is the
  cheaper one, and the user simply asks again.
- **Fence the single-handoff claim across processes.** Opened 2026-07-18 by a verification pass
  over the brain-handoff conductor ([ADR-0030 addendum](../adr/ADR-0030-brain-handoff.md)), which
  found the residual undocumented rather than unknown. The one-GPU-one-handoff rule is
  `SwappingModelManager.handoff_claim`, and it holds `self._handoff_claimed` as instance state, so
  it binds **one process**; the store-side guard ADR-0030 names as the cross-process backstop is
  `active()` read in `SwapConductor._prepare` and the record written two awaits later, a check
  followed by an act rather than a claim, so two brain processes on one Redis could both read "no
  handoff" and both evict the cortex. Not a live defect: the deployment runs exactly one brain
  process (one `brain` service in `docker/docker-compose.yml`, no replicas), so the in-process
  claim is the whole population of claimants, and the loser of either guard is refused before
  anything is drained or evicted and told a handoff is already running rather than that the swap
  broke. **Costs a port change, not a tweak:** `put` cannot express "only if no handoff is active",
  so `HandoffStore` gains a fenced claim verb, implemented in Redis as an atomic `SET
  cortex:handoff:active <id> NX` issued before the record write or as a Lua script (a MULTI/EXEC
  transaction cannot branch on an intermediate reply). It also needs an expiry story, because a
  fenced claim whose holder dies wedges every other process until the key is cleared by hand,
  where a stranded record today is deliberately TTL-free and settled by the next boot recovery: a
  lease (TTL plus a heartbeat) or a user id recovery can recognize. Then the fake carries the
  same semantics, the contract suite gains a two-concurrent-claimants case, and `_prepare` calls
  the claim instead of `active()`. **Trigger:** a second process that can swap (a second brain
  replica, a CLI or worker sharing the Redis, or a supervisor sidecar that swaps itself).
  **Still not met as of 2026-07-18**, now that the supervisor sidecar exists: it performs no swap of
  its own. The brain drives it through the port, its control API can only start, stop and report the
  tiers its own env declares, and it holds no handoff state at all, so it is not a second claimant.
- **Reconverge the brain's residency when the model-host sidecar restarts under it.** *Fix when it
  bites.* Opened 2026-07-18 by the model-host sub-slice, and observed live rather than reasoned
  about: `kill -9` on the supervisor daemon ended its container (both `llama-server` children died
  with it and VRAM returned to baseline), `restart: unless-stopped` revived it, and its boot default
  started the cortex again from a clean slate. That direction reconverges by construction. The other
  one does not. `SwappingModelManager` holds `_resident`, `_scope_model` and `_handoff_claimed` as
  instance attributes ([residency.py](../../brain/packages/core/src/cortex_core/residency.py)), and
  `recover_handoffs` runs **only** at brain startup
  ([wiring.py](../../brain/packages/orchestrator/src/cortex_orchestrator/wiring.py)), so a sidecar
  that restarts mid handoff leaves the brain believing the deep model is resident and holding a
  claim while the fresh sidecar serves the cortex. The turn then fails at the backend (the deep
  tier's endpoint answers nothing), the swap back's `stop`/`start` are idempotent and harmless
  against a sidecar that already did both, and the claim is released in the conductor's `finally`,
  so the failure is honest and self-limiting; what is lost is that one handoff, plus a window where
  `Health` misreports residency. That last half stopped being a prediction on 2026-07-18: the
  honesty-surfaces sub-slice made `Health` answer from the manager's published report, so a brain
  whose beliefs a sidecar restart invalidated now shows an amber dot naming a swap that is not
  happening (or a green one over a GPU that lost its model), until the handoff fails and the scope
  restores. **Nothing is at stake with escalation off** (the default), because the plain
  `SingleResidentModelManager` holds no residency state: a sidecar restart is then invisible to the
  brain, which was confirmed live (a turn answered normally straight after the restart).
  **What would close it:** the daemon exposing a boot id or generation counter on `GET /health`, the
  adapter carrying it, and the manager treating a change in it as "everything I believe about
  residency is stale, converge again" (which is `converge_residency`, already written, called from
  somewhere other than startup). That is a wire addition plus a caller, not a port change. The
  residency state that landed on 2026-07-18 is where the answer would be published, but it did
  **not** close any of this: `ResidencyReport` says what the GPU is serving in one line for a human,
  and carries no generation to compare a boot id against. Its writers are the swap itself and, from
  that day's audit repair, boot recovery publishing what it observed (`publish_boot_residency`),
  which is a *startup* observation and so still leaves nothing that re-reads the machine while the
  process runs. The same landing added two ways for the report to go stale, both with this same
  fix. After a restore that gave up, an operator who brings the cortex back by hand
  (`docs/runbooks/model-swap.md` step 2) leaves the report saying the usual assistant could not be
  reloaded until the brain restarts, which is why that runbook's recovery ends by restarting it.
  And a boot whose recovery could not confirm the cortex publishes `RESIDENCY_BOOT_FAILED`, which
  is honest at the instant it is written and stays amber even if the cortex comes up a minute
  later on its own: deliberately a false amber rather than a false green, and deliberately not
  paid for with a probe per `Health` (the ADR priced that at up to 5.80 s against a 5 s recheck).
  The lease is untouched by that publish, so a machine that is in fact serving still answers turns
  while the dot is wrong.
  **Trigger:** a sidecar that restarts (an OOM kill, a crash, an operator's `docker compose restart
  model-host`) while a handoff is in flight over the supervisor backend, seen more than once.
- **Check the sidecar's stop bounds against the brain's control deadline, instead of only
  documenting the pairing.** *Fix when it bites.* Opened 2026-07-18 by the audit round on the
  model-host sub-slice. A supervisor `stop` answers only once the child is reaped, so it can
  legitimately take `probe_timeout_s + stop_grace_s + reap_timeout_s`, and if that sum reaches the
  brain's `CORTEX_MODELHOST_TIMEOUT_S` the control client times out, `swap_in` raises
  `ModelHostError`, and a handoff whose eviction was working aborts. The shipped defaults are safe
  (5 + 10 + 30 = 45 below 60, all three measured), and the rule is now written in three places
  (the runbook, the compose override's comment, and the `DEFAULT_MODELHOST_TIMEOUT_S` comment), so
  what is deferred is **enforcement**, not the knowledge. It was left unenforced because the two
  sides are separate processes' env and neither can read the other's, which is the reason the
  original landing gave. That reason is now weaker in one direction: `GET /health` reports the two
  stop bounds the daemon was actually given, so the brain **could** read them at wiring time and
  refuse to boot (or log loudly) when its own deadline does not clear their sum plus the probe
  timeout. **What would close it:** the probe timeout on that same body (it belongs to the health
  probe's client rather than to the supervisor, so it needs a small widening of what the daemon
  reports), and a check in `swap_builders.build_control_client` that fails closed exactly as the
  endpoint validator does. The cost is that the brain would then depend on the sidecar answering
  at wiring time, which today it deliberately does not. **Trigger:** a user tuning either side's
  timing, or a second deployment shape where the defaults do not hold, and any report of a handoff
  aborting with `ModelHostError` on an eviction that in fact completed.
- **MTP (multi-token-prediction) model variants.** Deferred until they earn their keep, per
  [ADR-0004](../adr/ADR-0004-model-lineup.md).
- **The cortex reasoning trace is surfaced as a thinking status. This landed 2026-07-06
  ([ADR-0020](../adr/ADR-0020-reasoning-status.md)).** The cortex (gemma-4-12B) emits
  `reasoning_content` before `content` (found during the Slice 6.5 GPU validation), and thinking
  stays on for it; `LlamaCppBackend` used to read only `content`, so a long deliberation streamed
  nothing until it concluded. The chosen option (of disable-thinking / surface / token-budget) is
  **surface**: `ReasoningChunk` joins the `InferenceEvent` union, the shared `stream_tool_loop`
  yields `str | ReasoningDelta` (reasoning ephemeral, never persisted or fed back), and the engine
  maps it to a domain `StatusUpdate(state="thinking", …)` → the wire `ServerEvent.status` the
  proto/body/overlay already carried but the brain never emitted. CI-gated end to end over the
  fakes; **host-validated via Docker (agent, 2026-07-06, [ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):**
  live gemma-4-12B streamed a real reasoning trace surfaced as 326 `StatusUpdate(state="thinking")`
  events, reply clean and persisted==shown (integration test `test_reasoning_model_emits_reasoning_before_reply`).
  **The output guardrail over reasoning status landed 2026-07-12
  ([ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):** the inline chips (see [body-overlay.md](body-overlay.md)) gave the
  thinking status a rendered surface, so a laundered URL in the reasoning trace had a display
  channel the reply-side guardrail never inspected. The trace now streams through its own second
  `OutputFilter` under the same policy and user-URL allowlist (`output_channels.py`, an engine
  line-cap split): a `ThinkingChannel` scrubs each delta (a wholly-carried one emits no status),
  its carry surviving tool steps between thinking bursts so a URL split around a dispatch is
  joined before matching (an adversarial multi-agent review caught the per-burst-flush variant
  letting a fragmented URL cross the seam), released once at end of stream. Redact +
  strict modes and the obfuscation-resistant grammar are inherited; no new config, no seam
  change; reasoning stays ephemeral. Remaining behind the same
  `InferenceBackend`/`TurnCapabilities` seams (ADR-0020 deferred):
  the **disable-thinking / token-budget** alternatives (still available if a runaway trace needs
  capping) and **reasoning persistence/summarization**. The vision slice asked whether an image turn
  is the case that finally needs the disable-thinking half, and the answer measured 2026-08-03 is
  no, with a number attached ([vision.md](vision.md), [ADR-0029 agent-validation
  addendum](../adr/ADR-0029-vision-screen-capture.md)): a picture makes a think near-certain on an
  open-ended ask, 10 of 10 runs against 2 of 5 pixel-less, but nothing truncates, since the shipped
  request sends no `max_tokens` against a server at `n_predict: -1`. What it buys is latency,
  roughly 6 s before the first word on a simple screen and 15 s on a dense one against 1.2 s with
  thinking off, so this
  lever stays fix-when-it-bites and its trigger is a user who minds the wait rather than a truncated
  reply. **It bit hardest on 2026-08-06, on the history recap's fold**
  ([session-history.md](session-history.md), [ADR-0038](../adr/ADR-0038-ranked-recall.md)
  re-measured-behind-the-fence addendum), which is the clearest case for the lever yet and a
  different one from vision: a fold's thinking is not merely unwatched, it is thrown away by
  construction, since `drain_text` keeps `TextChunk` and drops `ReasoningChunk` before the caller
  ever sees it. Measured over three staged sessions, a fold decoded 400 to 850 tokens typically and
  once 6286, for an account of 330 to 650 characters, so the wait is 14.5 s to 30.8 s typically and
  reached 224.5 s, nearly all of it spent generating text nothing reads. The token-budget half is
  wanted here too and for the same reason (`RECAP_MAX` cuts the stored text after the model has
  spoken, so nothing bounds the request), and both together are what a move of
  `CORTEX_HISTORY_SUMMARY` off its default waits on. **Both halves landed the same day
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) cheap-fold addendum), and the port is what carries
  them.** `InferenceBackend.stream` gained `bounds: GenerationBounds | None`, one frozen value
  holding `max_tokens` and `thinking`, which the llama.cpp adapter renders as a `max_tokens` key
  and `chat_template_kwargs: {"enable_thinking": false}`; `None` is the default and emits neither,
  so every user-facing reply sends the byte-identical request it always did. It is per REQUEST
  rather than per server because one resident cortex both answers the user, where the compose file
  deliberately leaves deliberation on, and folds a recap, where it is discarded unread. **The two
  ship as a pair because either alone is worse than neither**, which was measured rather than
  argued: the identical fold prompt at `max_tokens` 160 and 256 with thinking left on came back
  `finish_reason: "length"` carrying 624 and 988 characters of `reasoning_content` and an EMPTY
  reply, and even at the shipped 512 it is a coin flip (one run decoded the whole cap for 92
  unusable characters, another finished thinking in 404 and answered). Paired, the same prompt
  decodes 88 tokens in 3.9 s where the unbounded request decoded 378 to 602 in 13.6 s to 21.5 s,
  for a slightly LONGER account. `--reasoning-budget 0` is still not working on this build, so the
  per-request `chat_template_kwargs` remains the only lever that does. **The two callers that were
  left open took it the same day ([ADR-0038](../adr/ADR-0038-ranked-recall.md)
  bounded-side-calls addendum), so every pass whose thinking `drain_text` discards now says so in
  its request.** `generate_title` sends `TITLE_BOUNDS` (`max_tokens=32, thinking=False`, 32 being
  `TITLE_MAX` in the request's own unit) and `JudgeRecallPolicy.select` sends `rank_bounds(k)`
  (`24 + 8k`, computed rather than fixed because a schema-constrained order's length is known
  before it is asked for). Measured on the shipped cortex: a title went from 235 to 303 decoded
  tokens at 7.9 s to 10.4 s to **4 tokens at 0.2 s to 0.3 s for the same titles**, and a recall
  rank from 448 to 613 tokens at 18.4 s to **12 to 22 tokens at 0.9 s**, its ranking unchanged
  (mean reciprocal rank 1.000 either way, the right note first 6 of 6). Two findings the residue
  did not predict: a JSON schema does **not** protect a constrained reply from a cap (a truncated
  one is not JSON, so it falls back exactly as an unreachable model does), and the trap of a cap
  with thinking left on, a coin flip on the fold, is a certainty on these two, empty three times
  in three at each of 16, 32 and 64 tokens, because their answers are a few tokens and the
  deliberation before them is hundreds. A user-facing reply still keeps its thinking deliberately, which is
  what per-request bounds are for. What the rank's number reopens is its own default, recorded in
  [memory.md](memory.md). **`state`-aware overlay treatment landed
  2026-07-13 ([ADR-0020 third addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now
  keeps the status event's `state` (a new `Message.statusState`) and a `"thinking"` chip renders
  distinctly (a `chip-think` modifier: the reasoning bob on its dot, an accent label, an aria
  label) from a generic status or tool chip, entirely in the CI-gated overlay tree with no seam
  change (the `state` field already rode the wire). A richer collapsed "thoughts" section stays
  open behind the same field. **The collapsed "thoughts" section landed and reasoning
  persistence/summarization was declined on 2026-07-16, both without a seam change ([ADR-0020
  fourth addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now also concatenates every
  scrubbed thinking delta into a new `Message.thoughts`, and the settled reply renders it as a
  collapsed disclosure above the bubble, the chip's retrospective counterpart (`overlayState.ts` +
  `Thoughts.tsx`, gated + browser-validated in both themes; a `<details>` at first, rebuilt on
  2026-07-20 as a button over `Collapse` so the trace rolls open instead of snapping). Persisting or
  summarizing the trace stays **declined for want of a consumer**: nothing reads a stored trace,
  re-display on reload needs a `GetSessionMessages` reasoning field (the read path the open-chat
  title-consistency entry independently needs widened) and the store to grow by the observed
  ~13,882-char single-turn scale, and summarization reverses this ADR's "never fed back" while
  re-raising the non-reentrant GPU-lease sequencing the title generator navigates. It moves to
  this backlog's dead-until-a-consumer list and reopens the day either consumer appears.
