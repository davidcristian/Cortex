# brain/packages/orchestrator (`cortex_orchestrator`)

**Purpose.** The grpc.aio service hosting `BrainService`, the brain's end of the wire, plus the
composition root that wires the core's ports to real adapters: the per-capability `build_*`
factories in `builders.py` and its line-cap splits, the boot orderings no single settings class can
check for itself in `bounds.py`, `run_from_env` in `wiring.py`, and the per-stream `StreamEngines`
in `engines.py`. A shell only: turn logic lives in `cortex_core`, and no conversation or task state
lives in this process beyond the in-flight turn. Configuration is env-only and is documented in
[brain-orchestrator-config.md](brain-orchestrator-config.md).

## The service

`BrainService(make_engine, store, *, ports=RpcPorts(), max_buffered_events=256,
confirm_timeout_s=…)` implements `BrainServiceServicer` and holds no state; the engine factory, the
session store and the optional `RpcPorts` are injected. `store` is the same instance the engine
writes, so the read-only session RPCs serve exactly what turns persist.
`RpcPorts(schedules=None, memory_cascade=None, residency=None)` is what the wire serves beyond a
turn, each absent when its capability is off.

- `Health` answers `HealthReply(ready=True, detail="cortex-orchestrator <version>")` while the
  normal residency is serving, and `ready=False` with the residency's own line while a handoff
  holds the GPU (ADR-0030 decision 6). A serving report may have notes, which then win over the
  version string while `ready` stays true: each is one `HealthNote` in `notes`, and `detail` joins
  them with `; `, a missing peer tier and a slow last handoff both being true of a serving brain
  with different remedies (ADR-0054 decisions 3 and 7, ADR-0055 decision 5). The read is
  `ResidencyReporter.residency()`, synchronous and lock-free by that port's contract. With no `residency` wired the answer is
  unconditional, and the drain before an eviction stays ready.
- `ListSessions` returns recent chats newest-active first, each `SessionSummary` mapped to the wire
  with unix-ms timestamps, `request.limit` clamped by `_clamp_limit` (`DEFAULT_SESSION_LIST_LIMIT`
  is 50, `MAX_SESSION_LIST_LIMIT` 200). `GetSessionMessages` returns one session's persisted
  history, empty for an unknown session.
- `RenameSession`, `DeleteSession` and `SetSessionHoisted` (ADR-0021 decisions 10 to 12) are
  user-only catalog writes through `session_rpc.py`. The restriction is structural: none is a tool
  in any registry and none runs through the turn engine, so no model, tool or tainted turn can
  reach them. `RenameSession` bounds the label (`clamp_title`, `MAX_TITLE_INPUT` of 200) and an
  empty title clears the override. `DeleteSession` deletes the chat first, then, with a memory
  backend wired, runs the injected `SessionMemoryCascade`, never passing `GLOBAL_SCOPE`; both steps
  are idempotent, so a retry recovers. A `SessionStoreError` aborts `UNAVAILABLE`, and the memory
  port's narrower `MemoryDataError` aborts `INTERNAL` instead (ADR-0008 decision 13).
- `ListDueReminders` and `AckReminder` (ADR-0025, policy in `reminders.py`) are the pull pair over
  the injected `ScheduleStore`. A `DueReminder` has the id, the text, the fired-at unix-ms stamp,
  the recurrence, the `tainted` bit and the origin `session_id`, where the text is a reminder's own
  or a fired task's `last_outcome`. The ack names a fire, so an ack for one a later fire replaced
  answers `acked=false` and leaves the later one deliverable, and `0` acks whichever fire is held.
  With no store wired both answer benignly rather than `UNAVAILABLE`, which the body's retrying
  transport would treat as transient.
- The two settings RPCs (ADR-0032) read and write the user's preferences, answering empty reads and
  dropping writes when no store is wired, the `ScheduleStore` precedent.
- The unary RPCs abort `UNAVAILABLE` on a `SessionStoreError`, and each arrives with a
  `grpc-timeout` the body announced (ADR-0024 decision 15), which no handler reads and grpc.aio
  enforces on its own; `Converse` announces none, a turn being long by design. The method bodies
  live in `preference_servicer.PreferenceRpcMixin`, `session_servicer.SessionRpcMixin`,
  `session_rpc.py` and `reminders.py`, with `stores.RedisStores` opening the session and preference
  stores from one URL and closing them as a pair, so `server.py` stays a thin binding.
- `create_server(config, make_engine, store, ports=RpcPorts())` builds the aio server, binds
  `config.bind_address` and returns it with the actually-bound port. With a token set it registers
  the `RpcTokenInterceptor` (ADR-0016, `auth.py`), which aborts any RPC without matching metadata
  `UNAUTHENTICATED` before the servicer runs, on a constant-time compare. It always registers the
  `AbandonedCallInterceptor` second, so an unauthenticated call is refused rather than watched.
