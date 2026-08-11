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
exists", and AGENTS.md sharpens it into a sentence about arithmetic rather than intent: *the
real adapter must pass the same contract test as the fake.* On 2026-08-09 that sentence was
found half-true for `MemoryStore`. A shared file, `memory_contract.py`, held the checks and a
tuple naming them, and only the integration-marked pgvector run read the tuple. The fake was
checked by a separate hand-written suite in `cortex_core`. The shared file therefore looked
like the guarantee and was not one: a check appended to it reached CI only if somebody also
remembered to write it a second time, and nobody would notice the omission, because the
omission's symptom is a test that never runs rather than a test that fails. That was fixed by
adding a fake-driven test parametrized over the same tuple.

This addendum is the sweep that asks whether it was the only one. The method was mechanical
and is worth repeating rather than re-derived: enumerate every port in both languages, find
its shared check list if it has one, find every driver of that list, and ask which drivers CI
actually runs. A list read by one driver and restated by another is the defect; a list read by
every driver cannot drift; a port with a single driver parametrized over its implementations
has no list to drift.

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
| `InferenceBackend` | `ScriptedInferenceBackend` | `LlamaCppBackend` | `inference/tests/cadence_contract.py`, decode cadence only | yes | yes, over `MockTransport` | yes, restated |
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

The Rust picture is not that a shared list drifted; it is that none exists. There is no
`macro_rules!` anywhere under `body/crates`, no contract module in that workspace, and no generic
function carrying assertions. `BrainTransport` is the strongest row regardless, its real adapter driven end to
end in CI against an in-process fake `BrainService` on loopback, and it is also the row where a
shared list would pay most, three independent hand-written suites currently describing the same
eleven-method trait.

### What the sweep found, and what it fixed

**One port had the memory defect, and it was `SessionStore`, the port the hard rule is written
about.** `session/tests/contract.py` exports fourteen checks and a tuple naming them, and the
tuple's only reader was `test_store_live.py`, the integration-marked live-Redis run. The
CI-visible driver, `test_store_contract.py`, restated all fourteen as hand-written wrappers.
The list happened to agree at the moment it was read, fourteen against fourteen, and the
agreement was worth exactly what the refinements index says such an agreement is worth: it
recorded that nobody had yet forgotten, and promised nothing about the next person. Fixed the
way the memory one was, by parametrizing over `contract.ALL_CHECKS` across the existing
two-implementation fixture, which is the arrangement the other four stores in that directory
already used.

**Proven able to fail, which is the only evidence that the fix is real.** A fifteenth check
that raises unconditionally was appended to `contract.py` and to `ALL_CHECKS`, and the
CI-visible driver was run twice over it, once as it now stands and once as it stood before.
Parametrized, it reddens twice, once per implementation, the ids being
`check_a_check_nobody_hand_wrote_a_wrapper_for` under each of the fixture's `in-memory` and
`redis` arms, alongside 66 passing. Restated, the same poisoned shared file gives `66 passed`, green, with the failing
check never executed at all. That is the defect measured rather than asserted, and it is the
same shape the memory fix demonstrated. Both files were restored afterwards and the whole
`packages/session` suite is green at 268 passed.

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
adapter, and nothing today holds the two to one description.

Across the Rust rows the defect is one step worse than a restated list, being a restated fake:
`FakeAudio`, `FakeNotify`, `FakeScreen` and `FakeBrain` are each hand-written twice, once under
`body/crates/core/tests/` and again under `body/crates/rpc/tests/`, with independent
expectations. The generic helpers that look like shared drivers (`register_via`, `get_via`,
`show_via`, `capture_via`, `probe`) carry no assertions; they prove the trait is usable as a
bound and nothing more. The four Windows adapters cannot run in CI, which is gate 3 and not a
defect, but a shared list would still be the only artifact holding them to the description
their fakes are held to, and it would be waiting the day the host runs it. The overlay's
`BrainBridge` is the sharpest single case, its 100% coverage threshold met while two of its
three implementations are named in `vite.config.ts`'s coverage `exclude`, which is a gate
reading green over code it was never pointed at. That row is the one closed since, on 2026-08-11,
by the addendum below; the Python and Rust rows are as the sweep left them, and its overlay row
above has been updated to what the tree now holds.

Building those suites is a slice, not a sweep, so it is deferred and recorded in
[docs/refinements/repo-gates.md](../refinements/repo-gates.md) rather than attempted here. The
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
the other crosses an IPC boundary. They cannot, and the line is not where the question put it.
`TauriBridge` is out because every one of its methods is an `invoke` call, so holding it to these
checks would mean faking `invoke` and measuring the fake. What the list does hold is both
implementations CI can run, at the altitude where they genuinely agree: the turn HANDLE rather
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
That ask rides a short timer now, which is also what it looks like by hand.

**Proven able to fail, three times, once per kind of thing it claims.** With `DemoBridge`'s
`deleteSession` put back to the no-op it once was, `checkADeletedChatStaysGone` reddens on the
`DemoBridge` arm alone (25 passed, 1 failed). With the turn's cancellation no longer clearing its
timers, `checkACancelledTurnGoesSilent` reddens the same way, the recorder holding 87 events where
the check demands none. With the completion moved ahead of the reply's words,
`demoBridge.test.ts`'s ordering claim reddens while all 26 shared checks stay green, which is the
division of labour working: the shared list holds the port, the demo's suite holds the script.
Each break was restored and the tree is green.

What stays open is everything else the sweep measured: the four Python ports with no shared list
(`Embedder`, `ToolRegistry`, `BodyGateway`, `Confirmer`), `InferenceBackend`'s unshared streaming
half, and every Rust row, where the fakes themselves are still written twice.

