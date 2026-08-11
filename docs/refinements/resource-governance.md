# Resource governance

Deferrals from the Slice 8.5 resource-governance work, whose origin decision is
[ADR-0012](../adr/ADR-0012-resource-governance.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** 7, counted by reading the entries below rather than by adjusting the last number.
The Intel NPU as a third placement target, a queue-depth bound,
two of the three the tier-outage close opened (a retry
that only asks about tiers it already believes are missing, and a placer holding one bit for the
card where the record holds one entry per tier), the two the total generation cap opened as it
closed (a finish reason the port does not carry, so a capped completion looks like a finished one,
and the whole-subtask figure two derivations rest on being out by a factor of two), and the brain
learning at boot that escalation cannot work and then forgetting it. The count held at 7 later on
2026-08-11 when **the deep model's clearing deciding the cortex's verdict at boot** landed ahead of
its trigger, one out and one in: the port has the narrower failure that entry asked for, an
unrostered deep tier is a green boot and a loud line rather than an amber dot, and what takes its
place is the fact that nothing remembers the line was ever logged, so each escalation still stalls
the assistant to discover the same 404. The same close found the entry had understated itself, the
swap back having met that 404 too and lost the cortex to it, which is a defect rather than a
deferral and is therefore fixed in the same pass and recorded at the ADR instead of here. The count
went 6 to 7 earlier
on 2026-08-11 when **the total generation cap** landed ahead of its trigger, one out and two in,
which is the same shape the tier-outage close had: what replaces it are the two questions building
it made askable, one of them a port change this fix deliberately did not need and the other a
number this fix's own measurements are the first to contradict. The count went 7 to 6 earlier, on
2026-08-09, when **the drain bound against
a fired task's lease** closed as declined, with nothing landing in its place: traced to the code
ahead of the usage it asked for, the drain waits on an in-flight admission and never on a lease,
so its stated mechanism was a comparison between two numbers that never meet and the abort it
called systematic is merely likely. A decline is a departure like any other here, which is why
this is the first move in this file's history that lowers the number without an arrival.
**The number held at 7 earlier on 2026-08-09 and the set did not, and this
line was not corrected with it**, which is the failure the index's third warning describes, caught
by re-reading the entries rather than the arithmetic: the third of that trio, boot recovery calling
a peer tier's failure the cortex being gone, landed hours after it opened and ahead of its own
trigger, and the deep tier's own clearing took its place, so for a stretch this line named an
entry that was closed and missed one that was open while the total stayed right. The count went 5
to 7 on 2026-08-09 when **admission reopening onto a tier that would not restart** landed ahead of
its trigger, one out and three in, which is this backlog
working as intended rather than a close that failed to close: the record it wanted is built, and
what replaces it are the three questions building it made askable for the first time (where else
an outage can come from, how finely the placer can skip, and which of the two boot verdicts a peer
belongs to). Twice earlier the same day the number was unmoved and the set was not: the read
timeout on the subagent
HTTP client landed 2026-08-09 and opened the total generation cap in the same pass, and hours later
the bounded admission wait landed and opened the queue-depth bound it declined, one out and one in
each time, which is the shape this file's own warning is about (a count that agrees with its header
proves nobody miscounted and nothing else). Before that, the subagent VRAM ask came and went inside
two days: the cortex reservation's re-measurement on 2026-08-07 opened it, having closed nothing
this count had ever carried (it had been deferred at two ADRs and recorded on no index), so the
count went 5 to 6 for an arrival with no matching departure; measuring the tier on 2026-08-08 took
it back to 5. All eight moves are the honest shape of that history rather than a bookkeeping slip.
This sentence read six until 2026-08-10 and seven until 2026-08-11: each time a move was prepended
at the head of this paragraph the tally under it was left where it was, which is the same omission
one paragraph up describes and the reason a summary of a running record has to be re-read whenever
the record grows. It is counted here by reading the moves above rather than by adding one.

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
  entry caps same-entry overlap at two lock objects whatever the budget admits, and the headroom
  holds one GPU spawn anyway, so a discount would change nothing about how many run. (That cap
  read as plain serialization until 2026-08-09, when the admission bound's arithmetic was corrected
  against this same measurement.)
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
- **A bounded admission wait landed 2026-08-09, ahead of its trigger and half of it declined
  ([ADR-0012 bounded-admission-wait addendum](../adr/ADR-0012-resource-governance.md)).** The entry
  read: "*Fix when it bites.* Admission waits with no timeout and no
  queue-depth bound. Depth-1 guarantees the queue drains while admitted runs terminate, and
  `MAX_SPAWN_BATCH` bounds one call, so nothing is unbounded in practice today. The trigger is a
  real deployment showing a turn stalled in admission long enough to matter; the fix is a timeout
  design over a `Clock`, refusing with the same typed error, not a policy flip."
  `ResourceBudgetScheduler.admit` now refuses after `wait_timeout_s` seconds with the same typed
  `SubagentAdmissionError` the runner already degrades to an `ok=False` result, wired from
  `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 3600 s, zero meaning never queue). Four things
  about it, two of them corrections to this entry's own text.
  **"Nothing is unbounded in practice today" was the false half**, and the read-timeout entry
  below said why without either of them noticing: a wedged `llama-server` stream held its
  admission forever, so the queue behind it never moved, and depth-1 plus `MAX_SPAWN_BATCH` bound
  how *many* wait rather than how *long*. That sibling landed hours earlier the same day, which is
  what let this one close ahead of its trigger: with a stall now bounded on both generation
  clients, the remaining ways for a queue to stop moving are a runaway generation (the entry at
  the bottom of this file) and nothing else anybody has named, so leaving the wait itself
  unbounded had stopped being defensible.
  **The port really was unchanged, and this time it was checked rather than claimed.** This area's
  header asserts that blanket over all three ports and the index's standing warning names the pair
  where it broke, so the signature was opened first:
  `admit(request) -> AbstractAsyncContextManager[None]` carries nowhere to put a per-spawn bound
  and needs none, because the bound is policy the budget owns, exactly like the two numbers already
  on that constructor. What the port gained is a sentence of contract, that an implementation which
  queues owes a bound on that queue and the same typed refusal when it elapses; `AdmitAllScheduler`
  satisfies it vacuously, having no queue, so the drain contract suite needed no new case and the
  twin is untouched.
  **"A timeout design over a `Clock`" is the other correction.** The bound is `asyncio.timeout`
  around the wait loop, the mechanism `drain` already uses on this very condition object, for three
  reasons the addendum argues: a duration belongs on the loop's monotonic clock rather than on the
  wall clock `Clock.now()` reads, the `Clock`/`Sleeper` pair exists for poll loops that would
  otherwise force real-time tests (this is a bounded wait on an event, whose timeout path an
  already-expired bound drives in microseconds), and one class should not bound its two waits two
  different ways. A `Clock` here would have been a decoration.
  **The number is derived, not felt**, which matters because a bound that refuses a legitimately
  queued spawn is worse than the unbounded wait it replaces: `MAX_SPAWN_BATCH` is 8, the shipped
  budget admits two at a time, and one entry holds a backend, and so a model lease, per placement
  target (4.8 s through two backend objects against 10.0 s through one), so the admitted pair
  overlaps while one spawn is GPU-placed and the other overflows and serializes only while both
  land on the same target. A whole CPU subtask measures 200 to 300 s, so the last of a full batch
  is admitted about **900 s** in while the pair overlaps and about **1800 s** in while it
  serializes, and the bound is twice the serial figure, which makes it an upper bound over both
  rather than an equality on either.
  **That premise was corrected on the day the bound landed.** The derivation first read the backend
  lock as unconditional, which the roster measurement recorded the day before had already ruled out
  for an entry that omits `gpu_endpoint`: two lock objects front one server, so its spawns overlap
  two ways. The number did not move, a closed GPU tier still leaving the serial case, but the claim
  did, from an equality to a bound four times the wait the shipped stack produces. Said plainly
  rather than left to be found: two full batches queued at once lose their tail to the bound while
  the entry serializes and clear it while the pair overlaps, and the first is the deployment that
  should raise the knob. **The queue-depth half did not ship** and is the entry below.
  **The correction needed a second pass the same day, because the first one under-reported its own
  reach.** It named the comment, the test, two documents and this entry, and four further sites
  went on restating the equality in the present tense: the operator guidance in
  [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md), the same knob's comment in
  `docker/docker-compose.subagents.yml`, the contract sentence in
  [modules/brain-orchestrator.md](../modules/brain-orchestrator.md) that its twin in
  `brain-core.md` had already been fixed against, and the row for this area in the
  [index](index.md). The runbook was the one that mattered, being where an operator sizes the
  knob: it asserted 1800 s for the shipped budgets, cited the corrected addendum for the premise
  that addendum now denies, and told a reader that queuing two batches at once needs the bound
  raised, which is false wherever the pair overlaps (2100 s clears 3600 s) and true only where a
  closed GPU tier or an ask that never fits leaves both spawns on one target (4200 s). Both boxes
  in that runbook now scope the serialization to a shared target and name the overlap as capped at
  two rather than absent, and the advice names the placement it applies to. The lesson is the
  cheap one: a correction's scope claim is itself a claim, and grepping the mechanism ("serialize",
  "one backend") alongside the numbers is what finds the copies that paraphrase instead of quote.
- **A queue-depth bound, to refuse a hopeless queue early rather than an hour late.** *Fix when it
  bites.* Opened 2026-08-09 by the close above, which shipped one of the two refusals that entry
  asked for. They answer different questions: the wait bound refuses **late**, after the caller has
  already paid the hour, while a depth bound refuses **early**, when the queue is already provably
  longer than the budget can drain. Only the wait bound is derivable today, because the scheduler
  holds charges and no durations: it knows a waiter asks for 2.0 cpus and has no idea whether that
  is thirty seconds of work or five minutes, so five waiters asking 0.5 each and five asking 2.0
  look identical to it and any depth number is a guess where the wait number is arithmetic over
  measurements. What that leaves open is a spawn joining an already hopeless queue and paying the
  whole bound before it is told, with `MAX_SPAWN_BATCH` and depth-1 still the only things bounding
  how long the queue can get. The trigger is the first deployment observed hitting the wait bound,
  which is also the first one with a measured drain rate to derive a depth from; the fix is a
  waiter count in `ResourceBudgetScheduler` and the same typed refusal, behind the same unchanged
  port for the same reason the wait bound was (the number is the budget's policy, not a per-spawn
  ask), which is a claim the close above establishes by having opened the signature rather than
  one this entry is asserting fresh.
- **The drain bound against a fired task's lease closed 2026-08-09 as declined, wrong premise and
  no free move ([ADR-0030 drain-bound addendum](../adr/ADR-0030-brain-handoff.md)).** The entry
  read: "`CORTEX_SWAP_DRAIN_TIMEOUT_S` (default 60 s) bounds quiescing the pool before anything is
  evicted. A ticker-fired task holds its admission for up to the schedule lease
  (`CORTEX_SCHEDULE_LEASE_S`, default 300 s), so a handoff requested while one is running drains
  to a timeout and correctly aborts before evicting anything. That is the designed direction, but
  with the shipped defaults it makes an escalation during a scheduled task systematically
  impossible rather than occasionally unlucky. The knobs already exist (raise the drain bound
  above the lease, or lower the lease), so the fix is a defaults decision informed by real usage."
  **The comparison reads a ceiling as a duration.** `drain` waits on one condition,
  `while self._in_flight > 0` under `asyncio.timeout(timeout_s)`, and `_in_flight` is moved only by
  `admit`, which `SubagentRunner.run` holds around the whole subagent run. So a drain waits out the
  remaining runtime of admitted runs and never a lease. The two do meet on one path, a ticker fired
  task reaching that same admission through `spawn_subagents`, which is why the entry reads as
  plausible; what it gets wrong is which quantity the lease names. The lease is the store's claim
  fence and, in `ScheduleTicker.run_once`, the `asyncio.wait_for` cap that cancels a wedged fire: a
  **ceiling** on the hold, not its duration. Comparing 60 s to 300 s compares a wait bound to a
  cancellation cap, and neither decides the outcome.
  **What decides it is a measurement, and the honest word is "usually".** A whole CPU subtask is
  200 to 300 s, so a drain meeting one in flight clears it only when 60 s or less remains: roughly
  a quarter of arrivals for a single run, fewer for an admitted pair whose releases stagger. Likely,
  not systematic, which is the word the entry used. The framing was narrow too: an interactive spawn
  holds the same admission with no lease at all, and since nothing caps a generation's length (the total
  generation cap below) and the 600 s ceiling bounds only the gap between chunks, its hold has no upper bound
  at all, so the collision is drain against delegated work of any origin.
  **Both proposed knob moves are refused.** Lowering the lease under the drain bound makes drains
  succeed by cancelling every fire before its own subtask can finish, breaking the feature to
  protect the handoff. Raising the drain bound over the lease covers fires and not interactive
  spawns, and no finite value makes the drain reliable while a generation's length is uncapped; the
  smallest that even covers a wedge sits above the 600 s ceiling, which is exactly the "do not hold
  the handoff open for minutes" the default was chosen for. What is left
  is a trade between handoff latency and handoff success, made with a knob that already exists by a
  deployment that has met the collision. Killing a subagent mid-stream stays refused (v1 never
  does). What landed with the decline is the falsified rationale: the comment on
  `DEFAULT_SWAP_DRAIN_TIMEOUT_S` and its restatement in
  [modules/brain-core.md](../modules/brain-core.md) both called 60 s "generous enough for a normal
  delegated run to finish", which this repo's own 200 to 300 s measurement denies, and the
  [model-swap runbook](../runbooks/model-swap.md) gained the sizing paragraph that names what the
  knob is really up against. **Reopens** on a deployment that reports the collision with the
  measured run durations to size against, which is the usage the entry asked for and the only thing
  that turns this trade into arithmetic.
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
  **It landed 2026-08-09**, ahead of its trigger, recorded at the
  [ADR-0030 tier-outage addendum](../adr/ADR-0030-brain-handoff.md) where the entry was opened and
  at the [ADR-0012 addendum](../adr/ADR-0012-resource-governance.md) that owns the port. A peer
  the swap back could not restart is now recorded in `StandingTiers` (`residency_tiers.py`), which
  closes GPU placement, names the tier on a **serving** `Health` reply, and is retried every
  `CORTEX_SWAP_TIER_HEAL_S` (30 s) by `TierHealer` until a pass sees the tier `ready`. Four things
  about it, two of them corrections to this entry's own text.
  **"This port stays unchanged" was the half that moved**, and it is the phrasing this file's own
  index warns about. The scheduler really is untouched. The **placer** port is not: `place` is
  synchronous, lock-free and argument-poor by design, so nothing can *ask* it whether a tier is
  up, and the only shape that fits is being *told*, which is a verb. `SubagentPlacer` gained
  `close_gpu()`/`open_gpu()`, deliberately not expressed as a charge, since a resident charged
  large enough to crowd the cap out would say "no room" where the truth is "no server" **and**
  would be silently reversed by the next successful `charge_standing`.
  **"Widening `ResidencyReport`" was the other correction**, and the reason is a lifetime rather
  than a shape: that value is republished at every residency transition, so down-ness written into
  it would be dropped by the next swap in, which publishes `RESIDENCY_LOADING` and knows nothing
  about peers. The record lives beside the report and is folded in on read, which is also what
  keeps the swap to one writer of what the GPU is serving.
  **The distinction the entry never named is the one the design turns on**: down versus merely
  evicted. Only a `start` that **raised** marks, only a **serving** report is annotated, and the
  handoff window is covered by the drain and the charge rather than by this, so a tier stopped for
  the length of a swap never reads as a fault. **What the user sees needed no new surface**:
  `HealthReply` already carries a detail beside `ready` and the overlay already renders a ready
  detail as `Brain ready: <line>`, so a serving report with something to say simply wins the slot
  the version string held, with no proto, Rust or TypeScript change.
  **Its cost claim held and its harm claim shrank.** "A wasted GPU attempt per spawn" is exactly
  what this removes. What it does not remove is a tier that dies **without** anybody having asked
  it to restart, which was measured against a real sidecar the same day: a tier with a bad
  artifact answers `200 loading` to a `start` and `failed` seconds later, so the restart loop marks
  it standing and nothing notices. That is the first of the three entries below.
- **The retry only asks about tiers it already believes are missing.** *Fix when it bites.* Opened
  2026-08-09 by the close above, whose record is written at exactly one site, the swap back's
  best-effort restart, and only where the host **refused**. Three shapes escape it: a peer that
  accepted its start and then failed to load (measured against the real sidecar, `200 loading`
  then `failed` with exit code 1), a peer that dies quietly between handoffs, and a peer a
  deployment never started at all. A fourth joined them on 2026-08-09 when boot recovery became a
  writer of the same record: a boot that could not reach the host marks nothing at all, by design,
  since nothing was asked to run, so a sidecar that comes up a minute later has its peers
  unretried until the next handoff. In each the placer keeps sending spawns to a dead endpoint and
  pays the dead attempt plus the CPU re-run this entry's parent exists to avoid. The fix is a
  sweep: the same pass asking `status` for **every** `evict_models` tier rather than only the
  marked ones, which costs one control call per tier per interval and closes the whole family. It
  is not built now because a sweep that may `start` a tier is a much stronger thing to hold
  correct against a handoff in flight than one that only retries a known failure, and because
  gating the peers inside the swap back instead is the wrong end (it would spend the load bound
  per tier inside the turn the user is waiting on). The trigger is the first deployment observed
  running with a peer tier dead and nothing noticing, which is also the first one whose logs say
  how often that happens.
  **A fifth shape joined on 2026-08-11**, from the opposite direction and now tellable apart at the
  port ([ADR-0030 unrostered-tier addendum](../adr/ADR-0030-brain-handoff.md)): a peer named in
  `CORTEX_SWAP_EVICT_MODELS` that the daemon has no artifact for is marked missing at boot, which
  is right, and then retried every interval for ever against a roster that cannot grow, since
  `ModelNotHostedError` is exactly the answer no retry can change. It costs two control calls a
  pass on loopback and a log line, so it is noise rather than harm, and the question it raises is
  the one this entry already owns: what a pass looks at. It belongs here rather than in an entry of
  its own because the two answers are one design, whether a tier that can never come back stops
  being asked about and whether the placer stays closed on it while it is.
- **The placer holds one bit for the card, where the record holds one entry per tier.**
  *Fix when it bites.* Opened 2026-08-09 by the same close. Any missing tier closes GPU placement
  for the whole pool, because the brain has no declared mapping from a hosted tier id
  (`CORTEX_SWAP_EVICT_MODELS`, a model-host roster name) to the GPU endpoint a roster entry dials
  (`CORTEX_SUBAGENTS_GPU_ENDPOINT`, a URL). Today that mapping would have exactly one possible
  value in every deployment this repo ships, so declaring it would be config nobody can get wrong
  and nobody can get right either. The cost of the coarse lever is a deployment that lists a tier
  the subagent pool never places on and loses GPU placement it did not need, which is decode rate
  rather than correctness, and the conservative direction is deliberate (under refusing costs a
  dead load per spawn). The fix is a declared tier id per roster entry, threaded into
  `PlacementRequest` so the placer can skip one target rather than all of them. The trigger is a
  deployment naming more than the subagent tier in `CORTEX_SWAP_EVICT_MODELS`, or a second
  GPU-capable executor, which is the same condition the placement-aware CPU charging entry waits
  on.
- **Boot recovery still calls a peer tier's failure the cortex being gone.** *Fix when it bites.*
  Opened 2026-08-09 by the same close, which refuses that conflation everywhere else and left this
  one site alone. `converge_residency` starts every `evict_models` tier inside the same `try` that
  decides whether the cortex was observed serving, so one peer that will not start makes the whole
  convergence answer `False`, the composition root publishes `RESIDENCY_BOOT_FAILED`, and the
  overlay goes amber with "the usual assistant did not come up at startup" over a cortex that is
  serving turns perfectly well. The fix is the same record threaded through that function and
  through `BootWatch._converge`, with the peers no longer deciding the cortex's verdict. It was
  left out because those two call sites reach the record through the manager, which sits one line
  under the file cap, so the change is a split rather than an argument; and because the retry
  clears the placer half within a pass either way, leaving only the readiness lie. The trigger is
  a boot observed reporting that lie, which needs a deployment that both evicts a tier and has one
  that will not start.
  **It landed 2026-08-09, hours later and ahead of that trigger, recorded at the
  [ADR-0030 boot-verdict addendum](../adr/ADR-0030-brain-handoff.md).** `converge_residency` now
  answers about the cortex and nothing else: each `evict_models` peer is cleared best effort and
  restarted best effort through the swap back's own `restart_evicted`, so a `status` or a `start`
  the host refuses is recorded in the manager's `StandingTiers` and skipped, while the verdict
  stays what was observed of the cortex. Three things about it, two of them corrections to this
  entry's own text.
  **The blocker was still the real one**, to the line: `residency.py` stood at 299 of 300 and both
  call sites reach the record through it. The split is by responsibility rather than by count:
  `ResidencyBoard` (`residency_board.py`) now owns the bookkeeping the moves and the restore both
  publish into (which model the GPU serves, what a human is told, whether a scope owns the card,
  and the one condition all three are written and waited on under), leaving the manager *when* the
  GPU may change hands and *who may lease*. No public import path moved and the board is not
  exported, like `HandoffClaim` beside it.
  **"The same record threaded through that function" was half the fix**, and a real sidecar is what
  said so. The reachable misconfiguration is a tier named in `CORTEX_SWAP_EVICT_MODELS` that the
  daemon has no artifact for, and such a tier is not in its roster at all: it answers 404 to the
  **status** of the clearing loop, several calls before the `start` this entry named. Witnessed
  live on 2026-08-09 against the real `model-host` image over real HTTP, which answered
  `settled=False` with an empty record while `GET /models/cortex` on the same daemon read `ready`,
  and answered `settled=True` with `missing=('subagent-gpu',)` once the clearing loop was
  peer-tolerant too. The children were stub HTTP servers, no GGUF being mountable that session;
  everything this touches is control plane.
  **The detail line had to stop naming a cause.** `TIERS_MISSING_DETAIL` said a tier "did not come
  back after a deep task", which is false on a brain that has never escalated, so it now reads
  `the model host is not running {models}, so delegated work is running on the CPU`. The record
  grew a second writer, so its sentence had to describe the state rather than one writer's story.
  What it leaves is the deep tier's own clearing, the entry below.
- **The deep model's clearing still decides the cortex's verdict at boot.** *Fix when it bites.*
  Opened 2026-08-09 by the close above, which made the peers' clearing best effort and deliberately
  left `plan.brain_model`'s fatal: a `status` or `stop` of the deep tier that raises answers `False`
  without asking about the cortex at all. That is right for the shape it was written for, an
  unreachable host, and right in the corner that matters, a deep model that really is resident and
  really cannot be stopped, since a boot that reported green over a card still holding it would be
  the opposite lie. It is wrong for one reachable shape: a deployment that sets `CORTEX_ESCALATION=1`
  without naming `CORTEX_MODEL_FILE_BRAIN` gets a daemon that 404s that tier for ever, so every boot
  is amber over a cortex that is serving. The reason it is recorded rather than fixed is that the
  port cannot tell the two apart: `ModelHostError` covers both "unknown model" and "I am not
  answering", and guessing from a message string is worse than the lie. The fix is therefore a
  narrower failure on the port (a typed "this host does not serve that id", which the sidecar
  already distinguishes as a 404 and the adapter already collapses), after which an unrostered deep
  tier is a configuration fault the boot can name instead of an amber dot. The trigger is the first
  deployment observed booting amber with a cortex that is serving, or the same port distinction
  being wanted for any other reason.
  **It landed 2026-08-11, ahead of that trigger, recorded at the
  [ADR-0030 unrostered-tier addendum](../adr/ADR-0030-brain-handoff.md).** The port has the
  narrower failure the entry asked for, `ModelNotHostedError`, a subclass of `ModelHostError` so
  that every caller which cannot use the distinction goes on catching what it always caught, and
  the adapter raises it for a 404 on a per-model route and for nothing else. Boot recovery clears
  the deep tier best effort in that one shape, so an unrostered deep tier is a green boot plus one
  `ERROR` naming both `CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION`, while a deep model that is
  resident and will not stop, an unreachable sidecar, and a cortex id the roster does not have all
  stay amber. Three things about it, one of them the entry's own account and two of them things it
  could not have known.
  **Its account of the tree held to the line**, checked before anything was designed: the flat
  error, the single `try`, and the sidecar's own `UnknownModelError` already crossing the wire as a
  404 that the adapter collapsed. So this was a port change and an adapter that stops discarding,
  which is why it was small.
  **The amber dot was the cheap half.** Driven one call further, through a real `swap_scope`
  against a real supervisor over HTTP, the shipped code met that same 404 in the swap back's stop
  of the model it had swapped in, failed the restore, failed its retry, and raised
  `ResidencyRestoreError` with the cortex left stopped and the seam saying recovery was manual. So
  a deployment that merely could not escalate lost its assistant at the first attempt to, and the
  fix therefore reaches `residency_moves.py` as well: the swap back skips exactly that one failure,
  since a tier the host never had can hold no card, and the swap in names the configuration fault
  rather than blaming the machine.
  **The distinction has a second site, and it is left open where it belongs.** The same 404 reaches
  the tier retry for a peer, which then asks a roster that cannot grow, every interval, for ever.
  Nothing is harmed and the log says so each pass, so what is open is a policy question about a
  tier that can never come back, and it is named on the retry entry above rather than filed as an
  entry of its own.
- **The brain learns at boot that escalation cannot work, and then forgets it.** *Fix when it
  bites.* Opened 2026-08-11 by the close above, which tells the operator once, at startup, that
  the deep tier is not in the model host's roster, and keeps that knowledge nowhere. Every later
  escalation therefore runs the whole prologue against a tier that cannot exist: the pool is
  drained, the cortex is evicted, the `start` comes back 404, and the scope's `finally` reloads the
  cortex, which at tier scale is minutes of the assistant being gone for a handoff that was never
  going to run, once per attempt. The user's note says the tier is not in the roster, which is
  honest but arrives after the stall. The fix is to remember the fact where the conductor can read
  it and refuse before the drain, and it is recorded rather than built because it needs two
  decisions this close did not need: where a fact about the host's roster lives on a brain whose
  every other belief about that daemon is invalidated by a restart (the boot id is the existing
  answer to exactly that question, so the refusal has to be re-derived when the daemon changes,
  not cached for the life of the process), and what the seam says about a capability that is
  configured and unavailable, the residency report carrying one detail line that already belongs to
  the peer record. The trigger is a deployment observed paying that stall, or a user asking why an
  escalation that was offered never happens.
- **A read timeout on the subagent HTTP client landed 2026-08-09, on two clients rather than the
  one this entry named ([ADR-0005 stall-ceiling addendum](../adr/ADR-0005-llamacpp-engine.md),
  recorded at the [ADR-0012 read-timeout addendum](../adr/ADR-0012-resource-governance.md)).**
  The entry read: "*Fix when it bites.* The actual unbounded-wait hazard under the admission
  budget: `build_subagents` builds `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, so one
  wedged `llama-server` stream holds its admission forever and every queued peer waits behind it.
  `read=None` is deliberate (a generation may legitimately stream for minutes on CPU), so the fix
  is a generous per-stream ceiling, not a short one, and it belongs to the inference adapter
  (ADR-0005), not the scheduler." Every word of that held except the count. **There were two
  unbounded clients, not one**, and the second is the one that matters most: the resident tier's
  (`builders.build_inference_backend`) carried the same `read=None`, and after a handoff the deep
  model streams through that very object, so the site this entry missed serves the slowest model
  in the lineup. Both are now built by `builders.build_generation_client`, and the reason the
  entry could miss it is that `builders.py` documented the policy as shared ("one knob") while
  naming only the connect phase.
  The ceiling is what the entry asked for, generous and per stream, and it is **two** numbers
  rather than one: `CORTEX_INFERENCE_STALL_TIMEOUT_S` 120 s and `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`
  600 s, because the worst legitimate silence differs by an order of magnitude between the tiers
  and one number would have to be the loose one, parking a wedged cortex turn for the CPU pool's
  whole allowance. The derivations are measurements: 17.5 s of contended time to first token
  scaled by the deep tier's own cost for the first, and twice the 300 s upper end of a measured
  whole CPU subtask for the second. What the entry could not have known, because the runbook note
  postdates it, is that the pool's wire queue is shorter than its admission queue: a backend holds
  its lease for the whole stream, so spawns of one entry on one target are serial **brain side**,
  ahead of the request, and this ceiling covers one call's own first token rather than a peer's
  generation. The semantics are the part worth repeating: httpx applies a read timeout to one
  socket read, so this bounds the **gap between chunks** and never a generation's length, and seam
  backpressure does not trip it.
