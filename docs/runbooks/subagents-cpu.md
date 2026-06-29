# Runbook for subagents on CPU (Slice 7 host half, ADR-0010)

Bring up the CPU subagent `llama-server` and validate delegation end to end. This is the
host-only half of Slice 7. CI stays subagent-free (subagents are opt-in, `CORTEX_SUBAGENTS_*`).
Subagents run on **CPU** (the GPU budget is the cortex's, ADR-0004), so this needs **no GPU**
and runs alongside `docker-compose.gpu.yml`.

## Prerequisites

- Docker Desktop (WSL2 backend) running.
- A small subagent GGUF (2-4B) under the models dir. The compose default expects a Qwen3.5-2B
  Q4_K_M at `D:\Software\AI\Models` (override with `CORTEX_MODELS_DIR` /
  `CORTEX_MODEL_FILE_SUBAGENT`). Note the Windows `D:` bind resolves only when Docker is invoked
  **host-side** (Windows shell or a WSL distro with the drive mounted). A plain WSL distro
  cannot see `D:`.

## 1. Bring up the subagent server

```powershell
docker compose -f docker-compose.yml -f docker-compose.subagents.yml up -d redis llama-subagent
# wait for health (a small CPU model loads in seconds):
curl http://127.0.0.1:8082/health   # -> {"status":"ok"}
```

`-ngl 0` keeps it CPU-only; `--jinja` enables the tool-capable chat template (so tools-enabled
subagents can function-call); `--parallel` matches `CORTEX_SUBAGENTS_MAX_CONCURRENCY` so each
scheduler-admitted subagent gets a server slot.

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

- **Machinery validated locally (2026-06-29).** The delegation path was proven on a real CPU
  `llama-server` using a **stand-in** small model (Qwen2.5-1.5B-Instruct Q4_K_M, in a WSL-local
  dir since `D:` is unreachable from a plain WSL distro): three concurrent subagents returned
  correct answers ("capital of France" → Paris, "17 + 25" → 42, plus a one-word reply), aggregated
  in order, `is_error=False`. See the [ADR-0010 addendum](../adr/ADR-0010-subagents.md).
- **Still the user's to confirm:** the final subagent model pick (the real Qwen3.5-2B on `D:`)
  and the cortex-driven path (step 3, GPU cortex emitting `spawn_subagents`). Lock the pick in the
  [ADR-0004 addendum](../adr/ADR-0004-model-lineup.md) with the measured CPU footprint/latency.
- If the subagent model tool-calls unreliably at 2B, prefer a gemma-4-E4B or Qwen3.5-4B (ADR-0004)
  at higher CPU cost, or keep subagents as pure text workers (they need no tools to be useful).
