# Runbook for subagents on CPU (Slice 7 host half, ADR-0010)

Bring up the CPU subagent `llama-server` and validate delegation end to end. This is the
host-only half of Slice 7. CI stays subagent-free (subagents are opt-in, `CORTEX_SUBAGENTS_*`).
Subagents run on **CPU** (the GPU budget is the cortex's, ADR-0004), so this needs **no GPU**
and runs alongside `docker-compose.gpu.yml`.

## Prerequisites

- Docker Desktop (WSL2 backend) running.
- The subagent GGUF: `Qwen3.5-2B-Q4_K_M.gguf` (the pick, ADR-0004). On the dev machine the models are
  mounted into WSL at **`/srv/models`** (Windows `D:\Software\AI\...`), so from WSL set
  `CORTEX_MODELS_DIR=/srv/models`; the compose default (`./models`) is for
  host-side (Windows) Docker, which resolves `D:`. A plain WSL distro sees the drive at `/srv`,
  not `D:`. Override the file with `CORTEX_MODEL_FILE_SUBAGENT` (default
  `unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf`).

## 1. Bring up the subagent server

```bash
CORTEX_MODELS_DIR=/srv/models \
  docker compose -f docker-compose.yml -f docker-compose.subagents.yml up -d redis llama-subagent
# wait for health (Qwen3.5-2B loads in ~15 s on CPU):
curl http://127.0.0.1:8082/health   # -> {"status":"ok"}
```

`-ngl 0` keeps it CPU-only; `--jinja` enables the tool-capable chat template (so tools-enabled
subagents can function-call); `--parallel` matches `CORTEX_SUBAGENTS_MAX_CONCURRENCY` so each
scheduler-admitted subagent gets a server slot.

> **Reasoning off (important).** Qwen3.5 is a reasoning model. On CPU, unbounded thinking is
> minutes per call and `LlamaCppBackend` discards the `<think>` traces (it reads `content`, not
> `reasoning_content`). Until the subagent tier disables reasoning (deferred-refinements list), add
> `--reasoning-budget 0` to the `llama-subagent` command, or the live test below will crawl.

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
(depth-1):

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml `
  -f docker-compose.tools.yml -f docker-compose.subagents.yml up -d
```

Then speak a prompt that invites parallel work ("look up X and Y at the same time") through the
overlay / a `Converse` client and confirm the cortex emits `spawn_subagents`, the subagents run,
and their aggregated results fold into the answer. Every dispatched call (cortex and subagent) is
audit-logged (ADR-0009/0010).

## 4. Teardown

```powershell
docker compose -f docker-compose.yml -f docker-compose.subagents.yml down
```

## Notes

- **Machinery validated on the real pick (2026-07-01).** The delegation path was proven on a real
  CPU `llama-server` running **Qwen3.5-2B Q4_K_M** (from `/srv/models`): concurrent subagents
  answered correctly (e.g. "17 + 25" → 42) in ~0.6 s each **with thinking off**, `is_error=False`;
  load ~14.5 s, ~893 MiB RSS. Pick locked in the [ADR-0004 addendum](../adr/ADR-0004-model-lineup.md);
  details in the [ADR-0010 addendum](../adr/ADR-0010-subagents.md).
- **Still the user's to confirm:** the cortex-driven path (step 3, the GPU cortex *deciding* to
  emit `spawn_subagents`), which needs the resident gemma-4-12B.
- If the subagent tool-calls unreliably at 2B (once reasoning is disabled), prefer gemma-4-E4B or
  Qwen3.5-4B (ADR-0004) at higher CPU cost, or keep subagents as pure text workers (no tools needed).
