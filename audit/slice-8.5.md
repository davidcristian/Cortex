# Audit of Slice 8.5 (Resource governance: revise the GPU/CPU managers)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

The CI half of Slice 8.5 is genuinely delivered exactly as the ROADMAP describes: the SubagentPlacer port (ports.py:65-79) with the pure VramBudgetPlacer fit-test (placer.py:41-45, headroom = soft_cap - cortex_reservation - placed, whole-model GPU/CPU with no straddle), admit(request) with the two-dimensional ResourceBudgetScheduler fully replacing ConcurrencyScheduler (scheduler.py, no source remnants), the runner's admit->place->route backends[target]->release-in-finally composition (runner.py:65-78), two target-selected backends wired in the orchestrator with InferenceBackend and proto/body.proto untouched, and the full CORTEX_VRAM_* / CORTEX_SUBAGENTS_* env surface replacing MAX_CONCURRENCY (config.py:48-162). ModelManager/acquire are verifiably untouched (git history), tests cover every claimed behavior, and all five consciously deferred items (drain, CUDA-OOM re-place, the real GPU runtime mechanism, placement-aware charging, NPU) appear in both the ROADMAP deferrals ledger (lines 545-559) and ADR-0012. The single undocumented issue is stale host collateral: docker-compose.subagents.yml and runbooks/subagents-cpu.md still describe the pre-8.5 CPU-only world, set the removed CORTEX_SUBAGENTS_MAX_CONCURRENCY, and (because the new config validator requires CORTEX_SUBAGENTS_GPU_ENDPOINT for backend=llamacpp) the existing subagents override would now crash the brain at startup, a misleading interim breakage no doc flags. Everything else would rate done-with-documented-deferrals; that one stale/misleading item drives the stricter verdict.

## Claims checked (15)

- **✅ verified.** A new pure-core port SubagentPlacer with place/release exists (not a fattening of ModelManager)
  - Evidence: brain/packages/core/src/cortex_core/ports.py:65-79 (SubagentPlacer Protocol, place(request)->Placement, release(placement)->None, both sync); test_placer.py:24-27 pins the port structurally

- **✅ verified**. VramBudgetPlacer fit-tests each spawn against soft_cap - cortex_reservation - placed, placing whole-model on GPU (-ngl 99) when it fits or spilling to CPU (-ngl 0), never a straddle, with a live ledger
  - Evidence: brain/packages/core/src/cortex_core/placer.py:41-45 (headroom = self._soft_cap_gb - self._cortex_reservation_gb - self._placed_gb; inclusive fit -> GPU reserve, else CPU reserve 0.0); placement.py:13-30 (PlacementTarget.ngl -> 99/0); tests brain/packages/core/tests/test_placer.py:30-68 cover fit, exact-fill, overflow, release, cortex-at-cap degenerate case

- **✅ verified**. ModelManager and its acquire are untouched by the slice
  - Evidence: ports.py:51-62 (ModelManager keeps acquire(model)->AbstractAsyncContextManager[ModelLease] with an explicit note that placement is separate per ADR-0012); model.py:31-44 SingleResidentModelManager.acquire unchanged; git log shows model.py last touched by Slice-4 commit 59648d0, and commit ea82801 (the 8.5 commit) confirms 'acquire and SingleResidentModelManager are untouched'

- **✅ verified**. No separate GPU-concurrency knob exists; the VRAM ledger bounds GPU concurrency
  - Evidence: No max_gpu_subagents anywhere in config.py or placer.py; ADR-0012 decision 2 (lines 70-74) records the rationale; placer.py has only soft_cap/reservation/_placed_gb

- **✅ verified**. SubagentScheduler.admit(request) gains a two-dimensional soft CPU/RAM budget: ResourceBudgetScheduler replaces ConcurrencyScheduler; over-budget spawns queue; an impossible charge raises
  - Evidence: ports.py:171-184 (admit(request) port); scheduler.py:22-68 (ResourceBudgetScheduler: _fits checks cpu AND mem sums, asyncio.Condition wait loop, ValueError 'exceeds the whole budget' for a charge over the whole budget, notify_all on release); ConcurrencyScheduler is gone from all source (grep hits only historical doc mentions and an env-hygiene delenv in orchestrator tests/test_config.py:34); tests test_scheduler.py cover queue-on-cpu-full, queue-on-mem-full, whole-budget rejection, nonpositive-budget rejection

- **✅ verified**. SubagentRunner composes admit (outer, waits) -> place (inner, sync) -> route to backends[placement.target] -> release in a finally
  - Evidence: runner.py:65-78 (async with res.scheduler.admit(res.request): placement = res.placer.place(res.request); try: backends[placement.target] ... finally: res.placer.release(placement)); SubagentResources bundle runner.py:24-37; behavior tests test_runner.py:184-205 (GPU-placed task runs the gpu backend and VRAM is released in the finally; zero-headroom task runs the cpu backend)

