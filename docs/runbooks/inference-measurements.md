# Runbook: measuring the GPU inference stack

What each in-turn model pass costs, how long the cortex may think, whether a model obeys the
thinking switch, and how much of a screen it can read. Every procedure here needs the stack from
[llamacpp-gpu.md](llamacpp-gpu.md) to be up; none of them runs in CI. The prompt-injection
harness is in [injection-probes.md](injection-probes.md).

All of these are agent-runnable in Docker against the real models. `-s` is required wherever a
run is described as printing its result: the printed table is the measurement, and the assertions
only check what must hold whatever the model says. `--no-cov` is required everywhere, or the
workspace's 100% coverage threshold fails the run.

## What the history recap keeps and what it costs

`packages/inference/tests/test_history_recap_live.py` is the measurement behind
`CORTEX_HISTORY_SUMMARY`. It takes about four minutes:

```
cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  uv run pytest -m integration --no-cov packages/inference/tests/test_history_recap_live.py -s
```

Five parts. The first asks a question whose answer dropped out of the window, once through the
character-budget window that ships and once through the summarizing one, printing what each sent
the model, the fold's cost cold and cached, both replies and their times to first token. The
second stages a conversation so the boundary moves five times and reports how often the fact
survived. The third prices the fold's request against the unbounded one that shipped before it.
The fourth runs the shipped token cap with thinking left on, which is the failure the cap and the
switch ship together to avoid. The fifth reruns the staged conversation at the shipped fold
floor and counts how many boundary moves cost a model pass.

Read the fold's wall time against the server's own counters:

```
docker logs cortex-model-host-1 | grep "eval time ="
```

`CORTEX_HISTORY_SUMMARY` defaults to on. Set it `false` for a deployment that would rather drop
old turns than wait for a fold. `CORTEX_HISTORY_RECAP_MIN_CHARS` (default 2000, clamped to the
character budget) is how much newly dropped conversation is worth a fold. The numbers are in
[history recap](../readings/history-recap.md).

## What a fold costs when several streams overlap

`packages/orchestrator/tests/test_fold_under_load_live.py` runs three streams at once, which is
what checks that the fold releases the GPU lease before the reply asks for it. It needs the base
file's Redis as well, so use `just up-gpu` rather than `just up`: the base file alone publishes no
`127.0.0.1:8080`, and running it over a live GPU stack recreates `brain` from the base definition
and drops `CORTEX_INFERENCE_BACKEND=llamacpp`. It takes about two minutes:

```
cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  uv run pytest -m integration --no-cov -s \
  packages/orchestrator/tests/test_fold_under_load_live.py
```

Five parts. The first runs a solo turn as a baseline and then three concurrent `Converse`
streams, each on its own session with its own planted fact, and prints every acquisition of the
GPU lease with the moment it was asked for, granted and released, and whose hold it waited
behind. The second runs two turns of one session at once, the only way to make two folds race for
one recap key. The third stalls a reader mid-reply at a one-credit bound and times what the next
stream's fold waits. The last two are the controls: a fold made to hold the lease across the
reply, which must deadlock and be reported as a leak rather than merely time out, and the same
two streams run one after the other, which must report zero contention. A run that reports no
contention fails deliberately, because streams that never overlap have measured nothing. The
numbers are in [ranked recall](../readings/ranked-recall.md).

## What the session title and the recall rank cost

Both passes go through `drain_text`, which keeps the reply and drops the reasoning. Both send
`thinking=False` and a cap sized from their own answer:

```
cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  uv run pytest -m integration --no-cov packages/inference/tests/test_session_title_live.py -s

cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \
  CORTEX_MEMORY_EMBEDDER_ENDPOINT=http://127.0.0.1:8081 \
  uv run pytest -m integration --no-cov packages/inference/tests/test_rerank_judge_live.py -s
```

The title run needs the GPU stack alone and takes about half a minute. The rank run also needs
the memory override's CPU embedder on `:8081` and takes about two minutes. The same
`docker logs cortex-model-host-1 | grep "eval time ="` says where the wall time went.

What this means for an operator: `CORTEX_GENERATE_TITLES=1` costs about a third of a second per
new session, and `CORTEX_MEMORY_RECALL=judge` costs about a second per recalling turn.
`CORTEX_MEMORY_RECALL_AUDIT=1` prints the basis that ranked each recall, so a fall back to the
cosine is visible rather than silent. `judge` is the default. A GPU-less brain should be told
`CORTEX_MEMORY_RECALL=raw` rather than left to fall back on every turn: with the model
unreachable the policy still answers, but it falls back on each one.

