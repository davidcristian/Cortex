# ADR-0001: Founding architecture

- **Status:** Accepted (Phase 0 reviewed and approved by the user, 2026-06-28;
  decision 4 later superseded by ADR-0005)
- **Date:** 2026-06-28

## Context

Cortex is a personal, local-first assistant (all inference and data on-machine; only
tools reach external services) maintained long-term by agents with small
context windows. Three model tiers (resident ~9-12B cortex, 2-4B subagents, on-demand
~31B brain) share a single 24 GB GPU, so models are loaded and unloaded at any time. The
overlay/hotkey/OS-control surface needs host OS access that does not cross the
WSL2/container boundary cleanly on Windows, while the inference/orchestration ecosystem
(vLLM) is Python-first. Development happens in WSL; Docker and the app run on Windows; a
later move to macOS or Linux is plausible.

## Decision

1. **External state as the swap-safety mechanism (the hard rule).** All conversation,
   task, and working state lives in external stores and never in a model-server process or
   KV cache. Every model instance is stateless and disposable; a handoff is
   serialize → swap → rehydrate → run → persist → swap back. All first interfaces are
   designed around this; a `ModelManager` service owns the GPU and exposes a queue, and
   the `SessionStore` is the single source of truth for context.
2. **Hexagonal (ports & adapters) on both sides of the language boundary.** A pure,
   I/O-free core holds domain types and application logic and depends only on ports
   (Python `Protocol`s) / traits (Rust). Adapters are thin translators and the only place
   external systems are touched. Ports are defined, contract-tested, and faked before any
   real adapter exists.
3. **Polyglot body/brain split with a gRPC seam; explicitly no FFI.** The brain
   (inference, orchestration, memory, MCP tool servers) is Python 3.12+/`uv`,
   dockerized. The body + overlay UI is one host-native Rust (stable)/Tauri process with OS
   trait backends plus a transport client, no business logic. The language boundary is
   exactly the process boundary and stays a **network boundary**: a shared
   [proto/body.proto](../../proto/body.proto) (tonic ⇄ generated Python stub) is the
   single source of truth for everything on the wire. **No PyO3 / in-process FFI**, because
   it would fuse deployment lifecycles, break the container/host split, and let types
   drift out from under one of the two toolchains.
4. **vLLM behind `InferenceBackend`.** All Blackwell/WSL2-specific configuration
   (SM120/FP8, FlashInfer, `--enforce-eager` workarounds) lives in the vLLM adapter and
   its runbook, never in the core. A future MLX/llama.cpp backend is a new adapter.
   *Superseded (2026-06-29):* [ADR-0005](ADR-0005-llamacpp-engine.md) replaced vLLM
   with llama.cpp once the model lineup was locked to GGUF artifacts (ADR-0004). The
   port-based design meant this was an adapter decision, exactly as intended.
5. **Stores: Redis + Postgres/pgvector.** Redis for hot session/task state and the event
   bus (what survives swaps); Postgres + pgvector for durable data and vector memory, with
   both behind `SessionStore`/`MemoryStore` repository ports. Embeddings come from a
   local model behind an `Embedder` port.
