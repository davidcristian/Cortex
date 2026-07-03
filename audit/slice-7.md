# Audit of Slice 7 (Subagents)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Slice 7's code is fully delivered and matches its claims: SubagentTask/SubagentResult, the TaskStore/SubagentScheduler ports with the InMemoryTaskStore fake, the shared stream_tool_loop extracted from TurnEngine, the SubagentRunner, the concurrent-batch spawn_subagents tool merged via CompositeToolRegistry, depth-1 wiring in build_subagents (subagents get the MCP subset without the spawn tool), the fakeredis-covered RedisTaskStore, CORTEX_SUBAGENTS_* config, the CPU llama-server compose override with enable_thinking=false, the integration-marked live test, the runbook, and the ADR-0010/ADR-0004 addenda. The Slice 8.5 supersession (ResourceBudgetScheduler replacing ConcurrencyScheduler, GPU-first placement, the new env knobs) is consistently written down across ROADMAP, ADR-0010's addendum, ADR-0012, and brain-core.md. Two real inconsistencies remain: the compose file and runbook were left behind by the Slice 8.5 config change. The documented full-stack bring-up would crash the brain because CORTEX_SUBAGENTS_GPU_ENDPOINT is required but never set, and the stale MAX_CONCURRENCY knob is no longer read. ADR-0012 does defer the compose/runbook overhaul to Slice 11's host half, so that gap is documented. The undocumented item is small but concrete: the ROADMAP declares the user's cortex-driven GPU validation closed 2026-07-01, yet ADR-0010 and the runbook still describe it as pending, leaving the closure with a ROADMAP-only paper trail; the RedisTaskStore also silently drops the ADR-0013 tainted flag on a store round-trip (covered by the recorded Slice-11 taint-persistence deferral, live path unaffected). Verdict is undocumented-gaps solely on the stale user-closure text; the implementation itself is complete.

## Claims checked (18)

- **✅ verified**. SubagentTask/SubagentResult pure value types exist in the core (no I/O)
  - Evidence: brain/packages/core/src/cortex_core/subagents.py:13-49. Frozen dataclasses; SubagentTask enforces tz-aware 'at' (lines 28-31); SubagentResult carries task_id/output/ok/detail plus the ADR-0013 'tainted' flag (line 49)

- **✅ verified**. TaskStore and SubagentScheduler ports are defined as Protocols in the core
  - Evidence: brain/packages/core/src/cortex_core/ports.py:152-168 (TaskStore: put_task/get_task/put_result/get_result) and ports.py:171-184 (SubagentScheduler.admit(request) returning an async context manager); exported in cortex_core/__init__.py lines 44-45, 119, 123

- **✅ verified.** InMemoryTaskStore fake exists and is contract-tested against the Redis adapter
  - Evidence: brain/packages/core/src/cortex_core/fakes.py:122-152; parametrized contract suite over both implementations in brain/packages/session/tests/test_task_store_contract.py:20-32 with shared checks in tests/task_contract.py

- **📄 verified-as-documented (host-only run; paper trail checked)**. The pure ConcurrencyScheduler (Slice 7 progress text) exists
  - Evidence: Delivered historically (git 7dfb4da 'feat(brain): subagent core, task store, CPU scheduler, runner, shared loop') and then REPLACED by ResourceBudgetScheduler in Slice 8.5 (brain/packages/core/src/cortex_core/scheduler.py:22 now holds ResourceBudgetScheduler only). The replacement is written down: docs/ROADMAP.md:304 ('ResourceBudgetScheduler, replacing ConcurrencyScheduler'), docs/adr/ADR-0012-resource-governance.md:158-159, docs/modules/brain-core.md:280-281. The Slice 7 status paragraph (ROADMAP.md:205-206) flags the 8.5 revision, so the historical mention at ROADMAP.md:228 is cross-referenced, not silently stale.

- **✅ verified**. The shared stream_tool_loop was extracted from TurnEngine and is used by both the cortex turn and subagents
  - Evidence: brain/packages/core/src/cortex_core/tool_loop.py:66-71 (stream_tool_loop, module docstring lines 1-16 records the extraction); consumed by TurnEngine at engine.py:23,103,111 and by SubagentRunner at runner.py:20,103-105