- `AbandonedCallInterceptor()` (`abandon.py`,
  [ADR-0061](../adr/ADR-0061-abandoned-call-line.md)) writes one `WARNING` per unary call the
  caller gave up on, with the RPC's wire `method` and the `time_remaining()` the announced deadline
  had left. **The type is the distinction, not the value**: a float above zero is a caller that
  stopped early, an integer `0` is the announced deadline enforced by the brain's own clock, and
  `None` is a caller that announced no deadline. Readings above the announcement are normal from a
  python caller, grpc-python rounding a `timeout=` up onto a coarse unit ladder. A handler with no
  unary-unary behaviour passes through untouched, which is how `Converse` stays unwatched.
- `serve(config, make_engine, store, ports=RpcPorts())` starts the server and blocks until
  SIGTERM, SIGINT or cancellation; both signal handlers are installed on the running loop for the
  server's lifetime and trigger the same graceful stop, draining in-flight RPCs for up to 5 s.

## The Converse stream

`converse(make_engine, client_events, *, max_buffered_events=DEFAULT_MAX_BUFFERED_EVENTS,
confirm_timeout_s=DEFAULT_CONFIRM_TIMEOUT_S, turn_id_factory=new_turn_id, sleeper=None)` is the loop
itself, independent of the servicer. `make_engine` is an `EngineFactory`
(`Callable[[Confirmer, ProgressSink], TurnRunner]`): each stream builds one `RpcConfirmer` and one
`RpcProgressSink` bound to its own output queue and runs the engine the factory returns. Closing
the generator tears down the pump and heartbeat tasks, any in-flight turn and the queue of
not-yet-started turns.
One stream's machinery lives in `converse_stream.py`, which `converse.py` re-exports from.

- A `UserTurn` runs one turn against `ClientEvent.session_id`. Each reply delta streams back as a
  `TextDelta`, a reasoning model's thinking as a `StatusUpdate` (ADR-0020), each audited dispatch
  as a `ToolActivity` plus the `ToolOutcome` closing it, and the turn ends with exactly one
  `TurnComplete{turn_id}`. A turn that spawns subagents also surfaces a
  `StatusUpdate{state="delegating"}` and a `ToolActivity` per subagent step, with no outcome, the
  pairing being about the turn's own dispatches (ADR-0029 decision 18). `UserTurn.images` go
  through `read_attachments` (`attached.py`) into the turn's `images` (ADR-0070); one it refuses
  ends the stream with `SeamError{code="attachment_refused"}` before the turn starts, so nothing
  is stored. The server accepts messages up to `MAX_TURN_MESSAGE_BYTES`, four images at their cap.
- **The stream names each turn before it starts it** (`TurnIdFactory`, ADR-0046 decision 9), when
  the turn starts rather than when it is queued, so the id is a fact about a turn that ran. The
  three mid-turn failures log `session_id` and `turn_id` and never the turn's text.
- Turns run one at a time per stream, but dispatch never blocks on the running turn: a `UserTurn`
  arriving mid-turn is queued, while later client events, a `Cancel` above all, are acted on at
  once. `Cancel` stops the in-flight turn and drops every queued-but-not-started turn, whose user
  message is never persisted; the stream stays open either way.
- Failures become exactly one terminal `SeamError{code, message}` and the stream then ends cleanly:
  `SessionStoreError` to `session_store_unavailable`, `InferenceError` to `inference_failed`, a
  refused attachment to `attachment_refused`, anything else to `internal` (`ERROR_CODE_*`).
  Client disconnect tears the turn down as `Cancel`
  does, and any pending confirmation dies with it as a denial.
- `RpcConfirmer(emit, *, timeout_s)` (`confirm.py`, ADR-0022) mints a `confirm_id`, emits
  `ServerEvent.confirm_request` on the stream's control path (`put_nowait`, so a stalled consumer
  cannot deadlock the ask) and awaits the matching `ConfirmResponse`. Timeout, client half-close
  and cancellation all deny, and unknown or repeated ids resolve nothing. The first two denials
  also emit `ServerEvent.confirm_resolved`, so the overlay can close a card it can no longer
  answer. Nothing is persisted, and `tests/confirmer_contract.py` holds the five checks every
  `Confirmer` owes, driven over this adapter and the core's `RecordingConfirmer`.
- `RpcProgressSink(emit, credit_sem, *, to_wire)` (`progress.py`, ADR-0010 decision 15) is the
  real `ProgressSink`. Unlike the confirmer's control path, `emit` is credit-balanced and best
  effort: it takes a buffer credit only when one is free right now, else drops the event, so a
  delegating turn's many steps cannot drift the bound and a stalled consumer loses cosmetic
  progress rather than stalling the subagent. Its `hold(wait)` keeps the stream's `TurnWaits`,
  whose innermost wait `current()` returns for the heartbeat. `EscalatingTurnEngine` is given the
  same sink, to hold each swap status it passes on.