6. **Toolchains and gates.** Python 3.12+/`uv` (ruff, `pyright` strict, which was chosen over
   `mypy --strict` for speed and stronger `Protocol` inference, pytest at 100%
   line+branch) and Rust stable/Cargo (fmt, clippy `-D warnings`, cargo-llvm-cov at
   100%), a 300-line cap on all non-test `.py`/`.rs` files (widened to `.ts`/`.tsx` on
   2026-08-03 with the overlay's, see open question 6), doc-first DoD, and a single
   dual-toolchain `just check` mirrored by pre-commit and GPU-less CI
   (see [AGENTS.md](../../AGENTS.md)).
7. **Generated code is exempt from the line cap and coverage.** Protobuf/tonic stubs
   live in clearly marked generated-only directories, excluded by the line-cap scan and
   coverage config. Hand-written wrappers around them are normal code and fully gated.
8. **Orchestration stays explicit.** Routing/handoff is typed code in the core, tested
   with fakes. No framework that hides control flow; if a helper library (Pydantic AI /
   LangGraph) is ever adopted it sits behind an interface. It gets its own ADR.

## Consequences

- Any model can be evicted mid-task and the system resumes from the store; the cost is
  that every workflow must be expressed as explicit serialize/rehydrate steps and tested
  that way (chaos tests kill models mid-task).
- The pure core makes 100% line+branch coverage achievable; GPU/OS/network specifics are
  quarantined in adapters with contract tests against fakes plus an `integration`-marked
  live suite excluded from coverage and CI.
- Two toolchains cost setup effort once (Slice 1) but keep each language where it is
  strongest; the proto file prevents contract drift between them.
- Portability later = writing new adapters (OS crates, inference backend), not rewrites.

## Open questions (deferred, each will get its own ADR when resolved)

1. **Letta vs. a lean custom memory layer over pgvector** gets decided when the memory
   slice lands; hidden behind `MemoryStore` either way.
2. **Whether body capabilities (volume/screen/input) also surface as MCP tools to the
   models**, or remain internal tools dispatched via the core's `ToolRegistry` over the
   `BodyGateway`. Initial working assumption: internal tools only, revisit with real use.
3. **Brain→body connectivity direction**: default assumption is the brain dials the
   body's gRPC server via `host.docker.internal`; fallback if Windows
   firewall/portability makes that brittle is tunneling body-directed calls over a
   body-initiated bidirectional stream.
4. **Concrete model choices** (cortex, subagent, brain, embedder) and their VRAM fit have
   candidate sets locked in [ADR-0004](ADR-0004-model-lineup.md) (all GGUF); the engine
   question this raised is resolved (llama.cpp, [ADR-0005](ADR-0005-llamacpp-engine.md));
   final per-tier picks decided in the real-inference slice with measurements.
5. **Default global hotkey** (`Win+Space` is taken on Windows) is configurable from day
   one; `Ctrl+Alt+Space` proposed in the roadmap's assumptions list, confirmed at the
   first body slice.
6. **Webview frontend gating** means the overlay's TS/HTML is kept minimal; lint/format
   gated, but the 100%-coverage and 300-line gates initially apply only to `.py`/`.rs`.
   Revisit if the frontend grows real logic. *Closed, in two halves, because the frontend
   did grow real logic:* coverage on 2026-07-01 and the line cap on 2026-08-03, both in
   [ADR-0011](ADR-0011-body-v1.md) addenda. The overlay's `.ts`/`.tsx` now carries 100%
   line+branch coverage and the 300-line cap; its stylesheet and markup stay outside the
   cap, argued in the second of those addenda.

## Addendum (2026-08-10): decision 2's contract-test half, read against the whole tree

Decision 2 says ports are "defined, contract-tested, and faked before any real adapter
exists", and AGENTS.md states it as a checkable requirement: *the real adapter must pass the
same contract test as the fake.* On 2026-08-09 that requirement was found half-met for
`MemoryStore`. A shared file, `memory_contract.py`, held the checks and a tuple naming them, and
only the integration-marked pgvector run read the tuple. The fake was checked by a separate
hand-written suite in `cortex_core`. The shared file looked like the guarantee without being one:
a check appended to it reached CI only if somebody also wrote it a second time, and the omission
produced a test that never runs rather than a test that fails, so nothing reported it. That was
fixed by adding a fake-driven test parametrized over the same tuple.

This addendum records the sweep that looked for other ports in the same state. The method was
mechanical, and is written down here so the next sweep does not re-derive it: enumerate every port
in both languages, find its shared check list if it has one, find every driver of that list, and
determine which drivers CI runs. A list read by one driver and restated by another can drift
apart, which is the defect. A list read by every driver cannot, and a port with a single driver
parametrized over its implementations has no second copy to drift.

### The Python ports

Every row's shared checks live in a `*_contract.py` beside the tests, and CI means `just
check`, which runs `pytest -m "not integration"`. "Live" names an integration-marked arm that
needs a real server and runs on the host.

| Port | Fake | Real adapter | Shared checks | CI: fake | CI: adapter | Live arm |
| --- | --- | --- | --- | --- | --- | --- |
| `SessionStore` | `InMemorySessionStore` | `RedisSessionStore` | `session/tests/contract.py` | yes | yes, over fakeredis | yes |
| `TaskStore` | `InMemoryTaskStore` | `RedisTaskStore` | `session/tests/task_contract.py` | yes | yes, over fakeredis | no |
| `ScheduleStore` | `InMemoryScheduleStore` | `RedisScheduleStore` | `session/tests/schedule_contract.py` | yes | yes, over fakeredis | yes |
| `HandoffStore` | `InMemoryHandoffStore` | `RedisHandoffStore` | `session/tests/handoff_contract.py` | yes | yes, over fakeredis | yes |
| `PreferenceStore` | `InMemoryPreferenceStore` | `RedisPreferenceStore` | `session/tests/preference_contract.py` | yes | yes, over fakeredis | no |
| `MemoryStore` | `InMemoryMemoryStore` | `PgVectorMemoryStore` | `memory/tests/memory_contract.py` | yes | no, needs a server | yes |
| `ModelHost` | `ScriptedModelHost` | `HttpModelHost` | `model_manager/tests/model_host_contract.py` | yes | yes, over a real supervisor on ASGI | yes, restated |
| `VisionProbe` | `ScriptedVisionProbe` | `PropsVisionProbe` | `orchestrator/tests/vision_probe_contract.py` | yes | yes, over `MockTransport` | yes, restated |
| `InferenceBackend` | `ScriptedInferenceBackend` | `LlamaCppBackend` | `inference/tests/cadence_contract.py`, `stop_contract.py`, `stream_contract.py` | yes | yes, over `MockTransport` | yes, restated |
| `Embedder` | `HashEmbedder` | `LlamaCppEmbedder` | `embedding/tests/embedder_contract.py` | yes | yes, over `MockTransport` | yes, restated |
| `ToolRegistry` | `InMemoryToolRegistry` | `McpToolRegistry`, and the `ReconnectingMcpToolRegistry` over it | `tools/tests/registry_contract.py` | yes | yes, both, over a serving `McpSession` | yes |
| `BodyGateway` | `InMemoryBodyGateway` | `GrpcBodyGateway` | `body_client/tests/gateway_contract.py` | yes | yes, over a real loopback `BodyService` | yes |
| `Confirmer` | `RecordingConfirmer` | `SeamConfirmer` | `orchestrator/tests/confirmer_contract.py` | yes | yes, over a scripted overlay | no |
| `ToolAuditSink` | `RecordingAuditSink` | `LoggingAuditSink` | none, and by design | n/a | n/a | no |
| `RecallAuditSink` | `RecordingRecallSink` | `LoggingRecallSink` | none, and by design | n/a | n/a | no |
| `ProgressSink` | `RecordingProgressSink` | `SeamProgressSink` | none, and by design | n/a | n/a | no |
| `Clock` | fixed clocks in tests | `SystemClock`, shipped from core | none, and by design | n/a | n/a | no |
| `Sleeper` | `RecordingSleeper` | `AsyncioSleeper`, shipped from core | none, and by design | n/a | n/a | no |
| `ZoneResolver` | `UTC_ONLY_RESOLVER` | `ZoneInfoResolver` | none, and by design | n/a | n/a | no |
| `ModelManager` | `SingleResidentModelManager` | `SwappingModelManager` | none, both pure core | n/a | n/a | yes |
| `SubagentScheduler` | `AdmitAllScheduler` | `ResourceBudgetScheduler` | `core/tests/test_scheduler_drain.py`, one driver | yes | yes, both pure core | no |
| `SubagentPlacer`, `ResidencyController`, `ResidencyReporter`, `TurnRunner` | core doubles | core implementations | none, all pure core | n/a | n/a | no |

The two CI columns are about the *shared* list, so a row with no shared checks reads `n/a` in
both. It does not mean the port is untested: every one of those has CI tests for its fake and
CI tests for its adapter, written separately and asserting whatever each author thought to
assert, which is precisely the condition a shared list exists to end.

Nine ports carried a shared check list on the day of this sweep, one `*_contract.py` each. All
nine listed every check the file defines, so no check had been written into a shared file and then
left off its own tuple, which was the other way this could have gone wrong. Eight of the nine
already had a CI-visible driver that reads the tuple rather than restating it. The table itself is
kept current as rows move, and each addendum below says which moved and when, so the count in this
paragraph is the sweep's measurement rather than today's.

### The Rust ports and the overlay

| Port | Fake | Real adapter | Shared checks | CI: fake | CI: adapter |
| --- | --- | --- | --- | --- | --- |
| `Hotkey` | `FakeHotkey` | `WindowsHotkey`, plus Linux/macOS `unimplemented!()` stubs | none | yes | no, `cfg(windows)` |
| `AudioControl` | `FakeAudio`, written twice | `WindowsAudioControl` | none | yes, both fakes | no, `cfg(windows)` |
| `Notify` | `FakeNotify`, written twice | `WindowsNotify` | none | yes, both fakes | no, `cfg(windows)` |
| `ScreenCapture` | `FakeScreen`, written twice | `WindowsScreenCapture`, and `DeniedScreenCapture` in core | none | yes, both fakes | the denying one yes, the Windows one no |
| `BrainTransport` | `FakeTransport`, `ScriptedTransport`, `FlakyTransport` | `BrainSeamClient`, and `RetryingTransport` over it | none | yes | yes, over a loopback fake `BrainService` |
| `Sleeper` | `FakeSleeper` | `TokioSleeper` | none | yes | no, `body/app` is outside the gated workspace |
| `Randomness` | `FakeRandomness` | `FullDelay`, `ShellRandomness` | none | yes | `FullDelay` only incidentally, `ShellRandomness` never |
| `BrainBridge` (overlay) | `FakeBridge` | `TauriBridge`, `DemoBridge` | `app/src/bridge/bridgeContract.ts` | yes | `DemoBridge` yes, `TauriBridge` no, it crosses Tauri IPC |

No shared list has drifted on the Rust side, because none exists. There is no `macro_rules!`
anywhere under `body/crates`, no contract module in that workspace, and no generic function
carrying assertions. `BrainTransport` is the strongest row regardless, its real adapter driven end
to end in CI against an in-process fake `BrainService` on loopback, and it is also the row where a
shared list would pay most, since three independent hand-written suites currently describe the
same eleven-method trait.

### What the sweep found, and what it fixed

**One port had the memory defect, and it was `SessionStore`, the port the hard rule is written
about.** `session/tests/contract.py` exports fourteen checks and a tuple naming them, and the
tuple's only reader was `test_store_live.py`, the integration-marked live-Redis run. The
CI-visible driver, `test_store_contract.py`, restated all fourteen as hand-written wrappers.
The two lists happened to agree at the moment they were read, fourteen against fourteen, which
only showed that nobody had yet forgotten to copy a check across; it said nothing about the next
edit. Fixed the way the memory one was, by parametrizing over `contract.ALL_CHECKS` across the
existing two-implementation fixture, which is the arrangement the other four stores in that
directory already used.

**Proven able to fail, which is the only evidence that the fix is real.** A fifteenth check
that raises unconditionally was appended to `contract.py` and to `ALL_CHECKS`, and the
CI-visible driver was run twice over it, once as it now stands and once as it stood before.
Parametrized, it makes two tests fail, one per implementation, the ids being
`check_a_check_nobody_hand_wrote_a_wrapper_for` under each of the fixture's `in-memory` and
`redis` arms, alongside 66 passing. Restated, the same poisoned shared file gives `66 passed`,
green, with the failing check never executed at all. That is the defect measured rather than
asserted, and it is the same shape the memory fix demonstrated. Both files were restored
afterwards and the whole `packages/session` suite is green at 268 passed.

**No other Python port drifts, and the reason is structural rather than lucky.** The other
eight shared lists are read by `pytest.mark.parametrize` in their CI driver, so a check
appended to any of them reaches CI on the next run with nobody's memory involved. Three ports
(`ModelHost`, `VisionProbe`, `InferenceBackend`) have live arms that restate rather than
iterate their tuple, which is worth knowing but is not this defect: those arms are
integration-marked, so they gate nothing in CI either way, and what the sweep asks is whether
CI runs the shared list, not whether the host does.

### The ports whose fake and adapter cannot share checks, and why

Recording these so the next sweep does not re-derive them.

- **The write-only sinks: `ToolAuditSink`, `RecallAuditSink`, `ProgressSink`.** Each method
  takes a record and returns `None`, so the port exposes nothing to read back. The fake
  appends to a list and the real adapter emits a structured log line, and no assertion can
  hold both to one observable without reaching around the port into a list on one side and a
  caplog on the other. The only check the port itself admits is that `record` does not raise,
  which is the vacuous coverage-chasing test gate 2 bans. What each side owes is checked where
  it lives: the fakes by the core suites that read their lists, the sinks by their own tests
  that read the emitted line.
- **`Clock` and `Sleeper`.** The real implementations *are* the wall clock and the event loop.
  Any shared check is either vacuous or a timing assertion, and a timing assertion in CI is
  the flake this repo has spent effort removing elsewhere.
- **`ZoneResolver`.** Its two implementations are deliberately not interchangeable. The core's
  default resolves UTC and nothing else, on purpose, because the pure core must resolve no key
  it cannot resolve without the tz database; `ZoneInfoResolver` resolves the whole database. A
  shared contract asserting they answer alike would assert the opposite of the design.
- **`MemoryStore`'s adapter arm.** `PgVectorMemoryStore` needs a Postgres with the extension
  installed, which CI does not have, so only the fake's arm of `memory_contract.ALL_CHECKS`
  runs there and the adapter's arm stays in the live run. That is gate 3 working, not a gap:
  the shared file is still the single list, and both arms read it.
- **The pure-core ports** (`ModelManager`, `SubagentPlacer`, `ResidencyController`,
  `ResidencyReporter`, `TurnRunner`). Every implementation is in the core, so there is no
  fake-versus-adapter parity question to answer. `SubagentScheduler` is in this group and has
  a shared suite anyway, `test_scheduler_drain.py`, parametrized over both implementations
  from one driver, which is a shape that cannot drift because there is only one driver.

### The ports with no contract suite at all

Four Python ports have a fake and a real adapter that a shared list *could* hold, and do not
have one: `Embedder`, `ToolRegistry`, `BodyGateway`, and `Confirmer`. `InferenceBackend` is a
fifth in part, having a shared list for the decode-cadence arm and nothing shared for the rest
of the streaming contract. Each of the five has a CI-runnable real adapter already: the
embedder and the tool registry over `MockTransport` and a fake MCP session, the gateway over a
real loopback `BodyService`, the confirmer over the seam's own fake. So the obstacle is not
hardware, and the argument that they need one is the same argument the sweep just measured on
`SessionStore`, one step earlier: the core is written against the fake and shipped against the
adapter, and nothing today holds the two to one description. All five have closed since, the four
on 2026-08-11 and `InferenceBackend`'s streaming half on 2026-08-16, each in an addendum below and
each moved in the table above; what the paragraph records is the sweep's own measurement.

Across the Rust rows the defect is one step worse than a restated list, being a restated fake:
`FakeAudio`, `FakeNotify`, `FakeScreen` and `FakeBrain` are each hand-written twice, once under
`body/crates/core/tests/` and again under `body/crates/rpc/tests/`, with independent
expectations. The generic helpers that look like shared drivers (`register_via`, `get_via`,
`show_via`, `capture_via`, `probe`) carry no assertions; they prove the trait is usable as a
bound and nothing more. The four Windows adapters cannot run in CI, which is gate 3 and not a
defect, but a shared list would still be the only artifact holding them to the description
their fakes are held to, and it would run the day the host runs the suite. The overlay's
`BrainBridge` is the sharpest single case, its 100% coverage threshold met while two of its
three implementations are named in `vite.config.ts`'s coverage `exclude`, so the gate reported
green over code it was never pointed at. That row is the one closed since, on 2026-08-11,
by the addendum below; the Python and Rust rows are as the sweep left them, and its overlay row
above has been updated to what the tree now holds.

Building those suites is a slice, not a sweep, so it is deferred and recorded in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates) rather than attempted here. The
tables above are that slice's worklist. It is being taken one port per commit from 2026-08-11,
each port with its own section in the last addendum below; the rows move in the tables as they
land, so a row reading `none` is genuinely still open.

## Addendum (2026-08-11): the overlay's `BrainBridge` gets the first shared list outside Python

`body/app/src/bridge/bridgeContract.ts` holds thirteen named checks and the `BridgeCase` a check
runs against; `bridgeContract.test.ts` is the driver, building a fresh case per check and running
the list over `FakeBridge` and `DemoBridge`. It is deliberately the same arrangement the Python
lists share rather than a tenth invention: a flat list of named functions and one parametrized
driver, `describe.each` over the implementations and `it.each` over the list standing in for the
fixture parameters and `pytest.mark.parametrize` of `test_task_store_contract.py`, with each
check's own name carrying into the test id the way a check function's `__name__` does there.
`demoBridge.ts` and `demoScript.ts` came out of `vite.config.ts`'s coverage `exclude` with it, so
the overlay's 100% threshold now measures both implementations the overlay can run, and the
exclude list holds only `main.tsx` and `tauriBridge.ts`, each with the reason written beside it.

**The sweep's open design question is answered rather than deferred.** It asked whether the
overlay's fake and its Tauri bridge can share a driver at all when one answers from a record and
the other crosses an IPC boundary. They cannot, and the boundary falls elsewhere than the question
assumed. `TauriBridge` is out because every one of its methods is an `invoke` call, so holding it
to these checks would mean faking `invoke` and measuring the fake. What the list does hold is both
implementations CI can run, at the level where they genuinely agree: the turn HANDLE rather
than the stream, since the demo plays a recorded conversation on a timer while the fake streams
nothing until its test says so; the pinned grouping rather than the whole listing order, since the
demo sorts a catalog it holds and the fake serves the table it was assigned; the ack's boolean
rather than what an ack does to the due list; and the disappearance of a cleared title rather than
what it falls back to. Each divergence is written down in
[docs/modules/body-app.md](../modules/body-app.md), and the demo's own cadence, its recorded
conversation and the four prompts that trip a hook, is pinned by `demoBridge.test.ts` beside it.

**It found three disagreements on its first run, before any implementation was changed to suit
it,** which is the return the sweep predicted for a list nobody had written yet. `FakeBridge`
ignored its `listSessions` limit, so a test could pass against a listing production would have
cut. `FakeBridge.setPreference` recorded a write the served record never carried, alone among its
writes in that: the three catalog writes beside it had always reflected theirs, which is exactly
the drift a per-implementation suite cannot see. And `DemoBridge` read `limit === 0` as "at most
none" where the port documents it as the brain's own default, so browser dev answered an empty
switcher to a caller asking for the default listing. All three are fixed against the port's own
description in `types.ts`, which is the arbiter when a check finds the two disagreeing. A fourth
came from the turn-handle check rather than from the two arms disagreeing: `DemoBridge` announced
a capture activity inside the `converse` call, a delivery the real bridge cannot make, its events
arriving over a Tauri channel after the call has handed back the cancellation its caller stores.
That request is now issued on a short timer, which is also how it behaves when driven by hand.

**Proven able to fail, three times, once per kind of claim it makes.** With `DemoBridge`'s
`deleteSession` put back to the no-op it once was, `checkADeletedChatStaysGone` fails on the
`DemoBridge` arm alone (25 passed, 1 failed). With the turn's cancellation no longer clearing its
timers, `checkACancelledTurnGoesSilent` fails the same way, the recorder holding 87 events where
the check requires none. With the completion moved ahead of the reply's words,
`demoBridge.test.ts`'s ordering claim fails while all 26 shared checks stay green, which is the
division of labour working: the shared list holds the port, the demo's suite holds the script.
Each break was restored and the tree is green.

What stays open is everything else the sweep measured: the four Python ports with no shared list
(`Embedder`, `ToolRegistry`, `BodyGateway`, `Confirmer`), `InferenceBackend`'s unshared streaming
half, and every Rust row, where the fakes themselves are still written twice.

## Addendum (2026-08-11): the Python ports with a fake, an adapter and no shared list

The sweep's Python worklist, taken one port per commit in the order the table lists them. Each
section below records what the list holds, where the two implementations legitimately diverge and
so what level of abstraction the checks sit at, what the list found on its first run, and the break that
proved it able to fail. `InferenceBackend` is deliberately not in this addendum: its decode
cadence is already shared and the rest of its streaming contract is a design question of its own
(what a list can say about an event stream two implementations produce at different rates), so it
stayed open here and got its own addendum on 2026-08-16, once that question had an answer.

### `Embedder`

`brain/packages/embedding/tests/embedder_contract.py` holds four checks and the
`EmbedderUnderTest` a check runs against; `test_embedder_contract.py` builds one per check and
runs the list over `HashEmbedder` and over `LlamaCppEmbedder` on an `httpx.MockTransport` whose
stand-in server answers the digest bytes of the text it was given. The four are that an embedding
is a non-empty sequence of real floats, that every text embeds at one width, that one text always
embeds to one vector with an unrelated embedding in between changing nothing, and that a backend
which cannot answer raises `EmbedderError`.

**Where the two legitimately diverge, and so what the checks do not say.** The fake answers a
`tuple` and the adapter a `list`; both are the `Sequence[float]` the port names, so no check reads
the concrete type. The widths differ too, 16 against whatever the deployment's model emits, which
is the port's own sentence about the core never assuming a value, so the width check compares an
implementation's own answers with each other and never with a number. And the stand-in server
sends its vector as JSON **integers**, which a real server is free to do since JSON has one number
type: that is what makes the float check a statement about the adapter's coercion rather than
about the transport.

**What it found: the fake could not fail.** `HashEmbedder` had no way to raise the one error the
port documents, so nothing in the core could exercise a remember or a recall against a dead
embedding server, and the fake could not stand in for the adapter on the only path where the two
have anything to disagree about. It gained `fail_with(EmbedderError(...))`, the same scripted
failure `InMemoryBodyGateway` has carried since it was written. No behavioural disagreement was
found between the two on the paths both could already walk, which is the expected outcome for a
port one method wide, and it is recorded here rather than left unstated.

**Proven able to fail, once per arm.** Dropping the adapter's `float(value)` coercion makes
`text_embeds_to_a_vector_of_real_numbers[llamacpp]` fail on its own (1 failed, 7 passed); making
the fake's width depend on the text's parity makes `every_text_embeds_at_one_width[hash]` fail on
its own; letting the adapter's `httpx.HTTPError` escape instead of wrapping it makes
`a_backend_that_cannot_answer_raises_embedder_error[llamacpp]` fail; and making the new
`fail_with` a no-op makes the same check fail on the `hash` arm, which shows that the knob is
exercised rather than decorative. Each break was restored.

### `ToolRegistry`

`brain/packages/tools/tests/registry_contract.py` holds six checks, the `ServedTool` a fixture
publishes and the `RegistryUnderTest` a check runs against; `test_registry_contract.py` runs the
list over three implementations, the core's `InMemoryToolRegistry` and both MCP ones, the
translating `McpToolRegistry` and the `ReconnectingMcpToolRegistry` production wires, the last two
over a serving `McpSession` that answers real `mcp` result types. The six are that every served
tool is advertised with its name, purpose and schema in order; that the listing is read again on
every walk; that a call comes back stamped with its own id and the tool's text; that a tool which
ran and failed is an `is_error` result rather than an exception; that a name the registry does not
serve never comes back as a success; and that an unreachable backend raises `ToolError` from both
verbs.

**Where the two kinds legitimately diverge, and what the port now says about it.** They diverge on
an unknown tool name, and the sweep's assumption that the port already settled that case was wrong.
The port's parenthetical promised `ToolNotFoundError`, which only a registry holding its whole set
can deliver: `McpToolRegistry` asks a server, and an MCP server answers an unknown tool with an error
*result*, so the adapter has never raised there and cannot without either sniffing an error string
or paying a listing round trip per call. Neither implementation is wrong, so the fix went into the
description: the port now states the safety half both owe, that a name an implementation does not
serve never comes back as a success, and names the divergence and its downstream consequence, the
dispatcher stamping its own `ToolError` sentence `TRUSTED` while a relayed error result stays
`UNTRUSTED`, which is the correct reading of each. A caller needing the distinction resolves
ownership by a live walk first, which is what `AggregateToolRegistry` already does.

**What it found: the fake could produce neither the port's central case nor a changing tool set.**
`InMemoryToolRegistry`'s handlers returned result text, so the fake could never produce a result
with `is_error` set, which is the case the port draws its whole `is_error`/raise distinction
around; every core test of a failing tool went through a handler *raising*, which is the other
branch, and the dispatcher labels the two differently. The handler's answer is now text or a whole
`ToolResult`, with the call's own id stamped on either. The fake also copied its tool set at
construction, so no test could change the set the port re-reads on every walk (it gained `serve`), and
it had no way to be unreachable, so nothing held it to the `ToolError` that
`SkipUnavailableToolRegistry` is built on (it gained `fail_with`, the same knob `HashEmbedder`
took the day before).

**Proven able to fail, four times, and the failing arms are the ones that can carry each
defect.** With the adapter reading `isError` as always false, the failed-tool check and the
unknown-name check both fail on the `mcp` and `reconnecting` arms while the fake stays green, 4
failed against 15 passed. That is what the unknown-name check is for: without it, a relayed
"Unknown tool" would reach the model as a success. With the adapter dropping the call's arguments,
the id-and-text check and the failed-tool check fail on the same two arms. With the fake answering
an empty listing instead of raising when it is unreachable, which is the silent degradation
`SkipUnavailableToolRegistry` exists to prevent, the backend check fails on the `in-memory` arm
alone. And with a listing cache added to `McpToolRegistry`, the re-read check fails on the `mcp`
arm **only**, not on `reconnecting`, because that wrapper builds a fresh inner registry per call
and is structurally immune to the defect. That last case is why both MCP arms are in the list
rather than one: they implement this obligation differently. Each break was restored.

### `BodyGateway`

`brain/packages/body_client/tests/gateway_contract.py` holds ten checks, the fixed capture every
fixture's body answers and the `GatewayUnderTest` a check runs against;
`test_gateway_contract.py` runs the list over `InMemoryBodyGateway` and over `GrpcBodyGateway`
talking to a `BodyService` served on loopback, so nothing on the adapter's side of the port is
stubbed: real protobuf, a real HTTP/2 connection, the generated stub. The ten are the volume read,
the write that touches only the field it was given, the write that reports the state after it, the
clamp, the notification that reaches the body with its taint bit, the decline that answers `False`
rather than raising, the capture that reports what the body pointed at rather than what was asked,
the capture refused for breaking the bound it asked for, the capture attempted exactly once, and
the single `BodyGatewayError` every verb fails with.

**Where the two legitimately diverge.** The level is a 32-bit float on the wire and a Python one
in the fake, so every level in the file is exact in both and the checks are about which field
moved rather than how many bits survived the trip. And the clamp happens in different places, the
fake doing it where it stands and the adapter's answer arriving already clamped by the body, so
the check asks only that a legal state comes back. Both are written into
[docs/modules/brain-body-client.md](../modules/brain-body-client.md).

**What it found: the fake handed back a capture the adapter would have refused.** A non-zero
`max_edge`/`max_bytes` is a bound on the *reply*, because an older body ignores the proto3 field
and the brain has no way to tell that its constraint was applied, and `GrpcBodyGateway` has
verified it on receipt
since the capture slice. `InMemoryBodyGateway` did not: it answered its scripted capture verbatim
whatever bound the call asked for. So a core test could watch a turn accept a picture production
would have thrown away, which is the fake being *more permissive* than the adapter it stands in
for, the direction that hides defects rather than inventing them. The rule is domain logic and not
wire translation, so it moved into the core as `hold_to_the_bounds_asked_for` and both
implementations now call it, which is also one fewer place for the two to drift apart. The fake
additionally gained `fail_with` and `show_notifications`, since a body that goes away mid-run and
a host that switches toasts off are conditions two of the checks need and construction arguments
cannot supply.

**Proven able to fail, four times, once per side.** With the bounds rule taken back out of the
fake, the refusal check fails on the `in-memory` arm alone (1 failed, 19 passed), which is the
defect above measured rather than asserted. With the adapter sending a zero for an absent level
instead of leaving the field unset, the presence check fails on the `grpc` arm alone, and that
zero is the value that would mute the host. With the adapter stamping the asked target onto the
answer instead of reading the body's, the target check fails the same way. And with the fake
recording a notification without its taint bit, the notification check fails on `in-memory`. Each
break was restored.

### `Confirmer`

`brain/packages/orchestrator/tests/confirmer_contract.py` holds five checks and the
`ConfirmerUnderTest` a check runs against; `test_confirmer_contract.py` runs them over
`RecordingConfirmer` and over `SeamConfirmer`. The list sits beside the real adapter rather than
beside the fake, which is where the other lists sit and where the fixture's work is: the seam
fixture wires a scripted **overlay** into the adapter's `emit`, reading the card off the control
path, decoding it back into a `ConfirmationRequest`, and answering through `resolve` exactly as
the Converse stream does with a `ConfirmResponse`. Nothing about the adapter is stubbed; only the
person is. The five are that an explicit approval is the only `True`, that a refusal blocks, that
a person who never answers denies, that the person is shown the call that would run, and that each
ask is answered on its own.

**Where the two legitimately diverge.** The fake records the request object it was handed, while
the real card crosses the seam as JSON built with `default=str`, so an argument value JSON cannot
represent would reach the person rendered rather than verbatim. The checks use JSON-native
arguments, which is what the model's own arguments always are, and the divergence is written into
[docs/modules/brain-orchestrator.md](../modules/brain-orchestrator.md).

**What it found: the fake's answer was fixed at construction.** A person is not a constant, and
the real confirmer's next answer is whatever the overlay sends next, so a fake that could only be
asked once about one answer could not stand in for it across two asks. It gained
`answer_with(approved=...)`. No behavioural disagreement came out of the five, which for a port
whose whole contract is "only an explicit yes is `True`" is the answer worth having.

**Proven able to fail, three times, and once deliberately not.** A timeout that approves instead
of denying makes `a_person_who_never_answers_denies` fail on the `seam` arm alone; a card emitted
without its reason makes the two checks that read what the person was shown fail on the `seam`
arm; and a fake that stops recording what it was shown makes the same two fail on `recording`. The
fourth attempt is the informative one: `resolve` rewritten to answer whichever request is pending
rather than the one whose id it was given leaves all ten green, because through the port only one
request is ever outstanding. That is the division of labour rather than a hole in the list, the
same split the overlay's closure described from the other side: the shared list holds the port, and
`test_confirm.py` holds the stream, where a stale or forged `confirm_id` resolving nothing is
checked directly. Each break was restored.

### What is left after these four

The four Python ports the sweep named now have shared lists. `InferenceBackend` stays open and is
the one Python row left, holding a shared list for its decode cadence and nothing shared for the
rest of streaming; that is a design question rather than a transcription, since the two
implementations produce their events at different rates and from different sources, and the list
that covers it has to say what an event stream owes without saying when. Every Rust row is
untouched, where the defect is one step worse than a restated list, the fakes themselves being
hand-written twice in two crates. The `InferenceBackend` half closed on 2026-08-16, in the
addendum below; the Rust rows are as this paragraph left them.

## Addendum (2026-08-16): `InferenceBackend`'s streaming half, and what a stream owes

The last Python row, and the one held back from the four above because it needed an answer rather
than a transcription: two implementations produce their events at different rates from different
sources, one from a script and one from bytes arriving over HTTP, so a shared list had to say what
a stream owes **without saying when**. `brain/packages/inference/tests/stream_contract.py` is that
answer, beside the two files that already held one closing event each;
`test_stream_contract.py` runs its eight checks over `ScriptedInferenceBackend` and over
`LlamaCppBackend` reading real llama-server bodies through an `httpx.MockTransport`, the same two
legs and the same fixture shape the cadence and stop lists use.

**The answer, check by check.** Every one is an obligation or an order, and none counts events,
sizes one, or asks when it arrives:

1. **The reply is its text deltas joined in arrival order.** How many deltas, how long each is and
   how far apart they arrive belong to the engine and are asserted nowhere.
2. **Thinking arrives apart and before.** A reasoning model's deliberation crosses as its own kind
   (ADR-0020), none of it is inside the reply, and none of it arrives after the reply has begun,
   which is what lets a consumer render one as an ephemeral chip and persist the other.
3. **A tool call crosses whole.** Id, name and arguments are one value; the fragments a wire
   splits an arguments string into are the adapter's business, never a caller's.
4. **A tool call never precedes the words beside it.**
5. **The two closing events arrive at most once each, the stop before the cadence, and both after
   everything they describe.** Each sibling list holds its own event alone, so the pair is
   described only here.
6. **A completion with nothing to say is a completion**, owing no stop, no cadence and no error.
7. **An abandoned completion costs the backend nothing**, the next one arriving whole. Every
   `finally: aclose()` in the core is written for this, since a user's Stop closes the iterator
   mid-completion, and an implementation holding a GPU lease for the stream's duration must
   release it when the stream is dropped.
8. **A backend that cannot answer fails its caller with `InferenceError`**, at a moment the port
   deliberately leaves open: an implementation may fail before it hands back an iterator or on the
   first event of one, and both shapes are live in this tree (`drain_text` guards its `aclose` for
   exactly that reason).

**What it found, twice against the port's own description.** The port said `TextChunk` deltas
arrive "interleaved with `ToolCall`s", which no implementation has ever done: the adapter assembles
calls from streamed fragments and can hand over none until the completion is over, and the twin is
scripted from what an implementation produced. The same sentence called the cadence the event that
"closes the stream", which is false in the other direction, since the calls trail both closing
events. Neither implementation was wrong, so the fix went into the description, in `ports.py` and
in `inference.py`, and the list holds the half both owe: a call never precedes the words beside it.
That repeats the `ToolRegistry` outcome, where an obligation no implementation could meet was
replaced by the one both already met.

**And once against the fake: it could not fail.** `ScriptedInferenceBackend` had no way to raise
the port's one error, so ten test files under `core/tests` and `orchestrator/tests` hand-roll a
backend of their own to make one, each with its own idea of what a dead server does. It gained
`fail_with`, the knob `HashEmbedder`, `InMemoryToolRegistry` and `InMemoryBodyGateway` already
carry; the attempt is recorded before it fails, since a backend that cannot answer still took the
request.

**Where the two legitimately diverge, and so what the list does not say**, written into
[docs/modules/brain-inference.md](../modules/brain-inference.md) instead of into a check. A delta
carrying no text is permitted by the port and dropped by the adapter, because llama-server opens
with a role-only chunk and closes with an empty delta and neither is anything to show; the core is
written for either, `turn_output` dropping an emptied delta and `ThinkingChannel` an empty status.
Tool calls trail both closing events in the adapter because a call is whole only once the stream
ends, so the check is about order against the text rather than position in the stream. And the
twin's script advances per call while the adapter is stateless per call, which is why nothing here
asks an implementation to answer twice the same way: unlike `Embedder`, this port never promised
determinism, and a sampled model could not keep it.

**`EchoInferenceBackend` is deliberately not a third leg**, though it is shipped wiring rather than
a double (the GPU-less default in `builders.py`). It has no thinking, calls no tool and always
answers, so three of the four worlds cannot be put to it, and adding any of them would turn a
backend a real deployment runs into a test stub, which is the argument `fakes_inference.py` already
makes about the cadence it must never fabricate. What it owes stays in `core/tests/test_fakes.py`.
Whether the twin should also reject a model it does not serve, where the adapter rejects one its
manager cannot lease, is the one question this list left open; it was filed as its own entry and is
answered by the served-model addendum below.

**Proven able to fail, seven times, and once informatively not.** Each break was made against
production code, measured with the whole `packages` suite (2517 passing), and restored:

| Break | Result | Shared checks that fail |
| --- | --- | --- |
| `_chunk_events` yields the reply before the thinking | 2 failed | the thinking check on `llamacpp` alone; the other is the adapter's own reasoning case |
| `_chunk_events` yields the cadence before the stop | 4 failed | the closing-order check on `llamacpp` alone; the other three are adapter cases |
| `consume_chunk` overwrites a call's arguments instead of accumulating them | 4 failed | both call checks on `llamacpp`, plus the derived case; the fourth is an adapter case |
| `ScriptedInferenceBackend.fail_with` made a no-op | 1 failed | the failure check on `scripted` alone, which shows the new knob is exercised |
| the twin appends a `DecodeStop(FINISHED)` to every round | 5 failed | the nothing-to-say and closing-order checks on `scripted`; the other three are the stop list on the same arm |
| `SingleResidentModelManager.acquire` releases its lock outside a `finally` | 3 failed | the abandonment check on `llamacpp`; the others are the two lease tests elsewhere |
| `_chunk_events` stops dropping the engine's padding | 23 failed | exactly one, and for an ordering reason rather than an emptiness one; the other 22 are the adapter's own suite |

The last row is the informative one, and it repeats what the `Confirmer` list found from the other
side: the shared list holds the port and the adapter's suite holds the translation, so a change
that only makes the adapter emit more events leaves seven of the eight checks green. That is the
division of labour rather than a hole. The one check that does fail fails because the role-only
opening chunk becomes a text delta ahead of the thinking, which is the ordering obligation working
as written.

## Addendum (2026-08-17): a backend answers only for a model it serves

This settles the question the streaming list above left open, by measuring what the two
implementations did with a model id no deployment hosts. `LlamaCppBackend`, asked for `'scribe'`
against a manager holding one resident, raised `InferenceError: model manager could not lease
'scribe' for inference` before any HTTP request left the process. `ScriptedInferenceBackend`, asked
for the same id, streamed its whole script and recorded the id in `calls` without reporting
anything. So the fake
was more permissive than the adapter it stands in for, which is the direction that hides defects
rather than inventing them: a wiring change naming an id nobody serves would pass every core test
written over the twin and fail on the first real turn.

**Neither implementation was wrong, because the port did not state the case.** With nothing in the
port to measure against, the twin's permissiveness was an unstated default rather than a decision.
The sentence written into `ports.py` is the narrowest one that closes the gap: an implementation
answers only for the ids it serves, and asked for one it does not, it fails with `InferenceError`.
What it deliberately does not say is **who checks or when**. Which ids
a deployment serves stays the `ModelManager`'s subject here, and a backend fronting a router would
legitimately recognise its whole table and take the refusal off the wire; both satisfy the
obligation, because the obligation is about the reply and not about the check. The reason it is an
obligation at all is that `model` is the caller's entire statement of which weights it wants
(ADR-0004): a reply produced by some other model arrives under the requested id with nothing to
mark it, so a caller cannot detect the substitution the way it detects a failure.

**What the twin gained.** `ScriptedInferenceBackend(rounds, serves=[...])` names the ids it stands
for, the wiring rather than the script, and refuses anything outside it with the port's one error
after recording the call, which matches `fail_with`'s existing treatment of a request a backend took
and could not answer. `serves=None` stays the default and answers for any id, because a twin given
no deployment to stand for has made no claim to violate, and the fifty-odd scripts written about
events rather than wiring should not have to invent one. The shared list is driven over a twin
given `CONTRACT_MODEL` and nothing else, which is exactly the wiring the adapter leg gets from its
`SingleResidentModelManager`.

**The ninth check needs no fifth world**, and that is why it is written this way:
`check_a_backend_answers_only_for_a_model_it_serves` asks the *deliberating* backend for
`UNSERVED_MODEL` and requires a failure. Every builder in the list already stands for a deployment
serving `CONTRACT_MODEL` alone, so the world the check needs is the one the fixtures already
arrange, and a fifth builder would have described the same deployment twice.

**Proven able to fail, twice, once per leg.** Each break was made against production code, measured
with the whole `packages` suite (2625 tests), and restored:

| Break | Result | Shared checks that fail |
| --- | --- | --- |
| the twin's refusal made a no-op | 1 failed | the served-model check on `scripted` alone, which shows the new knob is exercised |
| `SingleResidentModelManager.acquire` stops checking residency | 3 failed | the served-model check on `llamacpp`; the others are the manager's own test and the adapter's wrapping test |

The asymmetry between the rows is the division of labour again: the twin's refusal is reachable
only from the shared list, since nothing else in the tree hands the twin an id it does not serve,
while the adapter's comes from a collaborator two other tests already pin. What is left over is
that `serves` is opt-in, so the core's own hand-rolled backends still answer for anything, which is
recorded as its own entry rather than settled here.

## Addendum (2026-08-20): each configured caller's model id, pinned against its own deployment

The served-model sentence closed the gap in the port's description and left the opposite exposure
open. The obligation falls on the implementation, and no test in the tree could catch a caller
asking for the wrong id in the first place. `serves` is opt-in and exactly one fixture passes it,
the shared list's own builder in `test_stream_contract.py`; everywhere else the id is discarded
outright, `del model` appearing 53 times across 18 hand-rolled backends under `core/tests` and
`orchestrator/tests`. So a composition root that handed the turn engine one tier and the lease
another would have passed the whole suite and refused the first real turn.

[R-298](../refinements/tasks/298-served-ids-are-opt-in-everywhere.md) weighed three shapes for that
and this is the cheapest of them, one test per configured caller pinning that the id it asks for is
the id its deployment hosts. Nothing in production changed and `serves` stays `None` by default,
for the reason it was kept: a twin given no deployment to stand for has made no claim to violate.

**The three callers, and why each pin is more than a restatement of a constructor argument.** The
resident tier a turn asks for is `CORTEX_MODEL_CORTEX` read twice by `run_from_env`, once into
`TurnEngine(cortex_model=...)` and once into the backend whose manager grants the lease, and those
two reads meet nowhere below the root. That pin is driven over the llama.cpp backend, because the
echo one takes no lease at all, and against a refused loopback port, because what is under test
finishes before the wire: the assertion is on which failure comes back, the transport's, naming the
tier, or the manager's refusal to lease it. The deep tier a handoff swaps in is the plan's
`brain_model`, which `build_swap_runtime` uses as a key of its endpoint map while the deep phase
asks for it by name, so a map keyed by anything else leaves a swap unable to lease the model it
just started. The subagent entry every untrusted spawn is forced onto is `config.model`, declared
apart from the entries `named_roster` keys, meeting only in the builder, and `SubagentRoster`
refuses to be constructed when the two disagree.

**Every one of the three renames its tiers, which is the whole method.** Under the shipped ids the
deployment's value and the module's own constant are the same string, so a builder reaching for the
constant is indistinguishable from one reading the config, and every case that existed here left
the defaults in place. `test_the_enabled_runtime_is_the_one_lease_and_the_one_residency` already
leased both tiers and asserted both endpoints, and it stays green under a map keyed by literals;
the renamed twin beside it does not. Renaming the tiers is what separates a test that exercises
the wiring from one that only repeats the literals.

**Proven able to fail.** Each mis-wiring was applied to production code alone and measured over the
whole `packages` suite, then restored. Each is the same realistic slip: a root reaching for the
module constant instead of the deployment's own value.

| Mis-wiring | Test that fails |
| --- | --- |
| `TurnEngine`'s `cortex_model` becomes the literal `"cortex"` | the resident-tier pin, failing as "model manager could not lease" |
| the inference backend is built for the literal `"cortex"` | the same one, failing on the other id |
| the endpoint map's deep key becomes the literal `"brain"` | the renamed-tiers pin alone, out of the 29 cases in its file |
| the roster's default becomes the literal `"subagent"` | the untrusted-spawn pin alone; the roster case beside it, which leaves the id at its default, stays green |

**What is left over** is the fourth configured caller, the recall judge, which asks the resident
model to rank a pool and falls back to the unjudged ranking on any `InferenceError`. A lease
refused for a wrong id is exactly that error, so a mis-wiring there produces no failed turn.
Instead every recalling turn is ranked the way `CORTEX_MEMORY_RECALL=raw` ranks, with one warning
logged per recall that nobody is reading. That is recorded as its own entry rather than settled
here, since pinning it costs the memory wiring a fixture the other three did not need.
