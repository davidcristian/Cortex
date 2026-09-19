# Runbook: checking delegation end to end

Six procedures that run real subagents, from the delegation machinery alone up to a live cortex
deciding to delegate. Bringing the server up, choosing its model and every bound a run is held to:
[subagents-cpu.md](subagents-cpu.md). `--no-cov` is required on every command here, or the
workspace's 100% coverage threshold fails the run.

## 1. The delegation machinery, with no GPU cortex

The integration test calls `spawn_subagents` directly, as the cortex would, runs two subagents
concurrently on the live model, and checks that both returned output:

```bash
cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_live.py -v
```

## 2. The multi-model roster

Layer `docker-compose.subagents-roster.yml` to add the Qwen-2B override as roster entry `qwen` on
its own server (port 8083) beside the default. Run this without the tools override, so subagents
are tool-less: with tools layered, every spawn is sent to the default model and the spec stops
advertising the `model` setting.

```bash
CORTEX_MODELS_DIR=/srv/models \
  docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.subagents.yml -f docker/docker-compose.subagents-roster.yml up -d
cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
  CORTEX_SUBAGENTS_QWEN_ENDPOINT=http://127.0.0.1:8083 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_live.py -v
```

The roster test spawns one batch mixing a bare item, which takes the default model, with a
`{"model": "qwen"}` item. Servers are per model, so routing shows up in the logs, where each
container's `prompt eval time` count is its served-request count:

```bash
docker logs cortex-llama-subagent-qwen-1 2>&1 | grep -c "prompt eval time"
```

## 3. The GPU-placed tier, and both decisions of the placer

This is the one procedure here that needs a GPU, because it is the only one where a GPU-placed
subagent really executes on the GPU. It brings the hosted `-ngl 99` tier up beside the CPU server
and drives the placer over both, so the run shows a GPU placement happening and shows it not
happening; a GPU path that cannot be made to do the second proves nothing by doing the first.

```bash
CORTEX_MODELS_DIR=/srv/models \
  CORTEX_MODEL_FILE_SUBAGENT_GPU=google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf \
  CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083 \
  docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml -f docker/docker-compose.subagents.yml \
  -f docker/docker-compose.modelhost-loopback.yml up -d --build
# the tier is in the roster but NOT started: the daemon starts the cortex and nothing else
curl -s -X POST http://127.0.0.1:9300/models/subagent-gpu/start
curl -s http://127.0.0.1:9300/models/subagent-gpu   # poll until "state":"ready"
```

The loopback override is what makes this runnable from the host at all: the sidecar's tiers are
deliberately unpublished, and it maps the tier's `:8083` to `127.0.0.1:9083`, since `:8083` on the
host belongs to the roster override's second CPU server. Take it down with `just down-gpu`.

The file named on the first line is the CPU server's own default on purpose: the brain treats the
hosted tier and the CPU server as the two placement targets of one roster entry, so the two
variables have to name one artifact, and nothing checks that they do.

Then the two cases, which select themselves from the budget in the environment and skip otherwise.
Since the VRAM request was measured on 2026-08-08 the shipped budget selects the GPU one, so that
one needs nothing overridden and the CPU one is what has to be arranged for:

```bash
cd brain
# GPU: the shipped budget, whose 5.4 GiB of headroom holds exactly one 3.5 GiB request
CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py
# CPU: a soft cap the same request cannot fit, the overflow path every deployment
# below this card's size takes
CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
  CORTEX_VRAM_SOFT_CAP_GB=11 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py
```

Each run passes one test and skips the other, and the skip message prints the VRAM request and the
headroom it was compared against, so a run that skips both is a budget problem and says so.
Corroborate the routing outside the test with each server's own log, where a `launch_slot_` line
is one served request:

```bash
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml \
  -f docker/docker-compose.subagents.yml logs model-host | grep -c launch_slot_
```

**Prove the GPU path can fail.** Point `CORTEX_SUBAGENTS_GPU_ENDPOINT` at a closed port under the
GPU budget and the run must fail with three placements and a "a GPU-placed subagent did not
answer" warning, which is the CPU re-place taking over. A suite that passes that way is measuring
nothing.

Measured 2026-08-08 against the measured VRAM request, the cortex resident throughout. With
nothing overridden the GPU test passes, the tier's `launch_slot_` count moves by exactly one, and
that spawn answers in 152.11 ms (18 prompt tokens at 152.54 tok/s, 3 generated at 87.95 tok/s)
against 13134.73 ms for the sibling that overflowed to the CPU. The CPU test at
`CORTEX_VRAM_SOFT_CAP_GB=11`, whose 2.4 GiB of headroom is under the request, passes with the
tier's count still unmoved. The earlier run on 2026-08-04, when both cases still needed a raised
cap to reach the GPU, measured 221.05 ms against 12536.83 ms.

## 4. A cortex deciding to delegate

Layer all three overrides so the resident cortex can decide to delegate, and add the tools
override to give subagents tools too. The wiring hands them the MCP subset without the spawn tool,
so delegation is one level deep. The override sets both required endpoints
(`CORTEX_SUBAGENTS_ENDPOINT` and `CORTEX_SUBAGENTS_GPU_ENDPOINT`, which both resolve to the one
CPU server unless the GPU-placed tier is opted into and routed at) and passes through
`CORTEX_SUBAGENTS_{CPUS,MEMORY_GB,VRAM_GB,CPU_BUDGET,MEM_BUDGET_GB}`:

```powershell
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml `
  -f docker/docker-compose.tools.yml -f docker/docker-compose.subagents.yml up -d
