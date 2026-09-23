# ADR-0068: One shared contract list per port, read by one driver

**Status:** Accepted (2026-09-17)

## Context

[ADR-0001](ADR-0001-architecture.md) decision 2 says a port is defined, contract-tested and faked
before any real adapter exists, and AGENTS.md makes it checkable: the real adapter must pass the
same contract test as the fake. A shared file of checks is that guarantee only when every driver
reads it. `MemoryStore` had a `memory_contract.py` tuple read only by the integration-marked
pgvector run, while the fake was checked by a separate hand-written suite; a check appended to the
shared file reached CI only if somebody wrote it a second time, and the omission produced a test
that never runs rather than a test that fails. `SessionStore`, the port the hard rule is written
about, had the same defect: its fourteen shared checks were restated by hand in the CI driver. A
review then listed every port in both languages to find the others.

## Decision

1. **A port with a fake and a real adapter has one shared check list, read by one parametrized
   driver.** The list is a `*_contract.py` beside the tests, holding named checks and a tuple naming
   them; the CI driver parametrizes over that tuple and over every implementation CI can run, so a
   check appended to the list reaches CI on the next run. A list read by one driver and restated by
   another can disagree; a list read by every driver cannot. "CI" here means `just check`, which
   runs `pytest -m "not integration"`. A live run, integration-marked and needing a real server, may
   restate the list, since it checks nothing in CI.

2. **The inventory is read off the code, not off the table.** Python ports are the `class
   <Name>(Protocol` declarations across `brain/packages/*/src`, Rust ports the `pub trait`
   declarations across `body/crates` and `body/app/src-tauri/src`. Two kinds of protocol are not
   ports: internal boundaries inside an adapter package that stand for a library or process the
   adapter drives (`ChildProcess`, `ChildProcesses`, `DeviceMemoryProbe`, `HealthProbe`, `Database`,
   `Row`, `McpSession`), and protocols the core's own modules accept from each other (`BuiltinTool`,
   `HistoryWindow`, `OutputFilter`, `OutputGuardrail`, `SaliencePolicy`, `TaintView`).

3. **A check sits where the implementations genuinely agree, and each legitimate difference is
   written in the module doc instead.** The embedder fake answers a `tuple`, the adapter a `list`,
   at different widths, so the checks read the `Sequence[float]` and compare an implementation's
   widths with each other. `BodyGateway` clamps in different places, so the check asks only that a
   legal state comes back. The real confirmer's card crosses as JSON built with `default=str`, so
   the checks use JSON-native arguments. `EmailSender`'s adapter sees a Bcc that the standard
   library strips on the wire. Each is written in the package's page under `docs/modules/`.

4. **When no implementation can meet the port's sentence, the sentence changes.** `ToolRegistry`
   promised `ToolNotFoundError` for an unknown name, which an MCP registry asking a server cannot
   deliver without reading error text; the port now says that a name an implementation does not
   serve never comes back as a success. `InferenceBackend` said text deltas arrive interleaved with
   tool calls and that the cadence closes the stream; neither implementation does either, and the
   port now says that a tool call never precedes the words beside it.

5. **A fake is never more permissive than its adapter, and it can fail the way the port says.** A
   domain rule found only in an adapter moves where both implementations call it: the capture bound
   into the core as `hold_to_the_bounds_asked_for`, the draft refusals into
   `cortex_email/drafts.py`. A fake gains the port's documented failure as `fail_with`
   (`HashEmbedder`, `InMemoryToolRegistry`, `InMemoryBodyGateway`, `ScriptedInferenceBackend`,
   `FakeSender`) and a setting for each condition a check needs that construction cannot supply
   (`serve`, `show_notifications`, `answer_with`, `refuse`). A permissive fake hides defects: a core
   test can watch a turn accept what production refuses.

6. **Some ports have no list, by decision.** A write-only sink (`RecallAuditSink`, and
   `LoggingAuditSink` among the audit sinks) exposes nothing to read back, so a shared check
   would reach past the port into a list on one side and a log capture on the other, or be the
   vacuous test the coverage rule bans; each side is checked where it lives. `Clock` and `Sleeper`
   are the wall clock and the event loop, where a shared check is vacuous or a timing assertion.
   `ZoneResolver` and `MemoryScope` implementations answer differently, deliberately. A port whose
   every implementation is pure core has no question of agreement. `ToolAuditSink` does have a list,
   because `JsonLinesAuditSink` writes a file a check can read back.

7. **The overlay's `BrainBridge` list** is `body/app/src/bridge/bridgeContract.ts`, run by
   `bridgeContract.test.ts` with `describe.each` over `FakeBridge` and `DemoBridge` and `it.each`
   over the checks. `TauriBridge` stays out: every method is an `invoke` call, and running it
   against the list would mean faking `invoke` and measuring the fake. The overlay's coverage
   exclude holds only `main.tsx` and `tauriBridge.ts`, so the 100% threshold measures both
   implementations the overlay can run. The differences between the two are in
   [body-app](../modules/body-app.md).

