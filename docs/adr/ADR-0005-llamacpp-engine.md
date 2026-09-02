# ADR-0005: llama.cpp as the inference engine

- **Status:** Accepted (design decision, 2026-06-29; supersedes ADR-0001 decision 4's
  choice of vLLM)
- **Date:** 2026-06-29

## Context

ADR-0004 locked the model candidates. All are GGUF artifacts downloaded via LM Studio.
vLLM's GGUF support is experimental and per-architecture, and the founding vLLM choice
carried a class of consumer-hardware quirks (SM120/FP8 config, FlashInfer, the
CUDA-graph-capture hang on WSL2) that needed a dedicated runbook. This is a consumer
program on a consumer GPU, not a throughput-serving deployment.

## Decision

1. **llama.cpp is the engine behind `InferenceBackend`.** Native GGUF (the artifacts
   run as downloaded), first-class CUDA on consumer GPUs, none of the vLLM/WSL2 quirk
   class. The planned `blackwell-vllm.md` runbook is replaced by `llamacpp-gpu.md`
   (written in Slice 4).
2. **Serving shape: one `llama-server` process per loaded model**, its
   OpenAI-compatible HTTP API as the adapter surface (chat completions + embeddings).
   The `InferenceBackend` adapter is a thin HTTP client and is fakeable in tests like every
   other adapter.
3. **The Model Manager's swap mechanism is process lifecycle.** Load = start a
   `llama-server` on the artifact; unload = stop the process. This makes the hard rule
   literal: a swap kills the serving process outright, so anything not in the external
   store is gone by construction. That is exactly the discipline the architecture already
   enforces. The lease/queue design from ADR-0001 is unchanged.
4. **Embeddings run on the same engine** (nomic-embed GGUF candidates, ADR-0004): one
   engine for all tiers plus the embedder, one VRAM accounting model (per-process).
5. **GPU deployment stays dockerized** via the NVIDIA container toolkit in the
   `docker/docker-compose.gpu.yml` override (pinned llama.cpp CUDA server image or build),
   with models bind-mounted read-only from `D:\Software\AI\Models` (ADR-0004).
6. **Portability improves.** llama.cpp runs Metal and CPU: the future macOS move can
   likely reuse this same adapter against a Metal build (the second portability seam in
   AGENTS.md/ARCHITECTURE.md; the new MLX adapter ADR-0001 d4 anticipated is likely
   unnecessary), and a CPU build enables local GPU-less experiments. CI remains
   inference-free regardless.

## Consequences

- vLLM-specific text in ADR-0001, AGENTS.md, ARCHITECTURE.md, and ROADMAP.md is
  updated; ADR-0001 d4 carries a supersession note.
- vLLM's continuous batching / paged-attention throughput is given up. It is irrelevant for
  a single user; llama.cpp's single-stream latency is what matters here.
- Swap latency is now dominated by process start + GGUF load from the bind-mounted
  Windows drive; if that mount is slow, hot models get mirrored into a WSL-side cache
  (measured in Slice 4, per ROADMAP assumption 2).
- llama.cpp flags/versions are adapter + runbook concerns; the core never sees them.

## Addendum (2026-08-09): the stall ceiling on the generation clients

**Status:** Accepted. Closes "a read timeout on the subagent HTTP client" from
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance), whose deferral
was recorded at [ADR-0012](ADR-0012-resource-governance.md).

### What the tree actually said

The backlog entry named one call site, `build_subagents`. There were **two**, and they were the
only two unbounded HTTP clients in the brain:

- `builders.build_inference_backend` for the resident tier, which is also the client the **deep
  tier** streams through after a handoff, one `LlamaCppBackend` object being built once and handed
  to `BrainPhase` (`wiring.run_from_env`);
- `subagent_builders.build_subagents` for every roster entry's backend pair.

Both spelled `httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)`, and `builders.py` documented
the policy as shared ("one knob"). Every other client in the brain was already bounded: the model
host's control client (`swap_builders.build_control_client`), the embedder
(`memory_builders`), the vision probe (`vision.py`) and the sidecar's own probe. So the entry
undercounted the fix by exactly one site, and the site it missed is the one that carries the
slowest model this repo runs.

### Decision

1. **The read phase is bounded on both clients, by a per-tier ceiling.**
   `builders.build_generation_client(stall_timeout_s)` is now the one place a generation client is
   built; connect, write and pool keep the shared 10 s (a dead server is dead at the same speed
   everywhere), and the read phase takes the caller's number.
2. **It is a stall detector, not a cap on the generation.** httpx applies its read timeout to
   **one socket read**, not to the request, so what this bounds is the gap between SSE chunks: a
   reply that keeps arriving may stream for as long as the model wants, and one that stops
   arriving fails. A reader who takes it for a total time budget will set it far too low. The
   longest legitimate gap is therefore the time to first token, not the length of the answer.
   Measured here rather than taken from the documentation: a loopback server dribbling one chunk
   every 0.2 s under a **0.5 s** ceiling delivered all 15 chunks over **3.34 s**, 6.7x the
   ceiling in elapsed time, and raised `ReadTimeout` only once it went quiet.
   Consumer backpressure does not enter: the seam's credit bound (`CORTEX_SEAM_CONVERSE_BUFFER`)
   suspends the reader **between** reads rather than inside one, so the 16.52 s a stalled consumer
   was measured holding its lease ([ADR-0038](ADR-0038-ranked-recall.md)) spends none of this
   ceiling.
3. **Two knobs, not one**, `CORTEX_INFERENCE_STALL_TIMEOUT_S` (120 s) and
   `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` (600 s). The connect policy stays one knob for the reason it
   always was, but the worst legitimate silence differs by an order of magnitude between these
   tiers (the derivations below), and a single number would have to be the loose one: a wedged
   cortex stream would then park a turn, and the GPU lease under it, for the CPU tier's whole
   allowance. Both are `pydantic-settings` fields with a positivity bound, sourced like every
   neighbouring timeout in the brain (`capture_timeout_s`, `confirm_timeout_s`,
   `modelhost_timeout_s`), so a deployment on other hardware retunes without a rebuild.
4. **A stall crosses the port as `InferenceError`, named apart from a dead server.**
   `httpx.ReadTimeout` already fell under the adapter's `httpx.HTTPError` arm, so nothing untyped
   ever escaped; what it lacked was a distinguishable message, and "request failed" sends an
   operator hunting for a connection problem when the server took the request and then went quiet.
   `_transport_failure` in `backend.py` now names the two apart.

### Deriving the resident tier's 120 s

The longest legitimate gap on this client is the worst time to first token across the tiers it
serves.

- Measured 2026-08-08 on the 24 GB card, gemma-4-12B at 16K: **4.6 s solo**, and **10.3 s, 12.0 s
  and 17.5 s** across three overlapping `Converse` streams
  ([ADR-0038](ADR-0038-ranked-recall.md), [ADR-0014](ADR-0014-history-windowing.md),
  [docs/runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md)). Those three include waiting for
  the brain-side model lease, which is spent **before** the request reaches the wire, so taking
  17.5 s as a wire-side figure deliberately over-counts.
- The deep tier streams through this same client and is the slower model: it loads in **99.6 s**
  against the cortex pick's **38 to 52 s** on this card
  ([ADR-0004](ADR-0004-model-lineup.md) lineup table, repeated in the GPU runbook), a ratio of
  1.9x to 2.6x. Its own time to first token has never been measured directly, which is exactly
  what the margin below is for.
- A screen capture adds **0.6 s** of time to first token for 744 more context tokens
  ([ADR-0029](ADR-0029-vision-screen-capture.md)), so vision is noise at this scale.

17.5 s at the worst measured ratio is **45.5 s**, and the shipped ceiling is **120 s**, which is
2.6x that. The margin buys the deep tier's unmeasured first token and prompt shapes the run did not
cover (a full 16K context rather than the run's corpus). A ceiling that fires on a legitimately
slow first token would be worse than the hang it replaces, so the number is deliberately loose;
what it removes is "forever", not "slow".

### Deriving the subagent pool's 600 s

The pool's arithmetic is different, and the runbook's own warning is why: **admitted is not
concurrent**. Each roster entry holds one `LlamaCppBackend` per placement target and a backend
holds its model lease for the whole stream, so two spawns of one entry on one target run one after
the other however many the budget admits, measured at **4.8 s through two backend objects against
10.0 s through one, exactly serial**
([docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md)). The queue is therefore brain
side, ahead of the request, and the CPU server runs `--parallel 2` for the two backends that can
reach it at once. So this ceiling covers **one call's own first token on a CPU server**, not a
peer's whole generation.

- The default entry, gemma-4-E4B, generates at about **0.35 tok/s** under its 4 CPU cap, nothing
  bounds a subagent's length (`n_predict: -1`), and a three subtask batch runs **10 to 15 minutes**
  (subagents-cpu runbook). Serialized per entry, that is roughly **200 to 300 s** for one whole
  subtask, which is an upper bound on any single call's first token.
- A trivial ask on the CPU server measured **12536.83 ms** and **13134.73 ms** end to end
  ([ADR-0012](ADR-0012-resource-governance.md) placement runs of 2026-08-04 and 2026-08-08), and a
  tool-shaped call is prefill bound at about **8 s**, so the floor is already in the tens of
  seconds for work that is going perfectly.
- Steady state is nowhere near either: at 0.35 tok/s the gap between chunks is about **2.9 s**.
- The first request after a boot additionally pays first-touch paging of a 4.9 GB GGUF off the
  models mount, which nothing here has timed.

**600 s is twice the 300 s upper end of a measured whole subtask.** It is generous on purpose, as
the entry that asked for it insisted: on this hardware the honest reading is that a delegated
stream silent for ten minutes is wedged rather than working.

### What this does not do, and where that is recorded

A stall ceiling cannot detect a model that keeps talking. A subagent in a repetition loop streams
chunks forever, trips nothing here, and holds its admission exactly as the wedged one used to, and
nothing in the shipped wiring bounds a delegated generation's length. That is a **total generation
cap**, filed as its own deferral in
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance) with its trigger
and its shape (the `GenerationBounds.max_tokens` the port already carries, against a wall-clock cap
that would need the same timeout design and `Clock` as the bounded admission wait). It is not built
here because the two failures are different: this one converts an unbounded wait into a bounded,
reported one, while capping a length is a policy about answers.

Two earlier ADRs describe these clients as passing `read=None`
([ADR-0012](ADR-0012-resource-governance.md)'s deferral paragraph and
[ADR-0030](ADR-0030-brain-handoff.md)'s notes on the control deadline). Both were true when
written and are superseded here; the control deadline's argument survives unchanged, since it
bounds a whole call that streams nothing while this bounds the gap inside a stream.

### Distrust green

The ceiling is proven on a real socket, not against a faked transport: a loopback server answers
with the SSE headers and then sends nothing, and the backend built by
`build_inference_backend` raises `InferenceError` instead of waiting. `httpx.MockTransport` cannot
stand in, timeouts being enforced by the network stream underneath the transport, so a mocked
version would have proved the plumbing and never the bound. The test is wrapped in
`asyncio.timeout`, because a regression that hangs the suite proves nothing: restoring `read=None`
fails it in ten seconds. Five mutations were run and each made a named test fail: `read=None`
restored (2 tests), each builder's config value replaced by a literal (1 each), the stall arm
dropped from the adapter's translator (2), and the positivity bound dropped from both knobs (2).

## Addendum (2026-08-11): the total generation cap on a delegated run

**Status:** Accepted. Closes "a total generation cap, for the subagent that keeps talking" from
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance), which the
addendum above opened, and which this ADR declined on the same day: converting an unbounded wait
into a bounded reported failure is a transport concern, capping how much a model may say is a
policy about answers, and mixing the two would have shipped an unmeasured number inside a fix that
needed none. It lands here rather than beside the pool's budgets because that is where the decline
is written, and a reader who finds the decline has to find the reversal in the same place.

It lands **ahead of its trigger**, which was the first delegated run observed running away and
which nothing has seen. The trigger existed because the entry priced the fix as a guess about how
long a legitimate answer runs, and a cap set on a guess buys a truncated reply on every long
subtask. That price is what changed: the guess is now five measurements on the shipped tier.

### What the tree actually said

Re-derived rather than trusted, this backlog's own standing warning being that an entry's account
of the code goes stale.

- `subagent_attempt.PlacedAttempt.run` did call `stream_tool_loop(backend, model, working,
  context)` with nothing around it. Every word the entry wrote about the defect held.
- `GenerationBounds` does ride `InferenceBackend.stream`, its `max_tokens` does default to `None`,
  and llama-server does read that as `n_predict: -1`. What the entry could not have known is that
  **the loop had no way to carry one**: `ToolLoopContext` had a `schema` field and no `bounds`, and
  `stream_tool_loop` called `backend.stream(model, working, tools=specs, schema=context.schema)`.
  So "already expressible today, a value threaded from `SubagentsConfig` through the runner" was
  true of the port and false of the only path a subagent reaches the port by. The token half needed
  a field on the loop's context, which is one line of vocabulary and no port change at all.
- The bounded admission wait is `asyncio.timeout` over the scheduler's own condition, exactly as
  the entry's later correction said, and no `Clock` is injected for it. The split this repo already
  draws held on inspection: `Clock` is for wall-clock instants and for poll loops (`health_gate.py`
  says so in as many words), `asyncio.timeout` is for durations, which belong on the loop's
  monotonic clock.

The failure itself was reproduced before anything was designed, because a cap whose test never saw
the runaway is worth nothing. A backend that yields a text chunk forever, through the shipped
runner and the shipped scheduler, streamed **3,099,896 chunks in 5 s**, never returned, and
persisted no result, holding its admission and its VRAM placement the whole time.

### Decision

1. **Two bounds, one value: `AttemptBounds(max_tokens, timeout_s)`.** They answer the same question
   in the two units a runaway can be measured in, and a deployment that set one and not the other
   would have bounded half the failure. The cap is what binds a fast tier, where a deadline's worth
   of decoding is an essay; the deadline is what binds a slow one, where this pool's measured 0.30
   to 0.33 tok/s makes even a small token budget minutes of held admission. Both `None` is the
   request and the run this repo shipped before, byte for byte, and it stays the core default
   (`UNBOUNDED_ATTEMPT`); the deployment's numbers arrive from `SubagentsConfig` at the root.
2. **The token half is per completion and rides the loop's context.** `ToolLoopContext.bounds`
   reaches `backend.stream` for every completion an attempt asks for, so a subagent that reaches
   its repetition loop only after its first tool call is bounded as tightly as one that starts
   there. Rounds and the cap multiply, and `MAX_TOOL_STEPS` is what makes that product finite.
   `thinking` is left at its default, which emits no key: the pairing ADR-0038 insists on, where a
   cap on a reasoning model with thinking left on deletes the reply rather than shortening it, is
   kept by the tier, every subagent server this repo ships starting with `--chat-template-kwargs
   '{"enable_thinking": false}'` (ADR-0010).
3. **The wall-clock half is per attempt and covers everything the attempt does.** It is
   `asyncio.timeout` around the whole consumption, the idiom the bounded admission wait landed on,
   so it covers every completion **and every tool dispatch between them**. That is the unit that
   matters: what a delegated run holds while it runs is an admission slot, a VRAM placement and a
   model lease, and it holds all three across the tool loop rather than across one completion. A
   subagent suspended in a dead MCP sidecar's call holds exactly what one suspended in a generation
   holds.
4. **Reaching the deadline is an outcome the store and the spawn tool already understand.**
   `AttemptFailure.TRUNCATED` joins `INFERENCE` and `MALFORMED`, so a runaway arrives at the cortex
   through the very path a dead backend does: an `ok=False` `SubagentResult` whose detail names the
   bound and says to narrow the subtask. Nothing new escapes the runner, which matters because the
   spawn tool's `gather` is crossed only by `ToolError` and an escaping exception would discard the
   batch's other subagents with it. The fragment the model had produced is kept on the result, so
   the store has it, and the aggregate the cortex reads carries the refusal instead, because that
   fragment is mid-sentence by construction and reporting it as an answer would have traded a hang
   for a wrong answer.
5. **Only an expired deadline is a truncation.** `TimeoutError` is an `OSError` in Python and is
   the class `asyncio.timeout` raises, so one arriving from below (a socket that timed out, a tool
   that raised one) would otherwise be reported as a bound that had not fired, and on an unbounded
   attempt it would try to quote a bound that does not exist. The arm asks `deadline.expired()` and
   reports anything else as the backend failing to answer, which keeps it eligible for the CPU
   re-run and keeps the message honest.
6. **A truncation is not re-placed.** The CPU re-run exists for a backend that did not answer. A
   model still talking at its deadline was answering; it simply never stopped, and the slower tier
   is the last place to send it, a second whole deadline spent to be told the same thing. This is
   the argument `MALFORMED` already makes, and it is why the retry keys on the failure kind rather
   than on `ok`.
7. **The deadline is per attempt, armed fresh, not per task across the re-place.** A re-run handed
   what a failed attempt left of a deadline would be refused before it began, turning the one
   transport failure a re-place exists for into a certain failure. The cost is stated rather than
   hidden: a task can hold its admission for two deadlines rather than one, and only along the path
   a dead backend opens, since neither failure a deadline itself produces is re-placed.
8. **The precedence between this deadline and the stall ceiling is a wiring error, not a doc
   claim.** Both can fire on one stream and they say different things: the ceiling reports the gap
   between chunks, which is a wedged server, and the deadline reports the whole, which is a model
   that will not stop. Only the first is worth re-running elsewhere. So `SubagentsConfig` refuses
   to construct unless `run_timeout_s > stall_timeout_s`: under a deadline at or below the ceiling
   every wedge would be reported as a runaway and the CPU re-run scheduled for exactly that failure
   would quietly stop firing. Equality fails too, a ceiling that can only tie being one that never
   reports. The admission wait needs no such relation, being disjoint in time: it bounds queuing
   for a backend and this bounds using one, and no stream exists while the first is running.
9. **Neither knob has an off switch.** `CORTEX_SUBAGENTS_MAX_TOKENS` is at least 1 and
   `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` is strictly positive. The whole of this bound is that a
   delegated run cannot be unbounded, so a deployment retunes rather than disables. Zero is legal
   on the admission wait because there it means "never queue", a policy someone may want; a zero
   deadline would mean "never run", which nobody wants.

### Deriving the two numbers

Both are measured on the shipped default entry, gemma-4-E4B QAT q4_0 on CPU at the compose file's
own shape (`-ngl 0`, `--ctx-size 8192`, `--parallel 2`, thinking off), over five subtask shapes
spanning what delegation is for, from a one-word lookup to an open-ended essay no narrow subtask
would ask for. The essay is in the set on purpose, and what it did is the most useful thing in the
table.

| subtask | prompt tokens | decoded tokens | wall clock |
| --- | --- | --- | --- |
| one fact (name a primary color) | 19 | 2 | 11.5 s |
| one word (`Reply with exactly one word: PONG.`) | 18 | 4 | 20.7 s |
| extract every number from a report | 220 | 125 | 410.5 s |
| summarize that report, keeping every detail | 224 | 199 | 623.8 s |
| open-ended essay on the same report | 224 | **did not finish** | cut at 577 tokens, still writing, 1958 s |

The first four are what delegation is for, the narrow shapes the spawn spec asks the cortex for,
and they span two orders of magnitude while staying inside eleven minutes. The fifth is what
happens when a subtask is not narrow, and it is less an outlier than the failure this addendum
bounds arriving through a legitimate prompt rather than through a broken model. On this tier an
open-ended ask has no natural end. It was cut after 1958 s and 577 tokens because the measurement
had to end, not because it did, and nothing separated it from the four above while it ran, its
chunks arriving on the same cadence and its stall ceiling never in sight. So the cap is sized
against the narrow shapes, the deadline is what cuts this one, and the refusal both produce tells
the cortex to narrow the subtask rather than to try it again.

**The cap is 1024 tokens**, roughly five times the longest narrow reply in that table. It is sized
from the answer, the way the recap fold's six times and the title's eight are, rather than from the
context: what makes a cap safe is that reaching it is itself the evidence, and a reply five times
the longest one this tier has been measured writing is a model that is talking rather than working.
The per-slot context this compose ships (4096, being 8192 across `--parallel 2`) is the other
ceiling and sits above it, so the cap fires before the server's own limit does and the prompt keeps
its half.

**The deadline is 2400 s**, four times the longest whole subtask in that table. The first doubling
is the one the stall ceiling and the admission wait already carry, and for the reason they carry
it: a bound that cuts work which was going to finish is worse than the unbounded run it replaces,
since it turns a slow success into a failure. The second covers a **tool-using** run, whose loop
may spend on several rounds what the measurement spent on one completion, and which is the shape
with no measurement of its own here. It also lands strictly between the two bounds either side of
it, above the pool's 600 s stall ceiling and below its 3600 s admission wait, so the three are
ordered by the scope of what they bound: one silent gap, then one whole run, then the queue for a
run. A run can therefore never hold its admission longer than a peer is willing to queue for it.

A sixth measurement checks the cap against the server rather than against the arithmetic, since a
cap that never reached the wire would be the emptiest kind of green. The summarization prompt at
`max_tokens: 48` came back with `predicted_n: 48` and `finish_reason: "length"` in 196.8 s, its
reply ending mid-number. The cap reaches llama-server through this exact request shape, the server
honours it, and it says so on the wire; what the port does with that last fact is the first entry
under the next heading.

Two things the table says that were not being said before, and both are recorded rather than acted
on here. The runbook's "a whole subtask measures 200 to 300 s" is an underestimate: it holds for an
extraction and is out by a factor of two for a summarization, which is the shape delegation is most
often for. And the admission wait's derivation is built on that same figure. Retuning it wants a
batch measured rather than five single subtasks, so it is filed as its own entry rather than folded
in here.

### What this does not do, and where that is recorded

**A completion cut at `max_tokens` is not distinguishable through this port.** llama-server ends
the stream and reports `finish_reason: "length"` on the wire; the adapter surfaces text, reasoning,
tool calls and a decode cadence, and no finish reason, so the core cannot tell a model that stopped
from one that was stopped. On the constrained tool-less path that is caught structurally anyway, a
cut envelope failing to parse and arriving as `MALFORMED`, which is an honest `ok=False` with a
less useful reason. On the unconstrained path it is invisible, and the mitigation is the sizing
above rather than a mechanism: at five times the longest measured reply, what the cap cuts was
already not an answer. This repo's own precedent for the same problem is `clean_recap`, which reads
the reply's shape rather than the transport. Carrying the finish reason across the port is filed as
its own entry with its trigger, since it is a port change and this one needed none.

**The deep tier and the cortex are untouched.** `AttemptBounds` rides the subagent runner, not the
generation client, both because a token cap is request-side vocabulary the port already carries and
because the deadline has to cover tool dispatches, which no HTTP client can see. A user-facing turn
is not bounded here and should not be: the failure this closes is a delegated run holding a pool's
admission, and a cortex turn holds a lease the user is watching.

### Distrust green

The runaway is real in three places and faked in none of them.

- The **reproduction** above ran through the shipped runner before a line was written, and the same
  never-stopping backend is the fixture the checks now use, so every deadline case is exercised by
  the failure itself rather than by a stand-in for it.
- The **end-to-end check** is a real socket, the mirror of the wedged server the stall ceiling was
  proved against: a loopback server that answers with the SSE headers and then streams a content
  delta forever. `httpx.MockTransport` cannot stand in for either, and the chatty one additionally
  proves the ceiling does not fire, this server never being silent. From `SubagentsConfig` through
  `build_subagents`, the runner, the adapter and the socket, what comes back is the aggregate the
  cortex would read, carrying `FAILED:` and the bound.
- Every check sits under an outer `asyncio.timeout`, so a regression that restores the unbounded
  run **fails** rather than hanging the suite.

Seven mutations, each applied to production code alone with the whole `packages` suite re-run, so
the counts are measured rather than aimed at: dropping the `asyncio.timeout` wrapper fails **9**,
every deadline case plus the real-socket one, each at its outer bound; treating every
`TimeoutError` as the deadline fails **1**, the case that would otherwise have crashed formatting
a bound an unbounded attempt does not have; reporting a stopped run as `INFERENCE` rather than
`TRUNCATED` fails **1**, the re-place case; letting the envelope check win over the deadline
fails **2**, the mid-envelope case and the real-socket one, whose shipped wiring is that same
constrained niche; dropping `bounds` from the loop's `backend.stream` call fails **1**; relaxing
the config's ordering rule from strict to non-strict fails **1**; and dropping
`bounds=config.attempt_bounds` at the builder fails **1**, the real-socket case, which is the
whole chain proving it is a chain.

One mutation failed **nothing**, and it is reported rather than quietly dropped: removing the
`aclosing` around the loop generator. The cancellation a deadline delivers lands wherever the task
is suspended, and every suspension point this shape has but one is *inside* the loop generator,
which therefore unwinds and runs every `finally` on the way out, releasing the model lease with
them. The exception is a suspension in `progress.emit`, and even there the two release identically,
because the loop closes the backend's own stream before any step reaches that sink. The wrapper is
kept as the discipline `tool_loop` already applies to its own two generators and `drain_text`
argues for at length, so the release stops depending on where the timer happened to fire; no check
claims a bound it does not hold.

## Addendum (2026-08-16): the finish reason the port now carries

