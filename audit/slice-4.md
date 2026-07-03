# Audit of Slice 4 (Real inference: llama.cpp adapter + Model Manager v1)

**Audited:** 2026-07-02 · **Verdict:** done, with documented deferrals

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Every concrete promise in the Slice 4 section checks out against the tree. The CI-gated half is verified directly in code: LlamaCppBackend (brain/packages/inference/src/cortex_inference/backend.py) sits behind the unchanged InferenceBackend port and composes the new ModelManager port; the pure SingleResidentModelManager (brain/packages/core/src/cortex_core/model.py) implements acquire() lease + queue via an asyncio.Lock and raises ModelUnavailableError for any non-resident model (no swap); backend selection is config-driven with Echo as the default and llama.cpp opt-in via CORTEX_INFERENCE_BACKEND/CORTEX_INFERENCE_ENDPOINT (config.py, wiring.py, both tested); docker/docker-compose.gpu.yml carries the read-only model bind mount, GPU reservation, loopback publish, and the ctx-size/ngl knobs the measurements demanded; the live test is integration-marked and excluded by the workspace addopts. The host half (GPU compose up, live test on the 24 GB card, measured VRAM, gemma-4-12B pick) is verified-as-documented via the ADR-0004 addendum, the ADR-0007 host-validation note, and docs/runbooks/llamacpp-gpu.md. The three gaps found are all written down: the cortex_model_manager process-lifecycle deferral to Slice 11 (ROADMAP ledger + ADR-0007), the reasoning-content latency risk on the gemma cortex (ROADMAP ledger + ADR-0013 addendum), and low-severity dated-snapshot staleness in the runbook's placement/tbd rows whose supersession is recorded in the ADR-0004 addendum and the Slice 8.5 ledger entries. Verdict: done-with-documented-deferrals.

## Claims checked (17)

- **✅ verified**. llama.cpp adapter for InferenceBackend exists as cortex_inference.LlamaCppBackend, a thin HTTP translator over llama-server's OpenAI-compatible /v1/chat/completions with SSE parsing (delta.content until [DONE]) and every failure crossing the port as InferenceError with cause chained
  - Evidence: brain/packages/inference/src/cortex_inference/backend.py:31-33,123-169 (stream POSTs to lease.endpoint + _CHAT_COMPLETIONS_PATH, parses 'data:' lines, breaks on [DONE], wraps ModelManagerError and httpx.HTTPError into InferenceError at 162-167)

- **✅ verified**. The InferenceBackend port is unchanged by the slice. The core keeps talking only to InferenceBackend.stream(model, messages); the adapter composes the ModelManager behind it, wired at the composition root
  - Evidence: brain/packages/core/src/cortex_core/ports.py:36-48 (port); backend.py:131-148 (manager injected, lease acquired inside stream); wiring.py:85-89. Note: the port later gained a keyword-only tools param in Slice 6 (ADR-0009), documented in the port docstring. An additive later-slice evolution, not a Slice 4 discrepancy

- **✅ verified**. ModelManager is a core port with acquire(model) -> AbstractAsyncContextManager[ModelLease]; ModelLease.endpoint is the llama-server base URL; ModelManagerError/ModelUnavailableError are the typed errors
  - Evidence: brain/packages/core/src/cortex_core/ports.py:51-62; brain/packages/core/src/cortex_core/model.py:19-28 (ModelLease); brain/packages/core/src/cortex_core/errors.py:41-46

- **✅ verified**. Model Manager v1 is the pure SingleResidentModelManager in cortex_core: single resident model, acquire() lease + queue via an asyncio.Lock whose waiter queue is the queue API, no swap (acquiring any other model raises ModelUnavailableError); no I/O
  - Evidence: brain/packages/core/src/cortex_core/model.py:31-58 (lock at 41, non-resident raise at 51-56, lease yield under lock at 57-58)

- **✅ verified.** A ModelManager contract test exists that pins the contract for Slice 11's process-lifecycle adapter (port satisfaction, resident lease, non-resident raises, concurrent callers serialized)
  - Evidence: brain/packages/core/tests/test_model.py:3,21-43 (test_manager_satisfies_the_port, test_acquire_resident_leases_the_endpoint, test_acquire_non_resident_raises_without_swap, test_acquire_serializes_concurrent_callers)