8. **What an inference stream owes, without saying when.** `stream_contract.py` holds obligations
   and orders and never a count, a size or a time: the reply is its text deltas joined in order;
   thinking arrives apart from the reply and before it; a tool call crosses whole and never before
   the words beside it; the stop and the cadence arrive at most once each, stop first, after
   everything they describe; a completion with nothing to say is a completion; an abandoned
   completion costs the backend nothing; a backend that cannot answer fails with `InferenceError`,
   before or on its first event; and a backend answers only for a model it serves. Which ids a
   deployment serves stays the `ModelManager`'s subject, and the port leaves who checks and when to
   the implementation. `ScriptedInferenceBackend(serves=[...])` names the ids it stands for;
   `serves=None`, the default, answers for any id, because a stand-in given no deployment has made
   no claim to violate. `EchoInferenceBackend` is shipped wiring and not an implementation under
   test: it cannot think, call a tool or fail, and making it able to would turn a backend a
   deployment runs into a stub.

9. **Each configured caller's model id is checked at the root, under a renamed tier.** Six callers
   use a configured id: the turn engine (with the backend whose manager grants the lease), the deep
   tier's endpoint map, the subagent entry every untrusted spawn is forced onto, the recall judge,
   the recap summarizer and the trace-budget probe; the session title uses the turn engine's id.
   Each test drives the builder rather than the layer beneath it, renames the tier so the
   deployment's value and the module's constant differ, runs over a backend serving only the renamed
   id, and asserts an outcome only a model that was asked can produce: a turn run, a swap leased, a
   roster built, the judged order, the recap in front of the kept turns, the budget on the wire. The
   last three fall back silently on a refused lease, which is why their tests read the outcome.

10. **The recall policies share one list, held to what each owes.** All five policies, and the judge
    a second time over a model that cannot be asked: `candidate_k(k)` is `k` times the pool factor,
    an empty pool ranks nothing, at most `k` hits come back from the pool and none twice, and the
    pool is left as it was handed over. Only raw recall and the two MMR policies answer `min(k, n)`
    hits, since the dedup reranker and the judge prune deliberately
    ([ADR-0008](ADR-0008-memory-v1.md), [ADR-0038](ADR-0038-ranked-recall.md)). The four with a pool
    factor refuse one below one with the same message.

11. **The Rust rows stay open.** No Rust port has a shared list, and `FakeAudio`, `FakeNotify`,
    `FakeScreen` and `FakeBrain` are each written twice, under `body/crates/core/tests/` and
    `body/crates/rpc/tests/`. The generic helpers that look like drivers (`register_via`, `get_via`,
    `show_via`, `capture_via`, `probe`) contain no assertions. Building the lists is
    [R-018](../refinements/tasks/018-ports-without-contract-suite.md).

12. **A list is proven able to fail on each implementation when it is committed**, by breaking
    production code on one side and seeing the check fail on that side alone, per AGENTS.md.

## The inventory

Python, each list in the named package's `tests/`. "Live" is an integration-marked run.