**Status:** Accepted. Closes "a finish reason the port does not carry" from
[docs/refinements/index.md#resource-governance](../refinements/index.md#resource-governance), which
the addendum above opened under its own "What this does not do" heading and priced honestly as a
port change. It is one, and this is that change.

It lands **ahead of its trigger**, which was "the first capped delegated reply that a reader
mistakes for a finished one", and the reason to land it anyway is that this trigger cannot fire.
A truncation that reads as an answer leaves no evidence behind: the store keeps the fragment, the
result says `ok=True`, nothing marks it, and the reader who was misled is by definition unaware of
it. A trigger nobody can observe is a trigger that never arrives, so waiting for it means never
doing the work. The other half of the reason is that the mitigation standing in its place covers
less than it looks: it is a sizing argument about `max_tokens`, and `max_tokens` is one of two
limits that end a completion the same way on the wire, the server's context window being the other
and no part of that argument.

### What the tree actually said

Re-derived rather than trusted, this backlog's own standing warning being that an entry's account
of the code goes stale.

- The port really did not carry it. `InferenceEvent` was
  `TextChunk | ReasoningChunk | ToolCall | DecodeCadence` and `InferenceBackend.stream` named
  exactly those. Every word of the entry's account of the defect held.
- **The adapter was receiving the fact and stepping over it**, which is sharper than the entry
  said. `consume_chunk` read `data["choices"][0]["delta"]` and never `choices[0]["finish_reason"]`,
  while the very transcript the decode-cadence contract runs on carries `"finish_reason":"stop"` on
  the same final chunk the `timings` object rides. The reason was arriving in the same bytes the
  rate was being read from.
- The entry's argument against reading `DecodeCadence.tokens` still holds, and the re-derivation
  strengthened it into the argument for a separate event. The cadence is emitted only when the
  server reports `timings`; `finish_reason` comes off a different part of the chunk and is reported
  whether or not it does. So a reason carried on the cadence would have gone missing on exactly the
  build the entry named, and the "near miss" would have missed where it mattered.
- The constrained tool-less path's structural closure is real but weaker than the entry recorded.
  A cut envelope does fail to parse and arrive as `MALFORMED`, and `MALFORMED` is not re-placed,
  so the **behaviour** was already right; what was wrong was the diagnosis, which named the model
  breaking its grammar for a sentence the server had ended.
- The consumers are as named: `PlacedAttempt` on the delegated path, and the recap fold through
  `drain_text`, which keeps `TextChunk` and drops everything else.

One thing the entry could not have known, and it decides the shape below: **`finish_reason` is not
two-valued.** Against the shipped CPU tier (build `b9879-72874f559`) a capped request answers
`length`, an ordinary reply answers `stop`, and a completion that ends in a function call answers
`tool_calls`, which is the ordinary ending of every round of a tool loop but the last. A two-member
set would have filed every tool-using round under whatever it used for "other".

### Decision

1. **The stop is its own event, `DecodeStop(reason)`, not a field on the closing `DecodeCadence`.**
   The two ride one chunk on this build and are still separate facts with separate availability, so
   the field would have coupled a reason to a rate's silence. The second argument is the consumer's:
   every loop hands its cadences to a `CadenceWatch` whose contract is about rates, so a non-rate
   fact travelling inside that carrier would reach a collaborator shaped for another question. The
   cost, which the entry priced and this accepts, is that every backend and every consumer owes the
   new case; pyright is what collects it, the loop's text arm narrowing to a type with no `text`.
2. **The reason is a closed set the core owns: `StopReason.FINISHED`, `CAPPED`, `CALLED`,
   `UNKNOWN`.** The wire value is llama.cpp's vocabulary and the core must not depend on a
   backend's spelling, so the adapter translates and the core's word for a cut completion appears
   nowhere on the wire. Four members rather than two because `tool_calls` is a real ending, and
   because a word this core has not been taught must land somewhere that is not one of the other
   three.
3. **An unreadable reason is `UNKNOWN`, never silence and never a raise.** This is a third stance
   beside the two `decode.py` already documents. Raising would kill a finished reply over a
   telemetry field, which is the cadence's own argument; staying silent would file a fact this core
   failed to read under the same heading as a fact nobody offered, which is the exact conflation
   the whole arm exists to remove, one level down.
4. **Silence stays legal, and no consumer may read it as `FINISHED`.** A backend whose engine says
   nothing emits no stop, exactly as one whose engine reports no timings emits no cadence. The
   shared contract's `check_silence_is_a_legal_answer` is what keeps that a permission rather than
   a sentence in a docstring.
5. **Which limit cut the completion is not part of the answer.** `length` is what llama-server says
   for a request's own `max_tokens` and for the server's context window alike, and nothing on the
   wire separates them. Naming a cap the deployment set would therefore be a guess wherever the
   context ran out first, so the event says a token limit ended it and the consumer quotes its own
   knob only when it has one. This is also the hole in the sizing mitigation the previous addendum
   left in place: five times the longest measured reply is an argument about `max_tokens` and says
   nothing about the 4096-token per-slot context this compose ships.
6. **The tool loop absorbs the stop, exactly as it absorbs the cadence.** `ToolLoopContext.stops`
   takes a `StopLedger` and `stream_tool_loop` hands each completion's reason to it. Why the
   machine stopped is a fact about the machine and not something the turn said, so it must never
   reach a stream a user reads, and a caller that hands over no ledger drops it. That also keeps
   the loop's yield vocabulary, the seam every consumer of a turn is written against, unchanged.
7. **A capped delegated run is `AttemptFailure.TRUNCATED`, the deadline's own verdict in the other
   unit.** It reaches the cortex as an `ok=False` `SubagentResult` whose detail says to narrow the
   subtask, the fragment stays on the stored result for whoever reads the store, and the retry
   declines to re-place it for the reason a deadline-stopped run is not re-placed: a tier that
   filled its token budget will fill it again, and the slower tier is the last place to send it.
8. **The cap is read ahead of the envelope**, which is the precedence both deadline arms already
   keep. A cut reply lands mid-envelope by construction, so an envelope check that ran first would
   report a model breaking its grammar and send the reader to the model rather than to the limit.
9. **Every backend owes the answer, and `EchoInferenceBackend` gives it.** This is where the
   cadence's argument stops applying rather than extending. That fake must never report a rate,
   because a rate is a measurement only a real server has taken and a fabricated one would be a
   made-up number in a real log. Why its completion ended is not a measurement: the echo ends
   because its script does, it honours no `bounds`, and so it can truthfully say `FINISHED` and
   can never say anything else.

### What a real server said

Measured 2026-08-16 by the agent through the shipped adapter against the shipped CPU subagent tier
(gemma-4-E4B QAT q4_0 at `-ngl 0`, llama.cpp build `b9879-72874f559`), which needs no GPU, by
`packages/inference/tests/test_finish_reason_live.py` as written:

| arm | request | the stop that crossed the port | the text |
| --- | --- | --- | --- |
| capped | `max_tokens: 8`, "Write a long essay about the sea." | `CAPPED` | `## The Unbounded Heart: An Ode` |
| finished | no cap, "Reply with exactly one word: PONG." | `FINISHED` | `PONG` |
| the core | the capped arm through `PlacedAttempt` | `ok=False` | `## The Blue Expanse: A` |

The third row is the one that matters, because the first two only prove the fact arrives. What the
attempt returned is the refusal naming the bound, where before this change the identical run
returned that cut title as an answer.

The `tool_calls` value was read the same day off the same server, by offering it one tool and
asking it to use it, and it is why `CALLED` exists.

### What this does not do, and where that is recorded

**The recap fold is not a consumer, and the decline is on its merits rather than on cost.**
`clean_recap` already rejects any account that does not end a sentence, which is strictly stronger
than reading the transport for its own question: it catches a fold the server cut, a fold the model
ended mid-thought, and a fold that arrived mangled, where a stop reason catches only the first.
Making it a consumer also means changing `drain_text`, which returns a `str` today and has three
callers who want exactly that. What a stop would add is the diagnosis, since a rejected fold is
silently retried next turn and an operator reading the log cannot tell a cut account from a model
that wandered. That is worth a log line and not a signature change, and it is filed as its own
entry rather than folded in here.

**A cap that lands inside a tool call is still reported as a dead backend.** The adapter assembles
tool calls only once the stream is over, so a completion cut while the model was writing a call's
`arguments` raises `InferenceError` on the fragment, and the attempt answers that from its own
`except` arm without consulting the ledger, which by then knows the run was capped. That arm is one
line from reading it and the line is not obviously right: an `InferenceError` can arrive from a
round after the capped one, where reporting a truncation would hide a dead backend and skip the
re-place that exists for exactly it. The shape is rare by construction, a call's arguments being
short against a 1024-token cap, so it is filed rather than guessed at.

**The cortex turn does not read it.** The user watches the reply arrive and a stop that reached
that stream would be a fact about the machine on a surface for what was said, which is the same
argument the decode cadence is absorbed under. A turn that says "this was cut" needs a
rendered surface for it, which is an overlay change and not this one.

**Nothing crosses the body seam.** `proto/body.proto` is untouched: the stop is read entirely
inside the brain, and what reaches the body is the same reply text and the same turn events as
before. A finish reason that ever needs rendering in the overlay would cross there and would be
declared in that file first.

### Distrust green

The wire word is real in three places and faked in none of them: the shared contract's adapter leg
reads a real llama-server final chunk, the adapter's own cases carry the three words a live server
emits, and the integration test drives a real server and follows its answer through the shipped
attempt.

Twelve mutations, each applied to production code alone with the whole `packages` suite re-run, so
the counts are measured rather than aimed at.

| mutation | tests that fail |
| --- | --- |
| `_stop` never reads `finish_reason` | **14**, the contract's three answering checks on the adapter leg and every adapter case; no scripted case |
| `length` maps to `FINISHED` | **4**, the contract's cap check on the adapter leg and the three adapter cases that read the word |
| the stop is yielded before the text in `_chunk_events` | **3** |
| a missing `finish_reason` reports `FINISHED` | **29** |
| `StopLedger.observe` counts every stop as a cap | **8** |
| `StopLedger` starts capped | **28** |
| the ledger keeps only the last stop | **2** |
| a capped run is reported `INFERENCE` | **2**, the re-place case and the tool-loop one |
| the envelope check runs ahead of the cap | **1** |
| the refusal always quotes a bound | **1**, the unbounded run |
| the loop drops the stop instead of observing it | **6** |
| `EchoInferenceBackend` reports no stop | **1** |

Three of those readings say something the counts alone do not.

**Reordering the adapter's yields does not fail the contract's ordering check**, and the cadence
contract records the same finding about itself for the same reason: the transcript's final chunk
carries `finish_reason` on a content-less delta, so text and stop stay in order across chunks
however the adapter orders them within one. What catches the reorder is the adapter's own case for
a chunk carrying both, which is why that case lives beside the adapter rather than in the contract.

**A missing reason reported as `FINISHED` fails 29 tests, and only one of them is a stop check.** Every
chunk of every stream carries no `finish_reason` until the last, so that mutation puts a stop event
after every delta in the suite and breaks every case that asserts on a whole event list. The reach
is the evidence: silence is not a corner of this port, it is most of what a stream is.

**The type checker collects the new case, as claimed.** Deleting the `DecodeStop` arm from
`_reply_text` and running pyright over that file alone gives
`Cannot access attribute "text" for class "DecodeStop"`, so a consumer that ignores the event
cannot compile rather than failing at runtime on the arm that assumed text.

## Addendum (2026-08-16): the capped-reply note, and the two levers a user's own turn now has

**Status:** Accepted. Closes "disable-thinking and token-budget capping" from
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager),
the last case that entry still covered: a user-facing reply, which sent no bounds by design and
read its own stop not at all.

Its trigger was "a runaway trace on a real answer, or a user who minds the wait", and both halves
have now fired with numbers behind them. The wait is measured below and it is 11.8 s to 18.1 s
before the first word of an ordinary answer on the resident cortex, every second of it a
deliberation the user cannot read yet. The runaway is in the lineup's own table: two of the four
deep candidates consume an entire 8192-token context and return empty content, and the shipped
pick reaches its answers in 3847 to 4448 tokens, which is a wall one long question away
([ADR-0004](ADR-0004-model-lineup.md)).

### What the tree actually said

Re-derived rather than trusted, this backlog's own standing warning being that an entry's account
of the code goes stale, and this port changed twice on the day this landed.

- `GenerationBounds` reaches a user's turn through `ToolLoopContext.bounds` already, and neither
  `TurnEngine` nor `BrainPhase` set it, so both send the server's own `n_predict: -1`.
- Neither passes a `StopLedger` either, so both were blind to `StopReason.CAPPED`, which the
  finish-reason addendum above had made available hours earlier. The addendum's own "what this
  does not do" says the cortex turn does not read it and that a turn wanting to say "this was cut"
  wants a rendered surface, an overlay change. **That last inference is what the re-derivation
  overturned:** `swap_notes.py` already puts app-authored sentences onto a user's reply stream as
  `TextDelta`s, and `BRAIN_FAILED_NOTE` is already appended to a partial answer and persisted with
  it. The surface exists, nothing crosses the seam, and the overlay renders it as the reply text
  it is.
- Thinking-off is per server in `TierArgs.extra` and hard-wired to the GPU subagent tier alone
  (`config.py`'s `_REASONING_OFF`). **There is no env knob that turns it off for the cortex or the
  deep tier**, so "already switchable" was false for exactly the two tiers a user reads.
- Bounding the trace separately from the reply is not available. `--reasoning-budget` is a switch
  (0 or -1), not a token budget, it is per server, and it does not work on this build; nothing in
  the OpenAI request surface llama-server accepts bounds `reasoning_content` by a count. So a cap
  is necessarily a cap on the whole completion, which is what makes the pairing below mandatory
  rather than stylistic.

### What a real server said

Measured 2026-08-16 by the agent against the shipped cortex tier (gemma-4-12B-it QAT q4_0,
`-ngl 99`, `-c 16384`, `--jinja`, the ghcr `server-cuda` image on the 24 GB card), three ordinary
open-ended questions, one run each per arm.

| arm | trace | reply | decoded | first word | whole turn | finish |
| --- | --- | --- | --- | --- | --- | --- |
| unbounded, thinking on (shipped) | 2545 / 3064 / 2838 chars | 4562 / 4814 / 4021 chars | 1715 / 1941 / 2139 tok | **11.8 / 15.0 / 18.1 s** | 32.5 / 37.5 / 41.4 s | `stop` 3 of 3 |
| thinking off | **0** | 4332 / 3452 / 3605 chars | 1053 / 811 / 1125 tok | **0.4 s, all three** | 20.2 / 15.5 / 21.4 s | `stop` 3 of 3 |
| `max_tokens: 512`, thinking on | 2126 / 2110 / 1465 chars | **empty, 3 of 3** | 512 / 512 / 512 tok | never | 9.8 to 10.1 s | `length` 3 of 3 |

Three readings decide everything below.

1. **The wait is the trace, entirely.** Turning deliberation off moves the first word from 11.8 to
   18.1 seconds to 0.4 seconds, and the answers stay the same size and the same shape.
2. **A cap alone deletes the answer on a user's turn too.** The fold measured this on a
   summarization prompt ([ADR-0038](ADR-0038-ranked-recall.md)); it reproduces on the resident
   cortex answering a user, 3 of 3, at a cap of 512 with a trace of 1465 to 2126 characters
   underneath it. What the user would have received is nothing at all, streamed for ten seconds.
3. **A cap is therefore only ever half a setting**, and the visible half of the failure is that
   the reply is empty rather than short, which no amount of sizing fixes while the trace is
   unbounded and unbudgetable.

### Decision

1. **The honesty ships unconditionally and the levers ship as knobs.** `TurnEngine` and
   `BrainPhase` now pass a `StopLedger` always, and a turn whose completion stopped at a token
   limit ends with `REPLY_CAPPED_NOTE` on its stream and in the message it persists. This costs a
   deployment that sets nothing one event on a turn that was already truncated, and it fixes a
   silent loss that predates every cap: **the context window cuts replies today**, and a cut reply
   is stored and read as a finished short one.
2. **The note is reply text, not a status.** It follows `BRAIN_FAILED_NOTE` exactly: streamed as a
   `TextDelta`, appended to `parts`, persisted with the answer, because it explains text the user
   can still scroll back to. It is app-authored, so it needs no guardrail pass, and nothing crosses
   `proto/body.proto`.
3. **It never names which limit cut the reply**, because nothing on the wire separates a request's
   `max_tokens` from the server's context window, which the finish-reason addendum settled. The
   note says the machine's length limit and stops there.
4. **A failed deep phase says one thing, not two.** `BRAIN_FAILED_NOTE` already tells the reader
   the answer is unfinished, so the cap note is suppressed when the phase raised; two explanations
   for one stump, one of them possibly wrong, is worse than the truer one alone.
5. **Both levers are one env value, `ReplyBoundsConfig`, in its own module.** `CORTEX_REPLY_THINKING`
   (default true) and `CORTEX_REPLY_MAX_TOKENS` (default 0, meaning no cap) reduce to `None` when
   neither is set, so the unasked deployment's request is byte-identical. They live in
   `config_reply.py` rather than in `BrainRuntimeConfig` because that file is at its line cap and
   because these two are one decision with one argument, the precedent `config_tools.py` and
   `config_subagents.py` set. The value reaches the core on `TurnCapabilities`, which is where
   that bundle's own docstring says a per-turn capability joins, rather than as a constructor
   argument on each engine: both were already at ruff's argument ceiling, and it is the reason
   a handoff keeps the turn's bound for free, the deep phase being handed the same bundle with
   two fields replaced.
6. **Neither default flips.** Thinking on is what the deep tier was picked for, the lineup having
   rejected two faster candidates for never leaving their traces, and the cortex's trace is a
   rendered surface a user watches. What the measurement earns is the right to turn it off on a
   deployment that would rather have its answer in 0.4 s, not the right to decide that for every
   deployment. The delegated path's own bounds stay separate, in `config_subagents.py`, because a
   subtask nobody reads and an answer somebody is watching are not bounded on the same argument.
7. **The two knobs are documented as a pair**, since the measurement says a cap with thinking left
   on is not a smaller answer but no answer, and the runbook says so where an operator sets them
   (docs/runbooks/llamacpp-gpu.md).

### Distrust green

Six mutations, each applied to production code alone with the whole `packages` suite re-run.

| mutation | tests that fail |
| --- | --- |
| `cap_note` yields nothing when capped | **2**, the cortex note and the deep one |
| `cap_note` yields the note on every turn | **70** |
| the note is yielded but not appended to `parts` | **2**, the two that read the store back |
| `TurnEngine` passes no `StopLedger` | **1**, the cortex note |
| `BrainPhase` emits the note even when the phase failed | **1**, the two-notes case |
| `ReplyBoundsConfig.bounds` returns bounds when nothing is set | **1**, the default case |

Two readings say something the counts alone do not.

**The note-on-every-turn mutation fails 70 tests**, which is the measure of how ordinary the silent
path is. Nearly every turn in the suite ends with no stop reported at all, so a ledger that
answered "capped" for silence would rewrite the ending of the whole corpus, the shape the
finish-reason addendum's own 29 had one level down.

**The bounds mutation fails only its own unit test.** Nothing asserts on what the composition
root hands the engine, because `run_from_env` is exercised as a whole rather than for the value it
passes, so a wiring that read the config and dropped it would be caught by the config's test not
at all and by the engine's not at all. That gap is the honest cost of a knob whose producer and
consumer are tested apart, and it is the one thing here a live run is the only witness for.
## Addendum (2026-08-17): the trace budget, which is the middle of the thinking dial

**Status:** Accepted. Closes "the reasoning budget is all or nothing" from
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager),
which the capped-reply addendum above opened the day it measured the trace as the whole of the
wait and found no way to bound it separately.

That entry rested on one claim about the engine, and the claim was wrong on the image this
repo runs. It said `--reasoning-budget` is "a per-server switch taking 0 or -1, not a count, and
it does not work on this build at all". The binary's own help says otherwise:

```
--reasoning-budget N   token budget for thinking: -1 for unrestricted, 0 for immediate end,
                       N>0 for token budget (default: -1)
```

So the middle the entry wanted exists, in the one place the entry did not look again.

### What the tree actually said

Re-derived rather than trusted, an entry's account of the code being the thing this backlog
warns about.

- `GenerationBounds(max_tokens, thinking)` is the whole of the per-request vocabulary, and
  `thinking` renders as `chat_template_kwargs: {"enable_thinking": false}` or as nothing at all.
  The two ends of the dial, exactly as the entry described them.
- `tiers.py` is "the one place a llama-server command line is assembled", and `TierArgs.extra`
  already carries a per-tier tail: the GPU-placed subagent tier's reasoning-off pair. So a tier
  flag has a home and a precedent, and the cortex and deep tiers carry no tail at all today.
- Nothing in the brain reads or reports a trace length, so a budget expressed there would have to
  be a client-side cut, which is the option the entry itself priced and rejected.

### What a real server said

Measured 2026-08-17 by the agent against the shipped cortex tier (gemma-4-12B QAT q4_0, `-ngl 99`,
`-c 16384`, `--jinja`, the ghcr `server-cuda` image, build `b9870-2d973636e`, on the 24 GB card),
three ordinary open questions, one run each per arm.

| `--reasoning-budget` | trace | first word | reply | whole turn | finish |
| --- | --- | --- | --- | --- | --- |
| unset (shipped) | 2323 / 2996 / 2507 chars | 10.1 / 12.6 / 11.0 s | 4408 / 4712 / 4131 chars | 31.3 / 33.2 / 26.8 s | `stop` 3 of 3 |
| `512` | 2003 / 1963 / 2004 chars | 8.4 / 9.2 / 8.5 s | 4189 / 4659 / 4170 chars | 25.7 / 29.4 / 24.6 s | `stop` 3 of 3 |
| `128` | 507 / 483 / 536 chars | **1.7 / 2.6 / 2.5 s** | 4558 / 4450 / 4201 chars | 20.9 / 20.4 / 18.9 s | `stop` 3 of 3 |
| `0` | none | 0.2 s | 4483 chars | 19.0 s | `stop` |

Five readings decide everything below.

1. **It is a dial, not a third switch.** The first word moves with the count through four
   settings, and the reply stays the same size in all of them.
2. **The answer survives the cut.** Every arm finished `stop`, and a trace guillotined mid
   sentence at 128 was followed by a full coherent reply. That is the difference between the
   engine's budget and the client-side cut the entry rejected: the engine closes the thought and
   the model answers, where a client can only stop the stream and re-ask.
3. **It rescues the cap this ADR shipped half-usable.** `max_tokens: 512` with thinking on
   returned an empty reply 3 of 3 above; under a budget of 128 the same cap returned 1488 and
   1561 characters of answer. The pairing rule loosens from "a cap needs thinking off" to "a cap
   needs a bounded trace", which is what it always meant.
4. **It is per server and cannot be moved per request.** A request body carrying
   `reasoning_budget: 128` was ignored on an unbudgeted server (trace 2478 chars), and one
   carrying `reasoning_budget: -1`, whether at the top level or inside `chat_template_kwargs`, did
   not lift a budgeted server's own count (508 and 515 chars). Both directions, so this is the
   engine's answer and not a guess about it.
5. **Nothing else about the tier moves.** A per-request `enable_thinking: false` still yields no
   trace at all under a budget (0 chars, 0.34 s), so every pass whose deliberation `drain_text`
   discards is unaffected; and a trace cut at the count was followed by a well formed tool call
   parsing to its arguments and finishing `tool_calls`, so the cortex's tool loop is unaffected too.

**The shipped wiring was run, not only the flag.** The gap the capped-reply addendum above named
in its own distrust-green section, that nothing asserts what the composition root hands the engine,
is the gap a tier flag has too, so it was closed by running the stack rather than by a unit test:
with `CORTEX_REASONING_BUDGET=128` in the environment, `just up-gpu` brought the model host up
healthy and its supervised child's own command line read
`/app/llama-server --model ... --parallel 1 --jinja --reasoning-budget 128`, with a question through
that tier spending 498 characters of trace and 2.2 s to its first word for a 4849-character reply.

### Decision

1. **The budget is tier configuration, not a port field.** `CORTEX_REASONING_BUDGET` and
   `CORTEX_REASONING_BUDGET_BRAIN` reach `ModelHostConfig` and render as llama.cpp's own
   `--reasoning-budget N` on that tier's argv. Nothing crosses `InferenceBackend`, because there
   is nothing for it to carry: the engine will not read a budget off a request, and inventing a
   field the adapter drops would be a knob with no effect on the server.
2. **`GenerationBounds` does not grow.** The port already says whether a request asks for
   deliberation; the tier now says how long a requested one may be. Two orthogonal facts at the
   two layers that can express them, and the core stays a pure function over what it was given.
3. **No client-side budget is built.** The entry priced both candidates and both are worse than
   either end of the dial: stopping the stream and re-asking with thinking off spends the trace's
   time and then buys the thinking-off answer, and cutting the completion outright is the empty
   reply this ADR already measured. Neither can close the thought, which is the only thing that
   makes a bounded trace produce a whole answer.
4. **`-1` is the unset value, and `0` is a setting.** `-1` is llama.cpp's own word for
   unrestricted, so a deployment that names nothing emits no flag and its tier comes up with the
   argv it always had. Zero means the thought ends at once, so it must reach the argv rather than
   read as an absent knob, which is why this sentinel cannot be the falsy value the image budget
   uses.
5. **Two knobs, because two tiers are read on opposite arguments.** The cortex answers while
   somebody watches; the deep model was picked for reaching an answer inside its trace at all
   ([ADR-0004](ADR-0004-model-lineup.md)). A deployment that shortens one has no reason to have
   shortened the other.
6. **Neither default flips.** What the measurement earns is the right to bound the trace on a
   deployment that would rather have its answer sooner, not the right to decide that for every
   deployment. The runbook's advice is to start at `512` on a tier a user reads.
7. **The GPU-placed subagent tier gains nothing.** Its deliberation is already off at the
   template, so a positive count there would be a knob no env can make matter.
   **Superseded 2026-08-26 by the thinking-lever addendum below**, whose measurement is that the
   premise is false: the trace runs on any request carrying a `response_format`, which is every
   reply a tool-less subagent decodes. (That addendum blamed the template, and the
   switch-is-advisory addendum below corrects it: the template reads the kwarg fine, on a plain
   request.) That tier now carries `--reasoning-budget 0`, a fixed
   zero rather than a count, so what stays true is the second half of this decision: a *positive*
   count there is still a knob no env can make matter.

### What this does not do, and where that is recorded

- **One tier, one budget.** Two callers on the same tier cannot have different positive budgets,
  so a deployment wanting a short think for a user's reply and a long one for the deep phase can
  only get it by putting them on different tiers. Reopening needs an engine that reads the count
  off a request, which is
  [docs/refinements/tasks/295-per-request-trace-budget.md](../refinements/tasks/295-per-request-trace-budget.md).
- **What a bounded trace costs the answer is not measured.** Four multi-step items with one right
  answer each came back right at unbounded, `128` and `0` alike, so they price the latency and say
  nothing about the ceiling; the open questions' replies were compared by size and read, not
  scored. Recorded as
  [docs/refinements/tasks/296-trace-budget-quality-floor.md](../refinements/tasks/296-trace-budget-quality-floor.md).
- **`--reasoning-budget-message` is measured and not taken.** The flag injects a sentence before
  the end of thought, and it works: at a budget of 128 the trace ended with the operator's own
  words and the reply was full and coherent. It is not shipped because it buys nothing the budget
  alone did not, and because that sentence lands in `reasoning_content`, which the overlay renders
  as the user's visible thinking status; an operator's instruction to the model reading as the
  model's own thought is a surface change, not a knob. Adding it later is one tuple in `_reasoning`.
- **The flag has to exist in the deployment's own build.** A llama.cpp that does not know it fails
  the tier at startup rather than ignoring it, which is the argument for the default emitting
  nothing at all rather than an explicit `-1`.

### Distrust green

Two mutations, each applied to production code alone with the `model_manager` suite re-run.

