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
  **The override changes what a tool-less subagent answers, not only how fast.** All five entries of
  the subagent row have been measured through the constrained reply path at 288 runs each, 1440 in
  all (ADR-0028 lineup and row addenda), and they answer the same narrow work between **66 and 94 of
  96**:

  | override | answers, shipped constrained path | the thing to know |
  | --- | --- | --- |
  | `gemma-4-E4B_q4_0-it.gguf` (default) | 90 of 96 | the pick every sentence and flag here was tuned on |
  | `unsloth/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf` | 94 of 96 | the envelope costs it nothing measurable, but it is the row's largest weights |
  | `unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf` (roster alternate) | 83 of 96 | the cheap override, weaker against injection |
  | `gemma-4-E2B_q4_0-it.gguf` | 84 of 96, against 90 without the shipped sentence | loses a one-fact lookup on 8 draws of 32 to a reasoning channel a delegated run drops |
  | `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf` | 66 of 96, against 70 without it | answers an extraction on 12 draws of 32, the worst cell measured anywhere in this tier |

  Prefer the default. The E2B and the 0.8B are the two entries to override to last, for different
  reasons: the E2B loses answers to a channel nobody reads, and the 0.8B mostly hands the
  instruction back.

  **What keeps those numbers true, since nothing holds them.** Each is a dated reading of one
  artifact on one engine build at one cap under one appended sentence, judged by hand once per
  sweep, and four things move it: the GGUF the variable above names, the llama.cpp build serving it
  (each measurement names its image by digest), `CORTEX_SUBAGENTS_MAX_TOKENS`, since a run cut at
  the cap counts as a non-delivery whatever its text held, and `REPLY_INSTRUCTION` itself. Re-measure
  with `brain/packages/orchestrator/tests/test_envelope_cost_live.py` and publish with
  `just envelope-floor`, whose own metric is deliberately weaker than the rates tabled here
  ([R-507](../refinements/tasks/507-the-floor-sees-only-the-failures-a-machine-can-name.md)). **This
  table is on purpose the only place those rates live.** The description the cortex picks a roster
  entry by carries a speed and a hazard and no rate, because a rate advertised there would be read
  by a chooser that can see none of the four conditions above and cannot check which artifact the
  entry is serving (ADR-0018 addendum of 2026-08-30, and ADR-0028's of the same date for the sibling
  decline about the sentence).

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
> raised; a slower CPU than this one might. The default is about twice a whole subtask measured
> here, the CPU tier being the slow one on purpose (ADR-0005 stall-ceiling addendum). That subtask
> figure is an interval and not a point, and what sets it is what else the host is doing: the same
> shape read 222.8 to 324.3 s across a full batch on an idle box and 1736.6 s beside a saturated
> one. The ceiling is comfortable either way, since what it bounds is one silent gap between chunks
> and not a whole subtask, and even the saturated arm's slowest stretch put a chunk every 14 s.