| Port | Fake | Real adapter | Shared checks | CI: fake | CI: adapter | Live |
| --- | --- | --- | --- | --- | --- | --- |
| `SessionStore` | `InMemorySessionStore` | `RedisSessionStore` | `session/tests/contract.py` | yes | yes, over fakeredis | yes |
| `TaskStore` | `InMemoryTaskStore` | `RedisTaskStore` | `task_contract.py` | yes | yes, over fakeredis | no |
| `ScheduleStore` | `InMemoryScheduleStore` | `RedisScheduleStore` | `schedule_contract.py` | yes | yes, over fakeredis | yes |
| `HandoffStore` | `InMemoryHandoffStore` | `RedisHandoffStore` | `handoff_contract.py` | yes | yes, over fakeredis | yes |
| `PreferenceStore` | `InMemoryPreferenceStore` | `RedisPreferenceStore` | `preference_contract.py` | yes | yes, over fakeredis | no |
| `MemoryStore` | `InMemoryMemoryStore` | `PgVectorMemoryStore` | `memory/tests/memory_contract.py` | yes | no, needs a server | yes |
| `ModelHost` | `ScriptedModelHost` | `HttpModelHost` | `model_host_contract.py` | yes | yes, a real supervisor on ASGI | restated |
| `VisionProbe` | `ScriptedVisionProbe` | `PropsVisionProbe` | `vision_probe_contract.py` | yes | yes, `MockTransport` | restated |
| `InferenceBackend` | `ScriptedInferenceBackend` | `LlamaCppBackend` | `cadence_contract.py`, `stop_contract.py`, `stream_contract.py` | yes | yes, `MockTransport` | restated |
| `Embedder` | `HashEmbedder` | `LlamaCppEmbedder` | `embedder_contract.py` | yes | yes, `MockTransport` | restated |
| `ToolRegistry` | `InMemoryToolRegistry` | `McpToolRegistry`, `ReconnectingMcpToolRegistry` | `registry_contract.py`, and the own-text list | yes | yes, both, over a serving `McpSession` | yes |
| `BodyGateway` | `InMemoryBodyGateway` | `GrpcBodyGateway` | `gateway_contract.py` | yes | yes, a loopback `BodyService` | yes |
| `Confirmer` | `RecordingConfirmer` | `RpcConfirmer` | `confirmer_contract.py` | yes | yes, a scripted overlay | no |
| `ProgressSink` | `RecordingProgressSink` | `RpcProgressSink` | `progress_contract.py` | yes | yes, a list of queued events | no |
| `Mailbox` | `FakeMailbox` | `ImapMailbox` | `mailbox_contract.py` | yes | yes, a stand-in box | restated |
| `EmailSender` | `FakeSender` | `SmtpSender` | `sender_contract.py` | yes | yes, a stand-in `smtplib` | restated |
| `ToolAuditSink` | `RecordingAuditSink` | `JsonLinesAuditSink`, `TeeAuditSink` | `audit_contract.py` | yes | yes, a temporary file | no |
| `RecallPolicy` | none | five shipped core policies | `recall_policy_contract.py` | n/a | yes, all pure core | no |
| `SubagentScheduler` | `AdmitAllScheduler` | `ResourceBudgetScheduler` | `test_scheduler_drain.py`, one driver | yes | yes, pure core | no |

No list, by decision 6: `RecallAuditSink`, `Clock`, `Sleeper`, `ZoneResolver`,
`MemoryScope`, `ModelManager`, `SubagentPlacer`, `ResidencyController`, `ResidencyReporter`,
`PaceSink`, `TurnRunner`.

Rust and the overlay:

| Port | Fake | Real adapter | Shared checks | CI: fake | CI: adapter |
| --- | --- | --- | --- | --- | --- |
| `Hotkey` | `FakeHotkey` | `WindowsHotkey`, Linux and macOS stubs | none | yes | no, `cfg(windows)` |
| `AudioControl` | `FakeAudio`, written twice | `WindowsAudioControl` | none | yes | no, `cfg(windows)` |
| `Notify` | `FakeNotify`, written twice | `WindowsNotify` | none | yes | no, `cfg(windows)` |
| `ScreenCapture` | `FakeScreen`, written twice | `WindowsScreenCapture`, `DeniedScreenCapture` | none | yes | the denying one |
| `BrainTransport` | `FakeTransport`, `ScriptedTransport`, `FlakyTransport` | `BrainRpcClient`, `RetryingTransport` | none | yes | yes, a loopback fake `BrainService` |
| `Sleeper` | `FakeSleeper` | `TokioSleeper` | none | yes | no, outside the checked workspace |
| `Randomness` | `FakeRandomness` | `FullDelay`, `ShellRandomness` | none | yes | `FullDelay` incidentally |
| `BrainBridge` (overlay) | `FakeBridge` | `TauriBridge`, `DemoBridge` | `bridgeContract.ts` | yes | `DemoBridge` |

## Consequences

- A check written once reaches every implementation CI can run; forgetting to copy it is no longer a
  way to lose it.
- Port docstrings state only what every implementation owes, so a difference found by a list is
  written in the port's description or the module doc, never in one implementation's test.
- Six configured model ids cannot be mis-wired without a failing test, at no startup cost and no
  port change.
- Until R-018 is done, the Rust fakes can disagree with each other and with the Windows adapters.

## Alternatives rejected

- **A restated list in the CI driver**, one wrapper per check: it agrees with the shared file only
  until the next edit, and a missed copy fails nothing.
- **A startup check comparing each caller's id with the served ids**: every caller reads one config
  field, so it would compare a value with itself; it needs a question the port does not offer; and
  the echo backend serves any id.
- **Making `serves` required, or checking it in every hand-rolled backend**: a stand-in told nothing
  about a deployment states nothing a call could contradict.
- **Running `TauriBridge` against the list over a faked `invoke`**: it would measure the fake.

## Related

- [ADR-0001](ADR-0001-architecture.md) decision 2; [ADR-0002](ADR-0002-toolchain-checks.md) (the
  checks the drivers run under).
- Modules: [brain-core](../modules/brain-core.md), [brain-inference](../modules/brain-inference.md),
  [brain-session](../modules/brain-session.md), [brain-email](../modules/brain-email.md),
  [brain-tools](../modules/brain-tools.md), [body-app](../modules/body-app.md).
- Backlog: [R-018](../refinements/tasks/018-ports-without-contract-suite.md).
