# Runbook: the CPU subagent server

Bring up the subagent `llama-server`, choose which model it serves, and understand every bound a
delegated run is held to. The procedures that check delegation end to end are in
[subagents-validation.md](subagents-validation.md). Decisions:
[ADR-0010](../adr/ADR-0010-subagents.md) (delegation),
[ADR-0012](../adr/ADR-0012-resource-governance.md) (placement and budgets),
[ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md) (the roster).

Subagents are opt-in, so CI runs without them. Placement is GPU-first with CPU overflow, and by
default the compose files run one CPU server with both placement targets pointed at it, so a
GPU-placed subagent still executes on the CPU and nothing here needs a GPU. A real GPU-placed
executor exists as an opt-in tier of the `model-host` sidecar
(`CORTEX_MODEL_FILE_SUBAGENT_GPU`, `-ngl 99` on `:8083`); routing to it is the separate step of
setting `CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`.

## Prerequisites

Docker Desktop with the WSL2 backend, and the subagent GGUF on the model mount. On this machine
the models are at `/srv/models` inside WSL (Windows `D:\Software\AI\...`), so set
`CORTEX_MODELS_DIR=/srv/models`; the compose default of `./models` is for Windows-side Docker,
which resolves `D:`.

`CORTEX_MODEL_FILE_SUBAGENT` names the artifact, defaulting to
`google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf`. **The override changes what a
tool-less subagent answers, not only how fast.** All five entries were measured through the
shipped constrained reply path at 288 seeded runs each, 1440 in all, and they answer the same
narrow work between 42 and 77 of 96 ([reply envelope](../readings/reply-envelope.md), 2026-09-11):

| override | answers, shipped constrained path | the thing to know |
| --- | --- | --- |
| `gemma-4-E4B_q4_0-it.gguf` (default) | 77 of 96, against 71 without the shipped sentence | the model every sentence and flag here was tuned on; hands the report back on 14 of 32 summarizations |
| `unsloth/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf` | 70 of 96, against 86 without it | the largest weights of the five; hands the report back on 24 of 32 summarizations |
| `unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf` (roster alternate) | 59 of 96, against 70 without it | the cheap override, weaker against injection; hands the report back on 27 of 32 summarizations |
| `gemma-4-E2B_q4_0-it.gguf` | 54 of 96, against 89 without it | hands the report back on 31 of 32 summarizations, and loses answers to a reasoning channel a delegated run drops |
| `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf` | 42 of 96, the same without it | answers an extraction on 6 draws of 32, and its own unconstrained lookup falls under the floor |

Prefer the default. The E2B and the 0.8B are the two to override to last: the E2B loses answers to
a channel nobody reads, and the 0.8B mostly hands the instruction or the report back. A report
handed back as a summary is the shipped sentence's doing on every entry, and it arrives `ok=True`.

**No check holds those numbers, and four things move them**: the GGUF, the llama.cpp build serving
it, `CORTEX_SUBAGENTS_MAX_TOKENS`, since a run cut at the cap counts as a non-delivery whatever its
text held, and the `REPLY_INSTRUCTION` sentence itself. Re-measure with
`brain/packages/orchestrator/tests/test_envelope_cost_live.py` and publish with
`just envelope-floor`, one subtask shape at a time: a control cell refused on one shape withholds
the comparison for every shape passed with it. Set `CORTEX_ENVELOPE_SEED` so the two conditions of
each draw pair and the run can be repeated by number, and `just envelope-pairs` counts the cells
two seeded runs drew identically. A seed reproduces a completion only against the same
prompt-cache state, so a first draw on a freshly loaded server pairs with a run started the same
way and not with a warm one.

**Which model a running stack is on is read off the server, never off this file or the brain.**
Each subagent server publishes on loopback, and `GET /props` names the artifact in `model_path`
and again in `model_alias`; `GET /v1/models` reports the same string as the model's `id`.

```bash
curl -s http://127.0.0.1:8082/props   # the default entry; :8083 is the roster alternate
# -> ... "model_path":"/models/google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf" ...
```

That path is `CORTEX_MODEL_FILE_SUBAGENT` joined under `/models`, so it says which row you chose
and nothing more: a requantized file at the same path reads the same, and the server's own
`digest` field in `/v1/models` is empty on this build. The brain never reads it.

**Which build a server runs is logged by the brain.** Every streamed chunk names the server's build
as `system_fingerprint`, the same string `GET /props` names as `build_info`. The brain logs it the
first time a model's completion arrives and again whenever that model's build changes, for this
tier and every other one it streams from:

```
INFO:cortex_inference.backend:model now served by engine build build=<the system_fingerprint> endpoint=<the leased endpoint> model=<the model asked>
```