> **A subagent that keeps talking is bounded too, in both of its units.**
> `CORTEX_SUBAGENTS_MAX_TOKENS` (default 1024) is how far any one of a run's completions may
> decode, and `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default 2400 s) is the deadline on the whole run,
> the tool dispatches between its completions included (ADR-0005 total-cap addendum). This is the
> failure the ceiling above cannot see: a model in a repetition loop is never silent, so it holds
> its admission and its entry's lease exactly as a wedged stream used to while looking healthy the
> whole way. Reaching either is an `ok=False` result whose text names the bound, so the cortex
> reads a refusal it can act on rather than a fragment that looks like an answer. **The token half
> reports itself only since the finish reason crossed the inference port** (ADR-0005 finish-reason
> addendum): before that the deadline said which bound it was and a completion cut at the cap came
> back as a short answer, because llama-server said `finish_reason: "length"` on the wire and
> nothing carried it inward. A capped run now reads as cut whichever limit did it, this cap or the
> server's own context window, which the wire cannot tell apart; the refusal quotes this knob only
> when the deployment set one. Neither has an
> off switch; the deadline must stay **above** `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, and the brain
> refuses to start otherwise, since a wedge reported as a runaway loses the CPU re-run it deserves.
> The numbers are this hardware's, measured over five subtask shapes on the shipped entry, all five
> of them on the **tools-enabled** shape, so on a subagents-only stack the cap is confirmed rather
> than derived: forty draws of the tool-less shape answer in 256 to 429 decoded tokens, and every
> run measured reaching the cap reached it on a narration or a reasoning trace rather than on a long
> answer (ADR-0005 ceilings addendum). **Two bounds sit above the cap and the per-slot context is
> the looser of them.** In decoded tokens the run deadline admits about 425 on a saturated host and
> about 3200 on an idle one, against the context's 4096 less your prompt, so on a busy box the
> deadline fires before the cap can and raising `CORTEX_SUBAGENTS_MAX_TOKENS` there buys nothing.
> **Nothing refuses a deployment whose cap and deadline disagree, and that is a decision rather
> than a gap** (ADR-0005 independence addendum). The three orderings the brain does refuse at boot
> all compare seconds with seconds; this pair compares a count with a time, the exchange rate is
> your own tier's decode rate on the day, and it moved by a factor of seven here between an idle
> host and a busy one. So the conversion is yours: read the ceilings addendum's table before
> retuning either, and expect the cap to bind on a quiet box, the deadline on a loaded one, and the
> deadline on both once your subagents hold tools, since the cap is spent per completion and a
> tool-using run has several.
> The cap
> is about five times the longest narrow reply (199 tokens, a summarization) and the deadline four
> times the longest whole subtask (623.8 s, the same one), the extra doubling covering a tool-using
> run whose loop spends on several rounds what that measurement spent on one completion. A full
> batch later put the same shape at 222.8 to 324.3 s a subtask, so the whole-subtask figure is an
> interval and the deadline is four times its upper end; taken from that batch instead it is four
> times the longest a spawn was measured holding its admission there, 595.2 s, which lands on the
> same number. The
> deadline also lands between the two bounds either side of it, above the stall ceiling and below
> `CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, and the brain refuses to start on either ordering broken, so
> a deployment where a run holds its admission for as long as a peer will queue for that admission
> is one that never boots. A wait of **zero** is the exception and passes beside any deadline, that
> being the setting where nothing queues and so nothing waits on a run at all. What the boot check
> compares is the whole **hold** rather than one attempt's deadline: a GPU-placed run whose backend
> fails is re-run once on the CPU inside the same admission under a deadline armed fresh, so along
> that one path a task holds its room for two deadlines, and it is twice the deadline the wait has
> to outlast. The refusal names the hold it computed, so an operator who tightens the wait under it
> reads the product rather than either number alone.
> One more bound sits inside it, beside the stall ceiling rather than under it:
> `CORTEX_TOOLS_CALL_TIMEOUT_S` (default 60 s) bounds one tool dispatch, and a delegated loop
> dispatches tools between its completions. A dispatch spends that bound several times over, once
> listing the tools the run advertises, once more stripping the gated ones, once more routing
> across an aggregate, and once in the call, so the brain refuses a deployment where a whole
> dispatch is allowed to outlast the run that made it (ADR-0009 ordering addendum), that costing
> the whole run instead of the one call and reporting a wedged sidecar as a subtask that would not
> stop talking.
> **Both of those readings are of the tools-enabled shape, and this file's own stack ships the
> other one.** A subagents-only bring-up hands its subagents no dispatcher, so `constrain_output`
> is on and every reply is decoded into the fixed `{"reply": ...}` envelope (ADR-0028). Measured
> paired over the same report bodies, that shape costs **1.01 to at least 2.36 times** the tokens
> of the same subtask raw, 550 to at least 1024 against 366 to 544, and one narrow summarization in
> three reached the cap and came back refused. It is not writing more: its replies are **shorter**.
> The tokens went to a reasoning trace, and a delegated run drops every reasoning delta unread.
> **That is fixed in this file's own command block, and the fix is a server flag, so a subagent
> server started without it still has it** (ADR-0005 thinking-lever addendum). The pair to check on
> any subagent tier's argv is `--chat-template-kwargs '{"enable_thinking": false}'` **and**
> `--reasoning-budget 0`: the kwarg is what a chat template reads on a plain request, and the
> budget is what reaches a request carrying a `response_format`, the shape the kwarg was measured
> to stop holding on (ADR-0005 switch-is-advisory addendum) and the shape every tool-less subagent
> reply is decoded in. With only the kwarg, the summarization body above spent 200 decoded
> tokens with **no reply text in them at all** and came back a refusal; with both, the same body at
> the same cap answered from 17.5 s in, 50 tokens, finished rather than capped, with no trace.
> **So a cap refusal on ordinary narrow work is the missing flag before it is a runaway**; read the
> argv (`docker inspect -f '{{json .Args}}' cortex-llama-subagent-1`) before touching
> `CORTEX_SUBAGENTS_MAX_TOKENS`. If a tier really does need more room, keep the cap under **both**
> bounds above it and not just the roomier one: the per-slot context
> (`CORTEX_SUBAGENT_CTX_SIZE` divided by `CORTEX_SUBAGENTS_PARALLEL`, 4096 at the
> defaults) less the prompt, and what `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` can decode at your tier's own
> rate, which is the smaller of the two here and is about 425 tokens on a saturated host. Read the
> ADR-0005 envelope and ceilings addenda before retuning anything
> permanently. The wire is **not** silent while a trace runs: the reasoning arrives as its own
> deltas, 200 of them over 156.3 s with a longest gap of 3.46 s, so the stall ceiling is nowhere
> near firing and a wedged server is not what this looks like.
> **With both flags on, that shape stopped spending the cap and started losing the answer
> instead**, which no bound reports (ADR-0005 answer addendum). Read over 160 runs, four report
> bodies at ten draws each: the unconstrained shape, which is what a tools-enabled subagent decodes
> into, returned a summary on **40 of 40** draws and the tool-less envelope on **10 of 40**. The other thirty are well-formed replies that narrate the
> subtask instead of doing it, "The user wants a comprehensive summary of the provided site report"
> and the like, and they come back `ok=True` at 29 to 142 decoded tokens with a median of 43, so
> nothing in the logs, the stop reason or the refusal text marks them. The cause is not the schema
> and cannot be fixed with one: this engine renders the same prompt with a `response_format` and
> without it, so the model never reads the envelope.
> **That is repaired, and the repair is a sentence the runner appends to every constrained
> subtask** (`REPLY_INSTRUCTION`, ADR-0028 instruction addendum). Re-measured over 288 runs at three
> subtask shapes, the same four bodies at eight draws each, the envelope with that sentence answers
> **90 of 96** against **72 of 96** without it, and the whole of the difference on the shape that
> narrates: a summarization goes from 9 of 32 to 29 of 32 while an extraction and a lookup, which
> never narrated, sit at 31 and 30 of 32 against 32 and 31. **What the symptom now looks like has
> changed with it.** Before the sentence, the thing to look at was a short, fast, successful
> delegated summary, since the failures were quiet; after it, **not one** of 96 constrained runs
> failed quietly and all six failures were cap refusals whose answer had gone to the reasoning
> channel a delegated run drops, at 8 draws in 96 against 1 in 96 without the sentence
> ([R-479](../refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md)). So on a
> current stack a cap refusal on narrow work is the flags first, this second, and a runaway third.
> **That second cause is now measured on a correctly flagged server and it is not rare**
> (ADR-0005 firm-prompt addendum): at the request a delegated run really sends, 13 draws in 76 wrote
> 1582 to 4078 characters into the reasoning channel and 8 came back with an empty reply cut at the
> cap, on two of the four report bodies. So a tier whose argv reads right can still lose a narrow
> summarization this way, and **checking the argv does not rule it out**. Two things separate it
> from the missing flag above: 11 of the 13 traces open with a fragment of a channel marker
> (`</channels>`, `h</cha>`, a bare `>`) rather than with deliberation, which is what to grep a
> trace for, and adding the engine's per-request `reasoning_budget_tokens: 0` on top of the flags
> does not close it, so there is no knob here to reach for. What does close it is the pick: no Qwen
> entry of the lineup writes to that channel at all.
> A plan arriving in `reply` as an `ok=True` answer is rarer but still possible and still silent,
> which is [R-480](../refinements/tasks/480-a-narrated-reply-arrives-as-an-answer.md).
> **Every number in this note is the default pick's**, and the pick is one env var away from being a
> different one (ADR-0028 lineup addendum). On the Qwen roster alternate the quiet failure never
> went away, 8 of its 13 constrained non-deliveries still arriving `ok=True`, so on that pick the
> short successful delegated answer is still the thing to look at; and it writes nothing to the
> reasoning channel at all, so a cap refusal there is the flags or a runaway and never this.
> **Both halves of that generalise to the family** (ADR-0028 row addendum): every Qwen entry of the
> row writes nothing to that channel, 0 draws of 864, and every one of their cap refusals is a
> numeric runaway inside `reply`, so on any Qwen override the quiet answer is the symptom and the
> reasoning channel is not. On `Qwen3.5-0.8B` it is the usual case rather than the exception, 26 of
> its 30 constrained non-deliveries arriving `ok=True`.
> **Every rate above is read against the same pick answering the same bodies with no envelope at
> all, and that arm is now published rather than assumed** (ADR-0028 control-arm addendum). It
> returned 96 of 96 on three picks and then 93 and 92 on two more, both times because the pick
> failed the subtask, so it is a reading and not a constant. If you re-measure any of this, the
> driver writes one sample per arm and `just envelope-floor <those files>` is what turns them into
> rates: it reports that control arm per subtask shape and **refuses to print the comparison at
> all** when a cell of it is proven below nine tenths of its own runs, since a difference read
> against a control that failed the subtask prices the pick and not the envelope. A refusal is not
> a broken run: the samples are still on disk, and what they price is the override you chose.
> What they cut is a model that is talking rather than one that is slow: the sixth shape, an
> open-ended essay no narrow subtask should ask for, was cut at 577 tokens and 1958 s still writing.
> **Every number here is an idle-box number**, and a saturated host runs the same subtask five to
> eight times slower, 1736.6 s against a 2400 s deadline, so a busy machine is the one to watch for
> a narrow subtask reported as a runaway
> ([refinements/index.md#resource-governance](../refinements/index.md#resource-governance)).

> **Queuing for room is bounded too, and generously.**
> `CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default 7200 s) is how long a spawn may wait for the soft
> budget to free room before it comes back refused, with the bound named in the message so the
> reader lands on this knob. It has to clear two different things and the larger one is what sets
> it. The first is any legitimate wait these defaults can produce, which was **measured on a live
> full batch** rather than reasoned from single subtasks: 8 spawns against `CPU_BUDGET=4.0` and
> `CPUS=2.0` admit two at a time, and with the GPU path open the pair overlaps and the last of the
> batch is admitted **893.2 s** in, which is what these defaults ship; with it shut the pair
> serializes and the same spawn waits **1624.6 s**, so twice the serial figure is about 3250 s. The
> second is the longest one task can hold the room that queue is waiting for, which is **two whole
> run deadlines**, since a GPU-placed run whose backend fails is re-run once on the CPU inside the
> same admission. At the shipped deadline that is 4800 s, above the first figure, so the bound is
> stated in deadlines: **three of them**, the two a task can spend plus one of margin (ADR-0012
> bounded-admission-wait addendum). Raising `CPU_BUDGET` or lowering `CPUS` shortens the real waits
> and never needs this raised. **Two full batches queued at once now fit on either placement:** 16
> spawns put the last one about 2100 s in while the pair overlaps and about 3800 s in while it
> serializes, both inside the bound, where the old hour covered only the overlapping case.
> Zero is legal and means never queue at all: refuse anything that does not fit the budget right
> now.

