# brain/packages/orchestrator (`cortex_orchestrator`)

**Purpose.** The thin grpc.aio service hosting `BrainService` (the brain's end of the
seam), plus the composition root that wires the core's ports to real adapters (the
per-capability `build_*` factories in `builders.py`, the root `run_from_env` in
`wiring.py`). A shell only: turn logic lives in `cortex_core.TurnEngine`; no
conversation/task state may live in this process beyond the in-flight turn (AGENTS.md
hard rule).

**Public contract** (everything importable from `cortex_orchestrator`; `__all__` is the API):

Config (pydantic-settings; explicit constructor arguments beat the environment):

- `SeamServerConfig` uses env prefix `CORTEX_SEAM_`: `host: str = "127.0.0.1"`
  (`CORTEX_SEAM_HOST`), `port: int = 50051` (`CORTEX_SEAM_PORT`); `bind_address`
  property yields `"host:port"`. The body's live check dials the same endpoint via
  `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`). Keep the two in sync.
  `token: str = ""` (`CORTEX_SEAM_TOKEN`, ADR-0016) is the shared seam secret; set, it
  makes every RPC require the matching `x-cortex-seam-token` metadata (the body reads
  the same env var), empty disables the check (loopback-only remains the boundary).
  `converse_buffer: int = 256` (`CORTEX_SEAM_CONVERSE_BUFFER`, positive) bounds how many
  `ServerEvent`s one Converse stream buffers unread before generation stalls
  (backpressure, below).
