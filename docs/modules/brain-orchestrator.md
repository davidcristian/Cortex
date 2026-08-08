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
  (backpressure, below). `confirm_timeout_s: float = 120.0`
  (`CORTEX_SEAM_CONFIRM_TIMEOUT_S`, positive, ADR-0022) bounds how long a gated tool call
  awaits the user's `ConfirmResponse` before it is denied (fail-closed).
- `BrainRuntimeConfig` holds runtime wiring knobs, read only by the composition root:
  `redis_url: str = "redis://127.0.0.1:6379/0"` (`CORTEX_REDIS_URL`);
  `cortex_model: str = "cortex"` (`CORTEX_MODEL_CORTEX`) is a LOGICAL model id (ADR-0004), never a
  file path; and the GPU-budget facts the `SubagentPlacer` fit-tests against (ADR-0012):
  `vram_soft_cap_gb: float = 14.0` (`CORTEX_VRAM_SOFT_CAP_GB`, the deliberate soft cap, ADR-0004) and
  `cortex_reservation_gb: float = 8.6` (`CORTEX_VRAM_CORTEX_GB`, the resident cortex's footprint,
  re-measured 2026-08-07 at the shipped tier shape and lowered from 11.3, which was a total-used
  reading with the desktop's own floor inside it; the tier peaks at 8573 MiB above the floor and the
  reservation keeps 233 MiB over that, leaving 5.4 GiB of subagent headroom where there was 2.7,
  ADR-0012 re-measured-reservation addendum);
  `history_char_budget: int = 48000` (`CORTEX_HISTORY_CHAR_BUDGET`, ADR-0014) sets how many
  characters of session history one turn sends to the model (the newest whole turns;
  `0` disables windowing, negative rejected);
  `history_summary: bool = True` (`CORTEX_HISTORY_SUMMARY`, ADR-0038 decision 9) recaps the
  turns the window drops instead of losing them, and is ignored when the budget is `0`. It
  defaults ON since 2026-08-06 (ADR-0038 cheap-fold addendum), the user's standing decision
  carried by the numbers that had twice held it back: a fold now decodes 61 to 163 tokens rather
  than 400 to 850, costs 2.9 s to 6.2 s with no tail, announces itself on screen, and over five
  compounding folds the fact a question needed survived 3 times of 3. Set it `false` to prefer
  forgetting over waiting;
  `history_recap_min_chars: int = 2000` (`CORTEX_HISTORY_RECAP_MIN_CHARS`, same addendum) is how
  much newly dropped conversation is worth a fold's model pass; below it the fold waits for the
  next boundary move, which reads everything deferred since. `0` folds on every move, negative
  rejected, and the builder clamps it to the character budget;
  `output_guardrail: "redact" | "strict" | "off" = "redact"` (`CORTEX_OUTPUT_GUARDRAIL`,
  ADR-0015) is the model-independent laundering defense: `redact` (default) scrubs
  verbatim-untrusted-sourced URLs from the reply the user sees, `strict` (addendum) scrubs
  every non-user URL on a tainted turn, `off` restores the unguarded stream;
  `generate_titles: bool = False` (`CORTEX_GENERATE_TITLES`, ADR-0021 titles addendum) opts a
  deployment into brain-generated switcher titles (one extra inference call per new session, and a
  cheap one since the pass asks for no thinking and at most 32 tokens, ADR-0038 bounded-side-calls
  addendum; a model that answers with nothing usable still leaves the first-message derivation
  standing), threaded into `TurnCapabilities.generate_titles`.
- `InferenceConfig` uses env prefix `CORTEX_INFERENCE_`: which backend answers turns
  (ADR-0007 d4). `backend: "echo" | "llamacpp" = "echo"` (`CORTEX_INFERENCE_BACKEND`) and
  `endpoint: str = ""` (`CORTEX_INFERENCE_ENDPOINT`, the resident `llama-server` base
  URL). Validates that `llamacpp` has a non-empty `endpoint`. Echo is the GPU-less
  default (CI + no-GPU dev); `llamacpp` is opt-in, set by `docker/docker-compose.gpu.yml`.
  `vision: "auto" | "on" | "off" = "auto"` (`CORTEX_VISION`, note the bare name rather than the
  prefix, ADR-0029) decides whether `capture_screen` is advertised: `auto` probes the running
  server, `on`/`off` fix the answer for CI, for a deterministic test, and for a user who
  wants capture off without editing compose.
- `MemoryConfig` uses env prefix `CORTEX_MEMORY_` (ADR-0008): `backend: "none" | "pgvector" =
  "none"` (`CORTEX_MEMORY_BACKEND`), `dsn: str = ""` (`CORTEX_MEMORY_DSN`),
  `embedder_endpoint: str = ""` (`CORTEX_MEMORY_EMBEDDER_ENDPOINT`), `embedder_model: str`
  (`CORTEX_MEMORY_EMBEDDER_MODEL`), `scope: "global" | "session" = "global"`
  (`CORTEX_MEMORY_SCOPE`, scoping addendum), `on_tainted: "skip" | "record" = "skip"`
  (`CORTEX_MEMORY_ON_TAINTED`, ADR-0019), and `recall: "raw" | "reranked" | "mmr" | "recency_mmr" |
  "judge" = "raw"` (`CORTEX_MEMORY_RECALL`, rerank + MMR + recency-and-diversity addenda,
  ADR-0038) with its
  `recall_half_life_days` (30), `recall_recency_weight` (0.3), `recall_dedup_threshold` (0.98),
  `recall_pool_factor` (4), and `recall_mmr_lambda` (0.5, the MMR relevance-vs-diversity dial) tuning
  knobs (`recency_mmr` reuses the recency and lambda knobs, `judge` reuses the pool factor and, since
  its request was bounded, costs about 0.9 s per recall rather than 12, which is why its default is
  under review rather than settled, ADR-0038 bounded-side-calls addendum; `judge` is also the only
  value under which a recall may return **nothing**, the model having read the pool and declined it,
  ADR-0038 abstention addendum), plus
  `recall_audit: bool = False` (`CORTEX_MEMORY_RECALL_AUDIT`, ADR-0038) attaching the structured
  recall trail. `recall_policy_from_config(config, backend, cortex_model)` maps the string to the
  policy (the model rank is a policy over the inference port, which is why `build_memory` now takes
  that port and the cortex id) and `recall_audit_from_config(config)` maps the flag to
  `LoggingRecallSink` or to `None`. Validates that
  `pgvector` has both a DSN and an embedder endpoint. Set by `docker/docker-compose.memory.yml`.
