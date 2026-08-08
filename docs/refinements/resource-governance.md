# Resource governance

Deferrals from the Slice 8.5 resource-governance work, whose origin decision is
[ADR-0012](../adr/ADR-0012-resource-governance.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** 5, counted by reading the entries below rather than by adjusting the last number.
The Intel NPU as a third placement target, a bounded admission wait, a read timeout on the subagent
HTTP client, the drain bound against a fired task's lease, and admission reopening onto a tier that
would not restart. The subagent VRAM ask came and went inside two days: the cortex reservation's
re-measurement on 2026-08-07 opened it, having closed nothing this count had ever carried (it had
been deferred at two ADRs and recorded on no index), so the count went 5 to 6 for an arrival with no
matching departure; measuring the tier on 2026-08-08 took it back to 5. Both moves are the honest
shape of that history rather than a bookkeeping slip.

**Resource governance in Slice 8.5 ([ADR-0012](../adr/ADR-0012-resource-governance.md)):** each behind
the unchanged `SubagentPlacer`/`SubagentScheduler`/`ModelManager` ports.
- **`SubagentScheduler.drain()` for a swap landed 2026-07-17 with the brain-handoff drain
  sub-slice ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 4, recorded at the
  [ADR-0012 drain addendum](../adr/ADR-0012-resource-governance.md)).** The entry read: "Quiesce
  the subagent pool (evict → load brain → swap back). An additive method delivered in **Slice
  11**, composed with `release`/`acquire` at the swap orchestrator, never merging the ports."
  It landed exactly there: `drain(*, timeout_s) -> bool` plus its reversal `undrain()` on the
  port, implemented by `ResourceBudgetScheduler` and the new `AdmitAllScheduler` fake under one
  contract suite. The semantics the original one-liner could not carry: entering drain refuses
  every `admit` (typed `SubagentAdmissionError`, `POOL_DRAINING_MSG`) instead of queuing, since
  a brain-phase spawn queued against its own drain would deadlock the turn against its own swap;
  a spawn already waiting on a full budget is woken and refused, not left to sleep through the
  handoff; the wait for in-flight admissions is bounded by the conductor-passed timeout
  (`CORTEX_SWAP_DRAIN_TIMEOUT_S`, default 60 s, arriving with the conductor's wiring) and a
  timeout reports not-clean with nothing killed, so the swap aborts before anything is evicted;
  and the window holds until `undrain`, which the conductor owes in a `finally` on swap-back and
  abort alike. The swap conductor that calls it is the ADR-0030 conductor sub-slice, which
  consumes this verb as landed.
- **CUDA-OOM re-place on CPU landed 2026-07-18 with the model-host sub-slice
  ([ADR-0012 re-place addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "**CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM surfaces as `ok=False`
  today. Auto-recovery (re-issue a CPU-forced request) needs a real GPU to exercise, so it lands in
  **Slice 11** / the host half, not the pure core (simulating it would be vacuous coverage)."
  It landed as one CPU re-run after a GPU-placed failure with the re-place recorded in the result's
  `detail`, which is what ADR-0030's mapping asked for, but **not** keyed on a CUDA OOM: measured on
  the dev GPU, a 14.4 GB model started with `-ngl 99` on the 8 GB card does not fail at all, it
  spills to shared system memory under WSL2 and serves 177 s later, so a branch keyed on an OOM
  would have been unfireable here. The trigger is any GPU-placed attempt whose backend did not
  answer, which is reachable and which also mitigates the sibling entry below (admission reopening
  onto a tier that would not restart: every spawn placed on that tier fails at its backend, and now
  re-runs on the CPU instead of only reporting). The retry does **not** fire on a malformed
  constrained reply (a property of the model, not of where it ran), releases the GPU reservation
  before the re-run so headroom is never misreported to a concurrent spawn, re-uses the same
  admission and dispatch budget so it buys no second charge, and unions the two attempts' taint.
  The entry's own worry about vacuous coverage held up and is answered: the branch is proven by
  behaviour (a failing GPU backend, an answering CPU one) rather than by a simulated OOM, and each
  of its properties reddens a named test under mutation.
- **The real GPU-placed runtime mechanism landed 2026-07-18 with the model-host sub-slice, in a
  different container than this entry expected ([ADR-0012 host-half addendum](../adr/ADR-0012-resource-governance.md),
  [ADR-0030 model-host addendum](../adr/ADR-0030-brain-handoff.md)).**
  The entry read: "**The real GPU-placed runtime mechanism.** Two live `llama-server` sidecars (GPU
  `-ngl 99` + CPU `-ngl 0`) in `docker/docker-compose.subagents.yml` + per-container
  `--cpus`/`--memory` cgroup caps + real GPU-placed-subagent validation lands with the **Slice 11**
  lifecycle behind the corrected ports." Two of the three landed as written and one moved.
  ADR-0030 decision 3 relocated the GPU sidecar into the `model-host` supervisor container (the one
  holding the GPU reservation and the models mount), so the GPU-placed subagent is a **hosted tier**
  on :8083 with `-ngl 99`, opt-in behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`, rather than a second
  service in the subagents override; the CPU `-ngl 0` sidecar stays its own container as described.
  **The tier is not what `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at by default, and saying it was
  is the one wrong claim this entry shipped with (corrected 2026-07-18).** That variable still
  defaults to the CPU server (`docker-compose.subagents.yml`), which is the safe default, since a
  deployment that has not named a GPU subagent artifact would otherwise route GPU-placed spawns at
  a tier that answers nothing. Opting in is therefore three settings together, now written in the
  gpu override's own checklist and in [subagents-cpu.md](../runbooks/subagents-cpu.md): the
  artifact file, `CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`, and the tier's id in
  `CORTEX_SWAP_EVICT_MODELS` so a handoff stops it first. The caps landed on both containers
  (`cpus`/`mem_limit`/`memswap_limit`, verified applied by the runtime as `NanoCpus`/`Memory`/
  `MemorySwap`), with the CPU one's defaults set to the hard twin of the brain's soft admission
  budgets, which is what makes those budgets more than an honour system. **The granularity this
  costs is the interpretation to know about:** the cortex, the deep model and the GPU subagent are
  now processes in ONE cgroup, so no per-model CPU or RAM cap exists, only one cap set covering all
  three. ADR-0030 wins as the later and more specific decision, and its security argument is what
  buys it (a per-model cap would want a container per model, which is a controller that can start
  containers, which is the docker-socket shape decision 3 rejected). The numbers themselves are
  user-tunable placeholders: the 8 GB dev GPU cannot hold a real tier pair, so what was validated
  here is the mechanism, not the arithmetic. Real GPU-placed-**subagent** validation is the one
  piece still owed, and it is host-side for the same reason: a GPU-placed subagent only happens
  when `CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap minus the resident cortex, which needs a
  card that holds the cortex first. Consequently the `VramBudgetPlacer`'s GPU arm has never fired
  against a real placement: with the shipped settings every spawn overflows to CPU.
  **Index corrected 2026-07-19.** That bucket line read "Nothing of this area's trio remains here",
  true of the trio's *entries* and misleading about the area, since it read as if nothing at all
  were owed. It now names both halves of what is left, the subagent validation and the placeholder
  cap numbers, as host-side hardware work rather than deferred design, which is why neither is
  counted in this area's open items. **Both moved to
  [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md) the same day**, with the sentences
  above kept verbatim there; the cap numbers arrived carrying the mmap trap ADR-0012 records,
  which is that a cap below the artifact size makes a load thrash rather than fail.
  **The reason above is wrong in its second half, and half of that validation comes back here
  (2026-07-19).** "Which needs a card that holds the cortex first" says the dev GPU does not hold
  the cortex, and it does:
  [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured `gemma-4-12b-it-qat-q4_0.gguf`
  resident with its vision projector at `-ngl 99 --ctx-size 4096 --parallel 1`, and
  [ADR-0030](../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
  8188 MiB.
  What the card cannot do is hold anything *beside* that cortex, roughly 470 MiB of headroom
  against a multi-GB subagent, so a GPU placement **beside a resident cortex**, which is the
  arithmetic ADR-0012 cares about, stays host-side and stays item 6 of
  [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md). The **mechanism** does not need a
  resident cortex at all: with no cortex up, the budget sized to this card
  (`CORTEX_VRAM_SOFT_CAP_GB`, `CORTEX_VRAM_CORTEX_GB`, `CORTEX_SUBAGENTS_VRAM_GB` are all env), a
  small artifact in `CORTEX_MODEL_FILE_SUBAGENT_GPU` and `CORTEX_SUBAGENTS_GPU_ENDPOINT` pointed at
  the sidecar's `:8083`, the `VramBudgetPlacer`'s GPU arm can fire against a real placement here and
  the route from a GPU verdict to an `-ngl 99` tier can be exercised end to end. That is the same
  mechanism-versus-tier-scale split the swap already uses, it is agent-side under the rule that "on
  the host" includes the agent, and it is **actionable now** rather than host work. Nobody has run
  it: the GPU arm has still never fired against a real placement, which is exactly why the split
  matters.
  **It ran on 2026-08-04 and the GPU arm has now fired ([ADR-0012 GPU-arm
  addendum](../adr/ADR-0012-resource-governance.md), procedure in
  [subagents-cpu.md](../runbooks/subagents-cpu.md)).** The stack was the base plus the gpu,
  subagents and modelhost-loopback overrides, with the E4B subagent pick hosted twice: as the
  sidecar's `-ngl 99` tier on `:8083` (reachable at `127.0.0.1:9083`, since the sidecar's tiers are
  otherwise unpublished) and as the subagents override's `-ngl 0` CPU server on `:8082`. Both arms
  are witnessed by a new integration suite,
  `brain/packages/orchestrator/tests/test_subagent_gpu_live.py`, which reads the three env values
  through the same settings classes the composition root reads and records which backend each spawn
  was handed. With the soft cap raised to 20 GB for the card the repo is developed on (headroom
  8.7 GB against the shipped 5.5 GB ask), two concurrent spawns of one roster entry landed **one on
  the GPU tier and one on the CPU server**, which is the ledger doing its job rather than a
  coincidence of two servers: the tier's own `llama-server` log carries exactly one task, 18 prompt
  tokens at 104.83 tok/s and 4 generated at 81.07 tok/s for 221.05 ms in total, against 12536.83 ms
  for the sibling that overflowed. With the shipped soft cap of 14 GB (headroom 2.7 GB, under the
  same ask) both spawns overflowed and the tier's task count did not move, so the arm is proven able
  to stay silent as well as to fire. **The sentence above is therefore false as of that date and is
  kept as the record**; what is left of this entry's host half is the cap numbers.
  **The suite was proved able to fail before it was trusted.** The same budget with the GPU endpoint
  pointed at a closed port reddens on a third placement, because a GPU-placed attempt whose backend
  did not answer re-runs once on the CPU, which is also the first time the re-place two bullets up
  has fired from a real GPU placement rather than from a failing fake.
  **The host half went with it, because the run kept the cortex resident (2026-08-04).** The
  placement beside a resident cortex that this entry sent to item 6 of
  [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md) is what a GPU arm firing on that stack
  is, so that item closed the same day with its numbers at the
  [ADR-0012 fit addendum](../adr/ADR-0012-resource-governance.md). Its finding is about this
  entry's own numbers: the card holds both tiers with 11110 MiB free and the pair costs 14.00 GB of
  `nvidia-smi` total used, which is the deliberate soft cap, while the placeholders inside it claim
  16.8 GB for the same pair (a cortex reservation 0.8 GB high and a subagent ask 2 GB high). So the
  reason no spawn was ever GPU-placed is the arithmetic, and the lever is the cap, which is a user
  policy value rather than a placer question. What is still owed of this bullet is the cgroup cap
  numbers alone.
- **Placement-aware CPU charging closed 2026-07-16 as declined, wrong premise and no gain
  ([ADR-0012 admission-wall addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "`admit` charges every spawn its full `cpus`/`memory_gb` regardless of placement (conservative);
  charging GPU-placed subagents less is a tweak behind the same port." It is not behind that port.
  `admit(request)` takes a `PlacementRequest`, which carries no placement, and `SubagentRunner.run`
  enters admission *before* it places, by ADR-0012 decision 5, so the charge cannot know the target.
  Making it placement-aware needs a port change (a target argument, or an `admit` yielding a
  re-chargeable handle) or the admit/place inversion decision 5 exists to prevent, where a
  GPU-placed spawn queuing for a CPU slot holds reserved VRAM while it waits. The discount would
  also buy nothing: each roster entry holds one `LlamaCppBackend` per target and a backend holds its
  model lease for the whole stream, so same-entry spawns serialize there whatever the budget admits
  (measured live on the Qwen-2B override: two concurrent spawns took 4.8 s through two backend
  objects, 10.0 s through one, a ratio of 2.08). And there is nothing to discount today, since
  `CORTEX_SUBAGENTS_VRAM_GB=5.5` sits deliberately above the GPU headroom, so every spawn overflows
  to CPU. **Reopens** with a second GPU-capable executor, as a port change rather than a tweak.
  **The GPU-placed runtime arrived on 2026-07-18 and did not reopen it**, which is worth stating
  because this entry used to name that runtime as the condition. One hosted GPU subagent tier is
  still one `LlamaCppBackend` per target per roster entry, so the measured serialization above is
  unchanged and the discount would still buy nothing; and the shipped `CORTEX_SUBAGENTS_VRAM_GB=5.5`
  still sits above the headroom, so there is still nothing to discount. What would reopen it is what
  ADR-0030 decision 8's addendum already says: a **second** GPU-capable executor, so that two
  GPU-placed spawns can actually run at once and a placement-aware charge changes how many are
  admitted.
  **One sentence above went false on 2026-08-08 and the conclusion did not.** The ask was measured
  and is now 3.5 GiB against 5.4 GiB of headroom, so a spawn really is GPU-placed and "there is
  nothing to discount today" no longer describes the shipped stack. What still declines the entry is
  the other half, which the measurement did not touch: one `LlamaCppBackend` per target per roster
  entry still serializes same-entry spawns whatever the budget admits, and the headroom holds one
  spawn anyway, so a discount would change nothing about how many run.
- **The cortex reservation landed 2026-08-07 as a re-measurement, and it had never been an entry
  here.** Where it lived was two ADRs and no index: [ADR-0004](../adr/ADR-0004-model-lineup.md)'s
  swap-latency note 8, which saw the cortex read about 9.7 GB against its own 11.0 and asked a later
  sitting to confirm which figure the deployment pays, and
  [ADR-0030](../adr/ADR-0030-brain-handoff.md)'s co-residency addendum, which measured 8448 to 8468
  MiB and deliberately left `CORTEX_VRAM_CORTEX_GB=11.3` alone because lowering it widens what the
  placer admits and that is this area's decision rather than the handoff's. Both were right to
  defer and neither wrote a line anywhere that counts open work, so an item that bounded every
  spawn's fit-test sat outside every count for three days. That is the doc-first rule's own failure
  mode, recorded here plainly rather than quietly fixed.
  **What the re-measurement found.** The published 8448 to 8468 was an idle figure and a reservation
  has to cover a peak, which is why this was never a one-line edit. At the shipped tier shape, read
  out of the running child's argv (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja` with the projector
  and `--image-max-tokens 1024`), the tier is **8400 to 8484 MiB idle and 8573 MiB at its peak**
  above a floor read with the tier stopped at both ends of the session (1261 to 1301, then 1259 to
  1308 MiB, agreeing within 7 MiB, so nothing of the desktop's own drift is folded in). A 13180-token
  prompt with 924 tokens decoded allocated **nothing**, llama.cpp taking the 16K KV and the compute
  buffers at load; the only thing that arrives with the work is the vision path's 70 to 90 MiB on the
  first image, and it stays. And most of the apparent 2.8 GB gap was a unit: the 11.3 was
  `nvidia-smi` total used with the desktop's floor inside it, while every other term in this budget
  is a tier's own cost. **The reservation is 8.6 GiB**, 233 MiB over the measured peak, which covers
  the sampler's in-phase spread, the floor bracket and one more vision-sized allocation. The
  headroom goes from 2.7 to 5.4 GiB, so a spawn declared at the GPU tier's measured 3319 MiB is
  GPU-placed where nothing ever was ([ADR-0012](../adr/ADR-0012-resource-governance.md)
  re-measured-reservation addendum, procedure in
  [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)). One entry opens in its place, below,
  and it is the term the re-measurement deliberately did not touch.
- **The shipped subagent VRAM ask is a placeholder about 2.3 GiB above what the tier measures.**
  *Fix when it bites, and it bites the moment a deployment wants GPU subagents.*
  `docker-compose.subagents.yml` sets `CORTEX_SUBAGENTS_VRAM_GB=5.5` and the code default is 2.0,
  neither of them measured; the GPU-placed subagent tier read **3319 MiB** on this card on
  2026-08-04, which is 3.24 GiB. With the reservation corrected the headroom is 5.4 GiB, so the ask
  is now the only reason the shipped stack still refuses every GPU placement, where before it was
  one of two. The reservation was **not** rounded down to 8.5 to make 5.5 fit, which would have
  been choosing the answer and would have left two wrong numbers agreeing; the ask is the wrong
  number and it should be corrected by measuring one spawn of the roster's default entry rather
  than by arithmetic. It is a compose default plus a `SubagentsConfig` field, so nothing behind a
  port has to move, and the same sitting should decide whether the roster's alternate entry needs
  its own figure. Pinned by a test today
  (`test_shipped_vram_budget_still_refuses_the_compose_placeholder_ask`), so a later change to the
  reservation cannot quietly flip the shipped stack into GPU placement without answering this.
  **Closed 2026-08-08 by measuring the tier, one day after it opened
  ([ADR-0012 measured-ask addendum](../adr/ADR-0012-resource-governance.md), procedure in
  [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) section 2c).** The ask is **3.5 GiB**
  in both declarations, the compose default and the `SubagentsConfig` field. Measured at the shape
  read out of the running child's argv (`-ngl 99 --ctx-size 8192 --parallel 2 --jinja` with
  thinking off, no projector), with the cortex resident throughout and `nvidia-smi` total used
  sampled every 0.2 s, the tier is 3228 to 3355 MiB idle and costs at most **3410 MiB** above a
  floor read with it stopped at both ends of the session (10448 to 10500, then 10428 to 10493 MiB,
  agreeing within 20 MiB). Twelve requests each filling its slot's whole half of the 8192 KV
  (3803 prompt tokens plus 293 decoded, exactly 4096) moved nothing beyond the idle band: this tier
  has no vision path, so unlike the cortex the peak is a load-time figure with no late allocation at
  all. The margin is 174 MiB, which covers the sampler's spread and the floor bracket twice over.
  **The entry's own account was right about one placeholder and wrong about the other**, which is
  worth stating because it was the safe-sounding one: 5.5 was about 2.1 GiB high as recorded, but
  the code default of 2.0 was about 1.3 GiB **low**, so a deployment wiring subagents without the
  compose file was admitting a spawn onto room the tier would overrun, the unsafe direction, while
  the docs called it a GPU-less-safe placeholder. **The alternate needed no figure of its own**,
  which this entry asked the same sitting to decide: no GPU executor exists for the roster's
  alternate at all (its `gpu_endpoint` falls back to its own CPU server), so its 2.5 charges a
  ledger for a placement that always runs on the CPU, and that is the interim one-executor stance
  rather than a measurement anybody could take today. What replaces the old pin is a pair of tests
  reading the deployment's own numbers rather than literals: one places the shipped ask and its
  successor (GPU then CPU), the other holds the margin above the measured peak. Proven on the stack
  and not only in the gate: under the old ask the live GPU arm could not select itself (5.5 against
  5.4 GiB of headroom) and the tier served no task; under 3.5 the same command places one spawn
  there, answered in 152.11 ms against 13134.73 ms for the sibling that overflowed, and the arm was
  shown able to redden first by pointing the GPU endpoint at a closed port. **What is not fixed is
  what the ask means for the second spawn:** the ledger charges one tier's whole footprint per
  spawn, and a second spawn onto that standing process allocates nothing, so refusing it buys decode
  speed rather than memory. That is the modelling gap recorded in
  [inference-model-manager.md](inference-model-manager.md), unchanged here and now the honest
  reading of the refusal.
- **The Intel NPU as a third placement target.** A future OpenVINO `InferenceBackend` adapter + a
  `PlacementTarget.NPU`, pending a feasibility pass. Using the otherwise-idle NPU for tiny
  subagents or embeddings serves the same "keep the machine usable" motivation as the caps above,
  and OpenVINO GenAI is the engine because llama.cpp has no NPU path. The hardware is **present**
  (an Intel Core Ultra 9 275HX, confirmed 2026-07-01), so two unknowns decide it: (a) whether the
  NPU is reachable from the dockerized WSL2 brain at all, the likely blocker, since WSL2
  paravirtualizes the dGPU but not the NPU, so it may force a host-side runtime that crosses the
  dockerized-brain seam; and (b) whether NPU inference for a 2-4B model is fast and mature enough
  to be worth a target. **The two unknowns and the hardware confirmation moved here from the
  ROADMAP's Slice 8.5 block on 2026-07-19**, where they were the only record of either; the
  deferral itself has been recorded here and at its origin ADR since the extraction.
- **A hard budget wall closed 2026-07-16: the wall existed and now refuses as a value
  ([ADR-0012 admission-wall addendum](../adr/ADR-0012-resource-governance.md)).** The entry read:
  "The CPU/RAM budget bounds only what the scheduler *admits* (soft, admission-only, a deliberate
  tradeoff per ADR-0012 risks); hard enforcement remains a refinement behind the same
  `SubagentScheduler` port." Two corrections. **That reading is impossible behind that port:** hard
  enforcement over processes the scheduler never admitted is a cgroup/`.wslconfig` capability the
  user's ADR-0012 constraint rules out, and a port that only sees admissions cannot supply it.
  **At ADR-0012 decision 4's own reading** (refuse instead of queue) a wall already existed: a
  charge larger than the whole budget raised rather than waiting forever. Its *boundary behaviour*
  was the defect. The bare `ValueError` escaped `SubagentRunner.run`, `SpawnSubagentsTool`'s
  `gather` (discarding every sibling's answer), and `ToolDispatcher`, which catches only
  `ToolError`, reaching `converse.py`'s broad turn handler, which failed the turn with
  `ERROR_CODE_INTERNAL` and left the whole `Converse` stream refusing further turns; and
  `SubagentsConfig` never checked an ask against the budget, so env alone could reach that state.
  What landed: the typed `SubagentAdmissionError` on the port, caught by the runner and
  degraded to an `ok=False` "refused before running" `SubagentResult`, plus a boot-time config
  check that no roster entry asks more than the whole budget. A transient full budget still
  **queues**, deliberately: the work runs seconds later, depth-1 drains the queue, and a waiting
  spawn holds none of the budget, so refusing it saves nothing. Also noted: with respect to what it
  charges the budget was already hard; "soft" only ever meant that it binds nothing it did not
  admit. Behind it, two new entries below.
- **A bounded admission wait.** *Fix when it bites.* Admission waits with no timeout and no
  queue-depth bound. Depth-1 guarantees the queue drains while admitted runs terminate, and
  `MAX_SPAWN_BATCH` bounds one call, so nothing is unbounded in practice today. The trigger is a
  real deployment showing a turn stalled in admission long enough to matter; the fix is a timeout
  design over a `Clock`, refusing with the same typed error, not a policy flip.
- **The drain bound is shorter than a fired task's lease, so a task in flight aborts a handoff.**
  *Fix when it bites.* Opened 2026-07-17 by the brain-handoff conductor sub-slice, which wired
  `CORTEX_SWAP_DRAIN_TIMEOUT_S` (default 60 s) as the bound on quiescing the pool before anything
  is evicted. A ticker-fired task holds its admission for up to the schedule lease
  (`CORTEX_SCHEDULE_LEASE_S`, default 300 s), so a handoff requested while one is running drains
  to a timeout and correctly aborts before evicting anything: the user is told, the cortex keeps
  serving, and nothing is lost. That is the designed direction, but with the shipped defaults it
  makes an escalation during a scheduled task systematically impossible rather than occasionally
  unlucky. The knobs already exist (raise the drain bound above the lease, or lower the lease), so
  the fix is a defaults decision informed by real usage, not a design change; the trigger is a
  deployment where scheduled work and escalation collide often enough to notice. Killing a
  subagent mid-stream to make the drain succeed stays refused (v1 never does).
- **Admission reopens even onto a tier the swap back could not restart.** *Fix when it bites.*
  Opened 2026-07-18 by the pass that made the drain window wait for the standing residency, and
  recorded at the [ADR-0030 reopening addendum](../adr/ADR-0030-brain-handoff.md), that ADR owning
  both halves that create it (the best-effort tier restart and the reopening that follows the
  restore) while this port stays unchanged. The
  window now lifts only after the residency scope has restored the cortex and restarted every
  `evict_models` tier, and every reopening is witnessed against what was actually running. But
  the tier restart is deliberately best effort ([ADR-0030](../adr/ADR-0030-brain-handoff.md)
  decision 4: a tier that will not come back must not be reported as the cortex being gone), so a
  `ModelHostError` on that start is logged and swallowed, and `undrain` then reopens admission
  onto a subagent server that is not running. The next delegated run fails at its backend and
  degrades to an `ok=False` result, which is honest but wasteful, and nothing retries the tier
  until the next handoff or a restart. **Reachable by configuration since 2026-07-18**, which
  replaces this entry's original "nothing is at stake today, `CORTEX_SWAP_EVICT_MODELS` is empty
  until the real lifecycle sub-slice, so no tier is ever evicted": that sub-slice has landed, so a
  deployment that names a GPU subagent artifact and lists that tier in `CORTEX_SWAP_EVICT_MODELS`
  now really does evict it and can really see it refuse to come back. It stays unreachable in the
  **shipped defaults** (both of those are empty), and its cost fell in the same sub-slice: a spawn
  placed on a tier that did not restart now re-runs once on the CPU rather than only reporting, so
  what is left is a wasted GPU attempt per spawn instead of a lost one. Still recorded rather than
  built, for the same reason. The fix wants a residency
  state that knows a tier is down, so the placer skips it while something retries the start,
  rather than a scheduler change, which is why it is recorded
  here and not built: keeping the pool drained instead would be worse, since it would trade every
  delegated run for the ones that would have been placed on that one tier.
  **The honesty-surfaces sub-slice landed on 2026-07-18 and did NOT clear this**, which this entry
  used to imply it would. What that sub-slice introduced is one published `ResidencyReport` about
  what the GPU is serving, for the seam's `Health` to answer with (`residency_state.py`), and it is
  deliberately narrow: it carries no per-tier state at all, so there is still nothing for a placer
  to read. Widening it is the same shape of change it always was, now with a place to put it.
- **A read timeout on the subagent HTTP client.** *Fix when it bites.* The actual unbounded-wait
  hazard under the admission budget: `build_subagents` builds
  `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one wedged `llama-server` stream holds
  its admission forever and every queued peer waits behind it. `read=None` is deliberate (a
  generation may legitimately stream for minutes on CPU), so the fix is a generous per-stream
  ceiling, not a short one, and it belongs to the inference adapter (ADR-0005), not the scheduler.
