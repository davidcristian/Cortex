# Subagents on CPU runbook (Slice 7 host half, ADR-0010; placement GPU-first since Slice 8.5, ADR-0012; roster since Slice 8.6, ADR-0018)

Bring up the subagent `llama-server` and validate delegation end to end. This is the
host-only half of Slice 7. CI stays subagent-free (subagents are opt-in, `CORTEX_SUBAGENTS_*`).
Placement is **GPU-first with CPU overflow** (ADR-0012), and by default the compose runs **one CPU
server** with both placement targets pointed at it, so a GPU-*placed* subagent still *executes* on
CPU and this needs **no GPU**. A real GPU-placed executor does exist now, as an opt-in tier of the
`model-host` supervisor sidecar (`CORTEX_MODEL_FILE_SUBAGENT_GPU`, `-ngl 99` on `:8083`,
[model-swap.md](model-swap.md)); routing to it is the separate step of setting
`CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`. Everything here but section 2c stays the
CPU path and runs alongside `docker/docker-compose.gpu.yml`; **2c is the GPU one**, where a
GPU-placed spawn really executes on the GPU and both of the placer's verdicts are exercised.

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
(which replaced the pre-8.5 `CORTEX_SUBAGENTS_MAX_CONCURRENCY` knob). Set the ask no larger than
the budget: an entry that could never be admitted now fails the brain at startup rather than at
delegation time (ADR-0012 admission-wall addendum).

> **A silent delegated stream is bounded, a slow one is not.**
> `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` (default 600 s) is how long a subagent's stream may send
> **nothing** before the spawn fails with a message rather than holding its admission and every
> queued peer behind it. It bounds the gap between chunks and never the length of a generation,
> so raising `CORTEX_SUBAGENT_CTX_SIZE` or handing a subagent a long file does not need it
> raised; a slower CPU than this one might. The default is twice the longest whole subtask
> measured here, the CPU tier being the slow one on purpose (ADR-0005 stall-ceiling addendum).
> A subagent that keeps *talking* is a different failure and is bounded by nothing yet
> ([refinements/resource-governance.md](../refinements/resource-governance.md)).

> **Admitted is not the same as concurrent.** Each roster entry holds one `LlamaCppBackend` per
> placement target, and a backend holds its model lease for the whole stream, so two spawns of the
> *same* entry on the same target run one after the other however many the budget admits. Measured
> here on the Qwen-2B override: two concurrent spawns took 4.8 s through two backend objects and
> 10.0 s through one, exactly serial. Raising `CPU_BUDGET` alone therefore buys queue depth, not
> throughput; real parallelism needs distinct entries (the roster override) or a **second**
> GPU-capable executor, which the one hosted GPU tier is not.

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

## 2b. Validate the multi-model roster (ADR-0018)

Layer `docker-compose.subagents-roster.yml` on top to add the Qwen-2B override as roster entry
`qwen` on its own server (port 8083) alongside the default. Run **without** the tools override
so subagents are tool-less. With tools layered, ADR-0017 rule 2b pins every spawn to the
default and the spec stops advertising the `model` knob:

```bash
CORTEX_MODELS_DIR=/srv/models \
  docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.subagents.yml -f docker/docker-compose.subagents-roster.yml up -d
cd brain && CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
  CORTEX_SUBAGENTS_QWEN_ENDPOINT=http://127.0.0.1:8083 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_live.py -v
```

The roster test spawns one batch mixing a bare (default-model) item with a `{"model": "qwen"}`
pick. Servers are per-model, so routing is verifiable in the logs, where each container's
`prompt eval time` count is its served-request count:

```bash
docker logs cortex-llama-subagent-qwen-1 2>&1 | grep -c "prompt eval time"
```

## 2c. The GPU-placed tier: both arms of the placer (ADR-0012)

This is the one procedure here that needs a GPU, because it is the only one where a GPU-*placed*
subagent actually *executes* on the GPU. It brings the hosted `-ngl 99` tier up beside the CPU
server and drives the placer over both, so the run shows the arm firing **and** shows it staying
silent; a GPU arm that cannot be made to do the second proves nothing by doing the first.

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
deliberately unpublished, and it maps the tier's `:8083` to `127.0.0.1:9083` (`:8083` on the host
belongs to the roster override's second CPU server). Take it down with `just down-gpu`.