- **✅ verified**. SubagentRunner runs a delegated task as a stateless function over the TaskStore and persists a SubagentResult (failures become ok=False, not exceptions)
  - Evidence: brain/packages/core/src/cortex_core/runner.py:49-126 loads task by id (line 82), 'task not found' → ok=False (lines 83-86), InferenceError → ok=False with partial output (lines 109-118), result persisted via put_result (lines 123-126); tested in brain/packages/core/tests/test_runner.py

- **✅ verified**. Native spawn_subagents tool is a concurrent batch (instructions: string[]) with bad arguments returning is_error results
  - Evidence: brain/packages/core/src/cortex_core/spawn.py:21-41 (SPAWN_TOOL_NAME + batch spec), 49-59 (argument validation → error string), 92-114 (tasks persisted then asyncio.gather over runner.run (concurrent, line 110-111); taint aggregation line 113 per ADR-0013); matches the ADR-0010 increment-2 addendum (ADR-0010-subagents.md:133-145)

- **✅ verified.** CompositeToolRegistry merges built-in tools with the remote MCP registry behind the unchanged ToolRegistry port (built-ins take precedence, duplicate built-ins are a construction error)
  - Evidence: brain/packages/core/src/cortex_core/composite.py:28-58. Duplicate built-in raises ValueError (lines 34-37), describe_tools shadows same-named remote specs (line 47), invoke routes built-in → remote → ToolNotFoundError (lines 50-58); tested in core/tests/test_composite.py; end-to-end delegation over fakes in core/tests/test_delegation.py

- **✅ verified.** Depth-1 delegation: wiring gives the cortex the composite dispatcher while subagents get only the MCP subset without the spawn tool
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/wiring.py:163-167 (subagent ToolDispatcher wraps the raw tool_registry only, no composite, no spawn tool) vs wiring.py:188-192 (cortex dispatcher over CompositeToolRegistry with the spawn tool); run_from_env composes them at wiring.py:216-226; asserted in orchestrator/tests/test_wiring.py:215-297

- **✅ verified**. RedisTaskStore lives in cortex_session and is 100%-covered via fakeredis
  - Evidence: brain/packages/session/src/cortex_session/tasks.py:85-137 (adapter over redis.asyncio, every failure wrapped as TaskStoreError); brain/packages/session/tests/test_task_store_contract.py:12-100 uses FakeAsyncRedis for the contract, disconnected-client, corrupt-record, close-failure, and from_url paths

- **✅ verified.** CORTEX_SUBAGENTS_* env config exists with an opt-in 'none' default
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/config.py:127-162. SubagentsConfig with env_prefix CORTEX_SUBAGENTS_, backend default 'none'; note the knob set was revised by Slice 8.5: gpu_endpoint/vram_gb/cpus/memory_gb/cpu_budget/mem_budget_gb replaced max_concurrency (ADR-0012:164-166,185-188; ROADMAP.md:307-309), and the validator now requires BOTH endpoint and gpu_endpoint when backend=llamacpp (config.py:154-162)

- **✅ verified**. docker/docker-compose.subagents.yml adds a CPU llama-server sidecar with reasoning disabled via --chat-template-kwargs '{"enable_thinking": false}'
  - Evidence: docker/docker-compose.subagents.yml:31-59. llama-subagent service, -ngl 0 (line 47), --jinja (line 48), --chat-template-kwargs '{"enable_thinking": false}' (lines 54-55), Qwen3.5-2B-Q4_K_M default model (line 40), read-only model mount (lines 60-65), loopback-only port 8082 (line 69)

- **✅ verified**. test_subagent_live.py exists as an integration-marked, CI-excluded live test of the delegation machinery
  - Evidence: brain/packages/orchestrator/tests/test_subagent_live.py:42-43 (@pytest.mark.integration + skipif without CORTEX_SUBAGENTS_ENDPOINT); runs the real LlamaCppBackend + SubagentRunner + ResourceBudgetScheduler + SpawnSubagentsTool batch (lines 44-77); docstring documents exclusion via workspace addopts -m 'not integration' (lines 6-10)