The build behind a logged run is the one on the latest such line for its model. The embedder has
no such line, because an embeddings reply names no build.

## Bring up the server

```bash
CORTEX_MODELS_DIR=/srv/models \
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.subagents.yml up -d redis llama-subagent
# wait for health (gemma-4-E4B loads in ~38 s on CPU; the Qwen-2B override in ~15 s):
curl http://127.0.0.1:8082/health   # -> {"status":"ok"}
```

`-ngl 0` keeps it CPU-only. `--jinja` enables the tool-capable chat template, so tools-enabled
subagents can call functions. `--parallel` (`CORTEX_SUBAGENTS_PARALLEL`, default 2) gives each
admitted subagent a server slot, so keep it near `CORTEX_SUBAGENTS_CPU_BUDGET` divided by
`CORTEX_SUBAGENTS_CPUS`, which is the effective admission concurrency under the soft budget. Set
the per-entry request no larger than the budget: an entry that could never be admitted fails the
brain at startup rather than at delegation time. `--threads` reads
`CORTEX_SUBAGENTS_CPU_BUDGET`, the same variable the container's `cpus` cap reads, so the server
runs one thread per CPU of its quota rather than one per hardware thread it can see. llama-server
takes the floor of that float, so a budget of 2.5 starts 2 threads and a budget under 1.0 floors
to 0, which the engine reads as its own default of one thread per hardware thread.

## The bounds a delegated run is held to

**A silent stream is bounded, a slow one is not.**
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` (default 600 s) is how long a subagent's stream may send
nothing before the spawn fails with a message rather than holding its admission and every queued
peer behind it. It bounds the gap between
chunks and never the length of a generation, so raising `CORTEX_SUBAGENT_CTX_SIZE` or handing a
subagent a long file does not need it raised; a slower CPU than this one might. The default is
about twice a whole subtask measured here. That subtask figure is an interval rather than a point,
and what sets it is what else the host is doing: the same shape took 222.8 to 324.3 s across a
full batch on an idle box and 1736.6 s beside a saturated one, and even the saturated run's
slowest stretch put a chunk every 14 s.

**A subagent that keeps talking is bounded in both of its units.**
`CORTEX_SUBAGENTS_MAX_TOKENS` (default 1024) is how far any one of a run's completions may decode,
and `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default 2400 s) is the deadline on the whole run, the tool
dispatches between its completions included. This is the failure the stall ceiling does not cover:
a model in a repetition loop is never silent, so it holds its admission and its entry's lease
while looking healthy. Reaching either is an `ok=False` result whose text names the bound. A
capped run reads as cut whichever limit did it, this cap or the server's own context window, which
the wire cannot tell apart; the refusal quotes this setting only when the deployment set one.
Neither has an off switch, and the deadline must stay above `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` or
the brain fails to start, since a wedge reported as a runaway loses the CPU re-run a stall gets.

The cap is about five times the longest narrow reply measured here (199 tokens, a summarization)
and the deadline four times the longest whole subtask (623.8 s, the same one). Forty draws of the
tool-less shape answer in 256 to 429 decoded tokens, and every run measured reaching the cap
reached it on a narration or a reasoning trace rather than on a long answer. In decoded tokens the
run deadline admits at least 7200 on a saturated host and about 20,000 to 30,000 on an idle one,
against the per-slot context's 4096 less your prompt, so the cap binds first at either load and
the context is what a raised cap runs into. No check fails a deployment whose cap and deadline
disagree: the three orderings the brain rejects at boot all compare seconds with seconds, and this
pair compares a count with a time whose exchange rate is your tier's decode rate on the day. Read
[generation bounds](../readings/generation-bounds.md) before retuning either.

One more bound sits inside the run rather than under it.
`CORTEX_TOOLS_CALL_TIMEOUT_S` (default 60 s) bounds one tool dispatch, and a delegated loop
dispatches tools between its completions. A
dispatch spends that bound several times over, once listing the tools the run advertises, once
more removing the ones a subagent may not have, once more routing across an aggregate, and once in
the call, so the brain rejects a deployment where a whole dispatch may outlast the run that made
it.

**Queuing for room is bounded too, and generously.**
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 7200 s) is how long a spawn may wait for the soft
budget to free room before it comes back refused, with the bound named in the message. It has to clear two things and the larger sets it.
The first is any legitimate wait these defaults produce, measured on a live full batch: 8 spawns
against `CPU_BUDGET=4.0` and `CPUS=2.0` admit two at a time, and with the GPU path open the pair
overlaps and the last spawn is admitted 893.2 s in, while with it shut the pair runs one after the
other and the same spawn waits 1624.6 s. The second is the longest one task can hold the room that
queue is waiting for, which is two whole run deadlines, since a GPU-placed run whose backend fails
is re-run once on the CPU inside the same admission. At the shipped deadline that is 4800 s, so
the bound is three deadlines: the two a task can spend plus one of margin. The brain fails to
start if the wait does not outlast that hold, and the refusal names the hold it computed. Zero is
legal and means never queue at all.