- **The heartbeat** ([ADR-0069](../adr/ADR-0069-turn-heartbeat.md)): one task per stream waits
  `HEARTBEAT_PERIOD_MS` (30000) through the `Sleeper` port (`AsyncioSleeper` unless `sleeper` is
  given) and sends `ServerEvent.heartbeat` when a turn task is running and the output queue is
  empty, taking a buffer credit like the turn's events. So it is never dropped, never queued behind
  an unsent event, and never sent between turns. It contains the wait the stream's
  `RpcProgressSink.current()` reports, key and sentence, or neither when the turn waits on
  nothing (ADR-0069 decision 7). The body counts each one as a period of the turn's silence, and
  `crosscheck` compares this period with the body's copy.
- **Bounded backpressure**: at most `converse_buffer` events sit unread per stream, the turn's data
  path holding a credit per buffered event and returning it on dequeue, so a consumer that stops
  reading suspends generation at the bound. The terminal `SeamError` and teardown bypass the
  credits. What suspending generation costs other streams was measured 2026-08-08 and is a recorded
  deferral: the inference adapter holds the GPU lease for its generator's whole lifetime, so at a
  one-credit bound with the reader stalling 12 s that reply held the lease 16.52 s against the 2.2
  to 3.6 s an unstalled one holds it, and the next stream's history fold waited 16.51 s behind it.

## The composition root

`run_from_env()` reads the env configs, checks the delegation ordering as it reads it, and serves
with `RedisSessionStore.from_url`, `build_inference_backend`, `SystemClock`, the default-on history
window and output guardrail, and six opt-in adapters, each off by default so CI and the no-GPU dev
loop reach no external service: **memory** (`build_memory`, returning a recaller builder over a
given `InferenceBackend` and the model recall's judge asks, a `SessionMemoryCascade` for
`DeleteSession` and a closer), **tools** (`build_tool_registry`),
**subagents** (`build_subagents`), **body** (`build_body_gateway`), **schedules**
(`build_schedule`, with `build_schedule_tools` and a `ScheduleTicker` started beside `serve` and
stopped first in the `finally`), and the **brain handoff** (`build_swap_runtime`). Every adapter
returns a uniform closer, so the shutdown path is backend-agnostic, and `ORCHESTRATOR_VERSION` is
the version string `Health` reports.

- `build_inference_backend(config, cortex_model)` returns `EchoInferenceBackend` and a no-op
  closer, or `LlamaCppBackend` over a `SingleResidentModelManager` and the httpx client's `aclose`;
  `resolve_send_trace_budget` maps `CORTEX_INFERENCE_TRACE_LEVER` onto the bool the adapter holds,
  `auto` probing under `TRACE_BUDGET_PROBE_TIMEOUT_S` (5 s) and a server it cannot reach answering no.
  `build_generation_client(stall_timeout_s)` is the one place a generation client is built, shared
  with `build_subagents`: connect, write and pool take `LLAMACPP_CONNECT_TIMEOUT_S` (10 s) and the
  read phase takes the caller's per-tier ceiling, which httpx applies to one socket read, so it
  detects a stall rather than capping a generation.
- `build_history_window(runtime, *, sessions, backend, clock, model)` (`window_builders.py`)
  returns the char-budget window, `None` when the budget is `0`, or that window wrapped in
  `SummarizingHistoryWindow` whose recap `model` writes, and it is where `history_recap_min_chars` is clamped to the budget.
  `build_output_guardrail(mode)` takes the config's own `Literal`, so a name the config does not
  declare is a type error rather than a silently unguarded stream.
- `build_vision(config, body_config, body)` (`vision.py`, ADR-0029) resolves `CORTEX_VISION` into
  the `CaptureBounds` that say whether `capture_screen` may be registered at all and the
  `PropsVisionProbe` over `GET {endpoint}/props`, built only for `auto`. Every failure counts as no
  vision and logs a structured warning, and the answered line also names the engine, `/props`
  reporting the running build as `build_info` (ADR-0005 decision 9; the inference adapter logs the
  same string for every tier it streams from). The probe is asked per advertisement and per call,
  never remembered: a `llama-server` recreated without `--mmproj` mid-session used to keep
  advertising the tool, reproduced 2026-08-06 against the real stack. Asking costs 1.5 ms idle and
  1.7 ms with a generation in flight, worst of 40 samples 2.5 ms, so `PROBE_TIMEOUT_S` is 2 s.