- **✅ verified**. docs/runbooks/subagents-cpu.md exists and describes bring-up, machinery validation, and the cortex-driven full-stack run
  - Evidence: docs/runbooks/subagents-cpu.md:1-83. Prerequisites (/srv/models), server bring-up (§1), the integration-test invocation (§2), the cortex-driven GPU stack (§3), teardown, and the 2026-07-01 measured-validation note (lines 74-78)

- **✅ verified.** ADR-0010 exists with the increment-2 (batch tool), increment-4 (real-CPU-model validation + enable_thinking finding), and GPU-first addenda
  - Evidence: docs/adr/ADR-0010-subagents.md:1-189. 8 decisions (lines 27-88), increment-2 addendum (line 133), increment-4 addendum with measurements and the reasoning-disable fix (lines 147-175), 2026-07-01 GPU-first addendum recording the Slice 8.5 revision (lines 177-189)

- **✅ verified.** ADR-0004 addendum locks the subagent pick: Qwen3.5-2B Q4_K_M with measured CPU footprint
  - Evidence: docs/adr/ADR-0004-model-lineup.md:143-162. 'Slice 7 subagent pick + CPU measurement' addendum (2026-07-01): Q4_K_M 1.19 GB, ~14.5 s load, ~893 MiB RSS, thinking disabled; plus the later GPU-first placement addendum (lines 164-170) and the injection-harness note preferring gemma-4-E4B (lines 180-200, ROADMAP deferral lines 502-506)

- **📄 verified-as-documented (host-only run; paper trail checked)**. Increment 4: delegation validated on a real CPU llama-server running Qwen3.5-2B (~893 MiB RSS, ~14.5 s load, ~0.3-0.6 s/answer with thinking off)
  - Evidence: Host/Docker run not re-executable here; paper trail complete: ADR-0010-subagents.md:147-171 (dated addendum with measurements and the --reasoning-budget-0 negative finding), docs/runbooks/subagents-cpu.md:74-78, ROADMAP.md:235-243, integration test present and marked (test_subagent_live.py:42), commits e307107/971a2af/44aaeae

- **◐ partial.** The cortex-driven GPU path (resident gemma-4-12B deciding to emit spawn_subagents end to end) was closed by the user on 2026-07-01
  - Evidence: Recorded only in the ROADMAP status/progress text (ROADMAP.md:203-206, 243-245); the runbook describes the procedure (subagents-cpu.md §3) but still lists this path as 'Still the user's to confirm' (subagents-cpu.md:79-80), and ADR-0010's addendum likewise still says 'Still the host-only half' (ADR-0010-subagents.md:173-175). No dated ADR/runbook record of the closure result exists, so the paper trail is ROADMAP-only
  - Adversarial re-check: confirmed. The auditor is correct and cannot be refuted. The 2026-07-01 closure of the cortex-driven GPU path (resident gemma-4-12B deciding to emit spawn_subagents end to end) is recorded solely in ROADMAP status/progress text, introduced by commit 42fb330 whose diff touched only docs/ROADMAP.md. Every other artifact that should carry the result still marks the path as pending: the runbook's Notes section s

## Gaps (4)

### G1 · severity medium · documented (ADR-0012-resource-governance.md:180-183 ('Deferred to the host half (user): two real llama-server sidecars ... in docker/docker-compose.subagents.yml; the per-container caps; ... the runbook update') and ROADMAP.md:553-555 ('The real GPU-placed runtime mechanism ... lands with the Slice 11 lifecycle'); the env replacement itself is recorded at ROADMAP.md:307-309 and ADR-0012:185-188). The deferral is written down, but neither place says the current compose+runbook commands fail under the new validator. Misleading as written, hence medium.

