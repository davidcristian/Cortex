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

A stall ceiling cannot see a model that keeps talking. A subagent in a repetition loop streams
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
reddens it in ten seconds. Five mutations were run and each reddened a named test: `read=None`
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
   for a lie.
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
  run **reddens** rather than hanging the suite.

Seven mutations, each applied to production code alone with the whole `packages` suite re-run, so
the counts are measured rather than aimed at: dropping the `asyncio.timeout` wrapper reddens **9**,
every deadline case plus the real-socket one, each at its outer bound; treating every
`TimeoutError` as the deadline reddens **1**, the case that would otherwise have crashed formatting
a bound an unbounded attempt does not have; reporting a stopped run as `INFERENCE` rather than
`TRUNCATED` reddens **1**, the re-place case; letting the envelope check win over the deadline
reddens **2**, the mid-envelope case and the real-socket one, whose shipped wiring is that same
constrained niche; dropping `bounds` from the loop's `backend.stream` call reddens **1**; relaxing
the config's ordering rule from strict to non-strict reddens **1**; and dropping
`bounds=config.attempt_bounds` at the builder reddens **1**, the real-socket case, which is the
whole chain proving it is a chain.

One mutation reddened **nothing**, and it is reported rather than quietly kept: removing the
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
argument the decode cadence is absorbed under. A turn that wants to say "this was cut" wants a
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

| mutation | reddens |
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

**Reordering the adapter's yields does not redden the contract's ordering check**, and the cadence
contract records the same finding about itself for the same reason: the transcript's final chunk
carries `finish_reason` on a content-less delta, so text and stop stay in order across chunks
however the adapter orders them within one. What catches the reorder is the adapter's own case for
a chunk carrying both, which is why that case lives beside the adapter rather than in the contract.

**A missing reason reported as `FINISHED` reddens 29, and only one of them is a stop check.** Every
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

| mutation | reddens |
| --- | --- |
| `cap_note` yields nothing when capped | **2**, the cortex note and the deep one |
| `cap_note` yields the note on every turn | **70** |
| the note is yielded but not appended to `parts` | **2**, the two that read the store back |
| `TurnEngine` passes no `StopLedger` | **1**, the cortex note |
| `BrainPhase` emits the note even when the phase failed | **1**, the two-notes case |
| `ReplyBoundsConfig.bounds` returns bounds when nothing is set | **1**, the default case |

Two readings say something the counts alone do not.

**The note-on-every-turn mutation reddens 70**, which is the measure of how ordinary the silent
path is. Nearly every turn in the suite ends with no stop reported at all, so a ledger that
answered "capped" for silence would rewrite the ending of the whole corpus, the shape the
finish-reason addendum's own 29 had one level down.

**The bounds mutation reddens only its own unit test.** Nothing asserts on what the composition
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
   field the adapter drops would be a knob that lies.
2. **`GenerationBounds` does not grow.** The port already says whether a request wants
   deliberation; the tier now says how long a wanted one may be. Two orthogonal facts at the two
   layers that can express them, and the core stays a pure function over what it was given.
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

| mutation | reddens |
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

| mutation | reddens |
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

| mutation | reddens |
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