**Admitted is not the same as concurrent.** Each roster entry holds one `LlamaCppBackend` per
placement target, and a backend holds its model lease for the whole stream, so two spawns of the
same entry on the same target run one after the other however many the budget admits. Measured on
the Qwen-2B override: two concurrent spawns took 4.8 s through two backend objects and 10.0 s
through one. What one entry does get is an overlap of exactly two, and only while its admitted
pair straddles the two targets. Raising `CPU_BUDGET` past that pair buys queue depth rather than
throughput; more than two at once needs distinct roster entries or a second GPU-capable executor.

## Reasoning is off, by two flags

Both model families in the lineup are reasoning models, and unbounded thinking on CPU is minutes
per call, so the compose command sets `--chat-template-kwargs '{"enable_thinking": false}'` and
`--reasoning-budget 0`. Neither flag covers the lineup alone, which is why both are there. The
kwarg is a chat-template variable, and the E4B model's template reads it on a plain request and
stops mattering the moment a request makes the model want to deliberate, which a `response_format`
does: measured, the constrained shape decoded 200 tokens of pure trace with the kwarg set at the
server, at the request, and at both. `--reasoning-budget 0` is the engine's own flag and reaches
it, taking the same request to a reply from 1.0 to 2.4 s in with no trace at all. Which of the two
stops a tier deliberating depends on the model, and the two subagent candidates here are on
opposite sides of it, so keep both flags on every subagent server: the difference is a property of
a chat template, and the argv outlives whichever model a deployment names.

**So a cap refusal on ordinary narrow work is a missing flag before it is a runaway.** Read the
argv (`docker inspect -f '{{json .Args}}' cortex-llama-subagent-1`) before touching
`CORTEX_SUBAGENTS_MAX_TOKENS`. A correctly flagged server can still lose a narrow summarization
the same way, though: at the request a delegated run really sends, 13 draws in 76 wrote 1582 to
4078 characters into the reasoning channel and 8 came back with an empty reply cut at the cap. Two
things separate that from the missing flag. 11 of the 13 traces open with a fragment of a channel
marker (`</channels>`, `h</cha>`, a bare `>`) rather than with deliberation, which is what to grep
a trace for, and adding the engine's per-request `reasoning_budget_tokens: 0` on top of the flags
does not close it. What does close it is the model: no Qwen entry of the lineup writes to that
channel at all, and every one of their cap refusals is a numeric runaway inside `reply` instead.

On the Qwen entries the symptom to look for is the opposite one: a short, fast, successful
delegated answer that did not do the work. 32 of the roster alternate's 37 constrained
non-deliveries arrive `ok=True`, and on `Qwen3.5-0.8B` that is the usual case rather than the
exception. Reading the delegated answer is the operator's check either way, because a tier asked
to judge its own reply cannot tell an answer from a non-answer.

To check a tier by hand, start one standalone CPU server with the same flags and thread count:

```bash
docker run -d --name e4b-probe --cpus 4 -p 127.0.0.1:8090:8090 -v /srv/models:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server \
  --model /models/google/gemma-4-E4B-it-qat-q4_0-gguf/gemma-4-E4B_q4_0-it.gguf \
  --host 0.0.0.0 --port 8090 -ngl 0 --threads 4 \
  --jinja --chat-template-kwargs '{"enable_thinking": false}' \
  --cache-ram 0 \
  --reasoning-budget 0
```

Tear it down with `docker rm -f e4b-probe`. What to run against it is in
[subagents-validation.md](subagents-validation.md).

## Every refusal writes one line

A refused spawn does not fail the turn: the runner turns it into an `ok=False` result the cortex
reads and answers around, so nothing in the overlay says a subtask was dropped and the tool audit
records the aggregate's size rather than its text. The brain's own log is what lasts, one
`WARNING` from `cortex_core.runner` per refusal:

```
WARNING:cortex_core.runner:a spawn was refused before it ran model=<the roster entry that would have run> reason=<which refusal, in the scheduler's own words> task_id=<task id>
```

`reason` is the whole of the diagnosis and says which of the three refusals this was: a request no
budget could ever hold, a pool draining for a model handoff, or a queue that outlasted the wait
above. The formatter quotes a value containing whitespace and every one of these reasons does, so
`grep -c 'reason="waited'` over the brain's log counts the third refusal alone. The fields print
in name order whatever order the call site wrote them in.

## Teardown

```powershell
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.subagents.yml down
```
