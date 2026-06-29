# brain/packages/orchestrator (`cortex_orchestrator`)

**Purpose.** The thin grpc.aio service hosting `BrainService` (the brain's end of the
seam), plus the composition root that wires the core's ports to real adapters. A shell
only: turn logic lives in `cortex_core.TurnEngine`; no conversation/task state may live
in this process beyond the in-flight turn (AGENTS.md hard rule).

**Public contract** (everything importable from `cortex_orchestrator`; `__all__` is the API):

Config (pydantic-settings; explicit constructor arguments beat the environment):

- `SeamServerConfig` uses env prefix `CORTEX_SEAM_`: `host: str = "127.0.0.1"`
  (`CORTEX_SEAM_HOST`), `port: int = 50051` (`CORTEX_SEAM_PORT`); `bind_address`
  property yields `"host:port"`. The body's live check dials the same endpoint via
  `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`). Keep the two in sync.
- `BrainRuntimeConfig` holds runtime wiring knobs, read only by the composition root:
  `redis_url: str = "redis://127.0.0.1:6379/0"` (`CORTEX_REDIS_URL`) and
  `cortex_model: str = "cortex"` (`CORTEX_MODEL_CORTEX`) is a LOGICAL model id
  (ADR-0004), never a file path.

The service:

- `BrainService(engine: TurnEngine)` is the `BrainServiceServicer` implementation;
  the engine is injected (DI at the edge), the service holds no state.
  - `Health` → `HealthReply(ready=True, detail="cortex-orchestrator <version>")`.
  - `Converse` is the conversation loop (contract below).
- `converse(engine, client_events) -> AsyncGenerator[ServerEvent, None]` is the loop
  itself, servicer-independent (what `BrainService.Converse` delegates to). Closing
  the generator tears down the stream's pump task, any in-flight turn, and the queue
  of not-yet-started turns. Teardown completes even when it races a client `Cancel`
  whose turn is still cleaning up.
- `ERROR_CODE_SESSION_STORE_UNAVAILABLE` / `ERROR_CODE_INFERENCE_FAILED` /
  `ERROR_CODE_INTERNAL` are the `SeamError.code` values (`"session_store_unavailable"`,
  `"inference_failed"`, `"internal"`).
- `create_server(config: SeamServerConfig, engine: TurnEngine) -> tuple[grpc.aio.Server, int]`
  builds the aio server, registers `BrainService(engine)`, binds `config.bind_address`;
  returns the not-yet-started server plus the actually-bound port (the OS pick when
  `port=0`; gRPC reports 0 if the bind failed).
- `serve(config: SeamServerConfig, engine: TurnEngine) -> None` (async) starts the
  server and blocks until SIGTERM/SIGINT or task cancellation; handlers for both signals
  are installed on the running loop for the server's lifetime (removed on exit) and
  trigger the same graceful stop as cancellation: in-flight RPCs drain for up to the 5 s
  grace before the listener closes. SIGTERM is what `docker compose down` delivers.
- `run_from_env() -> None` (async) is the composition root: reads both configs from the
  env and serves with `RedisSessionStore.from_url(redis_url)` + `EchoInferenceBackend`
  + `SystemClock`. **The echo backend IS the runtime inference backend until Slice 4
  delivers the real engine adapter** (docs/ROADMAP.md). Replies are the deterministic
  `"reply {n}: {text}"` script (see brain-core.md). The store's connections are released
  on the way out. Keyword-only `store_factory` exists for tests (fakeredis injection).
- `ORCHESTRATOR_VERSION` is the static version string `Health` reports.
- Entrypoint: `python -m cortex_orchestrator` runs `run_from_env()`; configuration is
  env-only, per AGENTS.md.

**Converse contract** (proto/body.proto `BrainService.Converse`, stream ↔ stream):

- `UserTurn` runs one `TurnEngine` turn against the session named by
  `ClientEvent.session_id`; each engine delta streams back as a `TextDelta` ServerEvent
  (the echo script yields at least 3), followed by exactly one `TurnComplete{turn_id}`.
  `UserTurn.images` are **ignored in this slice**, because multimodal input arrives with
  vision (Slice 10).
- Turns run one at a time per stream, but dispatch never blocks on the running turn:
  a `UserTurn` arriving mid-turn is queued and starts when the in-flight turn
  finishes, while later client events (a `Cancel` above all) are still acted on
  immediately.
- `Cancel` stops the current in-flight turn (if any) **and drops every
  queued-but-not-started turn**. The user asked to stop, so nothing not-yet-started
  runs; a dropped turn's user message is never persisted and it emits no events. A
  `Cancel` with nothing running is a no-op. Either way the stream **stays open** for
  the next `UserTurn`. Core semantics apply to the stopped turn: its user message
  stays persisted (it counts toward `n`), the partial reply is dropped, no
  `TurnComplete` is emitted for it.
- Failures become exactly one terminal `SeamError{code, message}` event, with
  `SessionStoreError` → `session_store_unavailable`, `InferenceError` →
  `inference_failed`, anything else → `internal`, after which the stream ends cleanly
  (gRPC status OK, no unhandled exception server-side; later client events on that
  stream are not acted upon). Client events without a known payload are ignored.
- Client disconnect / RPC cancellation tears down the in-flight turn the same way a
  `Cancel` does.

**Invariants.**
- Conversation state lives ONLY in the session store: the service holds a turn's
  context solely while that turn is in flight, so a process restart between turns loses
  nothing. `"reply {n}: …"` keeps counting across `docker compose restart brain`
  (the Slice 3 acceptance; see the runbook).
- Loopback by default (ROADMAP assumption 5); listening wider is an explicit env choice.
- DI at the edge: only `run_from_env` reads env/config and picks adapters; everything
  below receives ports. Server construction stays injectable for tests.
- Seam names are imported only via the `cortex_seam` facade, never from `_generated`.
- Fully typed, pyright strict clean; 100% line+branch coverage. The `__main__` guard is
  the only coverage pragma. Tests are loopback-only (ephemeral ports, fakeredis), CI-safe.

**Dependencies.** cortex-core, cortex-seam, cortex-session (workspace), grpcio
(`grpc.aio`), pydantic, pydantic-settings.