## Addendum (2026-08-11): the Python ports with a fake, an adapter and no shared list

The sweep's Python worklist, taken one port per commit in the order the table lists them. Each
section below records what the list holds, where the two implementations legitimately diverge and
so what altitude the checks sit at, what the list found on its first run, and the break that
proved it able to fail. `InferenceBackend` is deliberately not in this addendum: its decode
cadence is already shared and the rest of its streaming contract is a design question of its own
(what a list can say about an event stream two implementations produce at different rates), so it
stays open in the tables and in the refinements entry.

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
found between the two on the paths both could already walk, which is the honest outcome for a port
one method wide, and it is worth writing down rather than leaving as a silence.

**Proven able to fail, once per arm.** Dropping the adapter's `float(value)` coercion reddens
`text_embeds_to_a_vector_of_real_numbers[llamacpp]` alone (1 failed, 7 passed); making the fake's
width depend on the text's parity reddens `every_text_embeds_at_one_width[hash]` alone; letting
the adapter's `httpx.HTTPError` escape instead of wrapping reddens
`a_backend_that_cannot_answer_raises_embedder_error[llamacpp]`; and making the new `fail_with` a
no-op reddens the same check on the `hash` arm, which is what proves the knob is load-bearing
rather than decorative. Each break was restored.

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

**Where the two kinds legitimately diverge, and what the port now says about it.** An unknown name
is the case, and the sweep's assumption that the port already settled it was wrong. The port's
parenthetical promised `ToolNotFoundError`, which only a registry that knows its whole set can
keep: `McpToolRegistry` asks a server, and an MCP server answers an unknown tool with an error
*result*, so the adapter has never raised there and cannot without either sniffing an error string
or paying a listing round trip per call. Neither implementation is wrong, so the fix went into the
description: the port now states the safety half both owe, that a name an implementation does not
serve never comes back as a success, and names the divergence and its downstream consequence, the
dispatcher stamping its own `ToolError` sentence `TRUSTED` while a relayed error result stays
`UNTRUSTED`, which is the correct reading of each. A caller needing the distinction resolves
ownership by a live walk first, which is what `AggregateToolRegistry` already does.

**What it found: the fake could express neither the port's central case nor its world.**
`InMemoryToolRegistry`'s handlers returned result text, so the fake could never produce a result
with `is_error` set, which is the case the port draws its whole `is_error`/raise distinction
around; every core test of a failing tool went through a handler *raising*, which is the other
branch, and the dispatcher labels the two differently. The handler's answer is now text or a whole
`ToolResult`, with the call's own id stamped on either. The fake also copied its tool set at
construction, so no test could move the world the port promises to re-read (it gained `serve`), and
it had no way to be unreachable, so nothing held it to the `ToolError` that
`SkipUnavailableToolRegistry` is built on (it gained `fail_with`, the same knob `HashEmbedder`
took the day before).

**Proven able to fail, four times, and the arms it reddens are the ones that can carry each
defect.** With the adapter reading `isError` as always false, the failed-tool check and the
unknown-name check both redden on the `mcp` and `reconnecting` arms while the fake stays green, 4
failed against 15 passed, which is the unknown-name check earning its altitude: it is the only
thing standing between a relayed "Unknown tool" and the model being told it succeeded. With the
adapter dropping the call's arguments, the id-and-text check and the failed-tool check redden on
the same two arms. With the fake answering an empty listing instead of raising when it is
unreachable, which is the silent degradation `SkipUnavailableToolRegistry` exists to prevent, the
backend check reddens on the `in-memory` arm alone. And with a listing cache added to
`McpToolRegistry`, the re-read check reddens on the `mcp` arm **only**, not on `reconnecting`,
because that wrapper builds a fresh inner registry per call and is structurally immune to the
defect. That last one is why both MCP arms are in the list rather than one: they are not the same
implementation of this promise. Each break was restored.

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
`max_edge`/`max_bytes` is a bound on the *reply*, because a proto3 field an older body ignores is
a constraint the brain only believes it set, and `GrpcBodyGateway` has verified it on receipt
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
fake, the refusal check reddens on the `in-memory` arm alone (1 failed, 19 passed), which is the
defect above measured rather than asserted. With the adapter sending a zero for an absent level
instead of leaving the field unset, the presence check reddens on the `grpc` arm alone, which is
the mute that would silence the host. With the adapter stamping the asked target onto the answer
instead of reading the body's, the target check reddens the same way. And with the fake recording
a notification without its taint bit, the notification check reddens on `in-memory`. Each break
was restored.

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
of denying reddens `a_person_who_never_answers_denies` on the `seam` arm alone; a card emitted
without its reason reddens the two checks that read what the person was shown, on the `seam` arm;
and a fake that stops recording what it was shown reddens the same two on `recording`. The fourth
attempt is the informative one: `resolve` rewritten to answer whichever ask is pending rather than
the one whose id it was given leaves all ten green, because through the port only one ask is ever
outstanding. That is not a hole in the list, it is the division of labour the overlay's closure
described in the other direction: the shared list holds the port, and `test_confirm.py` holds the
stream, where a stale or forged `confirm_id` resolving nothing is checked directly. Each break was
restored.

### What is left after these four

The four Python ports the sweep named now have shared lists. `InferenceBackend` stays open and is
the one Python row left, holding a shared list for its decode cadence and nothing shared for the
rest of streaming; that is a design question rather than a transcription, since the two
implementations produce their events at different rates and from different sources, and the list
that covers it has to say what an event stream owes without saying when. Every Rust row is
untouched, where the defect is one step worse than a restated list, the fakes themselves being
hand-written twice in two crates.