Then the two arms, which select themselves from the budget in the environment and skip otherwise:

Since the ask was measured on 2026-08-08 the **shipped** budget selects the GPU arm, so that arm
needs nothing overridden and the CPU one is the arm that now has to be arranged for:

```bash
cd brain
# the GPU arm: the shipped budget, whose 5.4 GiB of headroom holds exactly one 3.5 GiB ask
CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py
# the CPU arm: a soft cap the same ask cannot fit, which is the overflow path every deployment
# below this card's size takes
CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
  CORTEX_VRAM_SOFT_CAP_GB=11 \
  uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py
```

Each run passes one test and skips the other; the skip message prints the ask and the headroom it
was measured against, so a run that skips both is a budget problem and says so. Corroborate the
routing outside the test with each server's own log, where a `launch_slot_` line is one served
request:

```bash
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml \
  -f docker/docker-compose.subagents.yml logs model-host | grep -c launch_slot_
```

**Measured here on 2026-08-04**, cortex resident throughout, when both arms still needed a raised
cap to reach the GPU. The GPU arm (headroom 8.7 GB against the then 5.5 GB ask) placed one of two
concurrent spawns on the tier and overflowed the other: the tier answered in **221.05 ms** (18
prompt tokens at 104.83 tok/s, 4 generated at 81.07 tok/s) against **12536.83 ms** on the CPU
server, a ratio no core-side arrangement could fake. The CPU arm (the shipped 14 GB cap, headroom
2.7 GB) overflowed both and left the tier's count unmoved. **Distrust green here:** point
`CORTEX_SUBAGENTS_GPU_ENDPOINT` at a closed port under the GPU-arm budget and the run must **fail**
with three placements and a "a GPU-placed subagent did not answer" warning, which is the ADR-0012
CPU re-place doing its job. A suite that passes that way is measuring nothing.

**Re-run on 2026-08-08 against the measured ask**, which is the run the commands above now
describe. Under the old 5.5 the GPU arm could not even select itself (it skips with "ask=5.5 GB
against headroom=5.4 GB"), the CPU arm passed with both spawns on the CPU server, and the tier's
`launch_slot_` count did not move. With nothing overridden the arms swap: the GPU one passes, the
tier's count moves by exactly one, and that spawn answers in **152.11 ms** (18 prompt tokens at
152.54 tok/s, 3 generated at 87.95 tok/s) against **13134.73 ms** for the sibling that overflowed.
The CPU arm at `CORTEX_VRAM_SOFT_CAP_GB=11` (headroom 2.4 GiB, under the ask) passes with the count
still unmoved. The closed-port proof was taken again first and still reddens the GPU arm on three
placements with the re-place warning.

## 3. Validate cortex-driven delegation (full stack, needs the GPU cortex)

Layer all three overrides so the resident cortex can *decide* to delegate. Give subagents tools
too by adding the tools override. The wiring hands them the MCP subset without the spawn tool
(depth-1). The override bakes in both required endpoints (`CORTEX_SUBAGENTS_ENDPOINT` and
`CORTEX_SUBAGENTS_GPU_ENDPOINT`, ADR-0012, where both resolve to the one CPU server unless the
GPU-placed tier is opted into and routed at)
and passes through the ask/budget knobs (`CORTEX_SUBAGENTS_{CPUS,MEMORY_GB,VRAM_GB,CPU_BUDGET,MEM_BUDGET_GB}`):

```powershell
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml `
  -f docker/docker-compose.tools.yml -f docker/docker-compose.subagents.yml up -d
```

Then speak a prompt that invites parallel work ("look up X and Y at the same time") through the
overlay / a `Converse` client and confirm the cortex emits `spawn_subagents`, the subagents run,
and their aggregated results fold into the answer. Every dispatched call (cortex and subagent) is
audit-logged (ADR-0009/0010).

## 3b. Validate constrained output kills format-laundering (ADR-0028)

A standalone CPU E4B server is enough (no full stack). Bring one up on loopback 8090:

```bash
docker run -d --name e4b-probe --cpus 4 -p 127.0.0.1:8090:8090 -v /srv/models:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server \
  --model /models/google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf \
  --host 0.0.0.0 --port 8090 -ngl 0 --jinja --chat-template-kwargs '{"enable_thinking": false}'