- **✅ verified.** Config-driven backend selection: Echo is the default, llama.cpp is opt-in via CORTEX_INFERENCE_BACKEND=llamacpp which requires CORTEX_INFERENCE_ENDPOINT; run_from_env wires LlamaCppBackend over a SingleResidentModelManager only then
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/config.py:58-76 (backend default 'echo', validator rejects llamacpp without endpoint); wiring.py:77-89,213; tests at brain/packages/orchestrator/tests/test_config.py:96-113 and tests/test_wiring.py:133-142

- **✅ verified**. docker/docker-compose.gpu.yml override adds the llama-cortex service (ghcr.io/ggml-org/llama.cpp:server-cuda, --model, -ngl ${CORTEX_NGL:-99}, --ctx-size ${CORTEX_CTX_SIZE:-16384}, --parallel 1), a read-only bind mount defaulting to ./models, loopback-only publish 127.0.0.1:8080, NVIDIA device reservation, a healthcheck, and flips the brain to CORTEX_INFERENCE_BACKEND=llamacpp pointed at http://llama-cortex:8080
  - Evidence: docker/docker-compose.gpu.yml:14-22 (brain env + depends_on healthy), 24-46 (image + command), 47-53 (bind, read_only: true), 54-57 (loopback publish), 59-68 (healthcheck), 69-75 (gpu reservation)

- **✅ verified**. Live tests are integration-marked and excluded from coverage/CI (the proven gate): the live streaming test carries @pytest.mark.integration and the workspace addopts run -m "not integration" with --cov-fail-under=100
  - Evidence: brain/packages/inference/tests/test_backend_live.py:24 (@pytest.mark.integration); brain/pyproject.toml:63-66 (markers + addopts '-m "not integration"'); runbook documents the --no-cov convention (docs/runbooks/llamacpp-gpu.md:85-97)

- **✅ verified**. The adapter's SSE parsing and error mapping are 100% unit-tested without GPU or network via httpx.MockTransport plus the pure manager (malformed chunk, non-string content, HTTP status, transport error, unavailable model, tool-call reassembly)
  - Evidence: brain/packages/inference/tests/test_backend.py:58 (MockTransport), 67-243 (test_malformed_chunk_raises_inference_error, test_http_error_status_wraps_into_inference_error, test_transport_error_wraps_into_inference_error, test_unavailable_model_wraps_into_inference_error, etc.)

- **✅ verified**. Runbook docs/runbooks/llamacpp-gpu.md exists and covers the host half: prerequisites, env knobs (CORTEX_MODELS_DIR, CORTEX_MODEL_FILE_CORTEX, CORTEX_CTX_SIZE, CORTEX_NGL), compose bring-up, the integration-test invocation, measured numbers, and teardown. Engine flags live in the adapter/compose/runbook, never the core
  - Evidence: docs/runbooks/llamacpp-gpu.md:1-157 (config table 20-31, bring-up 68-84, integration test 85-97, measurements 119-150); logical id vs filename split at runbook:29-30 and config.py:45-47 (CORTEX_MODEL_CORTEX logical id)

- **✅ verified.** ADR-0005 (llama.cpp as the engine: one llama-server per model, OpenAI-compatible HTTP as the adapter surface, swap = process lifecycle, dockerized GPU deployment with the read-only model mount) exists and is Accepted
  - Evidence: docs/adr/ADR-0005-llamacpp-engine.md:1-51 (decisions 1-6, dated 2026-06-29)

- **📄 verified-as-documented (host-only run; paper trail checked)**. ADR-0007 (Model Manager v1 + llama.cpp adapter design: 6 decisions matching the shipped code) exists, Accepted, and carries the host-validated addendum (live test streamed a real completion on the 24 GB card, SSE shape held, ~11 GB multimodal cortex at 16K ctx, load mount-read bound)
  - Evidence: docs/adr/ADR-0007-model-manager-inference.md:1-98; host-validation record at lines 94-98 (the GPU run itself is host-only paper trail; the design decisions 1-6 were verified directly against code)

- **📄 verified-as-documented (host-only run; paper trail checked)**. ADR-0004 addendum records the Slice 4 measurements against measured VRAM and the cortex pick locked to gemma-4-12B: measurement table (gemma-4-12B 11.0/11.3 GB, Qwen3.5-9B 9.2/11.0 GB, load times under 55 W), the 14 GB soft cap (CORTEX_VRAM_SOFT_CAP_GB), the context-size footgun (--ctx-size + single slot), and load ≈ mount-read bound (~150-180 MB/s) answering ROADMAP assumptions 1 and 2
  - Evidence: docs/adr/ADR-0004-model-lineup.md:71-119 ('Addendum (2026-06-29): Slice 4 measurements & model placement'); mirrored in docs/runbooks/llamacpp-gpu.md:119-150 and ROADMAP assumption 1 (docs/ROADMAP.md:606-620); the ctx/ngl knobs landed in docker/docker-compose.gpu.yml:37-46 as the addendum states