- **✅ verified.** Inference reaches the placed endpoint via two backends selected by target; InferenceBackend and proto/body.proto are untouched
  - Evidence: orchestrator wiring.py:149-161 builds backends={GPU: LlamaCppBackend(SingleResidentModelManager(model, config.gpu_endpoint)), CPU: LlamaCppBackend(...config.endpoint)}; ports.py:36-48 InferenceBackend.stream signature unchanged (no endpoint/placement arg); proto/body.proto contains no placement content and was last touched by the Slice-2 commit 5197b0f

- **✅ verified**. New env: CORTEX_VRAM_SOFT_CAP_GB + CORTEX_VRAM_CORTEX_GB and CORTEX_SUBAGENTS_{GPU_ENDPOINT,VRAM_GB,CPUS,MEMORY_GB,CPU_BUDGET,MEM_BUDGET_GB}, replacing CORTEX_SUBAGENTS_MAX_CONCURRENCY
  - Evidence: orchestrator config.py:48-55 (vram_soft_cap_gb default 14.0, cortex_reservation_gb alias CORTEX_VRAM_CORTEX_GB default 11.3) and config.py:142-152 (SubagentsConfig env_prefix CORTEX_SUBAGENTS_ with gpu_endpoint, vram_gb, cpus, memory_gb, cpu_budget, mem_budget_gb; no max_concurrency field); validator config.py:154-162 requires both endpoints for backend=llamacpp; tests test_config.py:69-70,77-78 exercise the new vars

- **✅ verified**. Opt-in unchanged: CORTEX_SUBAGENTS_BACKEND defaults to none so no placer/scheduler is constructed and CI/dev run as before
  - Evidence: config.py:144 (backend: SubagentsBackendName = "none"); wiring.py:146-147 (if config.backend == "none": return None, _noop_aclose); ADR-0012 decision 8

- **✅ verified**. The ledgers are live-resource state rebuilt from zero, never the durable state the hard rule governs
  - Evidence: placer.py:32 (_placed_gb = 0.0 at construction, docstring lines 10-12), scheduler.py:31-32 (_cpu_used/_mem_used_gb start at 0.0); the design argument is ADR-0012 decision 7 (lines 132-144)

- **✅ verified.** ADR-0012 exists, is accepted, and records the design, the revised ADR-0007/ADR-0010 decisions, and the deferrals
  - Evidence: docs/adr/ADR-0012-resource-governance.md:1-209 (Status: Accepted 2026-07-01; Revises ADR-0007 and ADR-0010 dec 6-7; deferrals at lines 168-188); ADR-0010 carries a matching addendum ('Addendum (2026-07-01): subagents are GPU-first, not CPU-only (revises decisions 6-7)' naming Slice 8.5/ADR-0012)

- **✅ verified**. Module docs were updated for the new placement machinery
  - Evidence: docs/modules/brain-core.md:91-95,144,215,272-281 (Placement values, SubagentPlacer port, VramBudgetPlacer, ResourceBudgetScheduler 'replaces ConcurrencyScheduler'); docs/modules/brain-orchestrator.md:19,64 (GPU-budget knobs + VramBudgetPlacer wiring)

- **📄 verified-as-documented (host-only run; paper trail checked)**. The CI half is complete and green under just check, 100% line+branch, no GPU
  - Evidence: ROADMAP.md:290-297 status paragraph; commit ea82801 message ('100% line+branch under just check, no GPU'); test files test_placement.py, test_placer.py, test_scheduler.py, test_runner.py exist and cover the branches read; the orchestrator re-runs just check separately

- **✅ verified.** Deferred items (scheduler drain(), CUDA-OOM->CPU re-place, the real GPU-placed runtime mechanism (sidecars + cgroup caps + validation), placement-aware CPU charging, and the NPU third target) are all recorded in the ROADMAP deferrals ledger and in ADR-0012
  - Evidence: docs/ROADMAP.md:545-559 ('Resource governance, Slice 8.5 (ADR-0012)' ledger block listing all five); docs/adr/ADR-0012-resource-governance.md:168-183 (Deferred to Slice 11 + Deferred to the host half)

- **📄 verified-as-documented (host-only run; paper trail checked)**. The real GPU-placed runtime mechanism (two live sidecars + per-container cgroup caps) lands with the Slice 11 lifecycle, not in this slice
  - Evidence: ROADMAP.md:292-294 and 553-555; ADR-0012:180-183; git log confirms docker/docker-compose.subagents.yml and docs/runbooks/subagents-cpu.md were not touched by the 8.5 commit (last touched d60847b/971a2af, pre-8.5)

## Gaps (6)

