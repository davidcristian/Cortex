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
| `Embedder` | `HashEmbedder` | `LlamaCppEmbedder` | none | n/a | n/a | yes |
| `ToolRegistry` | `InMemoryToolRegistry` | `McpToolRegistry` | none | n/a | n/a | yes |
| `BodyGateway` | `InMemoryBodyGateway` | `GrpcBodyGateway` | none | n/a | n/a | yes |
| `Confirmer` | `RecordingConfirmer` | `SeamConfirmer` | none | n/a | n/a | no |
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

Nine ports carry a shared check list, one `*_contract.py` each. All nine list every check the
file defines, so no check has been written into a shared file and then left off its own tuple,
which was the other way this could have gone wrong. Eight of the nine already had a CI-visible
driver that reads the tuple rather than restating it.

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
tables above are that slice's worklist.

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