- **📄 verified-as-documented (host-only run; paper trail checked)**. "Final per-tier model picks recorded against measured VRAM": at Slice 4 close only the cortex tier was settled (gemma-4-12B); embedder (Slice 5), subagent (Slice 7), and brain (Slice 11) picks follow per the runbook, and the embedder/subagent picks were indeed recorded in later ADR-0004 addenda
  - Evidence: docs/ROADMAP.md:74-77 (Delivered paragraph scopes it to 'the cortex pick locked to gemma-4-12B'); docs/runbooks/llamacpp-gpu.md:145-147 ('Remaining picks... recorded in ADR-0004 as each lands'); ADR-0004:1-5 status line and addenda at 121-142 (embedder) and 143-162 (subagent)

- **✅ verified**. Module docs exist for the new code: docs/modules/brain-inference.md (purpose, public contract, error contract, invariants, dependencies) and brain-core.md documents ModelManager/ModelLease/SingleResidentModelManager
  - Evidence: docs/modules/brain-inference.md:1-55; docs/modules/brain-core.md:38,121-122,249-251

- **✅ verified**. cortex_inference's source depends only on cortex_core (the ports) plus httpx, per ADR-0007 d2
  - Evidence: brain/packages/inference/pyproject.toml dependencies = ["cortex-core", "httpx>=0.27"]; backend.py imports only cortex_core + httpx (backend.py:13-29)

- **✅ verified**. The cortex_model_manager package (process lifecycle) is deferred to Slice 11 and that deferral is recorded in the ROADMAP's Deferred refinements ledger and the origin ADR
  - Evidence: docs/ROADMAP.md:530-533 ('Inference / Model Manager, Slice 4' ledger entry: process lifecycle, co-residency, real swap land in Slice 11 behind the unchanged ModelManager port); docs/adr/ADR-0007-model-manager-inference.md:52-54 (d3) and 83-84 (consequences); docs/ROADMAP.md:77-79 (slice text itself)

## Gaps (3)

### G1 · severity low · documented (docs/ROADMAP.md:530-533 (Deferred refinements ledger, 'Inference / Model Manager (Slice 4)'); docs/adr/ADR-0007-model-manager-inference.md:52-54,83-84; docs/ROADMAP.md:77-79)

cortex_model_manager (process lifecycle: start llama-server on load, stop on unload; co-residency; real swap) is not implemented. Only the pure SingleResidentModelManager policy object exists, and the resident server is brought up declaratively by compose. This is by design ('no swap yet' is in the slice title's own scope).

### G2 · severity medium · documented (docs/ROADMAP.md:536-543 (Deferred refinements ledger, Slice 4 subsection); docs/adr/ADR-0013-untrusted-content.md addendum (referenced there); runbook workaround noted at docs/runbooks/llamacpp-gpu.md:113-116)

Reasoning-content handling: the chosen cortex gemma-4-12B is a reasoning model that emits reasoning_content before content, yet LlamaCppBackend reads only delta.content and docker-compose.gpu.yml does not disable thinking. A long deliberation streams nothing until it concludes (latency/truncation risk under a heavy think). Discovered during Slice 6.5 GPU validation, consciously left undecided until the cortex path is next touched.

### G3 · severity low · documented (docs/adr/ADR-0004-model-lineup.md:164-174 (addendum explicitly 'revises the subagents = CPU placement'); docs/ROADMAP.md:553-555 (ledger: the real GPU-placed runtime lands with Slice 11); docs/ROADMAP.md:205-206)

Stale text (dated snapshot, not misleading): docs/runbooks/llamacpp-gpu.md:130-132,139-141 still lists subagent/brain/embedder picks as 'tbd' and states 'subagents -> CPU', while later ADR-0004 addenda settled the embedder (nomic-embed-text-v1.5 Q8_0) and subagent (Qwen3.5-2B) picks and revised subagent placement to GPU-first/CPU-overflow (ADR-0012). The section is explicitly dated 'Measured so far (2026-06-29)' and points to ADR-0004 for 'full detail + placement strategy', which carries the revision; the current subagents compose still runs CPU-only (the GPU-placed runtime is a documented Slice 11 deferral). Same dated 'subagents run on CPU' phrasing survives at docs/ROADMAP.md:211, contextualized by the revision note at docs/ROADMAP.md:205-206.