> **Admitted is not the same as concurrent.** Each roster entry holds one `LlamaCppBackend` per
> placement target, and a backend holds its model lease for the whole stream, so two spawns of the
> *same* entry on the same target run one after the other however many the budget admits. Measured
> here on the Qwen-2B override: two concurrent spawns took 4.8 s through two backend objects and
> 10.0 s through one, exactly serial. What one entry does get is an overlap of exactly two, and
> only while its admitted pair straddles the targets: `CORTEX_SUBAGENTS_GPU_ENDPOINT` defaults to
> this same server, so an entry whose `VRAM_GB` ask fits the headroom once has one spawn GPU-placed
> and the other overflowed, two lock objects in front of one `llama-server`, while a closed GPU
> tier or an ask that never fits puts both on one target and back in line. Raising `CPU_BUDGET`
> past that pair therefore buys queue depth, not throughput, the third spawn only moving from the
> scheduler's queue onto a lock; more than two at once needs distinct entries (the roster override)
> or a **second** GPU-capable executor, which the one hosted GPU tier is not.

> **Reasoning is disabled** on the subagent server by **two** flags, baked into the compose
> command: `--chat-template-kwargs '{"enable_thinking": false}'` and `--reasoning-budget 0`. Both
> lineup families (gemma-4-E*, Qwen3.5) are reasoning models. Unbounded thinking on CPU is minutes
> per call, and `LlamaCppBackend` reads `content`, not the `reasoning_content` where `<think>`
> traces land, so it would look empty and crawl. With the kwarg, plain requests answer directly
> (~1.8 s on the E4B pick, ~0.3-0.6 s on the Qwen-2B override), and the E4B injection-robustness
> (0/10) holds with thinking off (ADR-0004 injection addendum).
> **Neither flag covers the lineup alone, which is why both are there** (ADR-0005 thinking-lever
> addendum). The kwarg is a chat-template variable, and the E4B pick's template reads it on a plain
> request and stops mattering the moment a request makes the model want to deliberate, which a
> `response_format` does: measured, the constrained shape decoded 200 tokens of pure trace with the
> kwarg set at the server, at the request, and at both. `--reasoning-budget 0` is the engine's own
> flag and reaches it, taking the same request to a reply from 1.0 to 2.4 s in with no trace at all.
> A deployment adding a subagent server of its own needs both.
> **Which of the two carries the tier depends on the pick, and both subagent candidates this repo
> ships are on opposite sides of it** (ADR-0005 switch-is-advisory addendum, lineup section). Asked
> at five draws a cell on a server carrying neither flag, both gemma-4-E picks honour the kwarg on a
> plain request and deliberate through it under a `response_format`, the E2B on 5 draws of 5 and the
> E4B on 4, so on those the budget is the whole of the defence for every reply an envelope is
> decoded in. The Qwen-2B override honours it on **both** shapes, on all five draws of each, so
> there the budget is a second lock on a door already shut. Keep both flags on both servers anyway: the
> difference is a property of the pick's own chat template, and the argv outlives the pick a
> deployment happens to name.

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
  --host 0.0.0.0 --port 8090 -ngl 0 --jinja --chat-template-kwargs '{"enable_thinking": false}' \
  --reasoning-budget 0
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
sharing one model run one after another, wording that understates this deployment's two-way
overlap on purpose, and points it at spreading a batch as the wall-clock lever. This procedure
observes whether a live cortex takes that advice on its own.
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

Budget your time by the CPU tier and not by the cortex. gemma-4-E4B generates at between **0.18
and 1.35 tok/s** under its 4 CPU cap here, the low end being what a saturated host costs it (the
cap is a quota, not a reservation), and Qwen3.5-2B at about **1 tok/s**; the batch runs no faster
than its slowest
member, and a run's length is bounded but generously (`CORTEX_SUBAGENTS_MAX_TOKENS` per completion
and `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` on the whole run, both sized to cut a model that is talking
rather than one that is slow), so a three subtask batch on the default entry runs 10 to 15 minutes
on the low reading and a chatty one runs longer. The
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