- `ScheduleTicker(store, clock, settings, *, spawn=None, body=None)` (`ticker.py`, ADR-0025) is the
  stateless firing loop: each `run_once` claims what is due under the fencing lease, fires the
  batch together and persists each outcome. Both kinds deliver through one best-effort ladder over
  `BodyGateway.notify`, where shown means acked at once, naming the fire it pushed, while a
  declined, failed or absent body leaves the item deliverable for the pull path, and exactly one of
  the two ever clears the slot. A `TASK` dispatches a synthetic `spawn_subagents` call through the
  ticker's own audited dispatcher (`confirmer=None`, with the item's taint, origin `session_id` and
  `item_id` on the stamp) and delivers its outcome rather than the instruction itself. `run` wraps
  each pass in a logged catch-all and paces on an `asyncio.Event`, so a graceful stop completes
  in-flight fires and releases unfinished claims best effort.
- `build_tool_registry` gives each configured endpoint a lazy `ReconnectingMcpToolRegistry`,
  dialled on first use so a sidecar down at boot neither fails startup nor needs a restart to
  rejoin (ADR-0009 decision 9), wrapped innermost in a `BoundedToolRegistry`, then in a
  `FilteredToolRegistry` where an allowlist is set, then in a `SkipUnavailableToolRegistry` under
  `skip`, merged behind one `AggregateToolRegistry` when there are several, and outermost an
  `OwnTextToolRegistry` over `EMAIL_OWN_TEXTS` (`own_texts.py`, ADR-0013 decision 10).
- Every dispatcher is built from one `DispatchSetup` (`dispatch_builders.py`), the `DispatchPolicy`
  and the audit sink together. `build_builtin_tools` assembles the built-in set once: delegation,
  the two volume tools when a `BodyGateway` is wired, `capture_screen` when a body is wired **and**
  the root confirmed the running model can see, the five schedule tools, and `escalate_to_brain`
  only when a handoff can actually run. Those built-ins need no confirmation by default, a user
  naming any in `CORTEX_TOOLS_GATED`. Subagent dispatchers keep `confirmer=None` and their registry
  is wrapped in `ConfirmFreeToolRegistry`, so a subagent is never handed a confirmable tool.
- `StreamEngines.for_stream` (`engines.py`) is the engine factory, an object built once rather than
  closures over the root's locals. It reads no env, opens no resource and picks no adapter: per
  stream it builds that stream's `TurnCapabilities` and returns the plain `TurnEngine`, or an
  `EscalatingTurnEngine` over a `SwapConductor` bound to this stream's dispatcher when a
  `DeepTier(swap, builtins, scheduler)` is present, whose manager is then the capabilities'
  `residency`. With a `DeepTier`, the stream's cortex calls (the turn, the recap and recall's
  judge, which is why the recaller is built per stream) go through a `HandoffAheadBackend` over
  that manager and the stream's sink. The deep phase's recall judge and history recap ask the deep
  model over the plain backend, because its scope can lease no other model. That value keeps a
  handoff from being
  half-wired, the deep tier's own vision-less built-in set travelling with the runtime that swaps
  and the subagent pool the conductor drains.
- With escalation wired, `run_from_env` also runs `recover_handoffs` before serving, publishes what
  it observed about the cortex with `publish_boot_residency`, starts the `TierRechecker` after that
  publish, registers `escalate_to_brain`, hands the manager to `serve` as the wire's `residency`
  reporter, and passes the runtime into `StreamEngines` as its `DeepTier`. `swap_closer` releases
  the handoff store and the control client in the shutdown `finally`, the client even when the
  store's own release raises.

**Invariants.**

- Conversation state lives only in the session store: the service holds a turn's context solely
  while that turn is in flight, so a restart between turns loses nothing.
- Loopback by default; listening wider is an explicit env choice.
- Only `run_from_env` reads env or picks adapters; everything below receives ports, and server
  construction stays injectable for tests.
- Wire names are imported only through the `cortex_seam` facade, never from `_generated`.
- Fully typed, pyright strict clean, 100% line and branch coverage. The `__main__` guard is the
  only coverage pragma, which is why the logging decision lives in `config_logging.py`.
- The widest line each shipped sink can build still fits one message of the container's log driver,
  asserted in `tests/test_widest_line.py` (ADR-0051 decision 15). `cortex_core.VALUE_CHARS` bounds
  one rendered field and nothing bounds the line, so the question is how many fields a sink can
  make wide at once: five on the tool audit's eleven, one on the recall trail's twelve, and one on
  the three of each file sink's gap line, `tool.audit.gap` and `memory.recall.gap`. The check sits
  here because this is the one place that sees every sink the brain ships.

**Dependencies.** `cortex-core`, `cortex-body-client`, `cortex-inference`, `cortex-seam` and
`cortex-session` from the workspace, plus grpcio (`grpc.aio`), httpx, pydantic and
pydantic-settings.
