# Subagents on CPU runbook (Slice 7 host half, ADR-0010; placement GPU-first since Slice 8.5, ADR-0012)

Bring up the subagent `llama-server` and validate delegation end to end. This is the
host-only half of Slice 7. CI stays subagent-free (subagents are opt-in, `CORTEX_SUBAGENTS_*`).
Placement is **GPU-first with CPU overflow** (ADR-0012), but until Slice 11 lands the real GPU
sidecar (the recorded ADR-0012 host-half deferral) the compose runs **one CPU server** and
points both placement targets at it. A GPU-*placed* subagent still *executes* on CPU. So this
needs **no GPU** and runs alongside `docker/docker-compose.gpu.yml`.

## Prerequisites

- Docker Desktop (WSL2 backend) running.
- The subagent GGUF: `gemma-4-E4B_q4_0-it.gguf` (the pick is injection-robust, ADR-0004
  pick-revision addendum). On the dev machine the models are
  mounted into WSL at **`/srv/models`** (Windows `D:\Software\AI\...`), so from WSL set
  `CORTEX_MODELS_DIR=/srv/models`; the compose default (`./models`) is for
  host-side (Windows) Docker, which resolves `D:`. A plain WSL distro sees the drive at `/srv`,
  not `D:`. Override the file with `CORTEX_MODEL_FILE_SUBAGENT` (default
  `google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf`; the cheaper/faster
  `unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf` when robustness matters less).

## 1. Bring up the subagent server

```bash
CORTEX_MODELS_DIR=/srv/models \
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.subagents.yml up -d redis llama-subagent
# wait for health (gemma-4-E4B loads in ~38 s on CPU; the Qwen-2B override in ~15 s):
curl http://127.0.0.1:8082/health   # -> {"status":"ok"}
```

`-ngl 0` keeps it CPU-only; `--jinja` enables the tool-capable chat template (so tools-enabled
subagents can function-call); `--parallel` (`CORTEX_SUBAGENTS_PARALLEL`, default 2) gives each
scheduler-admitted subagent a server slot, so keep it ≈ `CORTEX_SUBAGENTS_CPU_BUDGET /
CORTEX_SUBAGENTS_CPUS`, the effective admission concurrency under the ADR-0012 soft budget
(which replaced the pre-8.5 `CORTEX_SUBAGENTS_MAX_CONCURRENCY` knob).

> **Reasoning is disabled** on the subagent server (`--chat-template-kwargs
> '{"enable_thinking": false}'`, baked into the compose command). Both lineup families
> (gemma-4-E*, Qwen3.5) are reasoning models. Unbounded thinking on CPU is minutes per call,
> and `LlamaCppBackend` reads `content`, not the `reasoning_content` where `<think>` traces land,
> so it would look empty and crawl. With the flag, plain requests answer directly (~1.8 s on the
> E4B pick, ~0.3-0.6 s on the Qwen-2B override), and the E4B injection-robustness (0/10) holds
> with thinking off (ADR-0004 injection addendum).

## 2. Validate the delegation machinery (no GPU cortex needed)

The integration test invokes `spawn_subagents` directly (as the cortex would), running two
subagents concurrently on the live model and checking both returned non-empty output:

```bash
cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_live.py -v
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run.

## 3. Validate cortex-driven delegation (full stack, needs the GPU cortex)

Layer all three overrides so the resident cortex can *decide* to delegate. Give subagents tools
too by adding the tools override. The wiring hands them the MCP subset without the spawn tool
(depth-1). The override bakes in both required endpoints (`CORTEX_SUBAGENTS_ENDPOINT` and
`CORTEX_SUBAGENTS_GPU_ENDPOINT`, ADR-0012, where both resolve to the one CPU server until Slice 11)
and passes through the ask/budget knobs (`CORTEX_SUBAGENTS_{CPUS,MEMORY_GB,VRAM_GB,CPU_BUDGET,MEM_BUDGET_GB}`):

```powershell
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml `
  -f docker/docker-compose.tools.yml -f docker/docker-compose.subagents.yml up -d
```

Then speak a prompt that invites parallel work ("look up X and Y at the same time") through the
overlay / a `Converse` client and confirm the cortex emits `spawn_subagents`, the subagents run,
and their aggregated results fold into the answer. Every dispatched call (cortex and subagent) is
audit-logged (ADR-0009/0010).

## 4. Teardown

```powershell
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.subagents.yml down
```

## Notes

- **Machinery validated on the current pick, gemma-4-E4B QAT q4_0 (2026-07-03).** The same
  delegation path re-proven on the E4B server: `test_subagent_live.py` passed (two concurrent
  subagents, 3.3 s), "17 + 25" → 42 in ~1.8 s thinking-off with no reasoning trace, a clean
  `read_file` tool call (~8 s, CPU prefill-bound); load 38 s, ~2.5 GiB RSS. Pick revision +
  full measurement table in the [ADR-0004 pick-revision addendum](../adr/ADR-0004-model-lineup.md).
- **Machinery originally validated on Qwen3.5-2B Q4_K_M (2026-07-01, now the override).**
  Concurrent subagents answered correctly (e.g. "17 + 25" → 42) in ~0.6 s each **with thinking
  off**, `is_error=False`; load ~14.5 s, ~893 MiB RSS. Details in the
  [ADR-0010 addendum](../adr/ADR-0010-subagents.md).
- **Cortex-driven path host-closed (2026-07-01).** The maintainer ran step 3 with the resident
  gemma-4-12B and closed the slice: the cortex *decided* to emit `spawn_subagents` end to end
  (ROADMAP Slice 7 status; dated closure addendum in
  [ADR-0010](../adr/ADR-0010-subagents.md)). No measurements were recorded beyond the closure.
- Tool-calling is validated on the E4B pick (`--jinja`, a clean `read_file` call). If a task can
  tolerate the cheaper Qwen-2B override and IT tool-calls unreliably, fall back to the pick or
  keep that subagent a pure text worker (no tools handed to it).