```

Then speak a prompt that invites parallel work ("look up X and Y at the same time") through the
overlay or a `Converse` client, and confirm that the cortex emits `spawn_subagents`, that the
subagents run, and that their aggregated results fold into the answer. Every dispatched call, the
cortex's and each subagent's, is written to the tool audit.

## 5. Constrained output against format laundering

Start one standalone CPU server as [subagents-cpu.md](subagents-cpu.md) shows, on loopback 8090,
then run the integration test through the real `LlamaCppBackend`. It asserts that the same
injection an unconstrained stream obeys is defeated by the envelope constraint:

```bash
cd brain && CORTEX_SUBAGENT_ENDPOINT=http://127.0.0.1:8090 CORTEX_MODEL_SUBAGENT=e4b \
  uv run pytest -m integration --no-cov -s \
  packages/inference/tests/test_backend_live.py::test_constrained_decoding_kills_format_laundering_on_the_weak_tier
```

The unconstrained baseline appends an exfiltration link; the constrained request returns exactly
`{"reply": "..."}` with the link gone. Validated 2026-07-13, about 7 s.

## 6. Does the cortex spread a batch across roster models?

The spawn spec tells the cortex that subtasks on distinct roster models overlap while subtasks
sharing one model run one after another, and points it at spreading a batch as the way to shorten
a wall clock. This procedure observes whether a live cortex takes that advice on its own. Two
things decide whether a run means anything, so check both first.

- **Run it without the tools or email overrides.** Giving subagents an MCP dispatcher sends every
  spawn to the default model and `build_spawn_spec` then advertises no `model` setting at all, so
  a tools-enabled stack has nothing to observe. `build_subagent_tools` hands subagents a
  dispatcher whenever any tool registry is configured, so this is one override away.
- **Run it with at least two roster entries.** A one-entry roster gets the same fixed note.

```bash
CORTEX_MODELS_DIR=/srv/models docker compose --project-directory . \
  -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml \
  -f docker/docker-compose.subagents.yml -f docker/docker-compose.subagents-roster.yml up -d
```

Then drive the real cortex from the host, with the roster pointed at the loopback publishes:

```bash
cd brain
CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  CORTEX_SUBAGENTS_BACKEND=llamacpp \
  CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
  CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:8082 \
  CORTEX_SUBAGENTS_ROSTER__qwen='{"endpoint": "http://127.0.0.1:8083", "vram_gb": 2.5, "cpus": 2.0, "memory_gb": 1.5}' \
  uv run pytest -m integration --no-cov -s packages/orchestrator/tests/test_spawn_nudge_live.py
```

The first test is what makes a silence readable: it asserts that the spec really publishes the
roster's names as a `model` enum and really includes the spread sentence. The other two put one
question each and print what the cortex chose, because a choice is an observation rather than a
contract. Sampling is random, so run them several times and read the spread, and corroborate
against each server's own log:

```bash
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.subagents.yml -f docker/docker-compose.subagents-roster.yml \
  logs llama-subagent llama-subagent-qwen | grep -c launch_slot_
```

Measured here 2026-08-04, resident gemma-4-12B at 16K with a single slot and both CPU sidecars up:
twenty prose-only turns over four questions emitted zero spawn calls, and sixteen invited turns
all delegated and all put the batch on a single roster entry. A directed control question ("put
them on different subagent models") produced one call naming both entries and one served request
in each server's log, which is what proves the setting reachable before a silence is read as a
decision.

**Budget your time by the CPU tier rather than by the cortex.** gemma-4-E4B generates at between
3.0 and 12.4 tok/s under its 4 CPU cap here with its thread count set to that cap: 12.2 to 12.4
with one slot decoding on an idle host, 8.5 to 9.2 a slot with both, and 4.9 to 5.0 and 3.0 to 3.1
on a host saturated by one busy worker per hardware thread, the cap being a quota rather than a
reservation. Qwen3.5-2B under the same caps decodes at 22.6 tok/s on one slot and 17.2 to 17.3 a
slot with both, on an idle host. The batch runs no faster than its slowest member. At those rates
three 400-token replies on the default entry, two slots then one, decode in about 80 seconds on an
idle host and about three and a half minutes on a saturated one, before prompt evaluation and any
tool rounds. These readings are of 2026-09-11, taken off the compose stack's own server. The first
request after boot also pays first-touch paging of the GGUF off the models mount. If all you want
is the choice, it is made before the batch is dispatched: intercept `SpawnSubagentsTool` and end
the turn there, and a sample costs 5 to 8 seconds instead.

## What has been checked so far

- **The current model, gemma-4-E4B QAT q4_0 (2026-07-03).** `test_subagent_live.py` passed with
  two concurrent subagents in 3.3 s; "17 + 25" returned 42 in about 1.8 s with thinking off and no
  reasoning trace; a clean `read_file` tool call took about 8 s, bound by CPU prefill; load 38 s,
  about 2.5 GiB resident.
- **Qwen3.5-2B Q4_K_M (2026-07-01, now the override).** Concurrent subagents answered correctly in
  about 0.6 s each with thinking off; load about 14.5 s, about 893 MiB resident. If a task can
  tolerate this override and it calls tools unreliably, fall back to the default or keep that
  subagent a pure text worker with no tools.
- **The cortex-driven path, closed on the host 2026-07-01.** With the resident gemma-4-12B the
  cortex decided to emit `spawn_subagents` end to end. No measurements were recorded beyond that.
- **The roster and the cortex-driven choice, checked in Docker 2026-07-03.** Both sidecars were
  healthy off the real GGUFs, the roster live test routed a mixed batch to both models, and the
  resident gemma-4-12B emitted `spawn_subagents` with a per-item `"model": "qwen"` object. Two
  findings, both handled: given only prose the cortex may fold the model choice into the
  instruction text, which is why the spec now shows an object example, and it sometimes emits the
  object item JSON-encoded as a string, which the parser accepts.