- `BrainRuntimeConfig` holds runtime wiring knobs, read only by the composition root:
  `redis_url: str = "redis://127.0.0.1:6379/0"` (`CORTEX_REDIS_URL`);
  `cortex_model: str = "cortex"` (`CORTEX_MODEL_CORTEX`) is a LOGICAL model id (ADR-0004), never a
  file path; and the GPU-budget facts the `SubagentPlacer` fit-tests against (ADR-0012):
  `vram_soft_cap_gb: float = 14.0` (`CORTEX_VRAM_SOFT_CAP_GB`, the deliberate soft cap, ADR-0004) and
  `cortex_reservation_gb: float = 11.3` (`CORTEX_VRAM_CORTEX_GB`, the resident cortex's footprint);
  `history_char_budget: int = 48000` (`CORTEX_HISTORY_CHAR_BUDGET`, ADR-0014) sets how many
  characters of session history one turn sends to the model (the newest whole turns;
  `0` disables windowing, negative rejected);
  `output_guardrail: "redact" | "strict" | "off" = "redact"` (`CORTEX_OUTPUT_GUARDRAIL`,
  ADR-0015) is the model-independent laundering defense: `redact` (default) scrubs
  verbatim-untrusted-sourced URLs from the reply the user sees, `strict` (addendum) scrubs
  every non-user URL on a tainted turn, `off` restores the unguarded stream.
- `InferenceConfig` uses env prefix `CORTEX_INFERENCE_`: which backend answers turns
  (ADR-0007 d4). `backend: "echo" | "llamacpp" = "echo"` (`CORTEX_INFERENCE_BACKEND`) and
  `endpoint: str = ""` (`CORTEX_INFERENCE_ENDPOINT`, the resident `llama-server` base
  URL). Validates that `llamacpp` has a non-empty `endpoint`. Echo is the GPU-less
  default (CI + no-GPU dev); `llamacpp` is opt-in, set by `docker/docker-compose.gpu.yml`.
- `MemoryConfig` uses env prefix `CORTEX_MEMORY_` (ADR-0008): `backend: "none" | "pgvector" =
  "none"` (`CORTEX_MEMORY_BACKEND`), `dsn: str = ""` (`CORTEX_MEMORY_DSN`),
  `embedder_endpoint: str = ""` (`CORTEX_MEMORY_EMBEDDER_ENDPOINT`), `embedder_model: str`
  (`CORTEX_MEMORY_EMBEDDER_MODEL`). Validates that `pgvector` has both a DSN and an
  embedder endpoint. Set by `docker/docker-compose.memory.yml`.
- `ToolsConfig` uses env prefix `CORTEX_TOOLS_`, nested delimiter `__` (ADR-0009 + refinements
  addendum): `backend: "none" | "mcp" = "none"` (`CORTEX_TOOLS_BACKEND`); endpoints in one of
  two forms, either the singular `endpoint: str = ""` (`CORTEX_TOOLS_ENDPOINT`, one streamable-http
  MCP URL) or per-sidecar `endpoints: dict[str, str]` (`CORTEX_TOOLS_ENDPOINTS__<name>=<url>`,
  one env var per sidecar so layered compose overrides merge key-wise); and per-endpoint
  allowlists `allow: dict[str, tuple[str, ...]]` (`CORTEX_TOOLS_ALLOW__<name>=<JSON name
  list>`). `named_endpoints` is the effective roster, **sorted by name** (deterministic
  aggregate precedence; the singular form becomes the sole entry `"default"`). Validates that
  `mcp` has at least one endpoint, that both forms are not mixed (ambiguity fails closed), and
  that every allowlist names a configured endpoint. Set by `docker/docker-compose.tools.yml`
  / `docker-compose.email.yml`. Layer both and both tool families are live at once.
  `on_unavailable: "fail" | "skip" = "fail"` (`CORTEX_TOOLS_ON_UNAVAILABLE`) picks the
  dead-sidecar policy: `fail` keeps listing loud; `skip` wraps each endpoint in
  `SkipUnavailableToolRegistry` so healthy sidecars keep serving while the dead one is
  logged on every walk (ADR-0009 degraded-mode addendum; covers a sidecar dying after
  startup, though one down at boot still fails the MCP connect).
- `SubagentsConfig` uses env prefix `CORTEX_SUBAGENTS_` (ADR-0010, revised by ADR-0012/0018):
  `backend: "none" | "llamacpp" = "none"` (`CORTEX_SUBAGENTS_BACKEND`), `endpoint` (the CPU
  overflow `llama-server`) **and** `gpu_endpoint` (the GPU one), which are both required when
  `llamacpp`; `model` (`CORTEX_SUBAGENTS_MODEL`); one subagent's resource ask `vram_gb` /
  `cpus` / `memory_gb` and the soft admission ceilings `cpu_budget` / `mem_budget_gb`
  (defaults are GPU-less-safe placeholders; the maintainer measures real numbers on the host).
  Set by `docker/docker-compose.subagents.yml`. The flat fields define the roster's
  **default entry** (the robust ADR-0004 pick; `model_description` /
  `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` is its advertised text); each
  `CORTEX_SUBAGENTS_ROSTER__<name>` adds one **alternate** model as a JSON
  `SubagentRosterEntry` (`endpoint` required; `gpu_endpoint` empty falls back to it;
  per-entry `vram_gb`/`cpus`/`memory_gb`; `description` advertised verbatim, per ADR-0018, set
  by `docker/docker-compose.subagents-roster.yml`). A key naming the default is rejected.
  `named_roster` (property) synthesizes the ready-to-dial mapping, with the flat-field default
  first, alternates sorted, fallbacks applied; empty unless `backend="llamacpp"`.

The service:

- `BrainService(engine: TurnEngine, store: SessionStore, *, max_buffered_events: int = 256)`
  is the `BrainServiceServicer` implementation; the engine and the session store are injected
  (DI at the edge), the service holds no state. `store` is the same instance the engine
  writes, so the read-only session RPCs serve exactly what turns persist.
  - `Health` → `HealthReply(ready=True, detail="cortex-orchestrator <version>")`.
  - `Converse` is the conversation loop (contract below).
  - `ListSessions` → `ListSessionsReply` (ADR-0021): recent chats newest-active first via
    `store.list_sessions`, each a `SessionSummary` (title/preview/last_activity mapped to the
    wire, timestamps as unix-ms). `request.limit` is clamped by `_clamp_limit` (0/negative →
    `DEFAULT_SESSION_LIST_LIMIT`, capped at `MAX_SESSION_LIST_LIMIT`).
  - `GetSessionMessages` → `GetSessionMessagesReply` (ADR-0021): one session's persisted
    history via `store.history`, each a wire `SessionMessage`; unknown session → empty.
  - Both read RPCs are unary; a `SessionStoreError` aborts them `UNAVAILABLE` (the body maps
    that to `TransportError::Rpc`). They add no write path, only reads over existing state.
- `DEFAULT_SESSION_LIST_LIMIT = 50` / `MAX_SESSION_LIST_LIMIT = 200` are the `ListSessions`
  limit default and hard cap (ADR-0021).
- `converse(engine, client_events, *, max_buffered_events=DEFAULT_MAX_BUFFERED_EVENTS)
  -> AsyncGenerator[ServerEvent, None]` is the loop itself, servicer-independent (what
  `BrainService.Converse` delegates to). Closing the generator tears down the stream's
  pump task, any in-flight turn, and the queue of not-yet-started turns. Teardown
  completes even when it races a client `Cancel` whose turn is still cleaning up, and
  even while the turn is blocked on a buffer credit.
- `DEFAULT_MAX_BUFFERED_EVENTS = 256` is the default Converse buffer bound
  (`SeamServerConfig.converse_buffer` feeds the deployed value through `create_server`).
- `ERROR_CODE_SESSION_STORE_UNAVAILABLE` / `ERROR_CODE_INFERENCE_FAILED` /
  `ERROR_CODE_INTERNAL` are the `SeamError.code` values (`"session_store_unavailable"`,
  `"inference_failed"`, `"internal"`).
- `create_server(config: SeamServerConfig, engine: TurnEngine, store: SessionStore) -> tuple[grpc.aio.Server, int]`
  builds the aio server, registers `BrainService(engine, store)`, binds `config.bind_address`;
  returns the not-yet-started server plus the actually-bound port (the OS pick when
  `port=0`; gRPC reports 0 if the bind failed). With `config.token` set it registers the
  `SeamTokenInterceptor` (ADR-0016, `auth.py`): every RPC, unary and streaming, current
  and future, must carry the matching `x-cortex-seam-token` metadata (`SEAM_TOKEN_HEADER`)
  or is aborted `UNAUTHENTICATED` before the servicer runs (constant-time compare, rejection
  shaped to the method). Empty token = no interceptor, the previous server byte for byte.
- `serve(config: SeamServerConfig, engine: TurnEngine, store: SessionStore) -> None` (async)
  starts the server and blocks until SIGTERM/SIGINT or task cancellation; handlers for both signals
  are installed on the running loop for the server's lifetime (removed on exit) and
  trigger the same graceful stop as cancellation: in-flight RPCs drain for up to the 5 s
  grace before the listener closes. SIGTERM is what `docker compose down` delivers.
- `build_inference_backend(config: InferenceConfig, cortex_model: str) -> tuple[InferenceBackend, Callable[[], Awaitable[None]]]`
  picks the backend from config and returns it with the coroutine that releases it:
  `EchoInferenceBackend` + a no-op closer, or `LlamaCppBackend` over a
  `SingleResidentModelManager(cortex_model, endpoint)` + the httpx client's `aclose`
  (short connect timeout, no read deadline). The uniform closer keeps `run_from_env`'s
  shutdown path backend-agnostic.
- `build_history_window(char_budget: int) -> CharBudgetHistoryWindow | None` is the turn's
  history window (ADR-0014): a positive budget returns the char-budget window, `0` returns
  `None` (windowing off). On by default via `BrainRuntimeConfig.history_char_budget`.
- `build_output_guardrail(mode: str) -> UrlRedactingGuardrail | StrictUrlRedactingGuardrail | None`
  is the turn's output guardrail (ADR-0015): `redact` returns the default verbatim URL-redacting
  policy, `strict` (addendum) the redact-all-non-user-URL policy, `off` returns `None`. On by
  default via `BrainRuntimeConfig.output_guardrail`.
- `run_from_env() -> None` (async) is the composition root: reads the env configs and serves
  with `RedisSessionStore.from_url(redis_url)`, `build_inference_backend(...)`, `SystemClock`,
  the default-on history window (`build_history_window`, ADR-0014) and output guardrail
  (`build_output_guardrail`, ADR-0015),
  and three opt-in adapters, each disabled by default so CI and the no-GPU dev loop stay
  external-service-free: **memory** (`build_memory`, ADR-0008), **tools** (`build_tool_registry`
  builds the MCP `ToolRegistry` shared by cortex and subagents, ADR-0009: one `McpToolRegistry` per
  configured endpoint, wrapped in a `FilteredToolRegistry` where an allowlist is set, in a
  `SkipUnavailableToolRegistry` reporting through a structured warning when
  `on_unavailable="skip"`, and merged behind one `AggregateToolRegistry` when several, with every
  session owned by one `AsyncExitStack` whose `aclose` is the returned closer, and a failed
  later connect unwinds the earlier sessions), and **subagents**
  (`build_subagents(config, tool_registry, redis_url, clock, *, placer, task_store_factory)`,
  in `subagent_builders.py` (split from `builders.py` for the 300-line cap), the
  `spawn_subagents` tool over a `SubagentRoster` built from `config.named_roster` (ADR-0018):
  per entry its own GPU + CPU `LlamaCppBackend` pair (one shared httpx client) and
  `PlacementRequest`, all entries sharing ONE `ResourceBudgetScheduler` and the ONE
  `VramBudgetPlacer` built at the call site from the runtime VRAM knobs (one budget, one
  ledger, per ADR-0012), a Redis `TaskStore`, GPU-first placement with CPU overflow,
  ADR-0010/0012; the runner enforces ADR-0017 via `roster.resolve`; the subagent dispatcher
  comes from `build_subagent_tools(tool_registry, clock)`, the shared registry wrapped in
  `UngatedToolRegistry`, so a subagent is never handed a gated/outbound tool, ADR-0013
  subagent-exclusion addendum). The cortex's dispatcher is
  `build_cortex_tools(registry, spawn_tool, clock)`, the spawn tool merged with the MCP tools
  via a `CompositeToolRegistry`, or `None` when neither is enabled (the Slice 3 turn path). Its
  `ToolDispatcher` takes the default `confirmer=None` (ADR-0013): fail-closed, so a gated tool on a
  tainted turn is denied. No tool is gated today; the real overlay confirmer adapter is wired here
  with the first outbound tool (Slice 9/10).
  **Echo is the default inference backend; llama.cpp is opt-in via
  `CORTEX_INFERENCE_BACKEND=llamacpp`** (ADR-0007), so the deterministic `"reply {n}: {text}"`
  script (brain-core.md) runs in CI. Every adapter's resources are released on the way out.
  Keyword-only `store_factory` exists for tests (fakeredis injection).
- `ORCHESTRATOR_VERSION` is the static version string `Health` reports.
- Entrypoint: `python -m cortex_orchestrator` runs `run_from_env()`; configuration is
  env-only, per AGENTS.md.

**Converse contract** (proto/body.proto `BrainService.Converse`, stream ↔ stream):

- `UserTurn` runs one `TurnEngine` turn against the session named by
  `ClientEvent.session_id`; each engine reply delta streams back as a `TextDelta` ServerEvent
  (the echo script yields at least 3), a reasoning model's thinking as a `StatusUpdate`
  (ADR-0020, `state="thinking"`), followed by exactly one `TurnComplete{turn_id}`.
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
- **Bounded backpressure** (the Slice-3 deferral, landed 2026-07-03): at most
  `converse_buffer` events sit unread per stream. The turn's data path holds a credit
  per buffered event (returned on dequeue), so a consumer that stops reading suspends
  generation at the bound instead of growing an unbounded buffer. The terminal
  `SeamError` and stream teardown bypass the credits: failure reporting never blocks
  behind a full buffer, whatever the consumer does.

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

**Dependencies.** cortex-core, cortex-inference, cortex-seam, cortex-session (workspace),
grpcio (`grpc.aio`), httpx (the injected client for the llama.cpp backend), pydantic,
pydantic-settings.