- `ToolsConfig` uses env prefix `CORTEX_TOOLS_`, nested delimiter `__` (`config_tools.py`, split
  off at `config.py`'s line cap as the third dispatch declaration landed; ADR-0009 + refinements
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
  logged on every walk (ADR-0009 degraded-mode addendum; now covers a sidecar down at *any*
  time; sessions open per call, so one down at boot no longer fails startup and a recovered
  one rejoins without a restart, ADR-0009 boot-tolerance addendum).
  `costs: dict[str, int]` (`CORTEX_TOOLS_COSTS__<name>=<int>`, ADR-0009 cost addendum) prices a
  tool against a tool loop's dispatch budget; anything unpriced costs 1. `cost_policy` is the
  effective `ToolCostPolicy` the dispatchers take: it merges the built-in prices **under** the
  user's, because a nested-dict env key replaces the whole mapping, so a built-in kept as the
  field default would vanish the moment a user priced an unrelated tool. Built in is
  `spawn_subagents` at `DEFAULT_SPAWN_COST` (`MAX_TOOL_DISPATCHES // 4`, four delegations a
  turn, each of at most `MAX_SPAWN_BATCH` subtasks): it is the one wired tool whose single
  dispatch fans out into a batch of model runs and
  the one with no confirmation gate ahead of it, whereas `send_email` is deliberately unpriced
  since its ADR-0022 confirmation is the tighter bound. A price outside `1..MAX_TOOL_DISPATCHES`
  fails at boot (free stops bounding the tool; unaffordable means it can never run).
  `salience: "repeat" | "off" = "repeat"` (`CORTEX_TOOLS_SALIENCE`, ADR-0009 salience addendum)
  picks which calls a tool loop bothers dispatching: `repeat` refuses a call the loop has already
  made (once per round, twice per loop), `off` is the unfiltered loop. `salience_policy` maps the
  string to the core policy object (the `record_tainted_memory` precedent).
  `gated: tuple[str, ...]` (`CORTEX_TOOLS_GATED`, ADR-0022) defaults to
  `(ESCALATE_TOOL_NAME, "send_email")`: the email fail-closed pairing, plus the escalate
  built-in as the dispatcher-side backstop behind that tool's own always-gated advertised flag
  (ADR-0030; emptying the list does not ungate the escalate spec itself).
  `gate_reasons: dict[str, str]` (`CORTEX_TOOLS_GATE_REASONS__<name>=<text>`, ADR-0030
  decision 1) sets one gated tool's confirm-card reason where the generic
  outbound/irreversible line would be false; a blank text fails at boot, and `gate_reason_map`
  merges the built-in `escalate_to_brain` swap reason (`ESCALATE_GATE_REASON`) **under** the
  user's, the `cost_policy` merge argument exactly. `dispatch_policy`
  bundles all four declarations (`gated` + `cost_policy` + `salience_policy` +
  `gate_reason_map`) into the one
  `DispatchPolicy` value every dispatcher in the process is built with.
- `SwapConfig` uses env prefix `CORTEX_` (`config_swap.py`, ADR-0030), the brain handoff's one
  switch and the topology it enables: `escalation: bool = False` (`CORTEX_ESCALATION`) gates the
  whole capability, so CI and the GPU-less loop are byte for byte what they were without it;
  `modelhost_backend: "none" | "scripted" | "supervisor" = "none"`
  (`CORTEX_MODELHOST_BACKEND`) says who owns the model processes, where `scripted` is the in-core
  `ScriptedModelHost` (honest residency, no process started, no weights moved) and `supervisor`
  is the real `HttpModelHost` over the `model-host` sidecar's control API at
  `CORTEX_MODELHOST_ENDPOINT` (required with it, and the one thing that makes a swap move actual
  weights, [brain-model-manager.md](brain-model-manager.md)); `modelhost_timeout_s`
  (`CORTEX_MODELHOST_TIMEOUT_S`, 60 s) bounds one control call and must stay **above** the
  sidecar's own `stop` worst case (its SIGTERM grace plus its SIGKILL reap bound), since a stop
  answers only once the child is reaped; `brain_model` (`CORTEX_MODEL_BRAIN`, default `brain`) and
  `brain_endpoint`
  (`CORTEX_BRAIN_ENDPOINT`) are the deep tier's logical id and base URL; `evict_models`
  (`CORTEX_SWAP_EVICT_MODELS`) names further hosted tiers a swap must stop first (while the deep
  model is resident it is alone on the GPU) and start again on the way back, since those tiers
  are part of the standing residency every exit path converges to; `coresident`
  (`CORTEX_SWAP_CORESIDENT`, **off**) reverses that one rule, leaving those tiers serving through
  the handoff and skipping the drain window entirely, which is the deployment asserting its card
  holds the pair (ADR-0030's co-residency addendum has the measurement); `brain_vram_mib`
  (`CORTEX_SWAP_BRAIN_VRAM_MIB`, 0) is the free device memory that deep tier needs, measured on
  the deployment's own card, which the swap compares against the model host's reading immediately
  before the load and refuses the handoff when it is short; `swap_drain_timeout_s` (60 s) and
  `swap_load_timeout_s` (300 s) are the swap's two bounds. Enabling escalation without a model
  host or without a brain endpoint **fails at boot**, rather than advertising a tool that could
  only refuse, and so does co-residency on the `supervisor` host with no measured VRAM figure,
  since that flag is a claim about a card and this is the only thing that ever tests it (the
  card itself is read at the swap, being a number that moves while the machine runs). `residency_plan(cortex_model)` is the one `ResidencyPlan` the manager, the
  conductor, and boot recovery all read.
- `SubagentsConfig` uses env prefix `CORTEX_SUBAGENTS_` (ADR-0010, revised by ADR-0012/0018):
  `backend: "none" | "llamacpp" = "none"` (`CORTEX_SUBAGENTS_BACKEND`), `endpoint` (the CPU
  overflow `llama-server`) **and** `gpu_endpoint` (the GPU one), which are both required when
  `llamacpp`; `model` (`CORTEX_SUBAGENTS_MODEL`); one subagent's resource ask `vram_gb` /
  `cpus` / `memory_gb` and the soft admission ceilings `cpu_budget` / `mem_budget_gb`
  (`vram_gb` defaults to the measured **3.5** GiB, above the 3338 to 3410 MiB the GPU-placed tier
  costs at its shipped shape, so one spawn fits the 5.4 GiB headroom and the next overflows,
  ADR-0012 measured-ask addendum; the rest are GPU-less-safe placeholders the maintainer measures
  on the host). Set by `docker/docker-compose.subagents.yml`, which declares the same 3.5 and is
  tied to this default by nothing but the two comments that say so. The flat fields define the roster's
  **default entry** (the robust ADR-0004 pick; `model_description` /
  `CORTEX_SUBAGENTS_MODEL_DESCRIPTION` is its advertised text); each
  `CORTEX_SUBAGENTS_ROSTER__<name>` adds one **alternate** model as a JSON
  `SubagentRosterEntry` (`endpoint` required; `gpu_endpoint` empty falls back to it;
  per-entry `vram_gb`/`cpus`/`memory_gb`; `description` advertised verbatim, per ADR-0018, set
  by `docker/docker-compose.subagents-roster.yml`). A key naming the default is rejected.
  `named_roster` (property) synthesizes the ready-to-dial mapping, with the flat-field default
  first, alternates sorted, fallbacks applied; empty unless `backend="llamacpp"`. Every entry in
  it must fit the whole budget (`cpus <= cpu_budget` and `memory_gb <= mem_budget_gb`, equality
  allowed since such an entry runs alone), else construction fails: the scheduler could only ever
  refuse that spawn, and a subagent the machine may never run is a wiring error, not a runtime
  result (ADR-0012 admission-wall addendum).
- `BodyConfig` uses env prefix `CORTEX_BODY_` (ADR-0023, Slice 9 brings the first brain→body seam
  direction, the brain as gRPC client of the host body's `BodyService`): `backend: "none" |
  "grpc" = "none"` (`CORTEX_BODY_BACKEND`), `endpoint: str = ""` (`CORTEX_BODY_ENDPOINT`, the
  host body's bind, `host.docker.internal:50151` from the dockerized brain), plus three
  screen-capture knobs (ADR-0029): `capture_max_edge: int = 2048` and `max_image_bytes: int =
  MAX_IMAGE_BYTES` (6 MiB) are what the brain asks the body for **and** holds the reply to,
  since the body clamps both and an older body ignores both. The edge defaults above the body's
  own 1600 because the pixels are only worth sending when the model host's
  `CORTEX_IMAGE_MAX_TOKENS` gives the encoder somewhere to put them, which is a number this side
  knows and the body does not; `0` still means "the body's own default".
  `capture_timeout_s: float = 10.0`
  is the only deadline on this seam, because a blit plus an encode is the only call that can
  park a host thread. All three are **bounded so a misconfiguration fails at boot** rather than
  turning every capture into a turn-killing exception: `capture_max_edge` `ge=0, le=8192` and
  `max_image_bytes` `gt=0, le=6291456` (it may tighten the domain ceiling, never loosen it, the
  body clamping to its own regardless), both because the pair rides uint32 proto fields, and
  `capture_timeout_s` `gt=0`. Validates that
  `grpc` has a non-empty `endpoint`. Off by default (CI + no-GPU dev never dial a host body);
  the shared `CORTEX_SEAM_TOKEN` (SeamServerConfig, not a `CORTEX_BODY_` var) authenticates the
  dial.
- `ScheduleConfig` uses env prefix `CORTEX_SCHEDULE_` (`config_schedule.py`, ADR-0025): `backend:
  "none" | "redis" = "none"` (off by default, with no store, no built-ins, no ticker, and the
  reminder pull RPCs answer benignly empty), `poll_s: float = 5.0` (the ticker's pass
  interval), `lease_s: float = 300.0` (how long a claimed fire may run before it is
  re-claimable, so keep it above the slowest expected task), `claim_limit: int = 8` (one pass's
  batch cap), `max_active: int = 32` (the `schedule_task` creation bound). All positive,
  validated. `tz: str = "UTC"` is the IANA key model-facing schedule times render in
  (ADR-0025 display addendum), field-validated at boot so a typo fails the process rather than
  the first listing; `display_zone()` resolves it to the core's `DisplayZone` for
  `build_schedule_tools` to thread into `schedule_task` / `list_scheduled` /
  `snooze_scheduled`. Both `_resolve` (boot, raises) and the model-facing per-rule `in_zone`
  path (runtime, returns `None`) go through the one `zoneinfo`-backed `ZoneInfoResolver`
  (`cortex_session`); `build_schedule_tools` bundles it with the default zone into a
  `ZoneContext` for the two rule-parsing tools, the same resolver the codec decodes stored zones
  with (ADR-0025 per-rule addendum). `"UTC"` short-circuits to `UTC_DISPLAY` without touching the
  tz database. The store dials `CORTEX_REDIS_URL` (BrainRuntimeConfig), with no second URL knob.

The service:

- `BrainService(make_engine: EngineFactory, store: SessionStore, *, ports: SeamPorts = SeamPorts(),
  max_buffered_events: int = 256, confirm_timeout_s: float = …)`
  is the `BrainServiceServicer` implementation; the engine factory, the session store, and the
  optional `SeamPorts` are injected (DI at the edge), the service holds no state. `store` is the
  same instance the engine writes, so the read-only session RPCs serve exactly what turns persist.
  `SeamPorts(schedules=None, memory_cascade=None, residency=None)` is the frozen bundle of what
  the seam serves **beyond** a turn, each absent when its capability is off: `schedules` backs
  the reminder RPCs, `memory_cascade` (the same store+scope the recaller uses) is what
  `DeleteSession` forgets a deleted chat's private memories through, and `residency` is the
  `ResidencyReporter` `Health` reads. They travel as one value because the dependency ceiling
  (ruff.toml) asks optional collaborators to be bundled, as `TurnCapabilities` is for a turn.
  - `Health` → `HealthReply(ready=True, detail="cortex-orchestrator <version>")` whenever the
    standing residency is serving, **and `HealthReply(ready=False, detail=<the residency's own
    line>)` while a model handoff holds the GPU** (ADR-0030 decision 6): loading the deep model,
    the deep task itself, the swap back, a restore that gave up, and a boot whose recovery could
    not settle the cortex. The read is
    `ResidencyReporter.residency()`, synchronous and lock-free by that port's contract, because
    a probe arrives every few seconds precisely while a swap is in flight and one that queued on
    the GPU lease would hang for the whole load. With no `residency` wired (escalation off, the
    default) nothing can make the brain not-ready and the answer is unconditional, as it always
    was. The **drain** before an eviction is deliberately still ready: the cortex is resident and
    answering turns throughout it. The overlay classifies not-ready as amber `Degraded` and shows
    the detail verbatim, with no overlay change (body-core.md, body-app.md).
  - `Converse` is the conversation loop (contract below).
  - `ListSessions` → `ListSessionsReply` (ADR-0021): recent chats newest-active first via
    `store.list_sessions`, each a `SessionSummary` (title/preview/last_activity mapped to the
    wire, timestamps as unix-ms). `request.limit` is clamped by `_clamp_limit` (0/negative →
    `DEFAULT_SESSION_LIST_LIMIT`, capped at `MAX_SESSION_LIST_LIMIT`).
  - `GetSessionMessages` → `GetSessionMessagesReply` (ADR-0021): one session's persisted
    history via `store.history`, each a wire `SessionMessage`; unknown session → empty.
  - `RenameSession` → `RenameSessionReply` (ADR-0021 management addendum): a gated, **user-only**
    catalog write via `session_rpc.rename_session`, which bounds the label (`clamp_title`,
    `MAX_TITLE_INPUT`) and reuses `store.set_title` (the write the brain-generated titles built);
    `request.title == ""` clears the override. Its gate is structural, not the mid-turn Confirmer:
    it is no tool in any registry and never runs through the turn engine, so no model, tool, or
    tainted turn can reach it, only the overlay's own controls. `list_sessions` re-bounds the
    stored title at read, so a caller cannot store an unbounded or multi-line switcher label.
  - `DeleteSession` → `DeleteSessionReply` (ADR-0021 delete addendum): a gated, **user-only**,
    DESTRUCTIVE catalog write via `session_rpc.delete_session`. It `store.delete`s the chat FIRST
    (the visible transcript is the user's primary intent), then, when a memory backend is wired,
    runs the injected `SessionMemoryCascade` (`None` when memory is off) to forget the chat's
    private memories, but only under session scoping and never passing `GLOBAL_SCOPE`. Same
    structural user-only gate as `RenameSession` (no model/tool/tainted turn reaches it); the
    user's intent is secured by an overlay-local confirm, not the Confirmer. A `SessionStoreError`
    **or** `MemoryStoreError` aborts `UNAVAILABLE`, and both steps are idempotent, so a retry heals.
  - `SetSessionPinned` → `SetSessionPinnedReply` (ADR-0021 pinning addendum): a gated, **user-only**
    catalog write via `session_rpc.set_session_pinned`, forwarding `request.pinned` to
    `store.set_pinned`. `list_sessions` unions the pinned set into every listing, so pinning lifts a
    chat above the recency window. Same structural user-only gate as `RenameSession`/`DeleteSession`;
    a `SessionStoreError` aborts `UNAVAILABLE`. Idempotent by value.
  - The session RPCs are unary; a `SessionStoreError` aborts them `UNAVAILABLE` (the body
    maps that to `TransportError::Rpc`). Their servicer method bodies live in
    `preference_servicer.PreferenceRpcMixin` (the two settings RPCs, ADR-0032; empty reads and
    dropped writes when no store is wired, the `ScheduleStore` precedent), `stores.RedisStores`
    (the session + preference stores the composition root opens from one URL and closes as a
    pair, lifted out of `wiring.py` to keep it under the line cap),
    `session_servicer.SessionRpcMixin` (mixed into `BrainService`), and the mapping/clamp helpers
    and the rename/delete/pin writes in `session_rpc.py` (the `reminders.py` pattern), so
    `server.py` stays a thin binding.
  - `ListDueReminders` / `AckReminder` (ADR-0025; policy + mapping in `reminders.py`): the
    pull pair over the injected `ScheduleStore`, covering every fired-but-undelivered item
    (`DueReminder`: id, `text`, fired-at unix-ms, recurrence, the `tainted` provenance bit, the
    origin `session_id`) and the one narrow idempotent write (`acked=false` for an unknown or
    already-delivered id, so a retried ack is harmless). `text` is a reminder's own text, or, for a
    fired **task**, its `last_outcome` (the result the user is notified of, never the standing
    instruction; the task-outcome addendum reuses this pull surface, so a task outcome and a
    reminder ride the same wire message and overlay card, undistinguished for now). **With no store wired (the default)
    both answer benignly (empty / `acked=false`, never `UNAVAILABLE`)**, which the body's
    `RetryingTransport` would treat as transient and retry on every overlay open; a live
    store's `ScheduleStoreError` does abort `UNAVAILABLE` (the session-reads precedent).
- `DEFAULT_SESSION_LIST_LIMIT = 50` / `MAX_SESSION_LIST_LIMIT = 200` are the `ListSessions`
  limit default and hard cap; `MAX_TITLE_INPUT = 200` bounds an accepted `RenameSession` label.
  All three, the wire mapping (including `SessionSummary.pinned`), and the rename/delete/pin writes
  live in `session_rpc.py` (ADR-0021).
- `converse(make_engine, client_events, *, max_buffered_events=DEFAULT_MAX_BUFFERED_EVENTS,
  confirm_timeout_s=DEFAULT_CONFIRM_TIMEOUT_S) -> AsyncGenerator[ServerEvent, None]` is the loop
  itself, servicer-independent (what `BrainService.Converse` delegates to). `make_engine` is an
  `EngineFactory` (`Callable[[Confirmer, ProgressSink], TurnRunner]`, ADR-0022/0010, widened to
  the `TurnRunner` port by ADR-0030 so a deployment with escalation enabled can serve turns
  through the wrapper that carries a model handoff inside one turn): each stream
  builds one `SeamConfirmer` and one `SeamProgressSink`, both bound to its own output queue, and
  runs the engine the factory returns for it (a bare engine wraps as
  `lambda _confirmer, _progress: engine`, leaving gated calls fail-closed and delegated work
  unsurfaced). Closing the generator tears down the stream's pump task, any in-flight turn, and
  the queue of not-yet-started turns. Teardown completes even when it races a client `Cancel` whose
  turn is still cleaning up, and even while the turn is blocked on a buffer credit.
  `converse.py` owns this entry point and the contract above; one stream's machinery (the
  `ConverseStream` pump, its credit-bounded output queue, turn scheduling, teardown, plus
  `to_server_event` and the knobs and error codes below) lives in `converse_stream.py`, a line-cap
  split that `converse.py` re-exports from, so every `from cortex_orchestrator.converse import ...`
  and the `cortex_orchestrator` barrel keep resolving unchanged.
- `SeamProgressSink(emit, credit_sem, *, to_wire)` (`progress.py`, ADR-0010 progress addendum) is
  the real `ProgressSink` adapter: a spawned subagent surfaces the batch's scale (a `StatusUpdate`)
  and its audited tool steps (a `ToolActivity`) onto the same output queue while the turn is
  suspended inside the spawn dispatch. Unlike the confirmer's control path, `emit` is
  **credit-balanced and best-effort**: it takes a buffer credit only when one is free right now
  (`credit_sem.locked()` is False), else drops the event, so a delegating turn's many steps cannot
  drift the bound the way an unconditional `put` would, and a stalled consumer loses cosmetic
  progress rather than stalling the subagent. `to_wire` is the stream's own `to_server_event`
  (`converse_stream.py`), injected so this module never imports the stream.
- `SeamConfirmer(emit, *, timeout_s)` (`confirm.py`, ADR-0022) is the real `Confirmer` adapter:
  `confirm(request)` mints a `confirm_id`, emits `ServerEvent.confirm_request` (tool name, the
  draft as one JSON object, the reason, all shown verbatim) via the stream's **control path**
  (`put_nowait`, the `SeamError` precedent, so a stalled consumer can never deadlock the ask),
  and awaits the matching `ConfirmResponse` under `timeout_s`. Timeout, `close()` (client
  half-close, so no answer can ever arrive), and cancellation (turn/stream death) all deny;
  unknown or repeated `confirm_id`s resolve nothing. Pending state is one awaiting coroutine, with
  nothing persisted, nothing survives the turn (the one hard rule). The first two denials also
  emit `ServerEvent.confirm_resolved` on the same control path (`OUTCOME_TIMEOUT` /
  `OUTCOME_UNAVAILABLE`), so the overlay can close a card it can no longer answer; an answered
  confirm, a cancelled one, and an ask refused after `close` (which emitted no request) emit
  none (ADR-0022 resolution addendum).
- `DEFAULT_MAX_BUFFERED_EVENTS = 256` is the default Converse buffer bound
  (`SeamServerConfig.converse_buffer` feeds the deployed value through `create_server`).
- `DEFAULT_CONFIRM_TIMEOUT_S = 120.0` is the default confirm wait
  (`SeamServerConfig.confirm_timeout_s` feeds the deployed value through `create_server`).
- `ERROR_CODE_SESSION_STORE_UNAVAILABLE` / `ERROR_CODE_INFERENCE_FAILED` /
  `ERROR_CODE_INTERNAL` are the `SeamError.code` values (`"session_store_unavailable"`,
  `"inference_failed"`, `"internal"`).
- `create_server(config: SeamServerConfig, make_engine: EngineFactory, store: SessionStore,
  ports: SeamPorts = SeamPorts()) -> tuple[grpc.aio.Server, int]`
  builds the aio server, registers `BrainService` with that same bundle (`schedules` = the
  reminder pull RPCs' store, `residency` = what makes `Health` honest during a handoff; `None`
  each = that capability off), binds `config.bind_address`;
  returns the not-yet-started server plus the actually-bound port (the OS pick when
  `port=0`; gRPC reports 0 if the bind failed). With `config.token` set it registers the
  `SeamTokenInterceptor` (ADR-0016, `auth.py`): every RPC, unary and streaming, current
  and future, must carry the matching `x-cortex-seam-token` metadata (`SEAM_TOKEN_HEADER`)
  or is aborted `UNAUTHENTICATED` before the servicer runs (constant-time compare, rejection
  shaped to the method). Empty token = no interceptor, the previous server byte for byte.
- `serve(config: SeamServerConfig, make_engine: EngineFactory, store: SessionStore,
  ports: SeamPorts = SeamPorts()) -> None` (async), the composition root's one call: it
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
- `build_history_window(runtime, *, sessions, backend, clock) -> HistoryWindow | None`
  (`window_builders.py`, split from `builders.py` for the line cap when the summarizing window
  arrived) is the turn's history window (ADR-0014, ADR-0038 decision 9). It takes the runtime
  config whole, the `build_memory`/`build_subagents` shape, because it now reads four values off
  it: a positive `history_char_budget` returns the char-budget window, `0` returns `None`
  (windowing off), and `history_summary` wraps the budget window in `SummarizingHistoryWindow`
  over the session store and the cortex backend. The flag is ignored when the budget is `0`,
  there being no dropped prefix to recap. **`history_recap_min_chars` is clamped to the budget
  here**, which is the one place both numbers are in hand: a fold's cost is flat so an absolute
  floor is the right shape for deciding whether the pass is worth it, but a deferred fold leaves
  a gap in neither the window nor the account, and a floor above the budget would make that gap
  wider than everything the model can see. Both windowing and summarization are on by default
  (ADR-0038 cheap-fold addendum).
- `build_output_guardrail(mode: str) -> UrlRedactingGuardrail | StrictUrlRedactingGuardrail | None`
  is the turn's output guardrail (ADR-0015): `redact` returns the default verbatim URL-redacting
  policy, `strict` (addendum) the redact-all-non-user-URL policy, `off` returns `None`. On by
  default via `BrainRuntimeConfig.output_guardrail`.
- `build_body_gateway(config: BodyConfig, *, token: str) -> tuple[BodyGateway | None, Callable[[], Awaitable[None]]]`
  is the opt-in body dial (ADR-0023): `grpc` opens a `GrpcBodyGateway` (cortex-body-client) over
  `connect(config.endpoint, token=token)`, attaching the shared `CORTEX_SEAM_TOKEN` as
  `x-cortex-seam-token` metadata (empty = none), and returns it with its channel closer; `none`
  (default) returns `(None, no-op closer)`. Off by default so CI and the no-GPU dev loop never
  reach for a host body. The uniform closer keeps `run_from_env`'s shutdown backend-agnostic.
- `build_vision(config: InferenceConfig, body_config: BodyConfig, body: BodyGateway | None) ->
  tuple[CaptureBounds | None, VisionProbe | None, closer]` (`vision.py`, ADR-0029) resolves
  `CORTEX_VISION` into the two things the root needs. The bounds say whether `capture_screen` may
  be registered at all (no body, or `off`, means never). The probe is `PropsVisionProbe`, the
  `VisionProbe` adapter over `GET {endpoint}/props`, and it is built only for `auto`: `on` and
  `off` fix the answer without touching the network, which is what those switches are for. The
  running server is believed rather than a brain-side declaration, because the two can disagree
  and both directions are bad: advertising vision the server lacks spends the whole privacy cost
  of a screen read on an image nothing can read, and hiding vision the server has silently
  removes the capability. Every failure (unreachable, non-2xx, unparseable, an unexpected
  `/props` shape) counts as **no vision** and logs a structured warning.
- The probe is **asked per advertisement and per call**, never remembered (ADR-0029 live-probe
  addendum). It used to be asked once at startup and frozen into the built-in set, which left a
  `llama-server` recreated without `--mmproj` mid-session still advertising the tool: reproduced
  2026-08-06 against the real stack, where the stale advertisement cost a real screen read, a
  real notification and a turn that then died on llama.cpp's own 500. The root therefore hands
  the probe to `build_cortex_tools`, which wraps the composite in `SightedToolRegistry`; the
  registry is what re-asks. Asking is free at this scale (measured 1.5 ms idle, 1.7 ms with a
  generation in flight, worst of 40 samples 2.5 ms), which is why nothing is cached and
  `PROBE_TIMEOUT_S` is 2 s: the leash now sits inside a user's turn rather than at boot.
- `ScheduleTicker(store, clock, settings: TickerSettings, *, spawn=None, body=None)`
  (`ticker.py`, ADR-0025) is the stateless firing loop. `TickerSettings` carries the pacing
  (`poll_s`, `lease`, `claim_limit`) plus the `zone: DisplayZone` a calendar item re-arms on
  (`CORTEX_SCHEDULE_TZ`, defaulting to `UTC_DISPLAY`): a wall-clock re-arm is zone arithmetic,
  so creation and firing must read one zone (ADR-0025 calendar addendum). Each `run_once` pass claims what is due each `run_once` pass claims what is due
  (under the fencing lease), fires the batch concurrently, and persists each outcome; the
  ticker holds nothing but its loop (the one hard rule, live). Both kinds deliver through one
  best-effort `_deliver` ladder (`BodyGateway.notify`; shown → acked at once so pull will not
  re-show it, declined/failed/absent body → the item stays deliverable and the pull path delivers,
  and exactly one of the two ever clears the slot, the double-delivery defense). A `REMINDER`
  finishes deliverable then delivers its text under `REMINDER_TITLE`; a fenced-off finish (cancel
  or re-claim won) delivers nothing. A `TASK` dispatches a synthetic `spawn_subagents`
  call through `spawn`, the ticker's own audited dispatcher (`confirmer=None`, fail-closed;
  the dispatch's `TurnStamp` carries `item.tainted` → ADR-0017 pinning, plus the item's origin
  `session_id` (provenance on the dispatch, unconsumed until the ADR-0027 SubagentTask
  deferral lands); the result's trust becomes the fire-time taint the store ORs onto the item),
  then finishes deliverable and delivers its **outcome** (not the standing instruction) under
  `TASK_TITLE`, so a task's result reaches the user as a notification and survives a body-down
  fire in the store rather than being lost (ADR-0025 task-outcome addendum); no `spawn` wired →
  an `ok=False` outcome delivered the same way, so a stale TASK neither crashes nor lease-cycles. `run` wraps each pass in a logged catch-all and
  paces on an `asyncio.Event` (`stop()` wakes it, so the graceful path completes in-flight fires
  and strands no claims); unfinished claims are `release`d best-effort, the lease covering the
  rest. Every fire failure is logged, never fatal.
- `run_from_env() -> None` (async) is the composition root: reads the env configs and serves
  with `RedisSessionStore.from_url(redis_url)`, `build_inference_backend(...)`, `SystemClock`,
  the default-on history window (`build_history_window`, ADR-0014, recapping what it drops since
  ADR-0038's cheap-fold addendum) and output guardrail (`build_output_guardrail`, ADR-0015),
  and four opt-in adapters, each disabled by default so CI and the no-GPU dev loop stay
  external-service-free: **memory** (`build_memory`, in `memory_builders.py` split from
  `builders.py`, ADR-0008; returns the `MemoryRecaller` for the engine, a `SessionMemoryCascade`
  for `DeleteSession` over the same store+scope, and the closer, all `None`/no-op when off),
  **tools** (`build_tool_registry`
  builds the MCP `ToolRegistry` shared by cortex and subagents, ADR-0009: one lazy
  `ReconnectingMcpToolRegistry` per configured endpoint (dialed on first use, not at startup, so
  boot-tolerant, ADR-0009 boot-tolerance addendum), wrapped in a `FilteredToolRegistry` where an
  allowlist is set, in a `SkipUnavailableToolRegistry` reporting through a structured warning when
  `on_unavailable="skip"`, and merged behind one `AggregateToolRegistry` when several. No session
  is held between calls, so `build_tool_registry` is synchronous and its closer is a no-op),
  **subagents**
  (`build_subagents(config, tools, redis_url, clock, *, placer, task_store_factory)`,
  in `subagent_builders.py` (split from `builders.py` for the 300-line cap), the
  `spawn_subagents` tool over a `SubagentRoster` built from `config.named_roster` (ADR-0018):
  per entry its own GPU + CPU `LlamaCppBackend` pair (one shared httpx client) and
  `PlacementRequest`, all entries sharing ONE `ResourceBudgetScheduler` and the ONE
  `VramBudgetPlacer` built once at the root from the runtime VRAM knobs and handed to both this
  builder and `build_swap_runtime` (one budget, one ledger, per ADR-0012, and one object, since
  the residency scope tells that same ledger which model holds the card during a handoff), a Redis `TaskStore`, GPU-first placement with CPU overflow,
  ADR-0010/0012; the runner enforces ADR-0017 via `roster.resolve`; `tools` is the subagent
  dispatcher, pre-assembled at the root by
  `build_subagent_tools(tool_registry, clock, policy=CORTEX_TOOLS_*)`: the shared
  registry wrapped in `UngatedToolRegistry`, so a subagent is never handed a gated/outbound
  tool (ADR-0013 subagent-exclusion addendum), with the user's gated names as the
  dispatcher's authoritative backstop, which `confirmer=None` turns into a hard deny even if
  the skip-mode advertisement window ever resurfaced a stripped name, ADR-0022), **body** (`build_body_gateway`, ADR-0023, opening the opt-in
  `GrpcBodyGateway` dial to the host `BodyService`, off by default, closed in the `finally`),
  and **schedules** (`build_schedule(config, redis_url, *, store_factory)`, in
  `schedule_builders.py`, ADR-0025, giving the durable `RedisScheduleStore` or `None`; its
  built-ins come from `build_schedule_tools(config, schedules, clock, tasks_enabled=...)`
  and its firing loop from `build_ticker(config, schedules, clock, spawn_tool=..., body=...,
  policy=...)`,
  started beside `serve` via `start_ticker` (a named task with the death-logging callback)
  and stopped first in the `finally` via `stop_ticker`, with a graceful signal, then a
  `TICKER_STOP_GRACE_S` forced cancel the store's lease covers).
  The sixth opt-in adapter is the **brain handoff** (`build_swap_runtime(swap, runtime,
  inference, clock, sleeper, placer, handoff_store_factory)` in `swap_builders.py`, ADR-0030,
  `placer` being the pool's own so the swap's two edges can recharge it, ADR-0030 handoff-window
  addendum), which
  returns `None` unless `CORTEX_ESCALATION` is set and otherwise builds the process-wide half:
  the model host the backend name picks (the `ScriptedModelHost`, or the real `HttpModelHost` over
  a bounded control client from `build_control_client`), the `SwappingModelManager` that is BOTH
  the GPU lease the inference
  backend leases through (hence `build_inference_backend(..., manager=...)`) and the residency
  scope the conductor drives, the Redis `HandoffStore`, and the `ResidencyPlan`. With it wired,
  `run_from_env` runs `recover_handoffs` before serving (a handoff cannot outlive its process)
  and publishes its answer onto the manager with `publish_boot_residency(serving=…)`, so a boot
  that could not settle the cortex is amber from the first probe instead of green over a GPU
  serving nothing; registers `escalate_to_brain`; hands that same manager to `serve` inside
  `SeamPorts` as the seam's `residency` reporter (which is what makes `Health` honest mid
  handoff, ADR-0030 decision 6); and returns an `EscalatingTurnEngine` from `make_engine`: a
  fresh slot and inner engine per turn, and a `SwapConductor` over a dispatcher built from THIS
  stream's confirmer, so the deep model's phase runs the same audited tools the cortex phase did,
  with no slot of its own and **without `capture_screen`** (ADR-0029: the root builds a second
  built-in set with `vision=None` for the deep tier, because the probe asked the cortex's endpoint
  and no brain-tier candidate on the mount carries a projector, so registration follows the tier
  that will actually answer rather than the one that was probed). `swap_closer(swap)` releases the handoff store **and** the control client in the shutdown
  `finally` (the client even when the store's own release raises, so one refused close cannot leak
  the other resource), or is a clean no-op when nothing was built. `build_subagents` returns its `ResourceBudgetScheduler` alongside
  the spawn tool for the same reason: the conductor must quiesce that very pool before a swap
  evicts anything, and a second budget object would admit past the drain.
  The cortex's dispatcher is
  `build_cortex_tools(registry, builtins, clock, confirmer=..., policy=...)` over the
  built-in set
  `build_builtin_tools(spawn_tool, body, schedule_tools=..., escalation=..., vision=...)`
  assembles **once**
  (the one-sequence bundling that keeps the builder under the six-argument ceiling as
  capabilities accumulate, ADR-0025 d7): delegation, the two volume built-ins when a
  `BodyGateway` is threaded in (ADR-0023), `capture_screen` when a body is threaded in **and**
  the composition root confirmed the running model can see (a `CaptureBounds`, ADR-0029; its
  absence is how "no vision" is expressed, and offering the tool without both would spend the
  whole privacy cost of a screen read on an unreadable image), and the five schedule built-ins
  (`schedule_task`/`list_scheduled`/`cancel_scheduled`/`snooze_scheduled`/`edit_scheduled`,
  ADR-0025), plus `escalate_to_brain` when (and only when) a handoff can actually run
  (ADR-0030), all merged
  with the MCP tools via a `CompositeToolRegistry`, or `None` when nothing is enabled (the
  Slice 3 turn path). The volume, capture, and schedule built-ins are ungated by default
  (`capture_screen` because a screen read is neither outbound nor irreversible, the confirm card
  could not describe what it will capture since the call takes no arguments, and a gated call on
  a tainted turn is hard-denied with the confirmer never consulted, which would make "read this
  email, then look at my screen" structurally impossible);
  a user gates any by name in `CORTEX_TOOLS_GATED` (the dispatcher's authoritative backstop)
  and prices any by name in `CORTEX_TOOLS_COSTS`. All three declarations travel as one
  `DispatchPolicy`, so the cortex, the subagents, and the ticker are built from the same value
  and no declaration can reach one and miss another. The prices and the salience rule matter on
  the two that drive a `stream_tool_loop` (and since ADR-0009's turn-wide addendum a spawned
  subagent's loop spends the *spawning turn's* pool rather than one of its own, while its
  repeat history stays its own, per the salience addendum); on the ticker's private spawn
  dispatcher both are inert, since it dispatches one call directly and runs no loop.
  `run_from_env` hands `serve` an **engine factory** (ADR-0022/0010): each Converse
  stream's `SeamConfirmer` reaches its dispatcher and its `SeamProgressSink` reaches its turn
  through it, so an untainted gated call (e.g. the email sidecar's `send_email`, stamped by the
  `CORTEX_TOOLS_GATED` overlay in `build_tool_registry`) prompts the overlay, a tainted one is
  denied outright, and a spawned subagent's progress reaches that stream's overlay. Subagent
  dispatchers keep `confirmer=None` (fail-closed, ADR-0013).
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
  (ADR-0020, `state="thinking"`), each audited tool dispatch as a `ToolActivity` (ADR-0009
  addendum, the overlay's activity chip) plus the `ToolOutcome{tool_name, ok}` settling that
  dispatch once it resolves (ADR-0029 outcome addendum, one per activity the turn emitted, on
  every path out of the dispatch), followed by exactly one `TurnComplete{turn_id}`.
  A turn that spawns subagents also surfaces their progress on the same stream through this
  stream's `SeamProgressSink` (ADR-0010 progress addendum): a `StatusUpdate{state="delegating"}`
  for the batch's scale and a `ToolActivity` per subagent tool step, ridden while the turn is
  suspended inside the spawn dispatch (its generator cannot yield), best-effort and
  credit-balanced so a stalled consumer drops them. A delegated step carries **no** outcome: the
  pairing above is about the turn's own dispatches, and the surface the outcome feeds is over a
  cortex-only built-in a subagent cannot call. Declined rather than merely unbuilt, and the wire's
  own contract now says so (ADR-0029 delegated-pairing addendum);
  `test_a_delegated_step_reaches_the_wire_announced_and_unsettled` pins the asymmetry, since the
  body cannot tell a delegated activity from the turn's own.
  `UserTurn.images` are **still ignored**: vision arrived as a model-initiated capture
  (ADR-0029), and the user-attached image path is a recorded deferral
  (`docs/refinements/vision.md`) rather than a promise about a coming slice.
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
  `Cancel` does, and any pending confirmation dies with it, as a denial (ADR-0022).
- **The confirm exchange** (ADR-0022): a gated call mid-turn emits `ConfirmRequest` and
  suspends inside the dispatcher until the pump routes the matching `confirm_response`
  client event, the timeout denies, or input ends (`SeamConfirmer.close()` denies pending
  and future asks immediately, so a draining turn never hangs out the timeout). A denial the
  client did not author (timeout, input ended) is reported as `ConfirmResolved{confirm_id,
  outcome}` before the turn resumes, so the card closes ahead of the declined reply.
- **Bounded backpressure** (the Slice-3 deferral, landed 2026-07-03): at most
  `converse_buffer` events sit unread per stream. The turn's data path holds a credit
  per buffered event (returned on dequeue), so a consumer that stops reading suspends
  generation at the bound instead of growing an unbounded buffer. The terminal
  `SeamError` and stream teardown bypass the credits: failure reporting never blocks
  behind a full buffer, whatever the consumer does. `SeamProgressSink` rides the same
  credits but non-blocking (ADR-0010 progress addendum): it takes one only when free and
  drops otherwise, so subagent progress counts against the bound like a reply delta yet
  never stalls the subagent, and the bound does not drift (unlike the confirmer's
  control-path events, which over-credit by a documented, bounded amount).

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

**Dependencies.** cortex-core, cortex-body-client (the `GrpcBodyGateway` dial, ADR-0023),
cortex-inference, cortex-seam, cortex-session (workspace), grpcio (`grpc.aio`), httpx (the
injected client for the llama.cpp backend), pydantic, pydantic-settings.