docker/docker-compose.subagents.yml and the subagents-cpu.md runbook are stale against the Slice 8.5 config: the compose sets CORTEX_SUBAGENTS_BACKEND=llamacpp with only CORTEX_SUBAGENTS_ENDPOINT (docker-compose.subagents.yml:23-26), but SubagentsConfig now also requires CORTEX_SUBAGENTS_GPU_ENDPOINT (config.py:154-162). Nothing in any compose file or doc sets it, so the documented full-stack bring-up (runbook §3) would crash the brain at config validation. The compose and runbook also still set/describe CORTEX_SUBAGENTS_MAX_CONCURRENCY (compose lines 17,26,59; runbook line 28; ADR-0010 lines 71,113), which the config no longer reads (replaced by cpu_budget/mem_budget_gb).

### G2 · severity low · **not documented as a deferral**

Stale text on the user's cortex-driven GPU validation: ROADMAP marks it closed 2026-07-01 (ROADMAP.md:203-206,243-245), but docs/runbooks/subagents-cpu.md:79-80 still says 'Still the user's to confirm: the cortex-driven path (step 3)' and ADR-0010-subagents.md:173-175 still says 'Still the host-only half (needs the GPU)'. No dated addendum records the closure at the origin ADR or runbook, so the closure's paper trail contradicts two of the three documents.

**Adversarial re-check: confirmed.** The auditor is correct and could not be refuted. All three cited passages exist exactly as claimed: the ROADMAP marks Slice 7 "done (host-closed 2026-07-01)" with the cortex-driven GPU path "closed by the user", while docs/runbooks/subagents-cpu.md:79-80 and docs/adr/ADR-0010-subagents.md:173-175 still describe that same path as pending user confirmation. ADR-0010 has three addenda (2026-06-29 increment-2, 2026-06-29 increment-4, 2026-07-01 GPU-first placement); none records the cortex-driven validation closure. The 2026-07-01 addendum is solely about the GPU-first placement revision (ADR-0012) and explicitly leaves the "Still the host-only half" sentence in place above it. Git history confirms the closure commit (42fb330, Jul 4 2026) touched only docs/ROADMAP.md; the runbook and ADR-0010 were never updated afterward (only a path-tidy chore, d60847b). I also searched the entire "Deferred refinements & later work" section (ROADMAP.md:451-564), all other ADRs' addenda, docs/modules/, docs/design/, docs/runbooks/ (including body-overlay.md), docs/index.md, and commit messages for any dated record of the cortex-driven closure or a recorded deferral of the doc update. Nothing exists. The closure's only paper trail is the ROADMAP status line itself, which contradicts the origin ADR and runbook, exactly as the auditor reported.

### G3 · severity low · documented. ADR-0013-untrusted-content.md:239-240 and ROADMAP.md:517-520 defer 'Persisting taint / provenance across a mid-turn swap' to Slice 11 (taint is turn-local and reconstructed); the specific Redis-vs-fake field asymmetry is not called out anywhere, but falls under that recorded deferral.

RedisTaskStore drops SubagentResult.tainted on persistence: _encode_result/_decode_result (cortex_session/tasks.py:60-82) serialize only task_id/output/ok/detail, so a tainted result read back via get_result silently becomes tainted=False, whereas InMemoryTaskStore preserves the full object (fakes.py:142-152). The two implementations are not observably interchangeable for the ADR-0013 field, and the task contract (session/tests/task_contract.py) never round-trips tainted. Live path unaffected today: SpawnSubagentsTool consumes runner.run()'s in-process return (spawn.py:110-113) and no production code calls get_result.

### G4 · severity low · documented (ROADMAP.md:205-206 (Slice 7 status flags the ADR-0012 revision), ROADMAP.md:304 ('replacing ConcurrencyScheduler'), ADR-0010-subagents.md:177-189 (GPU-first addendum), ADR-0012-resource-governance.md:158-159, brain-core.md:280-281).

ROADMAP Slice 7 progress notes (lines 226-235) still name the ConcurrencyScheduler and describe subagents as CPU-only with a CPU-RAM budget. Slice 8.5's ResourceBudgetScheduler and GPU-first placement supersede that. Consistency is maintained by cross-references (Slice 7 status para lines 205-206 points to the 8.5 revision; ROADMAP.md:304 and ADR-0010's 2026-07-01 addendum record the replacement), so this is historical progress text, not a contradiction.