- **A total generation cap landed 2026-08-11, ahead of its trigger, because the number it was
  waiting on turned out to be measurable ([ADR-0005 total-cap addendum](../adr/ADR-0005-llamacpp-engine.md),
  which is also where its decline was recorded).** This is a fix-when-it-bites entry closed before
  it bit, which is established practice here when the fix is cheap and provable, and it is worth
  saying plainly why it was cheap. What kept the entry closed was never the mechanism, both halves
  of which the entry had already priced down to nothing; it was the guess about how long a
  legitimate answer runs. That is not a guess on this machine, it is an afternoon: five subtask
  shapes on the shipped CPU entry, from a one-word lookup to an open-ended essay, measured for
  decoded tokens and wall clock, with the cap set at roughly five times the longest narrow reply and
  the deadline at four times the longest whole subtask, the extra doubling covering a tool-using
  run whose loop spends on several rounds what the measurement spent on one completion. The trigger asked for one observed runaway to size
  the bound from; what the measurements give instead is the other end, the longest run that must
  **not** be cut, which is the end a cap is actually sized against.
  The entry read: "*Fix when it bites.* Opened
  2026-08-09 by the close above, whose ceiling cannot see this: a stall detector fires on silence,
  and a model in a repetition loop is never silent. Nothing in the shipped wiring bounds a
  delegated generation's length (`n_predict: -1`, no `max_tokens` on the subagent path), so a
  runaway subagent holds its admission and its entry's lease exactly as the wedged stream used to,
  and at the CPU tier's 0.35 tok/s it can do so for a very long time while looking healthy the
  whole way. **The trigger is the first delegated run observed running away**, which nothing has
  seen yet; that it has not been seen is why this is recorded rather than built, since a cap set
  without one measured runaway would be a guess about how long a legitimate answer is, and the
  cost of guessing low is a truncated reply on every long subtask. Two shapes, and only one of
  them is cheap: a **token** cap is expressible today, `GenerationBounds.max_tokens` already
  riding the `InferenceBackend` port and already used by the recap fold, so it is a value threaded
  from `SubagentsConfig` through the runner; a **wall-clock** cap is not, needing the same timeout
  design as the bounded admission wait above, and it is the one that would
  actually bound the pool's worst case, a token budget on a 0.35 tok/s tier still being minutes.
  **That half got cheaper on 2026-08-09**, hours after this entry was written, when the wait it
  points at landed: the design turned out to be `asyncio.timeout` around the wait rather than the
  injected `Clock` this entry priced it at (a duration belongs on the loop's monotonic clock, and
  the `Clock`/`Sleeper` pair exists for poll loops), so the wall-clock cap is the same wrapper
  around the attempt's stream consumption and needs no port to carry a deadline. What did not get
  cheaper is the number, which is still the guess about how long a legitimate answer runs that
  keeps this entry closed.
  Its origin decision is the [ADR-0005 stall-ceiling addendum](../adr/ADR-0005-llamacpp-engine.md),
  which declined it deliberately: converting an unbounded wait into a bounded reported failure is
  a transport concern, while capping how much a model may say is a policy about answers, and
  mixing the two would have shipped an unmeasured number inside a fix that needed none."
  Every word of the defect held, and the reproduction is the reason the fix is not a description of
  one: a backend yielding a text chunk forever, through the shipped runner, streamed **3,099,896
  chunks in 5 s**, never returned, and persisted no result, holding its admission and its VRAM
  placement throughout. One word of the *fix* did not hold, and it is the one an entry is most
  likely to get wrong: "expressible today" was true of the port and false of the path. The
  `InferenceBackend.stream` signature really does carry `GenerationBounds`, but `ToolLoopContext`
  had no `bounds` field and `stream_tool_loop` passed none, so the only route a subagent reaches
  that port by could not carry a cap. One field of loop vocabulary fixed it and the port is
  untouched, which is this area's blanket "behind the unchanged port" coming out true for once,
  though not for the reason the entry gave.
  What landed is `AttemptBounds(max_tokens, timeout_s)` on the runner: the cap rides every
  completion an attempt asks for, and the deadline is `asyncio.timeout` around the whole
  consumption, so it covers the tool dispatches between completions as well, which is the unit that
  actually holds an admission. Reaching the deadline is `AttemptFailure.TRUNCATED`, an `ok=False`
  result naming the bound, and it is deliberately **not** re-placed on the CPU, for the reason a
  malformed reply is not: a model still talking at its deadline was answering, and the slower tier
  is the last place to send it. Two things the entry could not have known, both settled here rather
  than left implicit: the deadline is armed **per attempt** rather than per task, since a re-run
  handed the remains of a spent one would be refused before it began, and it must sit **above** the
  pool's stall ceiling, which `SubagentsConfig` now refuses to start without, because a deadline
  under the ceiling would report every wedged stream as a runaway and silently delete the CPU
  re-run scheduled for exactly that failure.
  Two residues are recorded rather than folded in: the finish reason a capped completion carries is
  still not distinguishable through the port (below, in this file's open set), and the "200 to
  300 s whole subtask" the admission wait's own derivation rests on is an underestimate by a factor
  of two for a summarization, which these measurements are the first to say.
- **A finish reason the port does not carry, so a capped completion looks like a finished one.**
  *Fix when it bites.* Opened 2026-08-11 by the close above, which is honest about needing it.
  llama-server ends a capped completion and says so on the wire, `finish_reason: "length"`, and the
  adapter surfaces text, reasoning, tool calls and a decode cadence and no finish reason at all, so
  the core cannot tell a model that stopped from one that was stopped. The deadline half of that
  close reports itself, being the core's own bound; the token half does not. On the constrained
  tool-less path the gap is closed structurally, since a cut envelope fails to parse and arrives as
  `MALFORMED`, an honest `ok=False` with a less useful reason; on the unconstrained path a
  truncation reads as a short answer. What holds today instead of a mechanism is the sizing: at
  roughly five times the longest reply the shipped tier has been measured writing, what the cap
  cuts was already not an answer, and this repo's own precedent for the same problem, `clean_recap`,
  reads the reply's shape rather than the transport. **The trigger is the first capped delegated
  reply that a reader mistakes for a finished one**, or the same distinction being wanted by any
  other caller, the recap fold being the obvious second. The fix is a port change and is priced as
  one: a finish reason has to cross `InferenceBackend`, either as a field on the closing
  `DecodeCadence` (which already arrives once, whole, at the end of the completion it describes) or
  as an event of its own, and every backend including `EchoInferenceBackend` owes the new answer.
  `DecodeCadence.tokens` is the near miss worth naming, since a completion whose decoded count
  reached the cap did reach the cap: it is an inference rather than a statement, it is silent on a
  build that reports no timings, and the loop absorbs the event into a `CadenceWatch` whose
  contract is about rates, so reading it here would be a second consumer of a value shaped for
  another question.
- **The whole-subtask figure two derivations rest on is out by a factor of two.** *Fix when it
  bites.* Opened 2026-08-11 by the close above, whose measurements are what say so. "A whole CPU
  subtask measures 200 to 300 s" appears in the subagents runbook, in the stall ceiling's
  derivation and in the admission wait's, where it is multiplied out into the 900 s and 1800 s
  waits the 3600 s bound is twice. Measured on the shipped entry at the compose file's own shape,
  it holds for an extraction (410.5 s is already above it) and is out by a factor of two for a
  summarization (623.8 s), which is the shape delegation is most often for. Neither bound derived
  from it is *wrong* in the direction that matters, both being deliberately generous and both
  bounding a failure rather than pacing normal work, but the arithmetic under the admission wait
  now understates its own inputs, and a bound whose derivation no longer matches the machine is a
  bound nobody can retune with confidence. **The trigger is the first spawn observed refused at the
  admission bound**, or a retune of either bound for any other reason, at which point the figure is
  re-derived from a batch rather than from single subtasks; that is the measurement this entry is
  really waiting on, since the queue's arithmetic is about a batch's serialization and these five
  runs were one at a time.