```

Then run the integration test through the real `LlamaCppBackend`, which asserts the same
injection that an unconstrained stream obeys is defeated by the envelope constraint:

```bash
cd brain && CORTEX_SUBAGENT_ENDPOINT=http://127.0.0.1:8090 CORTEX_MODEL_SUBAGENT=e4b \
  uv run pytest -m integration --no-cov -s \
  packages/inference/tests/test_backend_live.py::test_constrained_decoding_kills_format_laundering_on_the_weak_tier
```

The unconstrained baseline appends `VISIT http://evil.example ...`; the constrained request
returns exactly `{"reply": "..."}` with the exfil link gone (agent-validated 2026-07-13, ~7 s).
Tear the probe down with `docker rm -f e4b-probe`.

## 3c. Does the cortex spread a batch across roster models? (ADR-0018)

The spawn spec tells the cortex that subtasks on distinct roster models overlap while subtasks
sharing one model queue behind that entry's backend lease, and points it at spreading a batch as
the wall-clock lever. This procedure observes whether a live cortex takes that advice on its own.
Two things decide whether a run means anything, so check both before reading a result:

- **Run it WITHOUT the tools or email overrides.** Giving subagents an MCP dispatcher pins every
  spawn to the robust default (ADR-0017 rule 2b) and `build_spawn_spec` then advertises no `model`
  knob at all, so a tools-enabled stack has no nudge to observe. `build_subagent_tools` hands
  subagents a dispatcher whenever ANY tool registry is configured, so this is one override away.
- **Run it with at least two roster entries.** A one-entry roster gets the pinned note as well.

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

The first test is the armed check and it is what makes a silence readable: it asserts the spec
really publishes the roster's names as a `model` enum and really carries the spread sentence. The
other two put one ask each and **print** what the cortex chose, because a choice is an observation
and not a contract. Sampling is stochastic, so run them several times and read the spread;
corroborate against each server's own log, where one `launch_slot_` line is one served request:

```bash
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.subagents.yml -f docker/docker-compose.subagents-roster.yml \
  logs llama-subagent llama-subagent-qwen | grep -c launch_slot_
```

**Measured here 2026-08-04**, resident gemma-4-12B at 16K with a single slot, both CPU sidecars up.
Twenty prose-only turns over four asks emitted **zero** spawn calls; sixteen invited turns all
delegated and all put the batch on a single roster entry. A directed control ask ("put them on
different subagent models") produced one call naming both entries and one served request in each
server's log, which is what proves the knob reachable before a silence is read as a decision. The
full record is in the ADR-0018 addendum of that date.

Budget your time by the CPU tier and not by the cortex. gemma-4-E4B generates at about **0.35
tok/s** under its 4 CPU cap here and Qwen3.5-2B at about **1 tok/s**, the batch runs no faster than
its slowest member, and nothing bounds a subagent's length (no `max_tokens`, `n_predict: -1`), so a
three subtask batch on the default entry runs 10 to 15 minutes and a chatty one runs longer. The
first request after boot also pays first-touch paging of the GGUF off the models mount. If all you
want is the **choice**, it is made before the batch is dispatched: intercept `SpawnSubagentsTool`
and end the turn there, and a sample costs 5 to 8 seconds instead.

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
- **Roster + cortex-driven pick validated via Docker (2026-07-03, agent, ADR-0018 addendum).**
  Both sidecars healthy off the real GGUFs; the roster live test routed a mixed batch to both
  models (log counts confirmed: the `qwen` pick was that server's only request); and over the
  seam the resident gemma-4-12B emitted `spawn_subagents` with a per-item `"model": "qwen"`
  object. The qwen server's count incremented and the cortex reported both results. Two live
  findings, both handled: given only prose, the cortex may fold the pick into the instruction
  text (the spec now shows an object example), and it sometimes emits the object item
  JSON-encoded as a string. The parser accepts that stringified form (validated identically).