| mutation | tests that fail |
| --- | --- |
| `_reasoning` always returns no flag | **4**, every tier that asked for a budget |
| `_reasoning` treats `0` as unset (`budget <= 0`) | **1**, exactly the test written for that line |

The second is the one worth stating: the sentinel is the only thing separating "nobody asked" from
"end the thought immediately", and a reading that folds them costs a deployment the setting it
chose while leaving every other test green.

## Addendum (2026-08-17): the cap that lands inside a tool call

**Status:** Accepted. Closes "a cap that lands mid tool call reads as a dead backend" from
[docs/refinements/index.md#subagents](../refinements/index.md#subagents), which the finish-reason
addendum above opened as the one path where a capped run does not reach the settling that reports
it.

### What the tree actually said

Re-derived and then reproduced, because this entry's whole claim is an ordering between four
pieces of code.

- `LlamaCppBackend.stream` yields each chunk's events inside the stream and assembles the model's
  tool calls only **after** it, so `finish_calls` raises with the `DecodeStop` already delivered.
- `stream_tool_loop` hands every `DecodeStop` to `context.stops`, so the ledger is already
  answering "capped" when that raise crosses it.
- `PlacedAttempt` catches `InferenceError` in an arm that reports `AttemptFailure.INFERENCE`
  without consulting the ledger.
- `SubagentRunner._placed` re-places exactly `AttemptFailure.INFERENCE` from a GPU placement.

So a cut tool call cost a second model load to be cut at the same cap again, and the stored detail
named a JSON decode error where the truth was a token limit.

### What a real server said

Measured 2026-08-17 by the agent against the cortex artifact run in a subagent tier's shape
(gemma-4-12B QAT q4_0, `-ngl 99`, `-c 16384`, `--jinja`,
`--chat-template-kwargs '{"enable_thinking": false}'`, build `b9870-2d973636e`), asking for a long
argument under a small cap, one run per cap:

| cap | `finish_reason` | tool-call fragments | assembled `arguments` |
| --- | --- | --- | --- |
| 20 | `length` | 14 | 71 chars, unterminated string |
| 40 | `length` | 34 | 177 chars, unterminated string |
| 80 | `length` | 74 | 466 chars, unterminated string |
| 160 | `length` | 154 | 899 chars, unterminated string |

Two readings settle the design. **The server does stream a partial tool call**, so this is not a
case the engine swallows, and **it says `length` while doing it**, so the two facts the verdict
needs are both on the wire. Then the shipped attempt over the shipped adapter, same server, cap 60:
before the arm it answered `AttemptFailure.INFERENCE` with
`malformed tool-call arguments from llama-server: '{"body":"Distributed systems are composed of ...`
and after it `AttemptFailure.TRUNCATED` with the refusal that names the cap.

### Decision

1. **The port grows a narrower error, not a flag.** `MalformedToolCallError(InferenceError)` says
   the stream arrived and the **model's own tokens** will not parse. It is a subclass, so every
   existing `except InferenceError` keeps catching it and no consumer changes; only a caller that
   can act on the distinction names it. The `MemoryDataError` and `ModelNotHostedError` precedent,
   for the same reason both were subclasses: a fact about the answer, filed apart from a verdict
   about the machine.
2. **Only `finish_calls` raises it.** A status, a stall, a chunk this adapter cannot read: all
   stay the wide type, because those are the server's failures and another server may do better.
   A tool call's `arguments` are the model's, and the same model on another target writes them
   again.
3. **The verdict needs both facts, and the arm asks for both.** `PlacedAttempt` reports
   `TRUNCATED` only when the narrower error arrives **and** its `StopLedger` saw a capped
   completion. This is what the entry could not resolve: reading the ledger in the wide arm would
   report a dead backend on a round after a capped one as a truncation and skip the re-place that
   exists for exactly that, and reading only the error type would call a model that broke its own
   grammar a truncation. Neither half alone is the answer, which is why the type had to exist.
4. **It is reported in the words the ordinary capped path already uses.** `cap_detail` is the same
   refusal `settle_reply` produces, so the cortex reads one sentence for one situation, and the
   runner declines to re-place it for the reason it declines the other: a tier that filled its
   token budget will fill it again.
5. **Silence stays silence.** A build that reports no finish reason leaves the ledger saying
   nothing, and an unparsable call under it is reported exactly as it was before this arm existed.
   The `StopLedger` invariant is unchanged: silence is not a cap.

### What this does not do, and where that is recorded

- **The cortex's own turn is untouched.** The same cut on the cortex path raises through
  `handle_turn` and surfaces as a seam error naming a JSON decode failure, where the turn's own
  capped-reply note would be the truer thing to say. It is a different consumer with a different
  surface, recorded as
  [docs/refinements/tasks/297-cut-tool-call-fails-the-cortex-turn.md](../refinements/tasks/297-cut-tool-call-fails-the-cortex-turn.md).
- **Nothing is done about the cut itself.** A run cut inside a tool call is still a run that did
  not answer; what changed is that it says so, and stops buying a second model load to find out
  again.

### Distrust green

Four mutations, each applied to production code alone with the whole `packages` suite re-run.

| mutation | tests that fail |
| --- | --- |
| the `MalformedToolCallError` arm deleted, so a cut call falls through to the wide one | **2** |
| that arm answers `TRUNCATED` without consulting the ledger | **1**, the no-cap case |
| `finish_calls` raises the wide `InferenceError` again | **1**, the adapter's own case |
| the ledger read in the **wide** arm instead, the one-line fix the entry warned about | **1**, the dead-backend-after-a-cap case |

The last row is the one worth stating: it is the fix that looks right, it passes every test that
existed before this arm, and the case it breaks is the case the entry named as the reason to wait.

## Addendum (2026-08-20): the same cut on the cortex's own turn

**Status:** Accepted. Closes "a cut tool call fails the cortex turn as an inference error" from
[docs/refinements/index.md#inference-model-manager](../refinements/index.md#inference-model-manager),
which the tool-call-cut addendum above opened under its own "What this does not do" heading as the
consumer it did not reach.

The addendum above fixed the delegated half of one shape and named the other. A completion cut
while the cortex was writing a tool call's `arguments` raises out of `stream_tool_loop` exactly as
a delegated one does, and on the cortex path nothing caught it: `handle_turn` had a bare
`try/finally` around its event stream, so the error travelled to the turn task in
`converse_stream.py`, which turns any `InferenceError` into a seam error carrying
`ERROR_CODE_INFERENCE_FAILED` and the exception's own text. The user was told inference had failed
and shown a fragment of JSON, the partial reply they had just watched arrive was dropped from
history, and nothing was recorded to memory.

### What the control flow actually was, since the arm turns on it

Re-derived before writing anything, because the hazard here is not the catch but where the catch
leaves the function.

- `stream_turn_events` flushes the guarded channels only after its `async for` completes
  normally. On an exception it closes the loop in its `finally` and flushes nothing, deliberately,
  so the caller decides whether a partial reply is worth keeping.
- `handle_turn` ran `cap_note`, joined the text, appended the assistant message, recorded the
  exchange and yielded `TurnCompleted` **after** that `try/finally`, all of it reachable only on
  the non-raising branch. So the persist path was not a step that could be skipped; it was code
  the raise jumped over entirely.

That is why the arm is an `except` that falls through rather than one that returns or re-raises.
Everything after the block runs once, for a cut turn exactly as for a turn that ended itself, and
there is no second write to leave out of step with the first.

### Decision

1. **The engine catches `MalformedToolCallError` and ends the turn.** Not `InferenceError`: a
   transport failure says nothing about whose tokens they were and stays a seam error, which is
   the same narrowness the delegated arm was built with and the reason the type exists at all.
2. **The arm flushes the channels itself**, since the mapper flushes only on a clean end. Without
   it a guardrail's held tail, a URL it was still matching, would be dropped from a reply the note
   is about to call everything the model produced. This is `BrainPhase`'s discipline, reached by
   the same reasoning about the same helper.
3. **The ledger picks between two sentences, and there are exactly two.** Capped, the truthful
   thing is what any capped reply already says, so `cap_note` speaks and the arm adds nothing;
   uncapped, no limit explains the fragment and `UNREADABLE_CALL_NOTE` says what happened without
   naming a bound that was never reached. `unreadable_call_note` reads the same boolean as
   `cap_note` and disagrees with it by construction, so the two can be called in sequence and the
   reader is never handed two explanations for one stump. Silence is still not a cap: a build
   reporting no finish reason takes the unreadable note, because sending a reader after a token
   budget nothing reported is the invention the ledger's invariant exists to refuse.
4. **It reports `TRUNCATED` in the words the ordinary capped path uses**, which is the delegated
   arm's decision restated for a different surface. There the words are `cap_detail` in an
   outcome; here they are `REPLY_CAPPED_NOTE` under the text, because a user is already watching
   the reply arrive and what is owed is a sentence rather than a refusal.
5. **The fault still reaches the operator, because the turn no longer does.** The arm logs a
   `warning` naming the session, the turn and `capped`, with the error as `exc_info`, which is
   where the fragment goes now that no seam error carries it. `capped` is the same reading the
   note is picked by, so the log says which sentence the user saw.

### What this does not do, and where that is recorded

- **The deep model's phase still reads this as a dead server.** `BrainPhase` catches the wide
  `InferenceError`, streams `BRAIN_FAILED_NOTE`, persists, and re-raises so the conductor marks
  the handoff failed, and the deep tier is where a cut is likeliest: it ships an 8192 context and
  the measured pick spends 3847 to 4448 tokens reaching an answer. Recorded as
  [docs/refinements/tasks/340-the-deep-phase-cannot-see-a-cut-call.md](../refinements/tasks/340-the-deep-phase-cannot-see-a-cut-call.md).
- **The ledger is per turn, not per completion.** A turn whose first round was capped and whose
  third round produced an unparsable call for its own reason takes the capped note. That is the
  identical residual the delegated arm accepted when it read a per-attempt ledger, and it is
  accepted here for the same reason: the alternative is a per-completion ledger, and a turn that
  lost material to a cap in any round did lose it.
- **Nothing is done about the cut itself.** A turn cut inside a tool call is still a turn whose
  tool did not run; what changed is that it says so and keeps what it wrote.

### Distrust green

Five mutations, each applied to production code alone with the core and orchestrator suites
re-run, 2,007 tests.

| mutation | tests that fail |
| --- | --- |
| the arm deleted, so a cut call raises to the seam again | **7** |
| the arm catches the wide `InferenceError` instead | **5**, every case that pins a dead backend still failing its turn |
| the arm re-raises after noting, the shape that persists nothing | **7** |
| `unreadable_call_note` stops reading the ledger, so both notes are emitted | **2** |
| the channel flush dropped from the arm | **1**, the guardrail's held tail |

The second and fourth rows are the ones worth stating. Widening the catch is the
simpler-looking arm and it swallows the failure the seam exists to report, which is why the
control arms for it are the tests that were already there. Dropping the ledger read is the arm
that looks harmless and hands a user two explanations, one of them about a limit that was never
reached.

## Batch addendum (2026-08-25): the whole-subtask figure, re-measured from a batch

Two bounds on a delegated run rest on one number: "a whole CPU subtask measures 200 to 300 s". The
stall ceiling's derivation reads it as an upper bound on any one call's first token, and the
admission wait's multiplies it out into the queue a full batch produces. The total-cap addendum
above then measured five single subtasks on the shipped entry and found the figure out by a factor
of two for a summarization, 623.8 s, and filed the correction rather than making it, because the
queue's arithmetic is about a **batch's** serialization and five runs taken one at a time say
nothing about that. This is that batch, and it moves the figure from a point to an interval.

### Re-derived first, and the chain under the figure is shorter than it looks

The 200 to 300 s figure was never measured. The stall-ceiling section derives it: the runbook said
a three subtask batch runs 10 to 15 minutes, and dividing by three serialized subtasks gives 200 to
300 s. So a bound rests on an arithmetic step over a rule of thumb, and the 2026-08-11 table is the
first time anything of that shape was timed at all.

### What was measured

One CPU `llama-server` at the compose file's own shape (`-ngl 0`, `--ctx-size 8192`,
`--parallel 2`, thinking off, `--cpus 4.0`, `--memory 8g`), the shipped gemma-4-E4B QAT q4_0 entry,
driven through the real `SpawnSubagentsTool` -> `SubagentRunner` -> `ResourceBudgetScheduler` ->
`VramBudgetPlacer` -> `LlamaCppBackend` chain at the shipped numbers (`CPU_BUDGET=4.0`,
`MEM_BUDGET_GB=8.0`, an ask of 2.0/3.0/3.5, the 1024-token cap and the 2400 s deadline). One full
`MAX_SPAWN_BATCH` of eight, every subtask the summarization shape the table above found longest,
each over its own report body so no two prompts share a slot's prompt cache. Two regimes, the same
server both times:

- **serialized**, a zero-headroom placer, which is what a closed GPU tier or an ask that never fits
  leaves: every spawn lands on the CPU backend, one model lease, one stream at a time;
- **overlapping**, the shipped placer (14.0 GB soft cap less the 8.6 GiB cortex reservation leaves
  5.4 GiB, which holds exactly one 3.5 GiB ask): one of the admitted pair is GPU-placed and the
  other overflows, two backend objects in front of the one server's two slots.

Seconds are from the batch's first admission. `held` is what the run deadline bounds and what a
queued peer waits out, and it is larger than the subtask itself because an admitted spawn queues on
the entry's model lease **inside** its admission.

| spawn | placed | admitted | released | held | | spawn | placed | admitted | released | held |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | cpu | 0.0 | 282.6 | 282.6 | | 1 | gpu | 0.0 | 288.1 | 288.1 |
| 2 | cpu | 0.0 | 553.5 | 553.5 | | 2 | cpu | 0.0 | 317.3 | 317.3 |
| 3 | cpu | 282.6 | 877.8 | 595.2 | | 3 | gpu | 288.1 | 588.8 | 300.7 |
| 4 | cpu | 553.5 | 1117.5 | 564.0 | | 4 | cpu | 317.3 | 572.5 | 255.2 |
| 5 | cpu | 877.8 | 1386.4 | 508.6 | | 5 | cpu | 572.5 | 893.2 | 320.7 |
| 6 | cpu | 1117.5 | 1624.6 | 507.1 | | 6 | gpu | 588.8 | 858.6 | 269.8 |
| 7 | cpu | 1386.4 | 1847.4 | 461.0 | | 7 | gpu | 858.6 | 1184.5 | 325.9 |
| 8 | cpu | 1624.6 | 2096.4 | 471.8 | | 8 | cpu | 893.2 | 1170.2 | 277.0 |

The left half is the serialized regime and the right half the overlapping one. Whole batch:
**2096.4 s** serialized, **1184.5 s** overlapping. Last spawn admitted: **1624.6 s** serialized,
**893.2 s** overlapping. Every one of the sixteen subtasks answered; none was cut at the cap or at
the deadline.

### What the batch says, in four findings

**A whole subtask is 222.8 to 324.3 s here, which is the figure the two bounds were written
against.** Those are the server's own `total time` readings for the eight serialized runs, plus a
solo one before the batch at 248.6 s. So the runbook's 200 to 300 s is very nearly right on this
box today and the 623.8 s reading above is 2.2 times it, on the same box, on the same image, two
weeks apart. Neither is wrong; the figure is an **interval**, and the record now carries it as one.
The decode rates are the same story: gemma-4-E4B read 1.26 to 1.35 tok/s through this batch, and
0.32 tok/s is what 199 tokens in 623.8 s comes to. What puts a reading at one end or the other is
what else the machine is doing, which the control below measures. A
bound derived as a multiple of a number with that spread must be sized on the slow end, which both
of these were, so **neither bound moves on this measurement**.

**A run holds its admission for longer than it runs, and that is what the deadline bounds.** An
admitted spawn queues on its entry's model lease *inside* its admission, so the serialized regime's
longest hold is 595.2 s against a 324.3 s subtask. The run deadline is 2400 s, which is four times
that longest hold almost exactly, so the total-cap addendum's "four times the longest whole
subtask" and a batch-taken "four times the longest hold" land on the same number by two different
routes. That is the strongest thing this run says about the deadline: it is confirmed rather than
retuned.

**The admission wait's own arithmetic is confirmed and slightly conservative.** Its derivation
predicted "about 1800 s" serialized and "about 900 s" overlapping for the last spawn of a full
batch; measured, 1624.6 s and 893.2 s. Twice the serial figure is about 3250 s, which the 3600 s
the bound shipped at already cleared.

**Overlapping is worth almost exactly two, which the derivation only assumed.** The two backend
objects in front of one `llama-server` running `--parallel 2` finished the same eight subtasks in
1184.5 s against 2096.4 s, and per-subtask holds *fell* rather than rose (255.2 to 325.9 s against
282.6 to 595.2 s), because what the serialized regime spends waiting on the model lease the
overlapping one spends running. The GPU-placed half of each pair executed on the same CPU server
here, both endpoints resolving to it as the shipped compose leaves them, so this is the overlap the
brain buys and not the GPU's own speed.

### What this does not do

**It does not re-measure the shapes.** Every subtask in the batch is the summarization shape, the
longest of the narrow four, chosen because a bound is sized on the slow end. The lookup and
extraction shapes are unchanged from the table above.

**It does not explain the interval on its own.** The control below does, and it is the more
important half of this run.

**It leaves the batch measured through an unconstrained run**, and the one constrained run taken
beside it says that matters. The driver ran with `constrain_output` off, which is the tools-enabled
shape; the tool-less shipped shape decodes the same reply into the fixed envelope (ADR-0028). The
grammar costs nothing per token, that run decoding at 1.41 tok/s against the batch's 1.26 to 1.35.
What it changed was the length: the same subtask ran to **1024 decoded tokens**, hit the shipped
token cap, and came back as `FAILED: the subtask stopped at a token limit`, in **740.4 s** against
the 222.8 to 324.3 s the unconstrained shape takes. One sample is not a rate, but it is an
existence proof that the cap can fire on a narrow subtask on the shape this repo ships by default,
which is not what the cap's own derivation expects of it. Filed as
[R-431](../refinements/tasks/431-the-token-cap-fires-on-the-shape-that-ships.md).

### The control: what the interval is an interval of

The batch above ran on an otherwise idle box. The control is the same subtask shape, the same
container, the same server, run once while the host is saturated: one busy shell worker per core
against 24 cores, with the container still capped at `--cpus 4.0`, load average near thirty.

| reading | quiet | saturated |
| --- | --- | --- |
| prompt eval | 276 tokens in 13.4 s (**20.6 tok/s**) | 275 tokens in 40.8 s (**6.7 tok/s**) |
| decode | **1.26 to 1.35 tok/s** | **0.18 tok/s** overall, **0.07 tok/s** sustained mid-run |
| whole subtask | **222.8 to 324.3 s** | **1736.6 s** |

The cleanest line in the run is the recovery. The load was killed while that subtask was still
decoding, and the server's own three-second rate on the same slot, the same task, went from 0.06 to
**1.39 tok/s** within seconds. Nothing else about the container changed, so what the arm measures
is host contention and not the model, the prompt or the image.

**So the cgroup quota does not protect this tier.** `--cpus 4.0` is a quota and not a reservation,
and llama.cpp starts a thread per host core rather than per quota core, so a saturated host does not
cost the container a fair share of four, it costs it most of what it had. A factor of seven on
decode and three on prompt eval is what that comes to here.

**And that is what the interval is.** The 623.8 s reading this addendum was opened to reconcile sits
between the two arms rather than outside either. Nothing needs a second explanation.

**What it costs the bounds**, said plainly, because it is the finding with a consequence. A whole
subtask on a saturated box measured **1736.6 s against a 2400 s run deadline**, so a legitimate
narrow subtask on a busy machine comes within 28% of the bound that exists to cut a runaway. The
bounds are all sized on the idle end and the machine can be five to eight times slower than that.
Nothing moves here, because the right answer is a measurement of a real busy deployment rather than
of a synthetic one, and because a bound raised on this arm alone would be sized on a shell loop.
Filed as [R-430](../refinements/tasks/430-the-bounds-are-sized-on-an-idle-box.md).

**What the arm is not.** The load is a shell loop that spawns a process per iteration, so it loads
the kernel as well as the cores, and the numbers above are a direction and an order of magnitude
rather than a calibration. What it establishes is that the tier is not insulated from its host,
which is enough to explain the interval and enough to size an entry against.

## Envelope addendum (2026-08-26): what the reply envelope really spends, measured paired

The batch addendum above measured the whole-subtask figure on the **unconstrained** shape and took
one constrained control beside it, which ran to the 1024-token cap and came back a refusal on an
ordinary summarization. One sample separates nothing, so this is the paired run that does: the same
three report bodies, both shapes, serialized against one CPU `llama-server` at the compose file's
own shape, driven through the real `SubagentRunner` -> `PlacedAttempt` -> `LlamaCppBackend` chain at
the shipped bounds. The driver is
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`, integration-marked, and it writes a
`contrast.py` sample per arm so the seconds are read by the same arithmetic every other live
measurement here is read by.

### Re-derived first

`constrain_output` still defaults to `True`, and `PlacedAttempt` still applies it exactly where the
run holds no dispatcher, which is what a subagents-only stack ships. The cap is still 1024 and its
derivation is still five times a 199-token unconstrained reply. The refusal text the entry quoted is
still what the runner returns. Nothing had moved.

### What three bodies say

Each row is one report body under both shapes. Tokens are llama.cpp's own `timings.predicted_n`,
seconds are the whole run through the runner, and `reply` is what the cortex was handed.

| body | raw tokens | raw wall | raw reply | envelope tokens | envelope wall | envelope reply | envelope stop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| warehouse | 434 | 336.0 s | 1512 chars | **1024** | 787.0 s | cut, refused | **capped** |
| clinic | 366 | 282.8 s | 1559 chars | 702 | 535.1 s | 158 chars | finished |
| fleet | 544 | 425.4 s | 2211 chars | 550 | 426.9 s | 1176 chars | finished |

**The raw shape reads 366 to 544 decoded tokens in 282.8 to 425.4 s.** The envelope reads **550 to
at least 1024** in 426.9 to 787.0 s, "at least" because the shipped cap censors the top row: that
run was still writing when the count ran out. Paired, the envelope costs **1.01 to at least 2.36
times** the tokens of the same body's raw run, and it is never cheaper.

`scripts/contrast.py` over the two samples, at its default 20000 resamples and seed 20260808, puts
the envelope **+234.9 s** of wall clock per body (95% CI +1.5 to +451.0) and **+380.5 s** of delay
before the first reply token reaches the port (95% CI +197.5 to +491.9). Neither interval spans
zero, over three questions, which is as much as three questions can say. The seconds understate the
envelope slightly and in one known way: the two arms of a pair are the same prompt, so the slot's
cache hands the second one its prompt back and it re-evaluates 19 tokens where the first evaluated
282, worth about ten seconds out of hundreds. The tokens are untouched by it.

### So it is the envelope, and not the body or the draw

The entry this closes named three candidate explanations. The pairing rules two of them out and
re-describes the third. It is not that one report body invites a long answer: every body's envelope
run is at or above its own raw run, and the design holds the body fixed. It is not ordinary
sampling variance either, in the direction that matters: the effect points the same way in all
three pairs and reaches a factor of two in two of them, though the third sits within six tokens of
no effect at all, which is the honest width of three questions. So it is the envelope. What it is
**not** is the envelope inviting a longer *answer*, which is what the entry assumed and what the
character counts refuse. The envelope's replies are **shorter**: 158 and 1176
characters against 1559 and 2211 for the same bodies raw. It spends more tokens and returns less
text.

### Where the tokens actually go, which is the finding

A probe at a cap of 200 on the same shape, with the two halves of the stream kept apart, decodes
**200 tokens of which 0 are reply text and 763 characters are reasoning**, opening
`Here's a thinking process to ensure all details are captured accurately`. Read off the wire
instead of off the port, the same request is 200 SSE lines over 156.3 s, **not one of them a
content delta**, arriving with a longest gap between two lines of **3.46 s**. So nothing here is
silent and nothing is wedged: the 600 s stall ceiling is two orders of magnitude away from what
this shape actually does, which is talk to itself at full speed. The subagent tier is
supposed to have thinking off: both lineup families are reasoning models, and every subagent server
this repo ships starts with `--chat-template-kwargs '{"enable_thinking": false}'` (ADR-0010), which
is why `PlacedAttempt` deliberately sends no per-request thinking key. **That server-side lever
holds on the raw request and does not hold once the request carries a `response_format`.** The raw
arm's first reply token arrives 13.1 to 14.2 s in, immediately after prompt eval; the envelope arm's
arrives 210.9 to 505.0 s in, because everything before it is a reasoning trace that
`stream_tool_loop` then drops unread.

So the shipped tool-less shape spends most of a cap sized on reply length on text no reader ever
sees, and ADR-0038's pairing rule is exactly the one being broken: a cap on a reasoning model with
thinking left on deletes the reply rather than shortening it. The warehouse row is that sentence
happening to an ordinary subtask.

### What moves, and what deliberately does not

**The cap does not move here.** Its derivation is invalidated on the shape that ships, but the
number that would replace it cannot be measured while the reasoning is running: the longest envelope
reading is a lower bound of 1024 rather than a length, and five times even that lower bound is 5120,
above the 4096 tokens a slot gets from this compose file's 8192 across `--parallel 2`. So the rule
that produced 1024 has no room left to produce anything on this shape. Retuning a cap around a
defect rather than fixing the defect would also be the wrong repair, and retuning it on an
extrapolated number is the exact failure the entry behind this run exists to warn against. The fix
is [R-456](../refinements/tasks/456-a-constrained-request-loses-the-thinking-lever.md) and the
re-derivation waiting on it is
[R-457](../refinements/tasks/457-the-caps-derivation-on-the-shape-that-ships.md), which may well
find nothing left to do.

**A mid-envelope cut is reported as the cap, live and end to end.** `settle_reply` reads `capped`
ahead of the envelope check so a reply the server stopped is never blamed on the model's grammar,
and the warehouse run exercised that path for real: `AttemptFailure.TRUNCATED`, the capped-run
refusal naming the deployment's own 1024, and no `MALFORMED`. The arm ordering does what it was
written to do.

**The registry now holds the cap.** `DEFAULT_SUBAGENT_MAX_TOKENS` was the only one of the four
bounds around a delegated run that `scripts/crosscheck.py` did not tie to the runbook and the module
contract that quote it, so retuning it alone was a silent green. It is tied now, which is what makes
the retune those two entries carry a change a gate will hold rather than one three documents can
drift behind.

## Thinking-lever addendum (2026-08-26): the flag that reaches a constrained request

**Status:** Accepted. Closes
[docs/refinements/tasks/456-a-constrained-request-loses-the-thinking-lever.md](../refinements/tasks/456-a-constrained-request-loses-the-thinking-lever.md),
which the envelope addendum above opened the hour it found where the envelope's tokens go.

The addendum above measured the defect and proposed the fix in one sentence: give a constrained
attempt a `GenerationBounds` with `thinking=False`, so the request carries the key itself rather
than trusting a server flag a `response_format` overrides. **That fix was built, run against the
live tier, and does not work.** What it was reaching for exists, one flag over.

### Re-derived first

Read off the tree rather than off the entry. `build_payload` still emits
`chat_template_kwargs: {"enable_thinking": false}` for a bound whose `thinking` is false and
nothing at all for one whose `thinking` is true. `PlacedAttempt` still built its `_generation` from
`bounds.max_tokens` alone, its comment still carrying the argument for sending no thinking key.
`UNBOUNDED_ATTEMPT` still made that `None`. `constrain_output` still defaults on and still applies
where the run holds no dispatcher. Nothing had moved.

### The fix the entry named, built and measured

`PlacedAttempt` was changed to build `GenerationBounds(max_tokens=..., thinking=False)` whenever
the attempt is constrained, riding the constraint rather than the cap, with the unbounded case
sending a bounds it had never sent. Three behaviour tests, green. Then the same probe the defect
was measured with, one body at a cap of 200 through
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`:

| arm | first reply token | decoded | stop | reply | reasoning |
| --- | --- | --- | --- | --- | --- |
| before, shipped code | 159.7 s | 200 | capped | 0 chars | 671 chars |
| the per-request key | 150.0 s | 200 | capped | 0 chars | 709 chars |

Unchanged, inside the noise of two runs of the same thing. So the change was reverted rather than
landed, and the wire was read instead of the port. Four requests against the same server, the
harness's own prompt, a cap of 40 so each costs half a minute:

| request | reply | reasoning |
| --- | --- | --- |
| no `response_format`, no kwargs | 171 chars from 3.0 s | none |
| `response_format`, no kwargs | none | a trace |
| `response_format` + `chat_template_kwargs` | none | a trace |
| `response_format` + kwargs, no system role | none | a trace |

And on a short arithmetic prompt (`"What is 17 + 25?"`) the `response_format` arm answers `42` with
no trace at all, with or without the key. **So the entry's mechanism was half right.** It is not
that a `response_format` cancels the kwarg. It is that on this template the kwarg is not what
suppresses the trace in the first place: ADR-0010 recorded that "the kwarg is ignored by
non-reasoning templates like gemma-4-E\*", and the pick this tier ships is one. What the constrained
shape changes is whether the model deliberates at all, and the key it was being asked to stop with
had never been reading on this model.

> **Wrong, and corrected 2026-08-27 by the switch-is-advisory addendum below.** The paragraph above
> is this addendum's one bad inference, and the table it rests on is why: its first row carried no
> kwarg and produced **no trace**, so the model was not deliberating on that prompt in that shape,
> and nothing under it can say what a key to stop a deliberation did. Measured on a prompt that does
> invite one, the E4B template reads the kwarg on a plain request and the `response_format` is
> exactly what costs it its effect, so the entry's own mechanism was right after all. Everything
> else here stands: the fix, the readings, and the reason the per-request key bought nothing. ADR-0010 records it working on the Qwen roster alternate,
which is the pick that addendum validated it against, and that reading is not re-taken here; what
kept the two conclusions from being separated is that until the envelope landed, nothing on this
tier asked the model to deliberate, so a template that read the kwarg and one that ignored it
behaved identically.

### The lever that does work

`--reasoning-budget 0`, which the trace-budget addendum above measured on the cortex tier and this
ADR's own decision then declined to give the subagent tier, on the grounds that "its deliberation is
already off at the template, so a positive count there would be a knob no env can make matter". The
first half of that sentence is what the envelope measurement refutes. The same server, restarted
with the budget beside the kwarg, on the same prompt at the same cap:

| server | reply | reasoning |
| --- | --- | --- |
| kwarg only | none, in 33 s | a trace |
| kwarg + `--reasoning-budget 0` | from 1.0 to 2.4 s | none |

### Decision

1. **Every subagent server this repo ships carries both flags.** The template kwarg stays, being
   what the Qwen roster alternate's template actually reads, and `--reasoning-budget 0` joins it in
   `docker/docker-compose.subagents.yml`, in the roster override beside it, and in the hosted GPU
   subagent tier's `_REASONING_OFF`. Neither is redundant and neither alone covers the lineup.
   The cost is the one the trace-budget addendum already named for the cortex tier: a llama.cpp
   that does not know the flag **fails the server at startup** rather than ignoring it, so a
   deployment pinning an old digest of `ghcr.io/ggml-org/llama.cpp:server` trades a slow subagent
   for one that will not come up. That is the right way round. A tier that refuses to start says
   so on the first `docker compose up`, where this defect said nothing for as long as nobody
   measured a delegated reply.
2. **Zero rather than a count, and not the deployment's own.** `CORTEX_REASONING_BUDGET` bounds the
   length of a thought the cortex is having on purpose. A narrow subtask needs no thought, so the
   subagent tier is not routed through `_reasoning` and a deployment that lengthens the cortex's
   trace cannot lengthen a subagent's with it.
3. **This stays per tier and does not become a port field.** The measurement above is why: the
   per-request key was built, run, and had no effect on the shape that needed it, and the
   trace-budget addendum separately measured that llama.cpp will not read `reasoning_budget` off a
   request in either direction. A port field the engine ignores is a knob with no effect, which is
   the same argument that kept the trace budget out of `GenerationBounds`.
4. **`PlacedAttempt` keeps sending no thinking key**, and the argument on `_generation` stands
   unamended. It said saying it again per request would change the request for a deployment whose
   template spells the flag differently; what this measurement adds is that it would also not have
   worked, so the reversal buys nothing on either side of the trade.

### The live reading

One body, one shape, one cap, through the committed harness against the compose file's own CPU
`llama-server` (gemma-4-E4B QAT q4_0, `-ngl 0 --jinja --parallel 2 --ctx-size 8192`), at
`CORTEX_ENVELOPE_MAX_TOKENS=200` so the arm is a probe rather than a run. Both rows are this
machine in this session, so they differ in the tier's argv and in nothing else.

| arm | first reply token | decoded | stop | reply | reasoning | outcome |
| --- | --- | --- | --- | --- | --- | --- |
| kwarg only | 159.7 s | 200 | capped | 0 chars | 671 chars | refused |
| kwarg + budget | **17.5 s** | 50 | **finished** | 151 chars | **0 chars** | answered |

A single labelled reading per arm rather than an interval, because two runs is not a width. The
before row also reproduces the reading the envelope addendum recorded from a separate probe (200
tokens, 0 reply text, 763 characters of reasoning), which is as much replication as either number
gets.

The run stopped **finished** rather than at the cap, which is the whole of the defect gone: what
reached the cortex is an answer and not the refusal that a cap on ordinary narrow work was
producing.

At the **shipped** cap of 1024, the same arm over the same three report bodies the envelope
addendum measured:

| body | first reply token | decoded | stop | reply | reasoning | envelope reading before |
| --- | --- | --- | --- | --- | --- | --- |
| warehouse | 7.5 s | 64 | finished | 230 chars | 0 | 1024, capped, refused |
| clinic | 18.0 s | 63 | finished | 223 chars | 0 | 702, 158 chars |
| fleet | 17.6 s | 89 | finished | 395 chars | 0 | 550, 1176 chars |

**63 to 89 decoded tokens against 550 to at least 1024**, at the cap that was firing. The cap now
has an order of magnitude of headroom on the shape it was failing, which is what
[R-457](../refinements/tasks/457-the-caps-derivation-on-the-shape-that-ships.md) was waiting to be
able to read.

**One thing these readings do not say, and it is not small.** The replies are short because they
are the wrong text. All three open by narrating the task rather than doing it: "The user wants a
comprehensive summary of the provided site report", "I need to summarize the provided text while
ensuring every single detail is retained", and the fleet run spends its reply arguing that the
instruction contradicts itself. With the trace suppressed, this model writes into `reply` what it
would otherwise have written into `reasoning_content`, and the envelope's `reply` property carries
no description telling it otherwise. That is three draws from a 4B model and it prices nothing on
its own, but it is the first sight of this shape answering without a trace and it is recorded
rather than smoothed over. What the envelope costs the *answer*, as against the tokens, is
[R-459](../refinements/tasks/459-what-the-envelope-costs-the-answer.md), and it is the reason the
cap is not re-derived from the numbers above in the same breath.

### What this does not do, and where that is recorded

- **The port's own thinking switch is now known to be conditional**, holding on a plain request and
  doing nothing on a constrained one on this template, and nothing in the tree says so to a caller.
  Four shipped bounds rest on it, and one of them, the rerank judge's, pairs it with a schema of
  its own.
  [R-458](../refinements/tasks/458-the-ports-thinking-switch-is-conditional.md).
- **Three files now spell the same reasoning-off pair and nothing holds them together**, the two
  subagent compose files and the model host's `_REASONING_OFF`.
  [R-460](../refinements/tasks/460-the-reasoning-off-pair-is-spelled-in-three-places.md).
- **The kwarg is deprecated on the shipped image**, which says so on every subagent boot:

```
Setting 'enable_thinking' via --chat-template-kwargs is deprecated. Use --reasoning on /
--reasoning off instead.
```

  So the older half of the pair is on a clock, and the replacement it names may well do the work of
  both. [R-461](../refinements/tasks/461-the-tiers-thinking-flag-is-deprecated.md).

## Switch-is-advisory addendum (2026-08-27): which request shapes a thinking switch survives

**Status:** Accepted, and extended 2026-08-28 by the mechanism section below, which names what
reading 4 could only say was decided out of sight and closes
[docs/refinements/tasks/464-why-a-grammar-restores-the-trace.md](../refinements/tasks/464-why-a-grammar-restores-the-trace.md),
and by the lineup section after it, which asks every remaining entry of
[ADR-0004](ADR-0004-model-lineup.md) the same question and closes
[docs/refinements/tasks/465-the-switch-across-the-lineup.md](../refinements/tasks/465-the-switch-across-the-lineup.md).
Closes
[docs/refinements/tasks/458-the-ports-thinking-switch-is-conditional.md](../refinements/tasks/458-the-ports-thinking-switch-is-conditional.md),
which the thinking-lever addendum above opened as its own residue, and **corrects that addendum's
account of the defect it fixed**. The repair it shipped is right and does not move. The mechanism
it wrote down is wrong, and the entry it opened was wrong about the same thing in the opposite
direction, so both are re-derived here from a measurement neither of them took.

### Re-derived first

Read off the tree rather than off the entry. `build_payload` still renders `thinking=False` as
`chat_template_kwargs: {"enable_thinking": false}` and a `thinking=True` bound as no key at all.
Four shipped bounds still pair a cap sized on the wanted answer with that switch: `TITLE_BOUNDS`
(32), `RECAP_BOUNDS` (512), `rank_bounds(k)` (24 + 8k, and the only one that also carries a schema,
`ORDER_ENVELOPE`), and the cortex turn's own, which a deployment builds from
`CORTEX_REPLY_MAX_TOKENS` and `CORTEX_REPLY_THINKING`. `drain_text` still drops every
`ReasoningChunk` before its caller sees one. Nothing had moved.

The entry's own worry, that the cortex family might ignore the kwarg the way the subagent pick was
said to, is answered by the tree before any server is started: each of those four bounds was landed
with a live before-and-after on the shipped cortex, and each shows the switch doing something large.
Re-run today against the running tier, unbudgeted, they still do:

| shape | with the switch | without it |
| --- | --- | --- |
| title, cap 32 | 0.3 / 0.3 / 0.3 s, same three titles | 4.1 / 4.4 / 3.2 s |
| recap, cap 512 | 2.2 / 2.2 / 2.5 s, 378 / 380 / 398 chars | 8.2 / 9.5 / 6.0 s, 368 / 382 / 326 chars |
| rank, cap 48 **and a schema** | 0.8 s per question, MRR 1.000, 0 fallbacks | 7.5 s per question, MRR 1.000 |

The rank row is the one the entry was afraid of, a cap and a schema and the switch together, and on
this tier it is the cheap arm that ships. So the four are safe where they run, and that is not what
this addendum is about.

### What a real server said

The question the entry could not answer from the tree is whether the switch is conditional on the
request's **shape**, which is what the thinking-lever addendum above denied. Measured 2026-08-27 by
the agent through the committed probe
(`brain/packages/inference/tests/test_thinking_switch_live.py`), which sends one prompt four ways
against one server: plain and carrying `REPLY_ENVELOPE`, each with the switch and without it. Both
servers were started with **neither** `--chat-template-kwargs` nor `--reasoning-budget`, since
either one is the deployment answering the question for the model. One run per cell, at a cap of
256, reading trace characters then reply characters:

| tier | plain, no switch | plain, switch | envelope, no switch | envelope, switch |
| --- | --- | --- | --- | --- |
| cortex, gemma-4-12B QAT q4_0, `-ngl 99 -c 16384` | 735, 0 | 0, 693 | 685, 0 | **0, 611** |
| subagent, gemma-4-E4B QAT q4_0, `-ngl 0 -c 8192` | 654, 0 | 0, 726 | 599, 0 | **664, 0** |

Every cell of that table is one draw, and the E4B's bold one is the cell that does not repeat: at
five draws it splits 4 to 1 rather than landing every time, which the mechanism section below
re-measures and explains. Every other cell here is 5 of 5 the way it reads, so only the first of the
four readings needs the qualifier, and it is the one that is strengthened rather than weakened by it.

Four readings decide everything below.

1. **The switch is conditional on the request's shape, and the entry was right.** On the E4B pick
   the same key, on the same server, in the same minute, suppresses the whole trace on a plain
   request and suppresses nothing at all under a `response_format`, where the model deliberates
   through it and spends the entire cap doing so. That last cell is the defect the envelope
   addendum measured, reproduced in isolation: 664 characters of trace, zero of reply, capped. Read
   at five draws it is 4 of 5 rather than every time, which says the same thing more sharply: a
   switch that a request shape reduces to a coin toss is not a switch.
2. **It is not the plumbing.** The obvious explanation, that a `response_format` costs a request
   its `chat_template_kwargs` before any template sees them, is refuted by the cortex row: same
   build, same adapter, same code path, and its constrained arm is silent. The key arrives. What
   differs is what the pick does with a grammar in front of it.
3. **The E4B template does read the kwarg**, which is the claim [ADR-0010](ADR-0010-subagents.md)
   carried and the thinking-lever addendum leaned on. Its plain arm is 654 characters of trace
   without the switch and none with it, on the identical prompt.
4. **Both picks agree on the plain shape and disagree on the constrained one**, so neither
   "the template reads it" nor "the shape decides it" is the whole rule. The honest statement is
   the small one: whether a switch holds is decided behind the endpoint, per pick and per shape,
   and no caller can see which. **Read a day later** in the mechanism section below, which names
   what decides it: the two picks ship different chat templates, and only one of them closes the
   thought in the prompt when it is told not to think. The lineup section after that one asks every
   remaining entry and finds the same thing deciding each of them, so a caller cannot see which and
   an **operator** can, off one `POST /apply-template`.

### Why the addendum above could not have seen this

Its four-request probe read, at a cap of 40 on the harness's own summarization prompt:

| request | reply | reasoning |
| --- | --- | --- |
| no `response_format`, no kwargs | 171 chars from 3.0 s | none |
| `response_format`, no kwargs | none | a trace |
| `response_format` + `chat_template_kwargs` | none | a trace |

The first row is the whole of it. That arm carried **no switch** and produced **no trace**, so the
model was not deliberating on that prompt in that shape, and the row below it could say nothing
about a key whose only job is to stop a deliberation that would otherwise happen. From those rows
the addendum concluded that the key "had never been reading on this model", which is the one
inference they cannot support. It is the same trap the same section had just named one paragraph
earlier about the `17 + 25` reading, and it was walked into with the trap written down.

What makes the difference here is a prompt with a few steps in it and a **control that has to
fire**: the arms that send no switch must deliberate, per shape, or the run is thrown away rather
than read. That is an assertion in the probe and not a line of output, for exactly this reason.

None of this changes what shipped. `--reasoning-budget 0` remains the only lever that reaches the
constrained shape on the E4B pick, every subagent server still carries it, and the per-request key
that was built and reverted would still have bought nothing. Only the sentence explaining why.

### The mechanism, read off the engine (2026-08-28)

Reading 4 above is where this stopped: whether a switch holds is decided behind the endpoint, and
no caller can see which. This is that decision, read rather than inferred. Measured by the agent on
`ghcr.io/ggml-org/llama.cpp@sha256:9f84380be42d6285a827629c809387349c3541aa8986f7536547ca33cc8dd47a`
(the CPU `server` image the subagent tier runs) and
`@sha256:9f0a986a78ab9261afc3266c807c16933ee4c26c62cb063f0c17f8da890f6c7e` (the `server-cuda` image
the model host is built on), both reporting `b10644-d7a207411`, each pick's server started with
neither reasoning flag and with `--verbose` so it prints the format and the grammar it chose.

**The reading is at five draws a cell, and the repeats change it.** Through the same committed
probe at `CORTEX_THINKING_REPEATS=5`, one prompt four ways, trace characters then reply characters
per draw:

| tier | plain, no switch | plain, switch | envelope, no switch | envelope, switch |
| --- | --- | --- | --- | --- |
| cortex, gemma-4-12B QAT q4_0, `-ngl 99 -c 16384` | 5/5 deliberated | 0/5 | 5/5 | **0/5** |
| subagent, gemma-4-E4B QAT q4_0, `-ngl 0 -c 8192` | 5/5 deliberated | 0/5 | 5/5 | **4/5** |

The phenomenon reproduces, and the one draw it was recorded from was reading a **tendency as a
rule**: on the E4B's constrained arm the switch holds on 1 draw in 5 rather than on none. That is
the shape of the cause below, where the trace is one of two branches the model may take.

Three readings say why, in the order the entry asked for them.

1. **The chat format does not change.** `peg-gemma4` on all 54 requests of this session across both
   picks, with a `json_schema` and without. A schema does not send the request down another handler.
2. **The prompt does not change either**, asked of each server itself through `POST /apply-template`
   rather than reasoned about: for one pick and one value of the switch, the plain shape and the
   constrained shape render **byte-identical** prompts. Only the switch moves a prompt. That is the
   direct form of what the cortex row could only infer, and the probe now asserts it, because a tier
   where it fails is a tier whose four cells are comparing two prompts.
3. **What the schema changes is that a grammar is built at all.** `common_chat_params_init_gemma4`
   builds one only for a request carrying a schema or tools, so a plain request here is decoded
   unconstrained: 12 plain requests, no grammar, against 22 constrained ones each carrying this root,
   byte-identical across both picks and both values of the switch:

   ````
   root ::= start (thought | )? "```json" space response-format-schema space "```"
   thought ::= "<|channel>thought" space until-5 "<channel|>"
   start ::= "<|turn>model\n"?
   ````

So the reasoning section is not forced open. It is **held** open, as one of the two continuations
the grammar allows at the first token, and it is the only one that admits prose: under that root a
model that would rather explain itself than emit a fence has exactly one legal place to do it. The
handler builds that alternative without ever reading `enable_thinking`, which is a template variable
and reaches the template alone. Sibling handlers in the same file do read it, gating their reasoning
rule on `extract_reasoning && inputs.enable_thinking`, so this is an omission in one handler rather
than a property of constrained decoding.

**And the difference between the picks is the template, not the model.** The two GGUFs ship
different chat templates, and with the switch sent they render different prompts, read here off the
slots the servers really launched:

```
cortex, 12B     …What does each of them pay?<turn|>\n<|turn>model\n<|channel>thought\n<channel|>
subagent, E4B   …What does each of them pay?<turn|>\n<|turn>model\n
```

The cortex's template answers "do not think" by **opening and closing an empty thought** before the
model writes a token. The E4B's answers by dropping the `<|think|>` marker and adding nothing. On a
plain request that is the same answer, because no grammar is in play and the missing marker is
enough for both picks, 5 draws of 5. On a constrained request the grammar makes a thought block
reachable again, and only the cortex's prompt has already spent it: its optional `thought` is
closed, and the fenced payload is all that is left. The E4B's prompt still leaves a thought block
open, and the model writes one on 4 draws of 5.

**So it is an engine behaviour, and the model is doing nothing surprising.** Naming that changes no
code here, for the reason the entry was left: the dependable lever is the tier's
`--reasoning-budget`, which is a **sampler** rather than a prompt or a grammar. It watches for the
thought's start sequence and forces its end tag, so it reaches every request shape by construction,
and it is what every subagent server carries.

**There is now a per-request one, which is this reading's own residue.** On this build the server
reads `reasoning_budget_tokens` (or `thinking_budget_tokens`) off the request body, falling back to
the tier's flag only when the request says `-1`. Sent as `0` on the exact cell that fails, the E4B's
constrained request with the switch, it holds on **5 draws of 5**, each returning the envelope. The
spelling this ADR's trace-budget addendum measured and recorded as ignored, `reasoning_budget`, is
still ignored on the same build in the same minute: 4 draws of 5 deliberated, which is the arm's own
baseline, and the server logged `reasoning budget: tokens=-1` for every one of them. That addendum's
sentence is therefore right about the name it tried and no longer right about the engine, and the
trigger recorded on
[docs/refinements/tasks/295-per-request-trace-budget.md](../refinements/tasks/295-per-request-trace-budget.md)
has fired. Rendering the port's switch as that key rather than only as the template kwarg is
[R-474](../refinements/tasks/474-the-switch-could-be-rendered-as-a-lever-that-holds.md), and it is
not taken here: this entry was scoped to naming the cause.

### The lineup, asked (2026-08-28): the template decides, and the family does not

Everything above is two picks of one family, which is a mechanism and not a rule, and
[R-465](../refinements/tasks/465-the-switch-across-the-lineup.md) is the entry that held that gap
open. Every remaining chat entry of the lineup ([ADR-0004](ADR-0004-model-lineup.md)) has now been
asked the same question through the same committed probe: five draws a cell, a cap of 256, each
server started with **neither** reasoning flag, all on `b10644-d7a207411` (the `-ngl 0` rows on
`ghcr.io/ggml-org/llama.cpp@sha256:9f84380be42d6285a827629c809387349c3541aa8986f7536547ca33cc8dd47a`,
the `-ngl 99` rows on
`@sha256:9f0a986a78ab9261afc3266c807c16933ee4c26c62cb063f0c17f8da890f6c7e`). A cell counts the draws
that deliberated **with the switch sent**, so `0/5` is a switch that held every time; the arms that
send no switch deliberated on 5 of 5 everywhere, which is the probe's asserted control and is what
makes the rest of the table mean anything.

| entry | placement | chat format | its template's answer to "do not think" | plain | envelope |
| --- | --- | --- | --- | --- | --- |
| gemma-4-12B QAT q4_0 (cortex pick) | `-ngl 99 -c 16384` | `peg-gemma4` | closes an empty thought | 0/5 | 0/5 |
| gemma-4-31B QAT q4_0 (deep pick) | `-ngl 99 -c 8192` | `peg-gemma4` | closes an empty thought | 0/5 | 0/5 |
| gemma-4-26B-A4B QAT q4_0 | `-ngl 99 -c 8192` | `peg-gemma4` | closes an empty thought | 0/5 | 0/5 |
| gemma-4-E4B QAT q4_0 (subagent pick) | `-ngl 0 -c 8192` | `peg-gemma4` | drops the block, adds nothing | 0/5 | **4/5** |
| gemma-4-E2B QAT q4_0 | `-ngl 0 -c 8192` | `peg-gemma4` | drops the block, adds nothing | 0/5 | **5/5** |
| Qwen3.5-0.8B Q8_0 | `-ngl 99 -c 8192` | `peg-native` | closes an empty think | 0/5 | 0/5 |
| Qwen3.5-2B Q4_K_M (roster alternate) | `-ngl 0 -c 8192` | `peg-native` | closes an empty think | 0/5 | 0/5 |
| Qwen3.5-4B Q4_K_M | `-ngl 0 -c 8192` | `peg-native` | closes an empty think | 0/5 | 0/5 |
| Qwen3.5-9B UD-Q4_K_XL | `-ngl 99 -c 16384` | `peg-native` | closes an empty think | 0/5 | 0/5 |
| Qwen3.6-27B Q4_K_M | `-ngl 99 -c 8192` | `peg-native` | closes an empty think | 0/5 | 0/5 |
| Qwen3.6-35B-A3B UD-Q3_K_XL | `-ngl 99 -c 8192` | `peg-native` | closes an empty think | 0/5 | 0/5 |

The cortex row and the E4B row are the readings above, carried in so there is one place to read the
lineup from. Two entries are measured at a quant this ADR does not name, the machine carrying
UD-Q4_K_XL and UD-Q3_K_XL where ADR-0004 writes Q4_K_M and UD-Q3_K_M; a quant is not a chat
template, so the rows stand for their entries and the substitution is recorded rather than hidden.
**The placement column varies and is not a variable**: it decides where the weights sit and nothing
about the prompt or the grammar, and both of its values appear on both sides of the split, the
Qwen3.5-2B holding on `-ngl 0` where the E2B fails on the same flag. One entry was run both ways
as the control for that, the Qwen3.5-4B, and its four cells read the same on the card as on the
CPU.

**No entry in the lineup ignores the switch on a plain request.** That is the reading with something
at stake and the one this entry called worth acting on, and it says nothing is owed:
`TITLE_BOUNDS`, `RECAP_BOUNDS` and the reply bounds a deployment builds from
`CORTEX_REPLY_MAX_TOKENS` each pair a cap sized on the wanted answer with the switch and carry no
schema, so on every entry above that pairing shortens a reply rather than deleting it. The one
shipped bound that carries a schema too, `rank_bounds` with `ORDER_ENVELOPE`, is built against the
**cortex** model by `JudgeRecallPolicy` and never against a subagent tier, and the cortex pick is on
the holding side of the column that splits. Nothing shipped stands on a failing cell, and this
section changes no code.

**What decides the constrained column is the template, and the two obvious candidates are both
refuted by this table.** Not the family: gemma-4 splits down the middle of its own entries, the 12B,
the 31B and the 26B-A4B holding where the E2B and the E4B do not, which is the same family across
its whole range on both sides of the split. Not the handler either, which is the first guess the
mechanism section invites: `peg-gemma4` serves both sides of that split, and the other handler in
this lineup builds the same shape of root, `<think>` and `</think>` where the gemma one writes its
channel markers, so neither handler closes the thought block a schema reopens. What separates the rows is the
column before the verdicts, read off each server's own `POST /apply-template` before a token is
decoded: an entry whose template answers the kwarg by rendering a thought **already closed** holds
under a schema, and one that answers by dropping the block and adding nothing does not. That was the
mechanism section's account of two picks. It predicts the constrained verdict on every entry here.

**Three smaller readings from the same runs.** The schema reaches no template anywhere in the
lineup: on every entry the two request shapes carrying one switch render byte-identical prompts,
which is the assertion the probe makes ahead of its cells and which held for all of them. The split
is not about size or tier either, landing inside one family across its whole range and putting the
smallest entry measured on the same side as the largest. And the Qwen claim this repo carried on the
strength of a `17 + 25` that invited no deliberation is now measured on a prompt that does: every
Qwen entry honours the kwarg, on both shapes, so the compose comment was right and had been standing
on nothing. [ADR-0010](ADR-0010-subagents.md) and the subagent runbook say so where they said the
weaker thing.

**The column predicts a cost and not only a rendering (2026-08-28).** Three subagent-tier entries
have since been run through the constrained reply path at 288 runs each, and the constrained column
above orders them by how often each writes its answer into the reasoning channel a delegated run
drops: Qwen3.5-2B, which closes an empty think, does it on 0 draws of 288 across both envelope arms
and all three subtask shapes; gemma-4-E4B on 8 of 96 constrained draws and gemma-4-E2B on 14, which
is the order this table's `4/5` and `5/5` put them in. So a cell here is a lost answer somewhere
else, and the full reading is the ADR-0028 lineup addendum.

**All five entries of the subagent row have since been asked, and the column is five for five
(2026-08-28).** Qwen3.5-0.8B and Qwen3.5-4B, the two remaining, write into that channel on 0 draws
of 288 each, on every arm and every subtask shape, which puts the Qwen entries of this row at **0 of
864** against 22 of 192 for the two gemma-4-E entries. The prediction was written down before either
server was started and it could have failed on either pick. What the column still says nothing about
is the answer rate: these two sit in the same cell of it and are 28 draws apart on the shipped
constrained path, 66 and 94 of 96. The full reading is the ADR-0028 row addendum.

**Where the residue went.** The prediction is a set of readings of one engine build rather than a
theorem, and nothing in the stack reads the rendering it turns on, though a loaded server answers in
one call.
[R-475](../refinements/tasks/475-a-tier-can-be-asked-what-its-template-answers.md).

### Decision

1. **`GenerationBounds.thinking` stays a field and stops being a promise.** Its docstring says what
   it is: a request to the deployment's chat template, honoured or not per pick and per request
   shape, and never a guarantee about the model. The pairing rule it exists for is restated in the
   terms the trace-budget addendum already used and this value had never caught up with: what makes
   a cap sized on the wanted answer safe is a **bounded trace**, of which the switch is the cheapest
   source and not a dependable one.
2. **The port owes the caller the evidence.** `InferenceBackend` now says that a bound asking for no
   thinking is passed on and never enforced, so a trace that arrived anyway still crosses as
   `ReasoningChunk` rather than being filtered into the silence the caller asked for. That stream is
   the only thing that can tell a caller the switch did not hold, and an implementation that
   swallowed it to make the port look truthful would leave the failure with nothing to read at all:
   an empty reply, a cap, and no account of where the tokens went. It is a shared contract check
   over both implementations rather than a note.
3. **`drain_text` says so out loud.** It is the one place that sees the request that asked and the
   trace that came back, and it is the place the trace is destroyed, so a completion that
   deliberated against the switch is dropped with a warning naming the model and the characters
   nobody read. Every caller of it holds a cap sized on an answer, so this is exactly the population
   at risk. The text is returned unchanged: the fix is a tier flag an operator sets, not something a
   side call can react to.
4. **The turn's own path deliberately gains nothing.** A user's reply renders its trace as the
   thinking status the overlay shows (ADR-0020), so a deployment whose `CORTEX_REPLY_THINKING=false`
   went unhonoured is already looking at the evidence. Silence is only a defect where the trace is
   discarded unread, which is the three side calls and not the turn.
5. **No adapter-side repair, and no capability probe.** Filtering the trace to honour the switch is
   forbidden by decision 2. Asking the server what its template does is not available either:
   `GET /props` reports the template, not what a pick does with a grammar in front of it, which is
   the thing that varied here. The answer is a measurement, so the answer ships as a probe.
   **Half of that is now askable**, and the mechanism section takes it: `POST /apply-template`
   renders the prompt a request would really get, which settles whether the key reached the
   template. What it still cannot say is what the model does next, so the sentence stands where it
   matters and the probe reads the half that is free.
6. **The probe is committed rather than run and written down.** `test_thinking_switch_live.py` is
   integration-marked and out of CI, takes an endpoint, and answers per request shape with its
   control asserted. A deployment that changes a pick can rerun it in one command, which is the
   difference between this reading and the two before it. It draws each cell
   `CORTEX_THINKING_REPEATS` times, defaulting to one so the runbook's single command still answers
   quickly, and anything reported here as a tier's behaviour is run at five or more: the first
   reading of this addendum's own subagent row was a single draw of a cell that splits 4 to 1.

### The line, on a real tier

Decision 3 was run rather than only unit tested, through the shipped `drain_text` against the same
unbudgeted E4B server, twice:

```
WARNING cortex_core.drain: the model deliberated on a request that asked for no thinking, and
the trace was dropped unread model=subagent chars=681
reply: ''
```

That is the failure this whole addendum is about, said at the moment it happens: a schema, a cap of
256, `thinking=False`, an empty reply, and 681 characters of trace nobody will ever see. The second
run is the one that matters as much: the **shipped rank prompt** through the same `drain_text` with
`ORDER_ENVELOPE` and `rank_bounds(3)` against the same server logged **nothing** and returned
`{"order": [2, 0, 1]}`, correctly ordered. A rank asks for a placing rather than a derivation, so
this pick does not deliberate over one even where it may, and the line stays what a line here should
be: rare, and about one thing.

### What this does not do, and where that is recorded

- **Why the E4B deliberates under a grammar was not known** when this addendum landed, only that it
  does and that the key reaches its template. The mechanism section above closes that a day later
  and [R-464](../refinements/tasks/464-why-a-grammar-restores-the-trace.md) with it. What the answer
  opened is the lever it named: the engine now reads a thinking budget off the request body, and the
  port's switch could be rendered as one rather than as a template kwarg the grammar overrules.
  [R-474](../refinements/tasks/474-the-switch-could-be-rendered-as-a-lever-that-holds.md).
- **Two picks were not a rule**, and the lineup section below is the whole lineup asked. Its answer
  is that the mechanism generalises and neither of this addendum's two picks was special: what a
  pick's own template renders when it is told not to think predicts its constrained verdict on every
  entry measured. What that leaves is a prediction nothing in the stack reads, though it is one HTTP
  call against a server that is already up.
  [R-475](../refinements/tasks/475-a-tier-can-be-asked-what-its-template-answers.md).
- **Nothing gates the pairing.** A future bound that pairs a cap with the switch on a tier where it
  does not hold is still written the same way and still fails at runtime; what changed is that the
  runtime now says so. A check that a schema-carrying bound is only used against a tier with a
  bounded trace would need the core to know a tier's argv, which it deliberately does not.
  [R-466](../refinements/tasks/466-nothing-holds-a-cap-to-a-bounded-trace.md).

### Distrust green

Six mutations, each applied to production code alone with the named suite re-run, then reverted.
The first two are over the 91 checks of the inference package suite
(`brain/packages/inference/tests/`), the last four over the 1628 of the core suite
(`brain/packages/core/tests/`).

| mutation | tests that fail |
| --- | --- |
| the adapter filters the trace the switch asked against | **1** |
| the adapter drops every reasoning delta | **3** |
| the drain never reports an unread trace | **1** |
| the drain reports every trace, asked against or not | **1** |
| the drain counts deltas rather than characters | **1** |
| a stream that died mid trace is reported as an ignored switch | **1** |

The first two rows are the pair worth reading together. The targeted filter, which is the repair a
well meaning adapter would reach for and the one decision 2 forbids, fails **exactly one check**,
`check_a_deliberation_the_request_asked_against_still_crosses` on the adapter's leg and nothing
else: no existing check passes any bounds at all, so before this the whole tree was green on an
adapter that quietly deleted the only evidence a caller has. Dropping reasoning outright fails
three, the two contract checks and the adapter's own reasoning case, which is what says the new
check is aimed at something the old ones do not cover rather than restating them.

The last row is the one the first draft got wrong. Moving the report inside the stream's `finally`
looks harmless and turns a dead server into a template that ignores the switch, blaming a
deployment for a transport failure; the check that a completion which failed part way describes
nothing is what separates them.

## Answer addendum (2026-08-28): what the envelope costs the answer, which is not its length

**Status:** Accepted. Closes
[docs/refinements/tasks/459-what-the-envelope-costs-the-answer.md](../refinements/tasks/459-what-the-envelope-costs-the-answer.md),
which the thinking-lever addendum's own first readings opened, and **corrects one sentence of the
envelope addendum above**: that addendum read the constrained arm's shorter replies as the envelope
returning less text, which is right as arithmetic and wrong as an account of what those replies are.
Opens [R-476](../refinements/tasks/476-the-envelopes-answer-rate-is-an-instruction.md) and
[R-479](../refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md).

Everything this ADR had measured about the reply envelope was a length: decoded tokens, wall clock,
characters returned. Nobody had read whether the answer was as good, and the first readings taken
once the trace was off were three replies that all narrated the task instead of performing it. Three
draws from a 4B model price nothing, so this is the reading that does.

### Re-derived first

`REPLY_ENVELOPE` is still a bare `{"reply": <string>}` with `additionalProperties: false`,
`PlacedAttempt` still sends it exactly where the run holds no dispatcher, and `settle_reply` still
reads `capped` before the unwrap. The cap is still 1024 and the deadline still 2400 s. Every
subagent server this repo starts still carries `--chat-template-kwargs '{"enable_thinking": false}'`
beside `--reasoning-budget 0`. Nothing had moved.

### How an answer was judged, and what that reading cannot do

Two readings over the same replies, one mechanical and one by a reader, and the mechanical one
carries the table because the instruction has a checkable meaning. It says "keeping every detail",
so **number recall** is the fraction of a body's distinct numeric literals that appear in the reply.
The reader's half then sorts every reply into `answer` (a summary from its first sentence),
`mixed` (a plan or preamble and then the summary) or `narration` (only text about the task).

The two agree, and the proxy turns out to separate the populations rather than rank them: across
**160 replies not one lands between 0.09 and 0.82**. A reply either carries essentially every number
in the report or it carries almost none, and reading the low ones confirms what they are, openings
like "The user wants a comprehensive summary of the provided site report" and
"Here's a plan to ensure all details are captured". Read at a seeded random twelve of the ninety one
low replies rather than at the ones that caught the eye, all twelve are narration and one of them is
the instruction handed back verbatim.

What this cannot do is worth saying plainly. It is one instruction over four operational report
bodies of one genre, judged by one reader with one proxy, and it measures whether an answer arrived
rather than how well it is written. A subtask that invites no deliberation is not represented here
at all, and on the evidence below that is exactly the axis the effect runs along.

### What it ran on

gemma-4-E4B QAT q4_0, the shipped subagent pick, on llama.cpp `b10644-d7a207411` from
`ghcr.io/ggml-org/llama.cpp@sha256:9f0a986a78ab9261afc3266c807c16933ee4c26c62cb063f0c17f8da890f6c7e`,
carrying the subagent server's own flags (`--jinja`, the reasoning-off pair, `--ctx-size 8192`,
`--parallel 2`, the server's own log reporting `n_ctx_slot = 4096`) and driven through the real
`SubagentRunner` chain at the shipped cap by
`brain/packages/orchestrator/tests/test_envelope_cost_live.py`. Four report bodies, ten draws each,
four request shapes: **160 runs**.

**It ran `-ngl 99` rather than `-ngl 0`, and that is a deliberate substitution.** What is being read
is what the model writes, not how fast it writes it, and the CPU placement decodes at 1.26 to 1.35
tok/s on an idle box and a fifth of that on a busy one, which puts the 200 runs behind this
addendum at about ten hours of decoding at the fast end alone. The GPU placement is not a made-up
shape either: it is the tier's other shipped one, the model host's opt-in subagent tier behind
`CORTEX_MODEL_FILE_SUBAGENT_GPU` (ADR-0030), and every flag but `-ngl` is the compose file's. The
assumption this rests on is that offload changes throughput and not what the model decides, and a
CPU control over the same bodies is recorded below rather than left as an assertion. **No wall clock
from this run is comparable with the batch addendum's**, and none is quoted.

### What 160 runs say

Each arm is the same four bodies at ten draws. `delivered` counts the replies that carried the
summary at all, meaning `answer` plus `mixed`, with a Wilson 95% interval beside it because a rate
over 40 draws is a rate and not a constant.

| arm | what the request carried | delivered | decoded tokens, median / max | reply chars, median | capped |
| --- | --- | --- | --- | --- | --- |
| raw | no schema | **40/40** (0.91 to 1.00) | 408 / 451 | 1556 | 0 |
| constrained | the shipped envelope | **10/40** (0.14 to 0.40) | 48 / 429 | 159 | 0 |
| described | the envelope, `reply` given a description | **9/40** (0.12 to 0.38) | 57 / 1024 | 202 | 1 |
| prefaced | a required `notes` field ahead of `reply` | **10/40** (0.14 to 0.40) | 96 / 472 | 156 | 0 |

One thing that does not vary is worth stating before the five that do: across all 200 runs behind
this addendum, at four request shapes, **not one came back `MALFORMED`**. The grammar held on every
draw, and everything below is about what the model chose to put inside it.

Five things follow, and the first is the finding.

1. **The envelope does not shorten the answer. It deletes the answer three times in four.** The
   unconstrained shape answered on every one of forty draws; the shape a subagents-only stack ships
   answered on ten. The intervals do not come near each other. This is the same effect the envelope
   addendum saw as "it spends more tokens and returns less text", read at the level the text is
   written rather than counted.
2. **When it does answer, it answers as well as raw.** Over the ten constrained replies that are
   summaries, number recall runs 0.82 to 1.00 with a median of 1.00, against raw's 1.00 throughout,
   at a median 1234 characters against raw's 1556. So the envelope costs an answer's **arrival** and
   not its quality, which is a different defect from the one the entry expected and needs a
   different repair.
3. **A description on the property changes nothing, and could not have.** This is the arm the entry
   asked for, on the reasoning that an empty schema tells the model nothing about what the field is
   for. It tells the model nothing either way: asked through `POST /apply-template`, this pick
   renders a **byte-identical prompt** with no schema, with the bare envelope, with the described
   envelope and with the two-field one, while the same endpoint on the same server does render a
   `chat_template_kwargs` change and does render a `tools` array. So a `description` here is read by
   the grammar builder and by nothing else, and the model meets a schema only as a constraint on its
   next token. **That generalises past this envelope and past this pick**: asked the same way on a
   `gemma-4-12B` server started in the same session, the cortex tier renders the same prompt with
   `REPLY_ENVELOPE`, with `ORDER_ENVELOPE` and with neither, its own two controls firing (a `tools`
   array shows, and `enable_thinking: false` renders the pre-closed thought the mechanism section
   above describes). So every schema this repo sends is invisible to the model as text, on both
   picks that receive one.
4. **Giving the narration a field of its own does not free the reply.** The `prefaced` arm makes a
   `notes` string required ahead of `reply`, so the grammar offers the preamble somewhere else to
   go. The model takes it and narrates twice: `"notes": "The user wants a summary of the provided
   site report..."` then `"reply": "I need to meticulously extract and organize all data points..."`.
   Ten of forty, the same rate as the arm with no such field. The text in `reply` is therefore not
   overflow with nowhere to go; the model is treating a plan as the whole of its output.
5. **The instruction is where the repair lives, and it is large.** The one place this engine lets
   anything be said to the model about the envelope is the subtask itself. Appending "Your entire
   response must be the summary itself. Do not describe the task, plan an approach, or announce what
   you are about to write." to the same instruction, on the same four bodies at ten draws through
   the shipped envelope, delivers **39 of 40** (0.87 to 1.00). Thirty eight of those forty runs
   decode between 248 and 323 tokens.

### The residue on the fifth reading, which is not free

Three of those forty draws, all on one body, wrote 2282 to 3692 characters into the **reasoning**
channel, which a delegated run drops unread, **on a server carrying both reasoning-off flags**. They
are the only three draws above 323 decoded tokens: one finished at 912 and two reached the 1024 cap
and came back refused. Read rather than counted they are not all one thing. Two are a deliberation,
opening "Here's a thinking process to arrive at the desired summary". The third is stranger and
worse: its reasoning channel holds a **complete summary** and its reply holds a second, different
summary that the cap then cut, so the model wrote the answer twice and the reader got neither.

Two things follow and both are bounded by how few draws they are. The instruction that keeps the
plan out of `reply` does not remove the plan, it relocates it, which is the next question rather
than a reason not to ask it and is carried by
[R-476](../refinements/tasks/476-the-envelopes-answer-rate-is-an-instruction.md). And
`--reasoning-budget 0` did not hold on those three, which the thinking-lever addendum above states
without qualification and which the other 160 runs here support without exception. Three draws on
one body under a probe instruction is not enough to amend a shipped claim, so it is filed rather
than acted on:
[R-479](../refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md).

### The CPU control

The assumption above is that `-ngl` changes throughput and not what the model decides, and this is
the arm that checks it rather than asserting it. A second server, the CPU `server` image
`ghcr.io/ggml-org/llama.cpp@sha256:9f84380be42d6285a827629c809387349c3541aa8986f7536547ca33cc8dd47a`
on the same build, `-ngl 0` and every other flag identical, under the compose file's own
`--cpus 4.0` and 8 GB: **16 runs**, the two envelope arms over warehouse at five draws and clinic at
three, stopped at that paired boundary because it decoded at 0.33 to 1.06 tok/s while the rest of
this session was running beside it.

It reproduces the phenomenon and the shape of the reading. The `constrained` arm delivered on 2 of
8 and `described` on 1 of 8, against the same two arms over the same eight cells on the GPU at 0 of
8 and 2 of 8, and over both of those bodies at all ten draws at 4 of 20 and 6 of 20. Every one of
the sixteen is again either a summary or a plan, with no reply between the two: the number-recall
gap that separates the 160 separates these as well. Sixteen runs cannot show a small difference
between the placements and are not offered as doing so. What they refuse is a large one, which is
what the substitution needed.

**The other family has now been controlled too (2026-08-28).** Everything above is gemma-4-E4B, so
the substitution had been checked on one family and spent on two. Qwen3.5-0.8B Q8_0 was re-run on
the same CPU image and build, `-ngl 0` and every other flag identical, on the summarization shape
over the same four bodies at two draws: **24 runs**, three arms of 8. It delivered **8 of 8 raw, 7
of 8 bare and 8 of 8 constrained**, against the same three arms on the card at 32 of 32, 26 of 32
and 28 of 32, and it wrote nothing into the reasoning channel on either placement. Twenty four runs
again refuse a large difference and cannot see a small one. What they price is the substitution's
whole point: this entry decodes at 10.4 to 17.3 tok/s on the CPU against 91 to 350 on the card, so
the 576 runs behind the ADR-0028 row addendum would have been most of a day on the placement the
compose file ships.

### Which of the entry's three outcomes, and what moves

The entry named three honest outcomes. This is the third, **it costs enough that the tool-less shape
wants a different grammar**, with one correction to that wording: what it wants is not a different
grammar. Readings 3 and 4 are two grammar changes that buy nothing, and reading 5 is a prompt change
that buys almost everything, because on this engine a schema constrains and never informs.

**Nothing in the shipped tree moves here.** The entry's own caution is that changing the grammar
every delegated reply is decoded into on a thin reading is the mistake this backlog exists to
refuse, and the reading that would justify a change points at the runner's instruction rather than
at `REPLY_ENVELOPE`. That is a decision about what the subagent contract says, so it is written down
and left to
[R-476](../refinements/tasks/476-the-envelopes-answer-rate-is-an-instruction.md) rather than typed
tonight. The laundering argument this envelope was built for is re-read against these numbers in the
ADR-0028 answer-rate addendum.

### Distrust green

The failure mode of a measurement with four arms is that two of them are the same request. Two
things say they were not. The `prefaced` arm's stream carries `{"notes": ..., "reply": ...}`, a
two-field object that only the substituted grammar admits, so the substitution reaches the wire. And
the `/apply-template` reading in point 3 has both of its controls firing on both picks: the same
endpoint, in the same minute, on the same server, does show a `chat_template_kwargs` change and a
`tools` array in the rendered prompt, so a schema that leaves it unchanged is a schema that is
genuinely not there. A null result whose instrument was never shown to move is not a reading, which
is the trap the switch-is-advisory addendum above was written to name.

## Ceilings addendum (2026-08-28): the cap re-derived on the shape that ships, and which bound binds

**Status:** Accepted. Closes
[docs/refinements/tasks/457-the-caps-derivation-on-the-shape-that-ships.md](../refinements/tasks/457-the-caps-derivation-on-the-shape-that-ships.md),
which the envelope addendum above opened and which has been waiting since for a constrained reply
that is actually an answer. The answer addendum above produced forty nine of them. Opens
[R-477](../refinements/tasks/477-the-caps-margin-over-an-answering-run.md) and
[R-478](../refinements/tasks/478-two-ceilings-on-one-run-and-no-ordering.md). It also **corrects one
sentence of the total-cap addendum**, which named the per-slot context as the cap's other ceiling
and never weighed the deadline against it.

### Re-derived first

`DEFAULT_SUBAGENT_MAX_TOKENS` is still 1024 and `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` still 2400.0.
`docker/docker-compose.subagents.yml` still ships `--ctx-size 8192` across `--parallel 2`, and the
server started from it says so itself in its first lines, `n_ctx_slot = 4096`. The four report
bodies this measurement runs over send prompts of **261 to 282 tokens**, read off the server's own
`prompt eval time` lines, which is the same neighbourhood as the 276 the batch addendum recorded.
Nothing had moved.

### The derivation, restated against the shape that ships

The total-cap addendum sized the cap as roughly five times the longest of five narrow replies, a
summarization answering in 199 tokens. Every one of those five was measured on the **unconstrained**
shape, and a subagents-only stack runs the constrained one, which is the whole of what this entry
was about. That shape now has readings of its own, forty draws over four bodies at the shipped cap:

| shape and instruction | replies that are answers | decoded tokens of those answers |
| --- | --- | --- |
| unconstrained, the harness's instruction | 40 of 40 | 372 to 451, median 408 |
| the shipped envelope, the same instruction | 10 of 40 | 256 to **429**, median 309 |
| the shipped envelope, an instruction that names what the reply holds | 39 of 40 | 248 to **912**, with 38 of that arm's 40 runs inside 248 to 323 |

**The rule that produced 1024 does not produce a number here.** Five times 429 is 2145 and five
times 912 is 4560; the second is above the slot's own 4096 before the prompt is subtracted, and both
are above what the deadline admits on a busy host, measured below. A rule whose output has to be
clipped by the bound it was supposed to sit under has stopped being a derivation.

### So the cap is confirmed where it stands, on a better argument than the rule

**1024 is above every answer this tier has been measured writing on the shape that ships** (longest
429) and comfortably above the band that 38 of 40 answering runs occupy under the instruction that
recovers the answer (248 to 323). And the sentence the number carries, that reaching the cap is
itself the evidence of a model talking rather than working, is now **measured true on this shape**
rather than inherited from another one. Three runs out of two hundred reached 1024 across every arm
run for the answer addendum, and not one of them was a long answer: one spent the budget writing a
thinking process into `reply`, and two spent 3351 and 3692 characters of it in the reasoning channel
a delegated run drops unread. Reaching this cap still means what the comment beside it says.

What is no longer comfortable is the margin at the other end, and it is recorded rather than acted
on: 912 is a finished, correct answer at 89% of the cap, and two of that arm's forty draws were cut
at it. That is [R-477](../refinements/tasks/477-the-caps-margin-over-an-answering-run.md), and it is
deliberately a trigger rather than a retune, since the instruction those numbers were measured under
is itself the open question at
[R-476](../refinements/tasks/476-the-envelopes-answer-rate-is-an-instruction.md).

### Which of the two ceilings binds, which is the question nobody had asked

The entry's second question is which bound a cap materially above 1024 would run into first, and it
needs no good reply to settle, only the three bounds put in one unit. Decoded tokens is that unit.
The rates are this tier's own, from the control in the batch addendum above: **0.18 to 1.35 tok/s**
decode and 6.7 to 20.6 tok/s prompt eval, the low end of each being what a saturated host costs a
container whose `--cpus` is a quota rather than a reservation.

| bound | decoded tokens it admits | how it gets there |
| --- | --- | --- |
| this deployment's cap | **1024** | `DEFAULT_SUBAGENT_MAX_TOKENS`, flat |
| the run deadline | **425** saturated to **3222** quiet | 2400 s less this prompt's eval, times the decode rate |
| the slot's context | about **3820** | 4096 less a 261 to 282 token prompt |

Three readings follow, and the third is the one the entry asked for.

1. **On a quiet host the order is cap, then deadline, then context.** The cap fires first, exactly
   as the total-cap addendum intended, and the two bounds above it are 3007 to 3222 and about 3820.
2. **On a saturated host the order inverts and the cap becomes unreachable.** At 0.18 tok/s the
   deadline admits about 425 decoded tokens, less than half the cap, so a run long enough to be cut
   by the cap is cut by the clock first and reported as a deadline rather than as a runaway. That is
   [R-478](../refinements/tasks/478-two-ceilings-on-one-run-and-no-ordering.md), since
   `SubagentsConfig` already refuses three orderings at boot and cannot check this one, the relation
   depending on a decode rate the core has no way to know.
3. **The deadline is the binding one of the two, everywhere on this tier's measured range.** It is
   below the context ceiling at both ends, and the crossover where the context would take over is a
   prompt of about 920 to 1140 tokens on a quiet host and about 3765 on a saturated one, against the
   261 to 282 a narrow subtask sends here. So **raising the cap materially above 1024 buys nothing
   on a busy host, and on an idle one it has about 3000 decoded tokens to grow into before it meets
   the deadline**, and the sentence in the
   total-cap addendum that names the context as the cap's other ceiling is true and points at the
   loosest of the three.

### What moves

Nothing in the tree, which is this entry's own preferred outcome of the two it named. The
derivation's restatement lands where the number is declared (`cortex_core/subagents.py`), where an
operator reads it (the delegation runbook) and here, so the shape the cap was measured on is no
longer a claim about a shape nothing ships.

## Instruction addendum (2026-08-28): the sentence that recovers the answer, across three shapes

**Status:** Accepted. The decision, the wording and the full table live in the ADR-0028 instruction
addendum, because what changed is what a delegated run *says* and not what this engine does. This is
the pointer, plus the two readings that belong beside the ones above because they are about the
engine rather than about the contract.

The answer addendum above measured a repair it declined to type, and it is now typed: the runner
appends `REPLY_INSTRUCTION` to every constrained subtask. Re-measured on the same pick, the same
build and the same digest, `-ngl 99` again, at three subtask shapes over four bodies at eight draws
each (**288 runs**), the shipped envelope answers **90 of 96** with that sentence against **72 of
96** without it, and the whole of the gap is the summarization shape, 29 of 32 against 9 of 32,
while an extraction and a lookup were already answering and stay within a draw of where they were.

**The reasoning residue now has a rate and a mechanism, and both matter here.** It is 8 of 96
constrained draws against 1 of 96 without the sentence and 0 of 96 raw, on two of the four bodies
and on all three shapes, so it is neither one body's quirk nor the sentence's alone. Six of the
eight are not deliberation at all: they open with a malformed channel marker, the literal `t</c>`,
`t <|channe|s_input>`, `h</c>` or `t</channe|c>`, and then write the answer itself into the
reasoning channel that a delegated run discards, running to the cap and coming back refused. That is
a **server-side parse of a control token the model should not have emitted**, which is a different
claim from a model choosing to think under a grammar, and it sharpens rather than settles
[R-479](../refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md).

**And the ceilings addendum's margin is unchanged by it.** Every one of those six ran to exactly
1024 with nothing in `reply`, so reaching this cap still means what the comment beside the number
says. No answering run in the 288 came near it.

**Both readings are one pick's, and the second of them is now three (2026-08-28).** The same 288 runs
have been taken on the roster alternate and on gemma-4-E2B, and the residue rate is 0 of 96 on the
first and 14 of 96 on the second, which is the lineup section's constrained column read as a cost.
The cap margin holds on all three, and no run either of them reported as an answer got past 721
decoded tokens. But
**reaching this cap does not mean one thing across the tier**, which is what the paragraph above
would say if it were read as a rule. On gemma-4-E2B all 11 capped runs are one of these traces, as
on the default pick. On the roster alternate all 10 are the opposite: no trace at all and a
degenerate repetition inside `reply` itself, nine of them on the extraction shape, on both envelope
arms alike. So on a pick whose template holds, a cap refusal on narrow work is a runaway and never
the reasoning channel. The full reading is the ADR-0028 lineup addendum.

## Independence addendum (2026-08-29): the two ceilings on one run stay independent, and nothing can order them

**Status:** Accepted. Closes
[docs/refinements/tasks/478-two-ceilings-on-one-run-and-no-ordering.md](../refinements/tasks/478-two-ceilings-on-one-run-and-no-ordering.md),
which the ceilings addendum above opened. Opens
[R-494](../refinements/tasks/494-one-pair-of-run-bounds-for-a-roster-of-tiers.md). It records a
decision and moves no number, and it is the first of the entry's two named resolutions: the cap and
the deadline are declared **independent on purpose**, the conversion between them stays the
operator's, and the second resolution, deriving one from the other off a configured decode rate, is
refused with an argument rather than deferred.

### Re-derived first, since an entry's account of a mechanism is not evidence

The three orderings this repo refuses at boot, read off the code:

- `SubagentsConfig._the_run_deadline_must_outlast_the_stall_ceiling`
  (`cortex_orchestrator/config_subagents.py`) refuses `run_timeout_s <= stall_timeout_s`.
- `SubagentsConfig._the_run_deadline_must_fit_inside_the_queue_for_it` refuses a hold,
  `ATTEMPTS_PER_ADMISSION` whole deadlines, at or above `admission_wait_s`, a wait of zero exempt.
- `check_tool_call_deadline` (`cortex_orchestrator/bounds.py`) refuses a deployment where
  `delegated_call_bounds(tools) * call_timeout_s` reaches `run_timeout_s`, and only when both
  capabilities are on.

All three exist and all three compare seconds with seconds. `DEFAULT_SUBAGENT_MAX_TOKENS` is still
1024 and `DEFAULT_SUBAGENT_RUN_TIMEOUT_S` still 2400.0 in `cortex_core/subagents.py`, and the
0.18 to 1.35 tok/s the entry quotes is the batch addendum's control arm, the same box, the same
container, the same image and the same subtask shape on an idle host and on a saturated one. Two
readings sit beside it that the entry did not carry, and both sharpen rather than soften what
follows: the saturated arm's 0.18 tok/s is its **overall** rate and its **sustained mid-run** rate
is 0.07, and the recovery reading says the whole factor is host contention, since the same slot on
the same task went from 0.06 to 1.39 tok/s within seconds of the load being killed.

### The pricing question, answered from the code before the decision was taken

The entry asks whether the two refusals are distinguishable enough at the cortex for the inversion
to matter at all. They are distinguishable **as text and nowhere else**, and the code is
unambiguous about it:

- Exactly one branch in the tree tells one failure kind from another, `SubagentRunner._placed`,
  which re-places only `AttemptFailure.INFERENCE` from a GPU placement. (`AttemptOutcome.ok` reads
  the kind too and asks only whether there was a failure at all.) Both truncations are
  `AttemptFailure.TRUNCATED`, so both are treated identically there: not re-placed, for the same
  reason.
- The kind does not survive the runner. `SubagentResult` carries `ok: bool` and `detail: str` and
  no failure kind at all, so nothing downstream could branch on it even if it wanted to.
- `SpawnSubagentsTool._format` renders every failed result as `FAILED: {detail}` and **drops the
  fragment**, so what reaches the cortex is one sentence and never the partial text.
- Those two sentences (`GENERATION_DEADLINE_MSG` and `GENERATION_CAP_MSG`, both in
  `cortex_core/subagent_outcome.py`) differ in their diagnosis and end in the **same instruction**:
  treat the subtask as unanswered and narrow it before delegating it again.

So the inversion cannot cause a wrong action. It can only cause a wrong **diagnosis**, read by an
operator or by the cortex as prose, and the diagnosis it produces is the deadline's rather than the
cap's. The harm is bounded at a reader being pointed at the clock knob when the token knob is what
the run really strained, which is a documentation-shaped harm, and that is what decides the shape of
the answer below. It is not the same harm as
[R-430](../refinements/tasks/430-the-bounds-are-sized-on-an-idle-box.md), which is a legitimate slow
subtask cut at the deadline and told it was talking rather than working; that one is a false
diagnosis and stays open on its own trigger.

### The two bounds are not in one unit, and not even in one scope

The ceilings addendum's table puts them in decoded tokens and reads the cap as flat. The cap is
flat per **completion**: `PlacedAttempt` turns `bounds.max_tokens` into the `GenerationBounds` every
completion of the loop carries, while `bounds.timeout_s` is armed once around the whole attempt,
tool dispatches included. The two are the same scope only where an attempt is one completion, which
is exactly the shipped tool-less shape (`stream_tool_loop` ends after one inference step when it
holds no dispatcher). With tools the loop runs up to `MAX_TOOL_STEPS` (8) rounds and each carries
the cap again, so the attempt's own decoding ceiling is 8192 tokens against a deadline that admits
425 saturated and 3222 quiet.

That is a third regime the entry does not have, and it is the one that settles this:

| shape | what the cap admits per attempt | what the deadline admits | which binds |
| --- | --- | --- | --- |
| tool-less, saturated host | 1024 | about 425 | the deadline |
| tool-less, quiet host | 1024 | about 3222 | the cap |
| tools-enabled, either host | up to 8192 | 425 to 3222 | the deadline, at both ends |

### So there is no ordering to check, and a check that claimed one would be lying

Which of the two bounds binds first depends on two things a boot check cannot read. **What else the
host is doing**, worth a factor of seven on the overall rate and nineteen on the sustained one, measured on
one machine with nothing about the deployment changed. And **whether this deployment gives its
subagents tools**, which multiplies one of the two bounds by the rounds cap and not the other.
A validator comparing two numbers has neither fact.

Deriving one from the other needs the exchange rate as configuration, and the same control says what
that number would be worth. Both directions are wrong at one end of the measured range:

- **Deadline derived from the cap.** At the quiet end, `1024 / 1.35` plus this prompt's eval is
  about 772 s, which would cut the 1736.6 s a legitimate narrow subtask was measured taking on a
  saturated box. At the saturated end it is about 5730 s, and `ATTEMPTS_PER_ADMISSION` of those is a
  hold of 11460 s against a 7200 s admission wait, so the deployment is refused at boot by the
  second of the three checks above, so a check this repo already runs would reject the deployment
  at boot.
- **Cap derived from the deadline.** That is the ceilings table read the other way: 425 tokens
  saturated, which is below the 429-token longest answer this tier was measured writing on the
  shipped shape and far below the 912-token answer it writes under the instruction that recovers
  one. A cap sized there cuts answers.

A configured rate would also be a hardware fact in a settings class that holds none, which is the
entry's own argument and which stands, but it is the weaker half: even a per-tier rate typed
correctly is wrong by up to an order of magnitude by the time the host gets busy.

### The decision

**The cap and the deadline are two independent bounds on one run, and this repo does not order
them.** They answer the same question in the two units a runaway is measurable in, neither replaces
the other, and which one binds is a property of the machine and the wiring rather than of the pair.
The conversion between them stays the operator's, the ceilings addendum's table is where it is
written down, and both declarations now carry a sentence saying so, so a reader who finds three
orderings refused at boot and no fourth learns that the fourth is absent by decision rather than by
oversight.

### What moves

Nothing executable. The sentence lands beside both declarations in `cortex_core/subagents.py`, in
the `SubagentsConfig` bullet of [docs/modules/brain-orchestrator.md](../modules/brain-orchestrator.md)
where a future agent reads what that class refuses, in the `AttemptBounds` bullet of
[docs/modules/brain-core.md](../modules/brain-core.md) (whose decode rate is corrected to the
interval the code carries while it is open), and in
[docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) beside the knobs an operator retunes.

### What this does not do

It does not measure anything. It also does not give the roster a way to say the conversion per
entry, which is what the decision leaves undone: one `AttemptBounds` reaches every entry of a roster
whose entries decode at different rates, and that is
[R-494](../refinements/tasks/494-one-pair-of-run-bounds-for-a-roster-of-tiers.md).

## Request-lever addendum (2026-08-29): the trace budget a request can carry, and the floor under it

**Status:** Accepted. Closes
[docs/refinements/tasks/474-the-switch-could-be-rendered-as-a-lever-that-holds.md](../refinements/tasks/474-the-switch-could-be-rendered-as-a-lever-that-holds.md)
and
[docs/refinements/tasks/295-per-request-trace-budget.md](../refinements/tasks/295-per-request-trace-budget.md),
which are one key on one payload read twice, a zero and a count.

It **supersedes two decisions of the trace-budget addendum above**, and both for the same reason:
their shared premise was that the engine will not read a budget off a request, and that premise has
moved. Decision 1 ("the budget is tier configuration, not a port field... inventing a field the
adapter drops would be a knob with no effect on the server") and decision 2 ("`GenerationBounds` does not grow") are
replaced by the decisions below. The rest of that addendum stands unchanged, including its reading
that the spelling it tried, `reasoning_budget`, is ignored on a request body: re-measured here on
the newest build at 5 draws of 5, it still is.

It **amends the switch-is-advisory addendum above** in one place and leaves the rest standing. Its
decision 1 is untouched: `thinking` stays a request and not a promise. Its decision 5 says "no
adapter-side repair, and no capability probe", and this addendum ships a capability probe, so the
sentence needs its scope said out loud rather than quietly widened. That decision was about asking
a server **what a pick does with a grammar in front of it**, which is a question about a model and
is still not on any endpoint. The probe below asks a different question, about the **engine**:
whether this binary parses a key. That one has an answer, it is free of the model, and it is one
call.

### Re-derived first, because an entry's account of the tree is not evidence

Read off the code before any server was started, and one thing the entry did not know had already
changed.

- `GenerationBounds(max_tokens, thinking)` was still the whole per-request vocabulary, rendering as
  `max_tokens` and `chat_template_kwargs: {"enable_thinking": false}` and nothing else.
- **Five** producers, not the four the switch-is-advisory addendum counted, because the fifth
  names no switch: `TITLE_BOUNDS` (32, off), `RECAP_BOUNDS` (512, off), `rank_bounds(k)` (24 + 8k,
  off, and the only one carrying a schema), the reply bounds a deployment builds from
  `CORTEX_REPLY_MAX_TOKENS`, and `PlacedAttempt`'s, which carries a cap alone and leans on the
  subagent tier's own `--reasoning-budget 0`.
- `drain_text` is the only consumer of the first three, and it drops every `ReasoningChunk` before
  its caller sees one, so their deliberation is discarded by construction.
- `LlamaCppBackend` is constructed at **three** sites, one for the cortex and two inside the
  profile a roster builds per entry, so a roster of `N` entries holds `1 + 2N` of them, which is
  what makes "probe the endpoint" a decision with a cost rather than a free one.
- The compose stack names llama.cpp by **mutable tags** (`ghcr.io/ggml-org/llama.cpp:server`, and
  `:server-cuda` as the model host's build base), so which build answers is decided by whoever last
  pulled.

That last point is not a detail, and it decided the floor. Both images on the host machine reported
`b10666-4e97ac86e` on 2026-08-29, where the reading this entry rests on was taken the day before on
`b10644-d7a207411`. Nothing in this tree pins either.

### What a real server said

Measured 2026-08-29 by the agent, the shipped subagent pick (gemma-4-E4B QAT q4_0) on
`ghcr.io/ggml-org/llama.cpp:server` reporting `b10666-4e97ac86e`, `-ngl 0 -c 8192 --jinja
--parallel 1`, started with **neither** reasoning flag, at a cap of 256, on the deliberation
inviting prompt the committed switch probe already uses. The constrained cells carry
`REPLY_ENVELOPE`, which is the shape a tool-less delegated reply really has.

| cell | draws | deliberated | reply |
| --- | --- | --- | --- |
| envelope, switch, no budget (the failing cell) | 30 | **26/30** | empty, `length`, every deliberating draw |
| envelope, switch, `reasoning_budget_tokens: 0` | 58 | **0/58** | the envelope |
| envelope, switch, `thinking_budget_tokens: 0` | 3 | 0/3 | the envelope |
| envelope, **no** switch, `reasoning_budget_tokens: 0` | 3 | 0/3 | the envelope |
| envelope, switch, `reasoning_budget: 0` (the old spelling) | 5 | **5/5** | empty, `length` |
| plain, no switch, no key | 3 | 3/3, 591 to 854 chars | empty, `length` |
| plain, no switch, `reasoning_budget_tokens: 128` | 5 | 4/5, 310 to 516 chars | 347 to 717 chars |
| plain, no switch, `reasoning_budget_tokens: 32` | 3 | 2/3, 72 and 92 chars | 530 to 585 chars |

Five readings decide everything below.

1. **The entry was right about the key and right about the rate, and this session very nearly
   was not.** The first five draws of the failing cell deliberated 5 of 5, which reads as a defect
   that always reproduces, and that reading was written down here before a larger one existed.
   Drawn twenty more times it is 17 of 20, and five more after that 4 of 5, for **26 of 30**: the
   entry's own 4 in 5, a coin toss rather than a certainty. The small sample was wrong in the
   flattering direction, which is this ADR's own standing lesson landing on the person applying
   it. What does not move is the cost: every deliberating draw spent the whole cap and returned an
   empty reply. The budgeted cell is the repair, 0 of 58.
2. **It is the key and not the switch.** The budget holds with the switch sent and with it left
   alone, which is what says the two are independent levers rather than one lever with two names.
3. **The old spelling is still dead**, on the newest build, in the same minute, 5 draws of 5. So
   the trace-budget addendum's sentence about `reasoning_budget` is right and stays.
4. **It is a dial and not a third switch**, which is the half [R-295](../refinements/tasks/295-per-request-trace-budget.md)
   was waiting for. Per request, on one server with no flag: unbounded spends 591 to 854 characters
   of trace and returns **nothing** inside the cap, 128 spends 310 to 516 and returns an answer,
   32 spends 0 to 92 and returns a longer one. Two callers on one tier can now hold two different
   positive counts, which is the whole of what that entry could not express.
5. **`thinking_budget_tokens` is a working alias**, and this repo sends one name. A second key on
   every request buys nothing on a build that reads either and is a second thing to keep true.

### The capability read, which is what makes the floor honest

A build that does not support the key ignores it and reports nothing. That is the failure this
repo dislikes most, and the tier flag of the same name does better by failing a server at boot. So the request
half needs a floor, and the entry was right that a constant is not one. The measurement above says
why more sharply than taste does: the tags float, and the build under this repo had already moved.

`GET /props` does not answer it. Read off the running server: `default_generation_settings.params`
carries no reasoning budget of any kind, and `chat_template_caps` is about the template rather than
the sampler. What it does carry is `build_info`, which is a **proxy** for the capability and not the
capability, and would have this repo comparing version strings against an upstream it does not pin.

The engine answers it directly, in the one place a server must be honest about a key it parses: it
**range-checks it**. Measured against two builds, one model, one prompt, a minute apart:

| build | `reasoning_budget_tokens: -2` | the same cell with the key at zero |
| --- | --- | --- |
| `b10666-4e97ac86e` | **400** `Field 'reasoning_budget_tokens': Value must be between -1 <= value <= 2147483647, but got -2` | the thought ends, 0 of 58 deliberated |
| `b9870-2d973636e` | **200**, a completion, the field ignored | unchanged, 3 of 3 deliberated |

The verdict and the behaviour agree on both, which is what makes this a capability read rather than
a guess. Two smaller findings shape the request it sends. Only a **well typed**
out-of-range integer trips the check: `"abc"`, `{}`, `true` and `[1]` all answer 200, the engine's
own reader swallowing a type error and taking its default, so a probe built on a malformed value
would have called every build ignorant. And validation runs **before** decoding, so the probe costs
one token on a build that says no and none at all on a build that says yes.

### Decision

1. **`GenerationBounds` grows a third number, `trace_tokens`.** `0` ends the deliberation at once,
   a positive count lets it run that far and then closes it, and `None` says nothing and leaves the
   tier's own `--reasoning-budget` deciding. There is no port-level word for "unrestricted" because
   `None` already is one, and a negative count raises rather than smuggling an engine's `-1`
   sentinel through a port. It renders as `reasoning_budget_tokens`, verbatim, a zero included.
2. **The switch and the count are independent, and nothing derives one from the other.** This is a
   rule rather than an omission, and it is the answer to the second thing the entry said had to be
   decided. `thinking=False` is what a caller says when it will not read the trace; `trace_tokens=0`
   is what it says when the trace must not be spent. A cortex turn renders its trace as the thinking
   status the overlay shows (ADR-0020), so a zero inferred from the switch would silently blank the
   one surface in this repo where a bounded trace is a loss rather than a saving. Two tests hold it,
   one at the payload and one at the deployment's own producer.
3. **The three side calls name a zero; a user's own reply names nothing.** `TITLE_BOUNDS`,
   `RECAP_BOUNDS` and `rank_bounds(k)` each carry `trace_tokens=0` beside the switch they already
   carried, because `drain_text` destroys their trace before a caller sees a character of it, so
   there is nothing there to lose and a whole cap to win back. The reply bounds gain
   `CORTEX_REPLY_TRACE_TOKENS`, **unset by default**, so the deployment names its own count or the
   tier keeps deciding. Zero is a real setting there, so the sentinel for "unset" is not the falsy
   value, which is the same trap the model host's own budget already names.
4. **The floor is a probe of the running server, with the deployment able to answer for it.**
   `CORTEX_INFERENCE_TRACE_LEVER` takes `auto` (the default), `on` or `off`, the same three words
   and the same shape as `CORTEX_VISION` (ADR-0029 live-probe addendum). `auto` asks the endpoint
   once and believes it; `on` and `off` fix the answer and open no socket, which is what a
   deployment behind a proxy or with no server at wiring time wants. Every failure is a no, so an
   unreachable server, another status, or a 400 that does not name the key all leave the request
   carrying no budget, which is the request this repo sent before the key existed. A deployment
   setting alone was the alternative and is refused for the reason the re-derivation found: the
   right value changes under an operator who did nothing, because the tag they pull is mutable.
5. **The answer is taken once, where the vision probe beside it is taken forever.** That difference
   is the whole argument for caching this one: vision is a property of an **argv**, which a model
   host can change under a running brain by recreating a child without a projector, and this is a
   property of a **binary**, which changes only when an image does. One answer therefore covers the
   deep tier too, that tier being another child of the same image. The cost is a boot-time question
   bounded by `TRACE_LEVER_PROBE_TIMEOUT_S` (5 s, sized from the measured 235 to 310 ms of prompt
   evaluation and 111 ms a token on the slowest tier this repo ships), and the compose stack already
   gates the brain on the model host being healthy.
6. **The port owes the same evidence for the count that it owes for the switch.** A trace that
   arrived despite a budget of zero still crosses as `ReasoningChunk`. It is a shared contract check
   over both implementations rather than a note, and a separate one from the switch's rather than a
   restatement of it: a count reads like an order where a switch reads like a request, so an
   implementation is more likely, not less, to think it may make the number true by dropping what
   came back. It may not. On a deployment where the key was withheld or ignored, that trace is the
   only evidence the caller has that its budget bought nothing.
7. **The delegated path gains nothing, and that is a decision.** `PlacedAttempt` still names no
   count. Every subagent server this repo starts already carries `--reasoning-budget 0`, and
   `scripts/flagcheck.py` derives that set from the stack's own wiring rather than from a list, so
   no shipped tier there is missing the sampler a zero would ask for. Every request that path sends
   wants the same zero, which is exactly what a per-server flag says best, and the trace-budget
   addendum's decision 7 already says a positive count there is a knob no env can make matter. The
   cost of the alternative is concrete: the lever is a boot-time question per endpoint, and a roster
   answers on two endpoints an entry, several of which a stock deployment never starts.

### The leak, which is the third thing the entry said had to be decided

Forcing the end of a thought lands **after** its start sequence, so what the model had already
written of the tag can survive into the answer: the entry recorded one draw in five whose reply
began with the leaked word `thought`, on `b10644-d7a207411`. Since the envelope's `reply` is what a
delegated run reports, a repair that ships has to say what happens to it.

**Measured, and it reproduced once in fifty eight.** The exact cell was drawn twenty eight times
through the raw wire and thirty more through the shipped adapter, and one of those thirty came
back as this:

```
{"reply": "thought"}
```

A whole, valid envelope whose entire answer is the channel name the forcing lands inside of. Across
every draw of the session carrying `reasoning_budget_tokens: 0`, that is **1 of 58**.

**The same sampler on the tier flag was drawn twenty times and did not do it.** A server started
the way every subagent server this repo ships is started, `--chat-template-kwargs` and
`--reasoning-budget 0` on its argv, answered the identical constrained request twenty times with no
trace, no leak and an answer every time. The flag and the key set the same sampler, and 1 of 58
against 0 of 20 does not separate at these sizes, so the honest reading is **one rare phenomenon
that the request key inherits rather than introduces**. It is already reachable in the shipped
stack, which is worth knowing before anybody decides this addendum added it.

**What it costs is worse than the entry supposed, and worse than this addendum's first draft said.**
The leak does not land in front of the payload where the envelope's grammar would reject it. It
lands **inside** the payload, so the reply parses, `unwrap_envelope` returns it, and a delegated
run reports `thought` as the subtask's answer. Nothing downstream can tell that from a real answer.

**Both attempts to count it were confidently wrong, in opposite directions**, and that is the part
worth carrying forward. The first detector asked whether the reply parsed and called a reply cut at
`max_tokens` a leak, reporting 2 of 5 where nothing had leaked. The second asked only about
position, and reported **0 of 20** on the very run whose fifth budgeted draw is quoted above. The
committed probe now reads both shapes, and the second of them is sound only for its own prompt: a
bill split three ways cannot be answered in one word, so a one-word answer there is a defect
whatever produced it. A file that asked the same of an arbitrary subtask would be wrong, which is
said on the property that asks it.

**So no repair ships, and the reason is not that it is rare.** A repair would have to strip a
template's start sequence out of a reply, which means the core knowing a per-pick token
(`<|channel>thought` on this family, `<think>` on the other), and that is the one thing the port
exists to not know. Nor can a shape rule stand in for it: a one-word answer is a defect on the
probe's own prompt and a perfectly good answer to a subtask that asked for a number. What ships is
the account, the counts, and a probe that will see it again on a build that raises the rate. It is
[R-495](../refinements/tasks/495-the-forced-thought-can-leak-its-own-start-tag.md).

### What this does not do, and where that is recorded

- **The lever is asked once and never again.** A llama.cpp image upgraded under a running brain
  changes the honest answer and the brain keeps the one it booted with. The direction is safe (an
  older answer withholds a key rather than sending one nothing reads), and a restart or
  `CORTEX_INFERENCE_TRACE_LEVER=on` fixes it, but nothing notices.
  [R-496](../refinements/tasks/496-the-trace-lever-is-answered-once-per-boot.md).
- **Nothing holds a producer's count to the lever being on.** A bound naming a count on a
  deployment whose engine ignores the key is silently the bound it always was, which is the same
  gap the switch has and the same reason: the core deliberately does not know a tier's argv or a
  deployment's build. `drain_text`'s warning is still the only runtime report, and it fires on the
  switch rather than on the count.
  [R-497](../refinements/tasks/497-nothing-reports-a-trace-budget-that-went-unread.md).
- **One reply count reaches both phases of a turn.** `CORTEX_REPLY_TRACE_TOKENS` rides the bounds
  the cortex turn and the deep phase already share, which the capped-reply addendum argues for on
  the cap ("a handoff is one turn continued"). The same setting at the **server** is deliberately
  two knobs, on the argument that the two tiers are read on opposite ones, so the inheritance is
  less obviously right here than it is for a cap. Nothing ships set, so nobody is in that position
  yet. [R-498](../refinements/tasks/498-one-reply-trace-budget-for-two-tiers.md).
- **What a bounded trace costs the answer is still not measured**, which the trace-budget addendum
  said of the tier flag and is now true of three shipped requests that name a zero.
  [R-296](../refinements/tasks/296-trace-budget-quality-floor.md) is where that has always lived,
  and this addendum does not close it: the side calls' zeros are safe on the argument that their
  trace was already discarded unread, not on a measurement of what they are worth.

### Distrust green

Thirteen mutations, each applied to production code alone with the named suite re-run, then
reverted. Six are over the **100 checks of the inference package suite**
(`brain/packages/inference/tests/`), four over the **1632 of the core suite**
(`brain/packages/core/tests/`), and three over the **458 of the orchestrator suite**
(`brain/packages/orchestrator/tests/`).

| mutation | suite | tests that fail |
| --- | --- | --- |
| the payload derives the budget from the thinking switch | inference | **2** |
| the payload reads a budget of zero as nothing asked | inference | **1** |
| the payload carries the budget whatever the engine reads | inference | **1** |
| the adapter filters a trace the request budgeted away | inference | **1** |
| the probe reads any refusal as a knowing build | inference | **1** |
| the probe asks with a value a knowing build accepts | inference | **1** |
| a negative trace budget is accepted at the port | core | **1** |
| the session title drops its count and keeps the switch | core | **1** |
| the history fold drops its count and keeps the switch | core | **1** |
| the recall rank drops its count and keeps the switch | core | **1** |
| a fixed lever mode probes the endpoint anyway | orchestrator | **1** |
| the reply bounds fold a budget of zero into unset | orchestrator | **1** |
| the reply bounds derive the count from the thinking switch | orchestrator | **3** |

Three of them are worth reading rather than counting.

**The adapter filter is the repair decision 6 forbids, and it fails exactly one check**, the new
`check_a_trace_the_request_budgeted_away_still_crosses` on the adapter's leg and nothing else. That
is the same reading the switch's own filter gave when the switch-is-advisory addendum ran it, and
it is what says the eleventh check covers something the ten before it do not: written as a targeted
drop of a trace whose budget was zero, it slips past every other check in the tree. Dropping every
reasoning delta instead fails four, which is the contrast that makes the targeted number mean
something.

**Rows one and thirteen are the same defect written at two layers**, and both are the one this
addendum's decision 2 exists to stop: a derivation from the switch to a zero, once in the payload
and once in the deployment's own producer. Neither is a strange thing for somebody to write, which
is why both are pinned rather than argued about in a comment.

**Row three is the floor itself.** With the lever ignored, the key rides every request on every
deployment, which is precisely the knob with no effect, and one check says so.

**And the runbook's own sample was tested against its gate**, which is not one of the thirteen
because its unit is a scan and not a suite. The probe's verdict is documented as a fenced line, so
`scripts/samplecheck.py` holds it to the call site: dropping the `lever` field from the sample is
reported at once, naming the file, the line and both field lists. The other mutation of it is worth
recording because it stayed **green when red was expected**, and correctly: reordering the fields
in the call's own `extra` changes nothing, the formatter rendering them in name order, which is
what that gate has always said it holds. The expectation was wrong rather than the gate.

## Template-probe addendum (2026-08-29): the rendering is a prediction, and it stops being load bearing

**Status:** Accepted. Declines
[docs/refinements/tasks/475-a-tier-can-be-asked-what-its-template-answers.md](../refinements/tasks/475-a-tier-can-be-asked-what-its-template-answers.md),
which proposed shipping the lineup section's rendering column as a boot time probe, and opens
[R-499](../refinements/tasks/499-the-rendering-predictor-is-asserted-nowhere.md).

It **completes the scope sentence** the request lever addendum above wrote for the switch is
advisory addendum's decision 5. That decision said "no adapter side repair, and no capability
probe", the request lever addendum carved the engine's own key out of it, and this one says the
remaining half stands: asking a server what a **pick** does with a grammar in front of it is still
not a question any endpoint answers, and the rendering that predicts it is a prediction rather than
an answer. Nothing else in that decision moves, and no code changes here.

### Re-derived first, because this entry's account of its own subject is where it fails

Read off the tree before any server was started, and the entry's central sentence had already
stopped being true.

- The entry says the third of its three template states is the only one where "a bound pairing a
  cap with `thinking=False` **and a schema** returns a short answer rather than no answer, and
  `rank_bounds` with `ORDER_ENVELOPE` is exactly that pairing". `rank_bounds(k)` now carries
  `trace_tokens=0` (`cortex_core.rerank_judge`), as do `TITLE_BOUNDS` (`cortex_core.session_title`)
  and `RECAP_BOUNDS` (`cortex_core.recap_prompt`). On a deployment whose engine reads that key, the
  template's answer decides nothing about any shipped bound, because the sampler has already closed
  the thought whatever the prompt left open.
- The hazard therefore survives in exactly one place, and it is worth naming precisely rather than
  waving at. `JudgeRecallPolicy` is built against the **cortex** model
  (`cortex_orchestrator.memory_builders`), and the cortex is one of the two tiers the model host
  starts with **no** fixed zero: `cortex_reasoning_budget` and `brain_reasoning_budget` both default
  to unrestricted and emit no flag, where the subagent tier alone carries `_REASONING_OFF`
  unconditionally (`cortex_model_manager.config`). So the only shipped schema carrying bound runs
  against a tier with no sampler floor, and its safety rests on the cortex pick's template or on the
  lever. That is a real and narrow question, and it is the strongest thing this entry has.
- `CORTEX_INFERENCE_TRACE_LEVER` is resolved once at `build_backend`, on the cortex endpoint, with
  the cortex model (`cortex_orchestrator.builders.resolve_trace_lever`). The composition root
  therefore already holds the answer that decides whether the template question matters, in the
  same function, at the same moment.

The entry's claim that the ground "has moved twice" is upheld on both moves. `POST /apply-template`
does render the prompt a request would really get, and the lineup section's eleven rows do read the
constrained verdict off it. What moved a third time is the ground under the entry itself.

### What a real server said

Measured 2026-08-29 by the agent on `ghcr.io/ggml-org/llama.cpp:server` reporting
`b10666-4e97ac86e`, both picks `-ngl 0 -c 8192 --jinja --parallel 1`, started with **neither**
reasoning flag, at a cap of 256, on the deliberation inviting prompt the committed switch probe
uses, the constrained cells carrying `REPLY_ENVELOPE`. Two entries were chosen because the lineup
table puts them on opposite sides of the column that splits.

| tier | cell | draws | deliberated | reply |
| --- | --- | --- | --- | --- |
| gemma-4-E4B QAT q4_0 (drops the block) | envelope, switch, no budget | 5 | **5/5** | empty, `length`, every draw |
| gemma-4-E4B QAT q4_0 | envelope, switch, `reasoning_budget_tokens: 0` | 5 | **0/5** | the envelope, every draw |
| Qwen3.5-2B Q4_K_M (closes an empty think) | envelope, switch, no budget | 5 | **0/5** | the envelope, every draw |
| Qwen3.5-2B Q4_K_M | envelope, switch, `reasoning_budget_tokens: 0` | 5 | **0/5** | the envelope, every draw |

The first two rows are the whole decision. The failing tier fails the way the column predicts, and
the key that already ships closes it on the same server in the same minute. The prediction is
correct and it is no longer about anything.

### And the probe the entry describes cannot be written the way it describes it

The entry says the answer is "one HTTP call and two string comparisons". Both renderings were read
rather than assumed, full prompts and not tails, and the comparison it names sorts nothing.

```
E4B,  no switch  194 chars  …<|turn>system\n<|think|>\n<turn|>\n<|turn>user\n…pay?<turn|>\n<|turn>model\n
E4B,  switch     162 chars  …<|turn>user\n…pay?<turn|>\n<|turn>model\n
2B,   no switch  187 chars  …<|im_end|>\n<|im_start|>assistant\n<think>\n
2B,   switch     198 chars  …<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n
```

Three readings, and the third is the one that decides.

1. **The renderings differ on both picks**, so "are these two strings equal" answers "the template
   read the key" for the failing tier as loudly as for the holding one. The entry's first state,
   a template that ignores the key entirely, is not what the failing tier is in and was not
   observed anywhere in the lineup.
2. **The E4B's two prompts have byte identical tails**, both ending `<|turn>model\n` with the
   thought block left open, and the difference is a whole system turn dropped at the **front**. The mechanism section
   above says exactly this and says it correctly, "dropping the `<|think|>` marker and adding
   nothing", and the two lines it quotes are tails, so the drop it describes is not visible in
   them. That is a presentational gap in this ADR rather than a wrong sentence, and it is repaired
   by the block above.
3. **So the predictor turns on the tail closing a thought, and recognising a closed thought means
   knowing a per pick template token.** `</think>` on the native family, `<channel|>` on gemma-4,
   and neither is on any endpoint. This ADR refused that exact knowledge one addendum ago, on the
   leak: "a repair would have to strip a template's start sequence out of a reply, which means the
   core knowing a per-pick token, and that is the one thing the port exists to not know." A probe
   that classifies a rendering needs the same vocabulary for a weaker purpose.

### Decision

1. **No template probe ships, and the rendering column stays a reading rather than a rule.** It is
   eleven readings of one engine build's handlers, correct on all eleven and on both picks
   re-measured here, and it is a **proxy** for the constrained verdict. The request lever addendum
   refused `build_info` on that ground while choosing a range check that is the capability itself,
   and the template rendering is the weaker of the two kinds: the engine is not asserting anything
   about it, so a handler that gated its reasoning rule on `enable_thinking`, which sibling
   handlers in the same file already do, would leave a shipped probe confidently wrong with nothing
   noticing. The tags float, which is the argument that refused a constant floor, and it lands on a
   carried prediction harder than on a constant.
2. **The hazard is repaired rather than reported, and the repair is the one that shipped.** The
   three side calls name `trace_tokens=0`, the lever decides whether it reaches the engine, and on
   the tier the entry is about that pairing was measured here at 0 of 5 where the unbudgeted cell
   is 5 of 5. A detector for a hazard that has a repair present is worth less than the repair, and
   on a deployment where the repair is absent the detector's only advice is to obtain the repair.
3. **What the entry wanted said at boot is already filed, in a form that needs no template
   vocabulary.** [R-497](../refinements/tasks/497-nothing-reports-a-trace-budget-that-went-unread.md)
   names the honest half as a line from the composition root, which knows the lever and the
   deployment's own count. That root can say "this engine reads no per request trace budget" from
   what it already has, and that sentence is true of every tier without asking any of them anything.
4. **The one thing the decline loses is that the reading is asserted nowhere.** The committed switch
   probe prints both renderings ahead of its cells and reads neither, so the rule that ties them to
   the verdicts is carried in prose across two documents and re-derived by hand. That is
   [R-499](../refinements/tasks/499-the-rendering-predictor-is-asserted-nowhere.md), and it is an
   integration probe's assertion rather than anything that runs in a deployment, which is the
   difference between it and what was declined.

### What this does not do, and where that is recorded

- **The cortex tier still has no sampler floor and one schema carrying bound**, so a deployment that
  swaps the cortex pick for a template on the failing side and runs an engine whose lever is off
  loses every rank to an empty reply, silently. `drain_text`'s warning fires on that completion, so
  it is reported after the fact and not before, which is the standing shape of this and is
  [R-466](../refinements/tasks/466-nothing-holds-a-cap-to-a-bounded-trace.md) for the gate half and
  [R-497](../refinements/tasks/497-nothing-reports-a-trace-budget-that-went-unread.md) for the boot
  half.
- **No lineup entry was re-measured except the two here.** The other nine rows stand on the reading
  the lineup section took, on the build it names, and this addendum does not refresh them.

## Firm-prompt addendum (2026-08-29): the reasoning-off pair is conditional on the prompt, and the request key is not a repair for it

**Status:** Accepted. Closes
[docs/refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md](../refinements/tasks/479-the-reasoning-budget-held-until-the-prompt-pushed.md),
and opens
[R-500](../refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md).

It stands **beside** the request-lever addendum above rather than under it, and saying why is the
whole reason this entry is not declined the way its sibling was. That addendum measured a **request
key holding on a server carrying no flag**. This entry is about **a server flag failing on a server
carrying both**. The second does not follow from the first, and on the delegated path the key the
sibling was declined in favour of is the same sampler zero said a second time. So the question here
is not whether a repair exists somewhere in the engine. It is whether the repair works on the shape
that ships, and it was measured rather than reasoned about.

### Re-derived first, because an entry's account of its own subject is not evidence

Read off the tree before any server was started, and two of the entry's three load bearing
sentences had already stopped being true.

- **The probe it names cannot take the cell it describes.** The entry says
  `brain/packages/inference/tests/test_thinking_switch_live.py` "already draws each cell several
  times against a server whose flags the operator chooses". That file's own docstring says the
  opposite, "the server must be started with **no** `--reasoning-budget` and **no**
  `--chat-template-kwargs`", and it is not a preference: each shape's no-switch arm is **asserted**
  to have deliberated, which is the control the file exists to carry, so a run of it against a
  server carrying the pair goes red on that control before it reports a rate. The cell the entry
  wants belongs where the entry's own rate was taken,
  `brain/packages/orchestrator/tests/test_envelope_cost_live.py`, which runs the shipped
  `SubagentRunner`.
- **One of the three documents it says owes a sentence already carries one.**
  [docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md) names this entry, gives 8 draws in
  96 against 1 in 96 with the sentence stripped, and orders the causes of a cap refusal on narrow
  work: the flags first, this second, a runaway third. What is unqualified is the other two, the
  compose command block's "the budget is the flag that reaches that shape" and
  [ADR-0010](ADR-0010-subagents.md)'s "on a current image `--reasoning-budget 0` does work and is
  what reaches that shape".
- **The request lever does not reach this path, and that is a decision rather than an omission.**
  `PlacedAttempt` builds `GenerationBounds(max_tokens=...)` and names no count, and the
  request-lever addendum's decision 7 argues it: every subagent server this repo starts already
  carries `--reasoning-budget 0`, so a request here would be asking for the zero the tier already
  set. That is what makes this entry unlike its sibling. There the repair was present and the
  proposal was a detector for it; here the proposal **is** the repair, and the repair is the flag
  that is failing.

### What a real server said

Measured 2026-08-29 by the agent, the shipped subagent pick (gemma-4-E4B QAT q4_0) on
`ghcr.io/ggml-org/llama.cpp:server-cuda` reporting `b10666-4e97ac86e`, `-ngl 99 -c 8192 --jinja
--parallel 1`, started **the way `docker/docker-compose.subagents.yml` starts one**, with both
`--chat-template-kwargs '{"enable_thinking": false}'` and `--reasoning-budget 0` on its argv. The
request is the shipped delegated one, built by the tree's own `task_messages` and `build_payload`:
the four report bodies of the envelope harness, the appended `REPLY_INSTRUCTION`, `REPLY_ENVELOPE`
as the `response_format`, `max_tokens` at the shipped 1024, and no other key. The unflagged rows
below are the same request against a second server of the same image and model started with
neither flag.

| server | request | draws | wrote to the channel | empty reply |
| --- | --- | --- | --- | --- |
| both flags | the shipped delegated request | 76 | **13** | **8**, every one cut at the cap |
| both flags | the same, plus `reasoning_budget_tokens: 0` | 20 | **1** | 1 |
| neither flag | the shipped delegated request | 8 | **8/8**, 1782 to 2799 chars | 0 |
| neither flag | the same, plus `reasoning_budget_tokens: 0` | 8 | **0/8** | 0 |

Four readings, and the third is the one nobody had.

1. **The entry is right, at eight times its sample and on a GPU rather than a CPU.** The pair is
   not absolute on this pick: 13 draws in 76 of the exact request a delegated run sends wrote 1582
   to 4078 characters into a channel that run drops unread, and 8 of those came back with an empty
   `reply` cut at 1024. The traces fall on **two of the four bodies**, warehouse and clinic, with
   fleet and network clean throughout, which is the same concentration the 288 run measurement
   reported and is the shape of a prompt effect rather than a body's quirk. The 76 draws are two
   at each of 38 seeds and are therefore not 76 independent samples: the pair at one seed agreed on
   whether the channel was used on 37 of 38 and was alike to the character on 33, so read the rate
   as 7 of 38 seeds rather than as a precision.
2. **The request key is not the repair, on the server this is about.** Twenty draws carrying
   `reasoning_budget_tokens: 0` on top of both flags still produced one, and it is the same
   phenomenon rather than a milder one: a garbled marker, then the answer written in prose into the
   channel, then the cap. One in 20 against 13 in 76 does not separate at these sizes and this
   addendum does not claim it does. What one occurrence does settle is the only question that was
   open, whether adding the key **closes the thought block** on a tier whose flag already set the
   same sampler. It does not.
3. **The key does work on this prompt where nothing else is set**, which is what stops reading 2 as
   a doubt about the key itself. On the unflagged twin of the same server, the same firm request
   deliberated on 8 draws of 8, on all four bodies, and on 0 of 8 with the key added. So the
   failure is not "this prompt defeats every lever", and the prompt invites a thought from every
   body rather than from the two that leak. It is specific to the tier that already carries the
   flag.
4. **The two servers write different traces, and the difference is the finding.** Every trace on
   the unflagged server opens as ordinary deliberation and reads like it: "Here's a thinking process
   that leads to the summary", "Thinking Process:", "*   **Analyze the Request:**". On the flagged
   server 11 of the 13 open with a **fragment of a channel marker** instead, the literal
   `</channels>`, `t</channell>`, `</chaann>`, `h</cha>`, `h</c>`, or a bare `>`, and then write the
   answer itself into the channel in plain prose. That is the same malformed opening the ADR-0028
   instruction addendum recorded on 6 of its 8, read here beside its own control.

### What the traces say about the mechanism, which reverses the entry's hypothesis

The entry supposed that a firm instruction makes prose inadmissible inside `reply`, so the prose
goes into the thought block the gemma-4 handler leaves open under a grammar, and "a budget of zero
would be one more thing the grammar outranks". The traces do not read that way, and the control is what says
so. A budget being outranked would leave the model deliberating the way an unbudgeted one does, and
that is exactly what the unflagged rows show and the flagged rows do not.

What the flagged rows show is the request-lever addendum's own leak, at a severity that addendum did
not reach. That addendum found that forcing the end of a thought "lands **after** its start
sequence", so what the model had already written of the tag survives, and recorded one draw in 58
whose whole reply was the leaked word `thought`. The fragments above are the other side of the same
event: a forced close emitted where no thought was open, mangled, and then read by the server's own
parser as a channel switch, after which every token of the answer is classified as reasoning. On
that reading the budget is not being overridden at all. It is firing, and its forcing is the thing
that goes wrong.

This is the best explanation of four readings and it is not an attribution. Nothing here read the
handler, and one build was measured. It is
[R-500](../refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md).

### Decision

1. **The reasoning-off pair is conditional on the prompt, and the two documents that state it
   without a qualifier gain one.** The compose command block and ADR-0010 both say the budget
   reaches the constrained shape, which is true and is not the whole of it. Both now say what it
   costs when it does not, with the rate and the symptom, so an operator reading either meets the
   failure where the claim is made rather than only in the runbook.
2. **The delegated path still names no count, and decision 7 of the request-lever addendum
   stands, on a better argument than it had.** It rested on the key being the zero the tier already
   set. That is now measured rather than assumed, and measured in the direction that matters: the
   key on top of the flag left the phenomenon reachable. Routing `trace_tokens=0` into
   `PlacedAttempt` would therefore add a key to every delegated request in the repo and buy nothing
   that was asked for, which is the same ineffective knob with extra steps.
3. **No repair ships, and the reason is that no repair here is this port's to make.** The three
   shapes a fix could take are all refused for reasons already written down. Stripping a garbled
   marker out of a reply needs the core to know a per pick template token, which the leak reading
   refused one addendum ago and the template-probe addendum refused again. A shape rule over the
   answer cannot tell a one word answer from a defect. And the pick itself is the real lever, the
   ADR-0028 row addendum having measured every Qwen entry writing nothing to that channel across
   864 draws, which is a lineup decision and not an engine one.
4. **What ships is the rate, the control and the symptom**, so the next reader meets a measured
   conditional claim rather than an absolute one, and so a build that raises or removes the rate is
   recognisable when somebody re-runs the same request.

### What this does not do, and where that is recorded

- **The garbled marker has no attributed cause.** The forced close is the best explanation of the
  contrast between the two servers, and it is a reading of traces rather than of the handler that
  writes them.
  [R-500](../refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md).
- **The key arm is 20 draws and each unflagged arm is 8**, sized to the session rather than to the
  question. What they establish is existence on one side and effect on the other, and neither is a
  rate. The flagged arm is the only row here anybody should quote as one, and it is 38
  seeds drawn twice rather than 76 independent draws.
- **No committed probe reproduces this cell.** The harness that can take it,
  `test_envelope_cost_live.py`, runs the shipped runner and therefore sends what `PlacedAttempt`
  sends, so the key arm above was drawn by hand off `build_payload`. That is the half of R-479's
  own closing condition this addendum does not meet, and it is named in
  [R-500](../refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md).
- **One pick, one build, one prompt shape.** Every number is gemma-4-E4B on
  `b10666-4e97ac86e` at the summarization shape, which is the shape the residue was already
  concentrated on. The lineup's own reading, that no Qwen entry writes to that channel at all,
  is untouched and unre-measured here.

### Distrust green

No rule, gate or branch is added, so there is no mutation table and this section says instead what
the measurement's own controls were. Two of them carry it. The **unflagged twin** is what separates
"this prompt defeats the lever" from "this tier's flag garbles its own close", and without it every
flagged reading here would have had two explanations and no way to choose. The **paired seed** is
what says the flagged rate is a property of the request rather than of the draw order: 38 seeds
drawn twice agreed on the channel 37 times, which is also the reason the rate is quoted over seeds
and not over draws. What no control here reaches is the handler itself, and that is why decision 3
ships an explanation labelled as one.

## Rendered-tail addendum (2026-08-30): the prediction is read back, by something that runs

**Status:** Accepted. Closes
[docs/refinements/tasks/499-the-rendering-predictor-is-asserted-nowhere.md](../refinements/tasks/499-the-rendering-predictor-is-asserted-nowhere.md),
which the template-probe addendum above opened as the one thing its decline lost. Opens
[R-509](../refinements/tasks/509-a-third-familys-closed-thought-reads-as-an-open-one.md) and
[R-510](../refinements/tasks/510-nine-rows-of-the-rendering-column-are-hand-read.md). It adds two
covered modules and one recipe, changes no shipped code and no pick.

### Re-derived first, and the entry is wrong about the page it is describing

The entry says the committed probe "asks each server `POST /apply-template` and prints both
renderings ahead of its four cells, and reads neither". Decision 4 of the addendum above says the
same thing in the same words. Read the file and neither half is quite true, and the correction
matters both ways.

- **It printed no rendering.** What it printed was two lengths and a verdict,
  `template reads the switch (194 chars against 162)`. So the reading a careful operator was
  supposed to be able to do by eye was not on the page at all: the tails the rule turns on were
  fetched, compared for length, and dropped. That is worse than the entry claims, and it is why
  this addendum records the renderings rather than only asserting over them.
- **It did read them, for one thing.** The two request shapes carrying one switch must render the
  same prompt, and that is asserted, because a tier where it fails is a tier whose four cells are
  comparing two prompts. What nothing read them for is the rule this entry is about.
- **The rule really is written twice**, as the entry says: the mechanism section above for two
  picks, and the lineup section's own column for eleven. Both are hand readings, and the second is
  where "it predicts the constrained verdict on every entry here" is claimed.

### Where the assertion goes, which is the whole decision

Inside the probe was the obvious place and is the wrong one, for two reasons that also decided the
envelope harness's control arm one addendum ago in [ADR-0028](ADR-0028-grammar-constrained-subagents.md).
An `integration`-marked file is code no gate runs, so a rule asserted there is a rule nothing
red-greens and no mutation table can be written over. And this repo has now three times put the
arithmetic behind a published claim in a covered module rather than in the driver that measured it
(`scripts/contrast.py`, `scripts/trailwidth.py`, `scripts/envelopefloor.py`), for the same reason
each time. There is a third reason particular to this rule: the probe is pointed at whatever server
an operator has, so a tier that breaks the prediction is **news to publish**, not a reason to red
the run that found it. A hard assertion would have made the discovery of a new handler look like a
broken test.

So the probe records and the reader judges. `test_thinking_switch_live.py` writes one sample per
tier (`CORTEX_THINKING_OUT`, `CORTEX_THINKING_TAG`) carrying what it was pointed at, the ask it
really sent, both renderings, and each cell's draws and deliberations; `scripts/switchtail.py`,
with `scripts/switchsamples.py` answering for that format, publishes the comparison. `just
switch-tail` runs it, and the probe prints the line to paste.

**Read on the tail, after the ask.** The trap the entry named is real and is the reason a plain
comparison of the two renderings sorts nothing: on the failing pick they differ by a whole
`<|think|>` system turn at the **front** and end byte identically. The tail here is whatever the
template appended after the last of the ask the driver recorded sending, which is the generation
prompt without this reader knowing one per pick turn marker, and a thought is closed when the last
marker in that tail is a closing one.

**The two sides are not equally strong and the report says which it is on.** A closing tail
predicts the switch holds on **every** draw, so one deliberating draw refutes it, and that is the
direction with something at stake: `rank_bounds` with `ORDER_ENVELOPE` is built against the cortex,
which is on the closing side and is one of the two tiers the model host starts with no sampler
floor. An open tail predicts the switch fails on **at least one** draw, which five draws that never
deliberated are evidence against rather than proof.

**Two refusals rather than verdicts.** A constrained cell drawn fewer than five times publishes
nothing, which is the probe's own rule made enforceable (that cell splits 4 to 1 on a shipped pick,
so the default one-draw run says either thing); and a shape whose control arm did not deliberate on
every draw publishes nothing either, a control that never fired leaving nothing for the switch to
have stopped. The probe asserts that control too, and the duplication is deliberate: the sample is
written before the assertions, so a red run still leaves a sample, and a reader that trusted it
would publish a verdict off a run that measured nothing.

### What a real server said

Measured 2026-08-30 by the agent on `ghcr.io/ggml-org/llama.cpp:server`
(`@sha256:db057ec90de0a423255a218b9612420993237ff33db68b3155dc3bba9b994a20`) reporting
`b10680-d7bd3bfca`, both picks `-ngl 0 -c 8192 --jinja --parallel 1` with **neither** reasoning
flag, at a cap of 256, five draws a cell, through the committed probe and published through the new
reader. The two picks are the pair the lineup table puts on opposite sides of the column that
splits.

| tier | switched tail, after the ask | reading | plain | envelope | published |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B Q8_0 | `<\|im_end\|>\n<\|im_start\|>assistant\n<think>\n\n</think>\n\n` | closes | 0/5 | 0/5 | agreed, exit 0 |
| gemma-4-E4B QAT q4_0 | `<turn\|>\n<\|turn>model\n` | leaves open | 0/5 | **5/5** | agreed, exit 0 |

Both templates read the key (187 against 198 characters, and 194 against 162), both controls
deliberated on 5 of 5, and the prediction held on both. One number moved and it is the split cell:
the E4B's constrained arm deliberated on **5 draws of 5** here where the lineup section recorded
4 of 5 on `b10644-d7a207411`, which is the same reading the template-probe addendum took on
`b10666-4e97ac86e`. The rule's verdict for that row is unchanged, since "does nothing" is what an
open tail predicts and one deliberating draw is enough for it.

### Decision

1. **The probe records; the reader judges.** The rendering the rule turns on is now written down
   beside the cells it predicts, and the comparison is a covered module with a mutation table
   rather than a sentence in two documents.
2. **A broken prediction is a refusal to publish, exit 1, and it is news about the record rather
   than about the deployment.** Nothing shipped depends on the rendering any more: the title, the
   recap and the recall rank each carry `trace_tokens=0`, and `CORTEX_INFERENCE_TRACE_LEVER`
   decides whether that reaches the engine. What a red says is that this ADR's rendering column has
   met a handler it does not describe, which is exactly the failure the template-probe addendum
   predicted and could not detect.
3. **The vocabulary stays in the probe's tree and out of the port.** `</think>` and `<channel|>`
   are per pick template tokens, and the leak reading refused to let the core know one. A file
   pointed at a server by hand may know them; `InferenceBackend` still may not, and decision 5 of
   the switch-is-advisory addendum, no capability probe, is untouched.
4. **The naming.** `switchtail.py` names the artefact the rule reads and the trap it exists to
   hold, in the family `contrast.py`, `trailwidth.py` and `envelopefloor.py` already speak: a
   compound of the subject and the thing measured on it. The alternates were `tailverdict.py`,
   which names the comparison but hides where it is read, and `thoughtdoor.py`, which borrows this
   metaphor this ADR's earlier prose used for a thought block the grammar reopens, and would send a
   reader of the gate tree nowhere. `switchsamples.py` is the format half, named as `logsamples.py` is.

### What this does not do, and where that is recorded

- **A closing marker in a third format reads as an unclosed thought.** The reader recognizes the
  two marker formats the shipped picks use and treats an unmarked tail as an open thought, which is
  the failing pick's real answer, so a third format's closing marker would be read as an unclosed
  thought and refused as a broken prediction.
  [R-509](../refinements/tasks/509-a-third-familys-closed-thought-reads-as-an-open-one.md).
- **Nine of the lineup's eleven rows are still hand readings.** Two were published through the
  reader here; the rest stand on the sweep the lineup section took, on the build it names.
  [R-510](../refinements/tasks/510-nine-rows-of-the-rendering-column-are-hand-read.md).
- **The driver's own half is ungated**, as the envelope harness's is: nothing red-greens an
  `integration`-marked file, so a field it stopped writing is caught by the reader's refusals and
  by nothing else. Those refusals are two of the mutations below.
- **Nothing runs any of this on a schedule.** The rule is checked when somebody points the probe at
  a server, which is the same standing shape as every live reading in this ADR.

### Distrust green

The rule is new, so it was made to fail before it was trusted. Mutations of the two modules, each
run against **`scripts/tests/test_switchtail.py` and `scripts/tests/test_switchsamples.py`
together, the 43-test suite that covers them** (`cd scripts && uv run pytest
tests/test_switchtail.py tests/test_switchsamples.py`):

| mutation | result |
| --- | --- |
| a tail with no marker read as a closed thought | 3 failed, 40 passed |
| the tail dropped, the whole rendering read for a marker | 2 failed, 41 passed |
| the closing side loosened, a cell holding unless every draw deliberated | 2 failed, 41 passed |
| the draw floor removed (`DRAWS = 1`) | 1 failed, 42 passed |
| the control arm no longer required to have deliberated | 1 failed, 42 passed |
| gemma-4's marker pair dropped, one family known | 2 failed, 41 passed |
| a rendering missing the ask published as if it had a tail | 2 failed, 41 passed |
| two cells claiming one placement, the first taken instead of refused | 1 failed, 42 passed |
| a sample carrying one rendering accepted | 2 failed, 41 passed |
| an empty list of cells accepted | 1 failed, 42 passed |
| a boolean accepted as a draw count | 1 failed, 42 passed |
| the control's own line reporting a switch verdict about a request that sent none | 1 failed, 42 passed |
| none, restored | 43 passed |

**And the instrument was run against real servers before it was believed**, which is what the
table above cannot do. Both agreeing runs are the readings in this addendum. Both refusals were
made to fire too: the default one-draw run of the same probe against the same Qwen server refuses
for its cell being drawn once, and the E4B's own sample with its constrained cell edited by hand to
0 deliberations of 5, which is the run a handler gating its reasoning rule on `enable_thinking`
would produce, prints the tail that left the thought open beside the cell that held and refuses to
publish. That edited sample is the trigger this entry recorded, and it is the only way to draw it
without a handler that does not exist yet.

## Marker addendum (2026-08-30): the flag that garbles the marker is the one that is not a sampler

**Status:** Accepted. Closes
[docs/refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md](../refinements/tasks/500-the-garbled-channel-marker-has-no-attributed-cause.md),
and opens
[R-511](../refinements/tasks/511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) and
[R-512](../refinements/tasks/512-no-committed-probe-splits-the-reasoning-off-pair.md). It adds no
rule, no gate and no shipped code, and it withdraws the explanation the firm-prompt addendum above
ships.

### Re-derived first, and the question the entry asks is the right one

The entry lists four candidate causes for the garbled channel marker, the two shipped reasoning-off
flags, the chat template's channel handling, the token cap cutting mid marker, and the engine build,
and asks which of them the firm-prompt contrast above isolates. Read against that measurement before
any server was started, the answer is **none of them**, and the reason is worth stating plainly.
That contrast has two cells, a server carrying both flags and a server carrying neither. It varies
two flags in one step, and one of those flags is not a sampler at all: the kwarg is an input to the
**rendering**, so "the two flags" and "the chat template's channel handling" are one axis in that
contrast rather than two candidates. The cap and the build are held fixed in both cells, which
excludes them from being what the contrast *shows* and does not exclude them from being what the
phenomenon *needs*. So the contrast isolates the pair, jointly, and separates nothing inside it.

The entry's second claim, that its own explanation is a reading of traces rather than of a handler,
also survives re-derivation and is the thing this addendum acts on. The forced close was reached for
because it was the only mechanism in the tree that could put a mangled marker on a wire. Nothing had
asked whether a forced close happens at all on the server that produces them.

### What a real server said

Measured 2026-08-30 by the agent, six servers of the shipped subagent pick (gemma-4-E4B QAT q4_0),
each `-ngl 99 --ctx-size 8192 --jinja --parallel 1` on the 24 GB card, differing only in flags and
in image. Four run `ghcr.io/ggml-org/llama.cpp:server-cuda` at
`sha256:952424b09abc18668a9891041b275bf8c96afb6107d65d33ba104da9b18490c7`, which reports
`b10680-d7bd3bfca`. Two run `ghcr.io/ggml-org/llama.cpp:server-cuda-b10666` at
`sha256:150b59966fb5b2cb1a8fa9d226267c56ebd22c520c7b3640331cde87f3c4fb01`, which reports
`b10666-4e97ac86e`, the build every number in the firm-prompt addendum above was taken on. The
request is the shipped delegated one, built by this tree's own `task_messages` and `build_payload`
at `GenerationBounds(max_tokens=1024)`, so the body carries `messages`, `stream`,
`response_format` and `max_tokens` and nothing else, plus a `seed` so that the arms of one draw are
paired.

**The rendering is where the two flags separate, and they separate completely.** `POST
/apply-template` with the shipped two message ask, on both builds:

| flags on the server | what the prompt ends up carrying |
| --- | --- |
| both, the shipped pair | no `<\|think\|>` |
| `--chat-template-kwargs '{"enable_thinking": false}'` alone | byte identical to the pair |
| `--reasoning-budget 0` alone | carries `<\|think\|>` |
| neither | byte identical to the budget alone |

The kwarg is the half that reaches the prompt: it drops the `<\|think\|>` this template injects at
the top of the first system turn. The budget leaves the prompt **byte identical to an unflagged
server's**, which is the whole of what the thinking-lever addendum above says about the two, read
here off the engine rather than off a behaviour. The chat template itself is byte identical across
the two builds.

**The draws, paired by seed over the two report bodies the firm-prompt arm's traces fell on.**

| build | flags | draws | wrote to the channel | opened with a marker fragment | empty reply |
| --- | --- | --- | --- | --- | --- |
| b10680 | both, the shipped pair | 20 | 5 | 2 | 4 |
| b10680 | kwarg alone | 20 | 5 | 2 | 4 |
| b10680 | budget alone | 20 | **0** | 0 | 0 |
| b10680 | neither | 15 | 15 | 0 | 0 |
| b10666 | both, the shipped pair | 10 | 5 | 3 | 4 |
| b10666 | budget alone | 10 | **0** | 0 | 0 |

Five readings, and the second is the one that decides the entry.

1. **The budget alone is the fix, and it is absolute over 30 draws on two builds.** Not one
   reasoning character on any of them, at the request shape and the subtask wording that the
   firm-prompt arm found the pair failing on. The flag this tier already carries works; it works
   when it is the only flag there.
2. **The kwarg alone reproduces the failure exactly, and adding the budget to it changes
   nothing.** The two arms are identical on **20 of 20 matched seeds**, to the character, in both
   the reply and the trace. So on the shipped pair the budget is inert: whatever the kwarg has done
   to the request, the sampler the other flag sets never gets to act. The pair is not two levers
   pointing the same way. It is one lever and one flag that turns the other off.
3. **The fragments reproduce, and they are the template's own closing marker misspelled.** Three
   spellings, `</channe|>`, `t</chaannnel>` and `h</c>`, and the older build drew all three at the
   same three seeds the newer one drew two of. This template
   opens a thought with `<\|channel>thought` and closes it with `<channel|>`, which has no slash in
   it; every fragment recorded here and every one quoted in the firm-prompt and instruction addenda
   is that closing marker written with a slash in it, or a truncation of one. The text that follows
   is the answer, in plain prose, inside the channel, running to the cap.
4. **The build is not the cause.** The same interaction, the same fragments and the same absolute
   budget arm appear on `b10666-4e97ac86e`, and the template is byte identical between the two. The
   cheap approximation the entry proposed for the attribution half was a second build, and the
   second build says the phenomenon does not live there.
5. **The cap is not the cause either, and the reason is a position rather than a rate.** The
   fragment is at character zero of the trace and the cap fires at the end of the decode. A cap
   cutting mid marker would leave a fragment at the end of what it cut, not at the start of what it
   opened, and the arm that never wrote to the channel ran under the same 1024.

### What this attributes

The garbled marker is **the model's own attempt to close a thought it opened**, on a prompt that
was rendered without the token that opens one, and the flag that produces that prompt is
`--chat-template-kwargs '{"enable_thinking": false}'`.

The forced close is excluded, and the exclusion is structural rather than statistical. In the kwarg
alone arm there is no reasoning budget set anywhere, on the server or on the request, so no forced
close exists to leave debris; and that arm is byte identical to the shipped pair's. Whatever writes
the fragment is present where no sampler is running. That is the opposite of the explanation the
firm-prompt addendum ships, which read the fragment as a forced close emitted where no thought was
open and mangled on the way out.

What the reading leaves open is one step further down, and it is a claim about llama.cpp's parser
rather than about this repo: the answer reaches `reasoning_content` at all, which on this template
requires the channel to have been opened and never closed, so a misspelled close is the most
economical account of why the whole answer is classified as reasoning and the reply comes back
empty. Nothing here read the handler, and that step is inference from the marker's shape. It is the
one part of the entry's attribution half this addendum does not deliver, and it is smaller than the
part it does: no repair depends on it.

### Decision

1. **The firm-prompt addendum's mechanism section is superseded, and this addendum says so where
   that section stands.** It ships a labelled explanation and the label was honest; the explanation
   is now measured to be wrong in its main clause. The reading that replaces it is above.
2. **The claim "the budget is the flag that reaches that shape" gains its missing condition,
   wherever it is written.** It is true and it is true only of the budget on its own. Beside the
   kwarg, on both builds measured, it reaches nothing. The compose command block,
   [ADR-0010](ADR-0010-subagents.md) and [docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md)
   all now carry that condition.
3. **No flag change ships here.** The repair this attribution implies is to stop sending the kwarg
   on a tier whose template reads it this way, and that is a lineup and gate decision rather than a
   one line edit: `scripts/flagcheck.py` requires every subagent server this repo starts to carry
   both, the Qwen family's template is the reason the kwarg is there at all, and the E4B pick's
   measured injection robustness was taken with thinking off. Deciding it needs the roster in front
   of it and a gate that can express "this flag, on this family",
   [R-511](../refinements/tasks/511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md).
4. **No committed probe ships here either.** Every arm above was drawn by hand off `build_payload`,
   which is exactly the gap the entry's probe half named and exactly the gap the firm-prompt
   addendum left,
   [R-512](../refinements/tasks/512-no-committed-probe-splits-the-reasoning-off-pair.md).

### What this does not do, and where that is recorded

- **The arms are sized to a sitting.** The budget arm is 30 draws over two builds and is the only
  row here anybody should quote as a rate; the flagged and unflagged rows are 10 to 20 draws
  each and establish reproduction rather than a rate. Every draw is the summarization shape on the warehouse
  and clinic bodies, which are the two the firm-prompt arm's traces fell on, so the marker rate here
  is over the bodies that produce markers and is not comparable to that addendum's 13 in 76 over
  four.
- **One pick and one family.** gemma-4-E4B throughout. The lineup's own reading, that no Qwen entry
  writes to that channel at all, is untouched and unre-measured here, and it is the reason decision
  3 is a roster question.
- **The parser step is unread.** Above, and it is the residue of the entry's attribution half.

### Distrust green

No rule, gate or branch is added, so there is no mutation table and this section says instead what
the measurement's own controls were, and what each of them buys.

The **budget alone arm** is the control that turns this from a contrast into an attribution: without
it, the kwarg alone arm reproducing the failure would still have left "both flags together" as the
subject, and the sentence a reader needs is that one of the two works and the other stops it. The
**seed pairing** is what makes the identity claim in reading 2 mean anything: 17 pairs agreeing to
the character is not a rate that failed to separate, it is two configurations that the engine cannot
tell apart. The **second build** is what stops the whole reading being about an image that moved
under the repo between one sitting and the next, which it had: the tag `server-cuda` reports
`b10680-d7bd3bfca` today and reported `b10666-4e97ac86e` when the firm-prompt addendum measured on
it. And `/apply-template` **read on both builds** is what makes the rendering column evidence rather
than a reading of the template's Jinja by eye. What no control here reaches is the handler, which is
why the parser step above is labelled as inference and no decision rests on it.

## Third-spelling addendum (2026-08-30): an unmarked tail is two tiers, and the key says which

**Status:** Accepted. Closes
[docs/refinements/tasks/509-a-third-familys-closed-thought-reads-as-an-open-one.md](../refinements/tasks/509-a-third-familys-closed-thought-reads-as-an-open-one.md),
opened by the rendered-tail addendum above. Opens
[R-517](../refinements/tasks/517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md).
It changes one covered module, no shipped code and no pick.

### Re-derived first, and the entry is right about the reader and wrong about what it would take

The entry says `scripts/switchtail.py` knows two marker pairs and reads a tail carrying neither as
an open thought. Both halves hold on the file: `MARKERS` is the two pairs, and `closes` compares
`rfind` of the openers against `rfind` of the closers, so a tail with neither answers `-1 > -1`,
which is `False`, which the report prints as `leaves the thought OPEN`. A third family's closing
marker therefore predicts "does nothing", and the moment its constrained cell holds the module
refuses to publish and names the record rather than the vocabulary. That is the entry's case and it
is exactly as stated.

Where the entry is wrong is its own account of the cost. It says the state "cannot be read off the
tail alone and needs something more, most likely the unswitched tail as the comparison", and that
this needs "a real third-family template to be measured against before it is written". The second
sentence does not follow from the first, because **the comparison it names is already in the
reader's hands and already measured**. `_tails` reads both renderings' tails on every run, and the
suite already asserts the fact the rule turns on:
`tail(GEMMA_OPEN, ASK) == tail(GEMMA_SWITCHED, ASK)`. The failing pick's answer to the key is a
whole `<|think|>` system turn removed from the **front**, so its switched tail is byte identical to
its unswitched one. What separates the two unmarked tiers is therefore the failing pick's own tail
equality, which two runs on two builds have, rather than a third marker format, which nobody has. The rule can be drawn from the picks the lineup already holds; only the row it would fire on
is missing, and a rule does not need its own violation in hand to be written correctly.

### Decision

1. **An unmarked tail that the key changed is refused, not read.** `marked` answers whether a tail
   carries either member of either pair. When the switched tail carries none **and** differs from
   the tail the same template renders with the key left alone, `_tails` publishes nothing and exits
   1: the template answered with a marker format this reader does not recognize, and reading that as
   an open thought would be the guess the entry named. When the unmarked tail is the one the key left
   alone, it is still read as open, which is the failing pick's real answer and the line the refusal
   is drawn against.
2. **The comparison is on the two tails and never on the two renderings**, for the same reason the
   reading is on the tail at all: on the failing pick the renderings differ by a system turn at the
   front, so comparing them would refuse the one pick this module exists to read correctly. That is
   two of the mutations below, and they fail on the same three tests.
3. **What an operator sees** is both tails printed with their readings, the line saying whether the
   template read the key, and then one `refused:` line saying the switched tail carries no marker
   of either recognized pair and is not the one rendered with the key left alone. The cells are not printed,
   as they are not for a rendering carrying no ask: the refusal is about whether this reader may
   speak at all, so it comes before the report of what was drawn. The recovery is the same ten
   seconds it was, with the difference that the tail printed is now named as unreadable rather than
   published as a verdict about a tier.
4. **This is the fifth refusal in this family and it is the same one.** `envelopefloor.py` refuses
   a draw floor and a missing control arm, and this module already refused a rendering it cannot
   place, a cell too thin, a control that did not fire. A reader here publishes nothing rather than
   guessing when its input cannot support a verdict, and an unmarked tail the key moved is exactly
   that input.

### What this does not do, and where that is recorded

- **A third family whose template appends nothing either way still reads as open.** The
  discriminator is that the key changed the tail, so a third family that renders one identical tail
  both ways falls on the failing pick's side of the line. Its control arm would then not deliberate
  and the run refuses one step later for that instead, which is a red in the wrong words.
  [R-517](../refinements/tasks/517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md).
- **No third family has been measured**, and none is in the lineup. The rule is drawn from the two
  families that are, and its unknown side has never fired against a real server; the invented pair
  in the suite is a fixture and is labelled as one.
- **The vocabulary is still two pairs and still in this tree.** Nothing here moves a template token
  toward the port, and no capability probe ships.

### Distrust green

Mutations of `scripts/switchtail.py`, each reverted from a file copy, run against
**`scripts/tests/test_switchtail.py` and `scripts/tests/test_switchsamples.py` together, the
51-test suite that covers the module and its format half** (`cd scripts && uv run pytest
tests/test_switchtail.py tests/test_switchsamples.py`):

| mutation | result |
| --- | --- |
| the refusal removed, an unrecognized marker format read as an open thought again | 2 failed, 49 passed |
| the tail comparison dropped, every unmarked tail refused | 3 failed, 48 passed |
| the comparison made on the two renderings rather than the two tails | 3 failed, 48 passed |
| an opener no longer a word this reader carries, only the closers | 1 failed, 50 passed |
| none, restored | 51 passed |

The two rows sharing 3 failed are not a revert loop: both break the failing pick, so both fail the
same three gemma tests, the front-of-prompt trap, the tail read as open, and the open tail refused
beside a cell that held.

## Quiet-control addendum (2026-09-02): a control that did not fire is read off the unswitched tail

**Status:** Accepted. Closes
[docs/refinements/tasks/517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md](../refinements/tasks/517-a-third-family-that-appends-nothing-either-way-still-reads-as-open.md),
opened by the third-spelling addendum above. Opens
[R-524](../refinements/tasks/524-the-readers-thought-vocabulary-is-a-hand-list-held-to-nothing-the-model-files-say.md).
It changes one covered module and one assertion message in the integration-marked probe, no
shipped code and no pick.

### Re-derived first, and the entry is right about the case and short by one place

The entry says a template that renders one identical tail both ways and closes its thought with a
marker `scripts/switchtail.py` does not list is read as an open thought, and that the run then
refuses on the control arm in the wrong words. Both halves hold on the file. `_tails` passes an
unmarked switched tail that equals the unswitched one, `closes` answers `-1 > -1` on a tail with no
listed marker, the report prints `leaves the thought OPEN`, and the control that had no open
thought to fill fails its floor, at which point `_judged` printed "this prompt invites no thought
here and the switch stopped nothing".

Where the entry is short is the count of places. The probe asserts the same control before the
reader is ever run (`assert not quiet` in `test_thinking_switch_live.py`), in the same words, and
because the sample is written before that assertion, an operator meets the wrong sentence on the
red run first and then again on `just switch-tail`. And there is a wider case the entry did not
name, which the reader could see outright and did not say: a template that renders the thought
closed in a **listed** marker with the key left alone. There `closes` on the unswitched tail
answers true, the report prints `closes the thought` on the no-switch line, and the refusal one
line later still blamed the prompt. That is a verdict withheld, where the entry's case is a hint
missing, and the same change supplies both.

### What the mount says

Read 2026-09-02 by the agent off the GGUF headers at `/mnt/ai/Models`, a struct walk over each
file's key-value block for `tokenizer.chat_template`, with no server started. Every ADR-0004 chat
entry is on the mount, plus two Qwen3.8 entries that are not in the lineup; the five nomic
embedder files carry no template and are not counted.

| family | files | markers the template writes | switch keys it reads | tail with the key absent |
| --- | --- | --- | --- | --- |
| gemma-4: 12B, 31B, 26B-A4B, E2B, E4B | 5 | `<\|channel>thought`, `<channel\|>`, `<\|think\|>` | `enable_thinking`, `thinking` | no marker, thought open |
| Qwen3.5: 0.8B (two quants), 2B, 4B, 9B (two quants); Qwen3.6: 27B, 35B-A3B (two quants) | 9 | `<think>`, `</think>` | `enable_thinking` | `<think>\n`, thought open |
| Qwen3.8: 27B (two quants), Flash-Next, outside the lineup | 3 | `<think>`, `</think>` | `enable_thinking`, `reasoning_effort`, `thinking` | `<think>\n`, thought open |

Seventeen chat model files, two marker pairs, and every one of them leaves the thought open when
the key is absent; the Qwen templates append `<think>\n\n</think>\n\n` only when `enable_thinking`
is defined and false, the Qwen3.8 ones under the same branch with two more keys around it. So no
pick in the lineup, and no file the next pick would be drawn from, has this entry's shape, and the
first close the entry named, a third pair in `MARKERS`, has nothing to be drawn from. A marker
typed against no template would be the guess the entry's parent warned against.

### Decision

1. **The control refusal is worded off the unswitched tail.** `unfired` reads the tail rendered
   with the key left alone, which `_tails` already reads and prints on every run, and returns one
   of three sentences. A tail closed in a listed marker names the template: it renders the thought
   closed with the key left alone, so this run says nothing about the switch on this tier, which is
   a verdict. A tail open in a listed marker keeps the old sentence, the prompt invites no thought
   here, now earned, since the thought stood open and no draw used it. An unmarked tail names both
   readings the tail alone cannot separate, the prompt inviting no thought and a thought closed
   with a marker this reader does not list, because the failing pick's answer to the key is a
   system turn at the front and a third format's closing marker at the tail read the same from
   there.
2. **The unmarked side is a hint and is worded as one.** On the failing pick a control that does
   not fire now prints the third-format possibility beside the prompt reading, with the tail on
   the page above it, and a reader spends the same ten seconds and finds no closing marker there.
   Nothing is published either way; the refusal is about which sentence stands beside the exit.
3. **The probe's own assertion points at the reader.** The `assert not quiet` message no longer
   says the prompt invites no thought. It says the run measures nothing about the switch, names
   both readings, and prints the `just switch-tail` line for the sample it has already written,
   which is where the vocabulary lives and stays (decision 3 of the rendered-tail addendum). The
   message was not raised against a server; pyright holds its one name, `written`, to the binding
   above the loop that raises it, and no gate runs the file.
4. **`_tails` returns the two tails rather than a verdict**, and `read` derives `closes` on the
   switched one and hands the unswitched one to `_judged`. That is the whole structural change,
   and it is what lets the refusal read a tail without rendering the prompt a second time.
5. **No third pair is added, and no server was started.** The mount answers the lineup question
   without a rendering, and the rendering column stands on `/apply-template` as before; nothing
   here moves a row of it.

### What this does not do, and where that is recorded

- **The vocabulary is still two pairs typed by hand, held to nothing.** The templates that write
  them are readable off the model files without a server, which is how the table above was taken,
  so `MARKERS` could be a recorded answer re-derived by a hand-run recipe, the shape
  `imagevolumes.py` takes.
  [R-524](../refinements/tasks/524-the-readers-thought-vocabulary-is-a-hand-list-held-to-nothing-the-model-files-say.md).
- **A third format rendered identically both ways whose control fires anyway is still read as
  open** and refused as a broken prediction in the record's words, the control refusal never being
  reached. That needs the model to open a thought of its own after the prompt closed one, and it
  needs the pair; it is named in R-524 as the second residue the pair would close.
- **Nine rows of the rendering column are still hand readings**, untouched by this addendum.
  [R-510](../refinements/tasks/510-nine-rows-of-the-rendering-column-are-hand-read.md).

### Distrust green

Mutations of `scripts/switchtail.py`, each restored from a saved copy, run against
**`scripts/tests/test_switchtail.py` and `scripts/tests/test_switchsamples.py` together, the
54-test suite that covers the module and its format half** (`cd scripts && uv run pytest
tests/test_switchtail.py tests/test_switchsamples.py`):

| mutation | result |
| --- | --- |
| the unmarked reading dropped, an unmarked tail worded as a marked one | 2 failed, 52 passed |
| the closed reading dropped, a tail the template closed worded as the prompt's doing | 1 failed, 53 passed |
| the two marked readings swapped | 2 failed, 52 passed |
| the switched tail handed to the refusal in place of the unswitched one | 1 failed, 53 passed |
| the refusal reverted to one fixed sentence for every tail | 3 failed, 51 passed |
| none, restored | 54 passed |

The fourth row is the one that needed a test of its own. Every new case renders the same tail both
ways, so a refusal reading the switched tail would have passed all of them; what catches it is the
existing control test, whose unswitched tail opens the thought and whose switched tail closes it,
and which now asserts which of the two the refusal was worded off.