The whole-turn version of that measurement runs as `just turn-cost`, three blocks in A/B/A order
with the brain recreated between them and the interval reported by `scripts/contrast.py`. It
takes roughly 14 minutes. Procedure and settings: [memory-pgvector.md](memory-pgvector.md);
numbers: [ranked recall](../readings/ranked-recall.md).

## How long the cortex may think, and what each setting costs

`CORTEX_REASONING_BUDGET` is a token budget for the trace. llama.cpp reads it as
`--reasoning-budget N`, injects the end of thought at the count, and lets the completion finish
normally, so the model is not cut off mid-answer. Reproduce it against the cortex tier directly,
one open question per setting, watching the stream:

```
docker run -d --name budget-probe --gpus all --network host -v $CORTEX_MODELS_DIR:/models:ro \
  ghcr.io/ggml-org/llama.cpp:server-cuda --model /models/$CORTEX_MODEL_FILE_CORTEX \
  --host 0.0.0.0 --port 8080 -ngl 99 --ctx-size 16384 --parallel 1 --jinja \
  --reasoning-budget 128
curl -sN http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"cortex","stream":true,"messages":[{"role":"user","content":"What makes a good API design?"}]}'
```

Measured 2026-08-17 on the shipped cortex tier (gemma-4-12B QAT q4_0, `-ngl 99`, `-c 16384`,
`--jinja`, the ghcr `server-cuda` image, build `b9870-2d973636e`, on the 24 GB card), three
ordinary open questions, one run each:

| `--reasoning-budget` | trace | first word | reply | whole turn | finish |
| --- | --- | --- | --- | --- | --- |
| unset (shipped) | 2323 / 2996 / 2507 chars | 10.1 / 12.6 / 11.0 s | 4408 / 4712 / 4131 chars | 31.3 / 33.2 / 26.8 s | `stop` |
| `512` | 2003 / 1963 / 2004 chars | 8.4 / 9.2 / 8.5 s | 4189 / 4659 / 4170 chars | 25.7 / 29.4 / 24.6 s | `stop` |
| `128` | 507 / 483 / 536 chars | **1.7 / 2.6 / 2.5 s** | 4558 / 4450 / 4201 chars | 20.9 / 20.4 / 18.9 s | `stop` |
| `0` | none | 0.2 s | 4483 chars | 19.0 s | `stop` |

Four readings decide how to set it.

1. **The wait is the trace and the budget is a dial on it.** The first word moves with the count,
   and the reply stays the same size at every count.
2. **The reply still ends on its own.** Every count finished `stop`, and a trace cut mid-sentence
   at 128 was followed by a full coherent answer.
3. **It makes `CORTEX_REPLY_MAX_TOKENS` usable with thinking on.** A cap of 512 against an
   unbounded trace returned an empty reply 3 of 3; under a budget of 128 the same cap returned
   1488 and 1561 characters of answer.
4. **Nothing else about the tier changes.** A per-request `enable_thinking: false` still yields
   no trace under a budget (0 chars, 0.34 s to the first word), and a trace cut at the count was
   followed by a well formed `read_file` call finishing `tool_calls`.

These price the wait and say nothing about answer quality: four multi-step questions with one
right answer each came back right at unbounded, `128` and `0`. Start at `512` on a tier a user
reads and check a lower count against your own hard questions.

## Whether your own model obeys the thinking switch

Turning thinking off per request asks the chat template to skip the deliberation. Whether the
model then does depends on the model and on the shape of the request: on the shipped cortex it
holds both plain and under a `response_format`, and on the shipped subagent model it holds plain
and fails under a `response_format`. The cause is the chat template, not the model. With thinking
off the cortex's template opens and closes an empty thought in the prompt while the subagent's
drops a marker, and the grammar llama.cpp builds for a `response_format` leaves the thought open
either way. Rates and the whole lineup are in [thinking switch](../readings/thinking-switch.md).

Ask your own tier, with a server started with **neither** reasoning flag:

```
cd brain && CORTEX_THINKING_ENDPOINT=http://127.0.0.1:8080 \
  CORTEX_THINKING_REPEATS=5 CORTEX_THINKING_OUT=../measurements \
  uv run pytest -m integration --no-cov -s \
  packages/inference/tests/test_thinking_switch_live.py
```

Keep `CORTEX_THINKING_REPEATS=5` before acting on the result: the cell that decides this split 4
to 1 the first time it was drawn, so one draw can say either thing. Then publish the reading
rather than reading it by eye. The run writes one sample per tier and prints the line to paste:

```
just switch-tail measurements/switch-<model>.json
```