### G1 · severity medium · **not documented as a deferral**

Stale and now-broken host collateral: docker/docker-compose.subagents.yml still sets the removed CORTEX_SUBAGENTS_MAX_CONCURRENCY (lines 17, 26, 59) and its header still says subagents are CPU-only per ADR-0004 (line 8), contradicting ADR-0012 GPU-first; worse, it flips CORTEX_SUBAGENTS_BACKEND=llamacpp without setting CORTEX_SUBAGENTS_GPU_ENDPOINT, which the new validator (orchestrator config.py:154-162) requires. Bringing up the existing subagents override today crashes the brain at startup with a ValidationError. docs/runbooks/subagents-cpu.md (lines 5, 28) likewise still instructs the removed env var and the CPU-only framing. The compose/runbook *update* is deferred in writing, but the interim breakage/contradiction itself is flagged nowhere.

**Adversarial re-check: confirmed.** The auditor is correct on every count. (1) The breakage is real: docker-compose.subagents.yml flips CORTEX_SUBAGENTS_BACKEND to llamacpp and sets only CORTEX_SUBAGENTS_ENDPOINT, while the ADR-0012 validator (config.py:154-162) now requires CORTEX_SUBAGENTS_GPU_ENDPOINT as well; run_from_env constructs SubagentsConfig() at startup (wiring.py:210) and the brain image builds from the current tree, so layering the override exactly as its own header (lines 1-2, 11) or runbook step 3 instructs crashes the brain with a pydantic ValidationError. The compose still sets/documents the removed CORTEX_SUBAGENTS_MAX_CONCURRENCY (lines 17/26/59) and its line-8 header keeps the CPU-only, ADR-0004-addendum framing that ADR-0012 (and ADR-0004's own 2026-07-01 addendum) reversed; the runbook (lines 5, 28) does the same. Neither file has been touched since before ADR-0012. (2) The documentation gap is real: ADR-0012:180-183 and ROADMAP:553-555 defer only the future work (two GPU/CPU sidecars, cgroup caps, "the runbook update") to Slice 11, phrased as new mechanism landing later, implying the existing CPU-only override keeps working in the interim. No document records that the existing override no longer boots or that the runbook instructs a removed env var. I searched the full ADR-0012, all ADR-0010 and ADR-0004 addenda, the entire ROADMAP deferred-refinements ledger and Slice 7/8.5 sections (which still present the override/runbook as working collateral), the brain-orchestrator module doc, all runbooks, the compose file itself, and the slice-8.5 commit messages, plus keyword sweeps (stale/broken/interim/ValidationError/"will fail"/"until then"). Nothing flags the interim breakage or contradiction. Minor nuance not changing the verdict: runbook steps 1-2 (server-only bring-up + the live test, which builds its backend directly rather than via SubagentsConfig) still work; the crash hits the header's canonical usage and runbook step 3, which start the brain, matching the auditor's "bringing up the existing subagents override crashes the brain at startup".

### G2 · severity low · documented (docs/ROADMAP.md:547-549 (deferrals ledger) and docs/adr/ADR-0012-resource-governance.md:169-171)

SubagentScheduler.drain() (quiesce the pool for a swap) is not implemented. Slice 11 adds it as an additive method behind the unchanged port.

### G3 · severity low · documented (docs/ROADMAP.md:550-552 and docs/adr/ADR-0012-resource-governance.md:172-175)

CUDA-OOM -> re-place on CPU auto-recovery is not implemented; a real CUDA OOM today surfaces as ok=False via the existing failure contract.

### G4 · severity low · documented (docs/ROADMAP.md:292-294 (slice status), ROADMAP.md:553-555 (ledger), docs/adr/ADR-0012-resource-governance.md:180-183 (host-half deferral incl. the runbook update))

The real GPU-placed runtime mechanism (two live llama-server sidecars (GPU -ngl 99 + CPU -ngl 0) in docker-compose.subagents.yml, per-container --cpus/--memory cgroup caps, measured vram/reservation/budget numbers, real GPU-placed-subagent validation, and the runbook update) is not delivered; it lands with the Slice 11 lifecycle behind the corrected ports.

### G5 · severity low · documented (docs/ROADMAP.md:556-557 and docs/adr/ADR-0012-resource-governance.md:177 (also decision 5, lines 117-119))

Placement-aware CPU charging is not implemented: admit charges every spawn its full cpus/memory_gb regardless of GPU/CPU placement (conservative over-charge).

### G6 · severity low · documented (docs/ROADMAP.md:343-350 (deferred-option paragraph in the slice) and 558-559 (ledger); docs/adr/ADR-0012-resource-governance.md:177-178)

The Intel NPU as a third PlacementTarget (OpenVINO InferenceBackend adapter) is not implemented, pending a feasibility pass on WSL2 reachability.