That compares the rendered prompt against the cells the same run drew and says whether this
tier's template still predicts its own constrained result. **Read the prompt's tail, not the
difference between the two renderings.** Both models change their prompt when the switch is sent
and only one changes it where it counts: on build `b10666-4e97ac86e` the E4B's two prompts are
194 and 162 characters and drop a whole `<|think|>` system turn at the front while ending byte
identically at `<|turn>model\n`, and the Qwen3.5-2B's grows from `<think>\n` to
`<think>\n\n</think>\n\n` at the end.

The command's second line names the engine build, the model file and the context size the server
reported on `GET /props`. Exit 0 published the agreement. Exit 1 is either a refusal to publish
(a control that never deliberated, a cell drawn fewer than five times, or a switched tail in a
chat-template format this reader does not recognise) or the prediction breaking on this tier,
which is news about the record rather than about your deployment. Nothing in the stack reads this
answer, so a failure here is a document to fix, not a deployment to stop.

If the switch does nothing on your model, set `CORTEX_REASONING_BUDGET=0` or a count instead, so
the engine ends the thought whatever the template was told, which is what every subagent server
here already does. The brain also says so at runtime, one `WARNING` per side call from
`cortex_core.drain` naming the `model` and the `chars` of trace it dropped unread.

To check that a per-request budget holds on the request shape the switch loses, against a server
started with neither reasoning flag:

```
cd brain && CORTEX_TRACE_ENDPOINT=http://127.0.0.1:8082 CORTEX_TRACE_REPEATS=5 \
  uv run pytest -m integration --no-cov -s \
  packages/inference/tests/test_trace_budget_live.py
```

Measured on the shipped subagent model at `-ngl 0` on `b10666-4e97ac86e`, a cap of 256 and a
constrained reply: the switch alone deliberated on 17 of 20 draws and returned an empty capped
reply on every one; with `trace_tokens=0` the trace stopped on 20 of 20. Forcing the end of a
thought happens after its start tag, so a fragment of that tag can survive into the answer: one
draw in 58 came back as `{"reply": "thought"}`. Re-measured 2026-09-07 at a hundred draws a cell
on builds `b10680-d7bd3bfca` and `b10666-4e97ac86e` at `-ngl 99`, no draw of the 600 leaked.
Expect not to see it, and read the printed count rather than one draw.

## What the cortex can read off a screen

The two settings and what they cost are in
[llamacpp-gpu.md](llamacpp-gpu.md#the-two-settings-that-decide-how-much-of-a-screen-the-cortex-reads);
the measurements are in [vision capture](../readings/vision-capture.md). The re-runnable part is
`packages/inference/tests/test_image_budget_live.py`, which checks the saturation, checks that
the budget raises it, proves the abort by removing the micro-batch from the shipped argv, and
includes the window-crop case with its corpus. Run it when llama.cpp is upgraded or the cortex
model changes. It needs the `cortex-model-host` image built, because the base tag moves:

```
cd brain && CORTEX_MODELS_DIR=<the host dir holding the GGUFs> \
  uv run pytest -m integration --no-cov -s packages/inference/tests/test_image_budget_live.py
```

The crop case alone is `-k window_crop`, about 80 s once the model is loaded. If the server never
becomes healthy while `docker logs` shows it serving, the published loopback port is not
reachable from this shell (some WSL networking modes route `127.0.0.1` past the Linux
`docker-proxy`); add `CORTEX_PROBE_HOST=container` and the probe asks the daemon for the
container's own address.

The byte half needs no GPU and no model, only the body's own downscaler and encoder. Re-run it
when the capture edge, the byte ceiling or the downscale filter moves:

```
cd body && cargo test -p body-core --test capture_bytes --release -- \
  --ignored --nocapture --test-threads=1
```

## Whether a reworded model-read text still works

`packages/inference/tests/test_model_read_wording_live.py` draws a text a model reads in its old
and its new wording on the same seed, on each tier that reads it: the recap preface under the
injection attacks and a fact question, and the spawn tool's model note with the default subagent's
description on two delegation asks. It starts its own server as the injection probes do, prints a
line per draw and a result per row, and reads the card once per row. `CORTEX_WORDING_DEADLINE`, in
seconds since the epoch, skips a row whose estimate would end after it. Its rows and the counts
that decide them are fixed in [R-707](../refinements/tasks/707-model-read-texts-keep-banned-words.md).

```
cd brain && CORTEX_MODELS_DIR=/srv/models uv run pytest -m integration --no-cov -s \
  "packages/inference/tests/test_model_read_wording_live.py::test_each_text_draws_alike_in_its_old_and_new_wording[gemma-4-12B]"
```
