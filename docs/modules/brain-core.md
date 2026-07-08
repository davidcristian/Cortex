# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing,
the "handle a user turn" use-case, the memory remember/recall use-case, tool dispatch, and
subagent delegation live here now; handoff orchestration joins them in a later slice. No I/O,
ever. This is the hexagon's center. The bounded infer↔tool loop is one shared function
(`tool_loop.stream_tool_loop`) that both the cortex turn and each subagent run (ADR-0010).

**Public contract** (everything importable from `cortex_core`; `__all__` is the API):

Routing (Slice 1):

- `Tier` is an enum of model tiers: `CORTEX`, `SUBAGENT`, `BRAIN` (string values).
- `RoutingHints` is a frozen dataclass: `explicit_tier: Tier | None = None`,
  `needs_deep_reasoning: bool = False`, `is_narrow_delegable: bool = False`.
- `route_turn(hints: RoutingHints) -> Tier` is a pure decision with strict precedence:
  explicit override → deep reasoning (`BRAIN`) → narrow delegable (`SUBAGENT`) →
  default `CORTEX`.

Conversation domain (Slice 3):

- `Role` is an enum: `USER`, `ASSISTANT`, `SYSTEM`, `TOOL` (string values). `SYSTEM` carries
  engine-injected context (recalled memories, ADR-0008); `TOOL` carries a tool result fed
  back to the model (ADR-0009). Both (and the in-turn tool-call messages) are derived per
  turn and handed only to the model, never persisted to a session's history in v1.
- `Message` is a frozen dataclass: `role: Role`, `text: str`, `at: datetime`, `turn_id: str`,
  plus the optional tool fields `tool_calls: tuple[ToolCall, ...] = ()` (set on an assistant
  message that asked to run tools) and `tool_call_id: str | None = None` (set on a `TOOL`
  result). Rejects naive `at` with `ValueError`, since externalized state must carry its
  timezone. `turn_id` ties a user message to the assistant reply it produced.
- `TextDelta(text)` / `StatusUpdate(state, detail)` / `TurnCompleted(turn_id, full_text)` are
  frozen domain events; `TurnEvent` is their union (the orchestrator maps them onto the proto's
  `ServerEvent`). `StatusUpdate` is ephemeral mid-turn progress. Its first use (ADR-0020) is a
  reasoning model's live thinking (`state="thinking"`), never persisted or part of the reply.
- `TextChunk(text)` / `ReasoningChunk(text)` carries one streamed reply / thinking delta from a
  backend; `InferenceEvent` is the union `TextChunk | ReasoningChunk | ToolCall`, what an
  `InferenceBackend` yields (ADR-0009/0020).

Session listing (Slice 8.7, ADR-0021; `sessions.py`):

- `SessionSummary` is a frozen dataclass: `session_id: str`, `title: str`, `preview: str`,
  `last_activity: datetime`. One recent chat as the overlay's switcher shows it; `title`/
  `preview` are already derived (one line, truncated), `last_activity` tz-aware.
- `summarize_session(session_id, messages) -> SessionSummary` is the pure derivation both
  `SessionStore` implementations share (so the rule never drifts): `title` from the first
  message, `preview` from the last, `last_activity` from the last's `at`; each collapsed to
  one line and truncated (`TITLE_MAX` / `PREVIEW_MAX`). Requires a non-empty history.

Model management (Slice 4, ADR-0007):

- `ModelLease` is a frozen dataclass: `endpoint: str`. A live claim on the GPU for one
  model, valid only inside the `acquire(...)` block that yields it; `endpoint` is the
  base URL of that model's `llama-server`.

Memory domain (Slice 5, ADR-0008):

- `MemoryRecord` is a frozen dataclass: `id: str`, `text: str`, `embedding: tuple[float, ...]`,
  `at: datetime`, `scope: str = GLOBAL_SCOPE`, `tainted: bool = False`. One durable memory;
  rejects naive `at` with `ValueError` (memory outlives every process). `scope` is its namespace
  (ADR-0008 addendum); `tainted` is the untrusted-provenance marker (ADR-0019), set `True` when the
  exchange came from a turn that read untrusted content, so recall fences it as data. The caller
  fills every field, leaving the store a pure translator.
- `ScoredMemory` is a frozen dataclass: `record: MemoryRecord`, `score: float`. A retrieval
  hit and its similarity (higher = closer).

Tool domain (Slice 6, ADR-0009; untrusted-content fields Slice 6.5, ADR-0013):

- `Trust` is an enum `TRUSTED` / `UNTRUSTED` (string values): the provenance of a tool result's
  content (ADR-0013). `UNTRUSTED` is third-party content framed as data; `TRUSTED` is
  system-generated. The default is `UNTRUSTED` everywhere (fail-closed).
- `ToolSpec` is a frozen dataclass: `name: str`, `description: str`,
  `parameters: Mapping[str, Any]` (the JSON Schema the model fills; passed through verbatim,
  never interpreted by the core), `gated: bool = False` (an irreversible/outbound action that
  needs confirmation once the turn read untrusted content, but no tool sets it today). What a tool
  advertises.
- `ToolCall` is a frozen dataclass: `id: str`, `name: str`, `arguments: Mapping[str, Any]`,
  `tainted: bool = False`. A model's request to run one tool; `id` correlates it with its
  `ToolResult`. `tainted` is never the model's to set: the dispatcher **overwrites** it at
  dispatch time with the calling turn's taint (ADR-0018) so a built-in that spawns further work
  can propagate provenance, staying transient (the loop persists the unstamped calls) and never the
  gate's input (the gate uses the dispatcher's explicit argument).
- `ToolResult` is a frozen dataclass: `call_id: str`, `content: str`, `is_error: bool = False`,
  `trust: Trust = Trust.UNTRUSTED`. The outcome fed back to the model; `is_error` marks a tool
  (or dispatch) failure; `trust` is the content's provenance (fail-closed default), read by the
  loop to fence untrusted content and mark taint.
- `ToolInvocation` is a frozen dataclass: `name`, `arguments`, `ok: bool`, `detail: str`,
  `at: datetime` (tz-aware, rejects naive), `trust: Trust = Trust.UNTRUSTED` (the provenance
  audit trail). One audit-trail line.
- `ConfirmationRequest` is a frozen dataclass: `tool_name: str`, `arguments: Mapping[str, Any]`,
  `reason: str`. What the dispatcher hands the `Confirmer` to approve a gated call out of band.

Subagent domain (Slice 7, ADR-0010):

- `SubagentTask` is a frozen dataclass: `id: str`, `instruction: str`, `context: str`,
  `at: datetime` (tz-aware, rejects naive), `model: str = ""`, `tainted: bool = False`. One
  narrow task delegated to a subagent, persisted before it runs; `context` is the material the
  subagent works from (the cortex conversation is never shared, as the subagent is stateless over
  the task). `model` is the roster entry the cortex requested (`""` = the default) and `tainted`
  the spawning turn's taint at spawn time. They are the two `SubagentRoster.resolve` inputs only the
  spawn site knows, riding the record so the runner resolves safely from the store alone
  (ADR-0017/0018).
- `SubagentResult` is a frozen dataclass: `task_id: str`, `output: str`, `ok: bool = True`,
  `detail: str = ""`, `tainted: bool = False`. A subagent's outcome; `ok=False` (with `detail`)
  marks a failure the cortex consumes as a value, mirroring `ToolResult.is_error`; `tainted` is
  set when the subagent read untrusted content, aggregated by the spawn tool (ADR-0013).

Placement domain (Slice 8.5, ADR-0012):

- `PlacementTarget` is an enum `GPU` / `CPU` (string values), where a subagent's whole model runs
  (never a partial straddle). `.ngl` maps it to the llama.cpp offload flag: `GPU → 99`, `CPU → 0`.
- `PlacementRequest` is a frozen dataclass: `model: str`, `vram_gb: float`, `cpus: float`,
  `memory_gb: float`. One subagent's resource ask; `__post_init__` rejects a non-positive resource
  with `ValueError`. `vram_gb` is fit-tested against headroom; `cpus`/`memory_gb` are the
  per-container caps the scheduler sums.
- `Placement` (frozen dataclass): `target: PlacementTarget`, `reserved_gb: float`. A `SubagentPlacer`
  verdict; `reserved_gb` is the request's `vram_gb` on GPU, `0.0` on CPU, so `release` is exact.
Roster domain (Slice 8.6, ADR-0018; in `roster.py`):

- `SubagentResources` is a frozen dataclass bundling one subagent entry's placement machinery:
  `backends: Mapping[PlacementTarget, InferenceBackend]`, `scheduler: SubagentScheduler`,
  `placer: SubagentPlacer`, `request: PlacementRequest`. Mirrors `TurnCapabilities`, collaborators
  that always travel together (`request.model` is the id handed to the backend). In a multi-entry
  roster the `scheduler`/`placer` are the SAME objects in every entry (one budget, one VRAM
  ledger); only `backends`/`request` differ.
- `SubagentProfile` is a frozen dataclass: `resources: SubagentResources`, `description: str = ""`.
  One roster entry; the description is the trade-off text the spawn spec advertises (informs
  optimization only, never safety).
- `SubagentRoster` is a frozen dataclass: `entries: Mapping[str, SubagentProfile]`, `default: str`
  (must be an entry; empty rosters rejected with `ValueError` at construction). `resolve(requested,
  *, tainted, tools_enabled) -> str | None` is where ADR-0017 executes: `tainted or tools_enabled`
  → the robust `default` whatever was requested (unknown names included); else the requested
  entry (`""` = default); an unknown name on a clean tool-less path → `None` (the runner fails
  it closed).

Body-gateway domain (Slice 9, ADR-0023; in `body.py`):

- `VolumeState` is a frozen value: `level: float` (0-1), `muted: bool`. One reading of the host's
  system volume (the shape both `get_volume` and `set_volume` return across the brain→body seam).

Untrusted-content boundary (Slice 6.5, ADR-0013; the pure primitives in `untrusted.py`):

- `SECURITY_PREAMBLE` is the standing-rule constant, injected as a `Role.SYSTEM` message by the
  engine/runner when a turn has tools: content in the untrusted markers is data, never obeyed.
- `wrap_untrusted(content, *, nonce) -> str` fences untrusted content as
  `<untrusted-tool-output id=NONCE> … </untrusted-tool-output id=NONCE>`; a closing tag embedded
  in `content` cannot end the fence (it lacks the per-turn `nonce`), the delimiter-injection defense.
- `security_preamble_message(at, turn_id) -> Message` is the preamble as a `Role.SYSTEM` message.
- `new_nonce() -> str` is a new per-turn nonce (`secrets.token_hex(8)`), unpredictable, dies with the turn.
- `DENIED_MSG` is the `is_error` result content for a gated tool blocked on a **tainted** turn
  (ADR-0022: unconditional, never confirmable within the turn).
- `USER_DECLINED_MSG` is the `is_error` result content for an **untainted** gated call the user
  declined (or no confirmer answered): the model relays "no", never retries (ADR-0022).
- `TaintLedger` is mutable, turn-local: `tainted: bool = False` plus `untrusted_urls: set[str]`
  (the laundering evidence, ADR-0015). `mark(trust)` flips `tainted` on the first `UNTRUSTED`
  result; `observe(result)` (what the shared loop calls) marks AND collects an untrusted
  result's URLs; `ingest_untrusted(content)` is the non-tool twin (ADR-0019). The engine calls it
  for a recalled tainted memory so it taints and contributes URLs like a live untrusted result.
  Reconstructed each turn, never persisted. Structurally satisfies `TaintView` (below), so the
  engine passes the live ledger straight to `OutputGuardrail.open`.
- `ToolLoopContext` is a frozen bundle of a tool loop's per-invocation collaborators (`dispatcher`,
  `clock`, `turn_id`, `taint`, `nonce`), keeping `stream_tool_loop` under its argument ceiling.

Output guardrail (ADR-0015; the pure laundering defense built from the redactor + policies in
`guardrail.py`, the URL grammar + identity in `urls.py`):

- `extract_urls(text) -> frozenset[str]` (in `urls.py`) finds every clickable URL in `text` (schemes
  `http(s)`, `ftp`, `mailto:`, `tel:`), normalized for identity (scheme+authority lowercased,
  trailing prose punctuation dropped, path/query case kept; an opaque `mailto:`/`tel:` has no
  `://` so it folds whole). Every scheme is anchored at a word boundary, so `sftp://`/`hotel:` are
  not partial-matched. Three **obfuscation-resistant** passes reduce a rewritten link to its plain
  identity (ADR-0015 addenda): **defang** refanging (`hxxp(s)`→`http(s)`, `[://]`/`[:]//`→`://`,
  bracketed dots `[.]`/`(.)`/`{.}`/`[dot]`/`(dot)` inside a scheme'd URL → `.`), **percent-decoding**
  once (`evil%2ecom`→`evil.com`), and **NFKC** folding (fullwidth/compatibility homoglyphs → ASCII).
  So a defanged, encoded, or fullwidth link normalizes to the same identity as its plain twin. A
  *transform* in the reply is caught, not only verbatim reproduction. Both sides of the defense use
  it for collection (`TaintLedger.observe`) and the user-message allowlist, so a collected URL and
  its reappearance always compare equal. Held deliberately out (they would over-redact prose or
  need a dependency): bare addresses/domains, whitespace-split defang (`evil dot com`), cross-script
  homoglyphs/IDN/punycode, multi-pass encodings, and unlisted schemes (`data:` …).
- `TaintView` (protocol) exposes the **live** taint signals the guardrail reads at scan time
  (`tainted: bool`, `untrusted_urls: AbstractSet[str]`); the turn's `TaintLedger` already
  satisfies it structurally (guardrail cannot import `untrusted`, which imports it).
- `OutputGuardrail` (protocol) has `open(taint, *, allow) -> OutputFilter`: one turn's filter over
  the turn's live `TaintView` (both fields grow as results arrive) and the URLs the user's own
  message carried.
- `OutputFilter` (protocol) provides `feed(chunk) -> str` (the scrubbed text safe to emit now; an
  ambiguous suffix (a URL still growing, a partial `http(s)://`/`mailto:`) is carried) and
  `flush() -> str` (end of stream resolves the carry).
- `UrlRedactingGuardrail` is the default policy: a URL whose normalized form is in
  `taint.untrusted_urls − allow` (collected *verbatim* from untrusted content) is replaced with
  `REDACTED_LINK` (`"[link removed: untrusted source]"`, trailing prose punctuation preserved);
  every other byte passes through. A clean turn (nothing collected) is untouched.
- `StrictUrlRedactingGuardrail` (ADR-0015 addendum) is the opt-in policy: on a **tainted** turn
  (`taint.tainted`), redact *every* URL outside `allow`, not just the verbatim-collected ones,
  the answer to a model that transforms or reconstructs a laundered link. An untainted turn is
  untouched, so the model's own recalled links still stream on a clean turn.

Ports (`typing.Protocol`; failures cross them only as the typed errors below):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown),
  `async list_sessions(*, limit) -> Sequence[SessionSummary]` (recent chats newest-active
  first, at most `limit`; ADR-0021 adds a read over the same state, no write path).
  The source of truth for conversation state; survives swaps and restarts.
- `InferenceBackend` has `stream(model, messages, *, tools=()) -> AsyncIterator[InferenceEvent]`:
  one stateless streamed completion, yielding `TextChunk` deltas interleaved with `ToolCall`s
  the model makes from the offered `tools` (ADR-0009). `model` is a logical id (ADR-0004).
- `ModelManager` provides `acquire(model) -> AbstractAsyncContextManager[ModelLease]`: owns the
  GPU, queues for access, yields a `ModelLease`; leaving the block releases it to the
  next waiter. Consumed by the inference adapter (and, later, the handoff use-case).
- `Embedder` provides `async embed(text) -> Sequence[float]`: one stateless call, text to vector.
  Dimension is fixed by the deployment's model (ADR-0008); the core assumes no value.
- `MemoryStore` provides `async add(record) -> None`, `async search(embedding, *, k, scopes=None) ->
  Sequence[ScoredMemory]` (top-`k` by similarity, most-similar first). `scopes` restricts the
  candidate set to those namespaces (ADR-0008 scoping addendum); `None` (the default) ranks over
  ALL memories (the global-space behavior). Durable, cross-session; the caller builds each record
  (including its `scope`).
- `ToolRegistry` has `async describe_tools() -> Sequence[ToolSpec]` (advertise the tools),
  `async invoke(call) -> ToolResult` (run one call; `is_error` reflects a tool-level
  failure). An unknown tool or a transport failure raises `ToolError`
  (`ToolNotFoundError` for the name). The dispatcher, not the registry, turns that into an
  error result.
- `ToolAuditSink` has `async record(invocation) -> None`: every dispatched call is written
  here, success or failure (the AGENTS.md audit requirement).
- `Confirmer` has `async confirm(request: ConfirmationRequest) -> bool` (ADR-0013): approves or
  denies a gated tool call out of band. The human's decision, never the model's; a missing
  confirmer denies (fail-closed). The real adapter is the orchestrator's `SeamConfirmer`
  (ADR-0022): the request rides the Converse stream to the overlay's approval card.
- `TaskStore` has `async put_task(task) -> None`, `async get_task(task_id) -> SubagentTask | None`,
  `async put_result(result) -> None`, `async get_result(task_id) -> SubagentResult | None`. The
  hot store (Redis) a subagent is a stateless function over: task and result live here, never in
  a model process (ADR-0010). Unknown ids return `None`.
- `SubagentPlacer` has `place(request) -> Placement`, `release(placement) -> None` (both sync): the
  VRAM-budget accountant (ADR-0012). `place` fit-tests `request.vram_gb` against the live headroom
  (`soft_cap − cortex_reservation − placed`), reserving it on GPU or spilling to CPU; `release`
  frees it. The GPU/VRAM contract, separate from `ModelManager`'s lease and `SubagentScheduler`'s
  budget. The three compose at `SubagentRunner`.
- `SubagentScheduler` (`admit(request) -> AbstractAsyncContextManager[None]`): a soft two-dimensional
  CPU/RAM budget for spawns (yields once the request's `cpus`/`memory_gb` fit the summed targets,
  queues over budget, releases both on exit). A charge larger than the whole budget raises
  `ValueError`. A counting budget, not the GPU lease (ADR-0012, revising ADR-0010).
- `BodyGateway` provides `async get_volume() -> VolumeState`,
  `async set_volume(*, level=None, mute=None) -> VolumeState` (ADR-0023): the brain-side handle on
  the host body's OS actions. It is the first brain→body seam direction (the brain dials the body's
  `BodyService`). Absent kwargs leave that field alone; an unreachable body surfaces as
  `BodyGatewayError`. The real adapter is `cortex_body_client`'s `GrpcBodyGateway` over the gRPC
  seam, opt-in and off by default (wired at the composition root, not here).
- `Clock` provides `now() -> datetime`, always tz-aware. The core's only time source.
- `SessionStoreError` / `InferenceError` / `ModelManagerError` (+ its
  `ModelUnavailableError`) / `MemoryStoreError` / `EmbedderError` / `ToolError` (+ its
  `ToolNotFoundError`) / `TaskStoreError` / `BodyGatewayError` are typed errors; adapters wrap their
  backend's failures into these with the cause chained.

Use-case:

- `TurnEngine(store, backend, clock, *, cortex_model=DEFAULT_CORTEX_MODEL,
  capabilities=TurnCapabilities(), turn_id_factory=<uuid4>)` is pure orchestration over the
  ports. `handle_turn(session_id, text)` is an async generator: routes via
  `route_turn(RoutingHints())` (always `CORTEX` in this slice; the tier keys the model
  choice), builds the user `Message` (clock + turn-id factory), appends it to the store,
  runs the inference↔tool loop over ALL of the stored history, unless a
  `capabilities.window` selects the newest slice (ADR-0014; persistence untouched),
  yields `TextDelta` per streamed chunk, then persists the assistant `Message` and
  yields one `TurnCompleted`.
  Cancellation semantics: closing the event stream mid-generation (`aclose()`) keeps
  the persisted user message, does NOT persist the partial assistant text, and closes
  the abandoned backend stream. Backend failures surface as `InferenceError` after the
  user message was persisted.
  Memory (optional, ADR-0008): when `capabilities.memory` is set, before inference the
  engine recalls the top `DEFAULT_RECALL_K` (5) memories for the user text, within the
  turn's `session_id` scope (ADR-0008 addendum; global by default), and, if any, prepends
  them as a `Role.SYSTEM` message to the context the backend sees (ephemeral, never stored).
  A recalled memory carrying the `tainted` marker is **fenced** with the turn nonce and taints
  the turn (ADR-0019: `ingest_untrusted`), so it re-enters as data (never trusted context) and
  the `SECURITY_PREAMBLE` is added even on a tool-less turn to explain the markers. After
  completion it records the `User: …\nAssistant: …` exchange to memory, **unless the turn read
  untrusted content**, in which case nothing is recorded by default (ADR-0013). With
  `capabilities.record_tainted_memory` on (ADR-0019) a tainted turn is recorded instead with
  `tainted=True`, so recall fences it; an untainted turn always records a trusted memory.
  Tools (optional, ADR-0009): when `capabilities.tools` is set, the engine prepends the
  untrusted-content `SECURITY_PREAMBLE` (ADR-0013) and runs the shared `stream_tool_loop` with
  that `ToolDispatcher` and a fresh per-turn `TaintLedger`. The loop advertises the registry's
  tools each step, dispatches a step's `ToolCall`s (audited, gated), feeds results back as an
  `ASSISTANT`-with-`tool_calls` message plus (untrusted-fenced) `Role.TOOL` results, and re-infers
  up to `MAX_TOOL_STEPS` rounds. These tool messages are in-turn only (never persisted in v1).
  Guardrail (optional, ADR-0015): when `capabilities.guardrail` is set, every assistant delta
  passes through the per-turn `OutputFilter` (opened over the ledger's live URL set, the user
  message's own URLs allowlisted). An emptied delta emits no event, the flush tail is emitted
  last, and the sanitized text is what streams, completes, AND persists: the reply on record is
  the reply shown. With a bare `TurnCapabilities()` (the default) the turn behaves exactly as
  Slice 3.
- `TurnCapabilities(memory=None, tools=None, window=None, guardrail=None,
  record_tainted_memory=False)` is a frozen bundle of the optional per-turn collaborators (a
  `MemoryRecaller`, a `ToolDispatcher`, a `HistoryWindow`, and an `OutputGuardrail`) plus the
  tainted-turn recording policy (ADR-0019), keeping the engine within its DI ceiling. The bool
  governs only writing. A stored tainted memory is always fenced on recall regardless.
- `HistoryWindow` (protocol, `windowing.py`) / `CharBudgetHistoryWindow(max_chars)` are the
  session-history windowing seam and its shipped policy (ADR-0014). `select(history)`
  returns the slice one turn sends to the model: `CharBudgetHistoryWindow` keeps the newest
  whole turns (grouped by consecutive `turn_id`) whose summed text length fits `max_chars`,
  as a contiguous tail, with turns kept or dropped whole, the walk stopping at the first
  overflow, the newest turn always kept even oversized (the current user message must reach
  the model). Characters approximate tokens (~4 chars/token) so the core needs no tokenizer.
  Applied at inference-message assembly only. The store keeps the full history.
  `max_chars < 1` raises `ValueError` (`0` as an off switch lives in the wiring, not here).
- `stream_tool_loop(backend, model, working, context: ToolLoopContext)` (in `tool_loop`)
  is the bounded infer↔tool loop shared by `TurnEngine` and `SubagentRunner` (ADR-0010): an
  async generator yielding assistant text deltas, mutating `working` in place with the tool-call
  and `Role.TOOL` result messages; ends on a tool-free step, a `None` dispatcher, or
  `MAX_TOOL_STEPS` (8) rounds. It draws the untrusted boundary (ADR-0013): each call is dispatched
  with the turn's `tainted` state and the tool's `gated` flag (the ADR-0022 gate: tainted denies
  outright, untainted confirms), its result is observed by `context.taint` (taint bit + the untrusted-URL
  evidence the output guardrail reads, ADR-0015), and an `UNTRUSTED` result is fenced by
  `wrap_untrusted` before it re-enters `working`. `MAX_TOOL_STEPS` and `ToolLoopContext` are here.
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.
- `MemoryRecaller(store, embedder, clock, *, scope=GLOBAL_MEMORY_SCOPE, id_factory=<uuid4>)` is
  the memory use-case (ADR-0008). `record(text, *, session_id, tainted=False)` embeds `text`,
  persists a `MemoryRecord` (id from the factory, `at` from the clock, embedding from the embedder,
  `scope` from the policy's `write_scope(session_id)`, `tainted` from the caller per ADR-0019), and
  returns it; `recall(query, *, k, session_id)`
  embeds `query` and returns the store's top-`k` `ScoredMemory` within the policy's
  `read_scopes(session_id)`. Stateless over the store: every memory lives in `MemoryStore`, so
  recall is identical across restarts and swaps. Wired into `TurnEngine` (retrieve-into-context,
  record-at-turn-end) when injected. The engine threads its `session_id` through both calls.
- `MemoryScope` (port, `scope.py`) + `GlobalMemoryScope` / `SessionMemoryScope` (ADR-0008 scoping
  addendum) are the pure policy mapping a turn's `session_id` to its `write_scope` and `read_scopes`
  (the `HistoryWindow` pattern). `GlobalMemoryScope` (the `GLOBAL_MEMORY_SCOPE` singleton, the
  default) writes `GLOBAL_SCOPE` and reads `None` (all), keeping recall cross-session;
  `SessionMemoryScope` writes/reads the `session_id`, isolating a conversation's memory to itself.
  Selected at the composition root via `CORTEX_MEMORY_SCOPE`; the store filters, the policy decides.
- `ToolDispatcher(registry, audit, clock, *, confirmer=None)` is the turn's tool gateway and
  capability gate (ADR-0009/0013). `dispatch(call, *, tainted=False, gated=False)` runs `call`
  through the `ToolRegistry`, writes exactly one `ToolInvocation` (with the result's `trust`) to
  the `ToolAuditSink`, and returns the `ToolResult`; a `ToolError` becomes a `TRUSTED` `is_error`
  result (our own message, so it neither frames nor taints). The gate (ADR-0013, table revised by
  ADR-0022): a `gated` call on a `tainted` turn is blocked outright as `DENIED_MSG`, with the
  confirmer deliberately unconsulted; on an untainted turn it runs only when the `Confirmer`
  approves, else `USER_DECLINED_MSG` (the fail-closed `confirmer=None` default included). Both
  blocks return **without invoking the tool**, audited. Before the
  registry invoke it **stamps the turn's taint onto the call** (`replace(call, tainted=tainted)`,
  ADR-0018). That is provenance for built-ins, never the gate's input, and a model-forged stamp is
  overwritten. `describe_tools()` passes through to the registry. Stateless over the ports; the
  loop drives it.
- `SubagentRunner(store, roster, clock, *, tools=None)` is a subagent's body (ADR-0010/0012/0018),
  a stateless function over the `TaskStore`. `run(task_id)` loads the `SubagentTask` **by id**
  (never from cortex memory, so a missing task is an `ok=False` "task not found" result),
  **resolves** the roster entry via `roster.resolve(task.model, tainted=task.tainted,
  tools_enabled=…)` (ADR-0017; an unknown model is an `ok=False` "unknown subagent model" result,
  fail closed), **admits** against that entry's scheduler CPU/RAM budget (outer, may wait),
  **places** on GPU or CPU against the VRAM budget (inner, synchronous), routes to the entry's
  `backends[placement.target]`, runs `stream_tool_loop` on the entry's `request.model` with its
  optional tool subset (instruction as the user ask, `context` as a `Role.SYSTEM` message; a
  tools-enabled subagent also gets the `SECURITY_PREAMBLE` and its own `TaintLedger`, ADR-0013),
  persists + returns a `SubagentResult` carrying `tainted` from that ledger, and always releases
  the VRAM in a `finally`. A mid-stream `InferenceError` becomes an `ok=False` result carrying
  the partial text. Exposes `roster`/`tools_enabled` (read-only) so the spawn tool advertises
  exactly what it will honor. Tools-enabled but not given the delegation tool, so fan-out is
  depth-1.
- `SpawnSubagentsTool(runner, store, clock, *, task_id_factory=<uuid4>)` is the built-in
  `spawn_subagents` tool (`SPAWN_TOOL_NAME`), the cortex's delegation primitive (ADR-0010/0018).
  Its `spec` is **derived from the runner's roster**: an instructions item is a bare string or
  `{instruction, model?, context?}` (`anyOf`); the `model` enum lists every entry with its
  description and the ADR-0017 caveat, omitted entirely when the runner is tools-enabled or the
  roster has one entry (a knob that cannot do anything is not advertised). `invoke(call)`
  validates items against the roster (bad input / unknown model → an `is_error` result, not a
  raise); a string item that parses as a JSON object carrying an `instruction` key is diverted
  into the object path (real models sometimes stringify the object form, per the ADR-0018 addendum;
  same validation either way). It persists one `SubagentTask` per item, each stamped with the
  requested `model`, the item's `context`, and the **call's `tainted`** (the dispatcher's
  stamp). It runs the `SubagentRunner`s
  **concurrently** (bounded by the scheduler), and returns one aggregated `ToolResult`, with a
  `[subagent N] …` block per subtask, failures shown inline. The aggregate is `UNTRUSTED` iff any
  subagent was tainted, so a subagent that read a malicious file taints the cortex through the
  normal result path (ADR-0013). A `BuiltinTool` (`.spec` + async `invoke`), registered in a
  `CompositeToolRegistry`.
- `GetVolumeTool(body)` / `SetVolumeTool(body)` are the built-in `get_volume` / `set_volume` tools
  (`volume.py`), the cortex's host-volume primitives over a `BodyGateway` (ADR-0023), cortex-only
  like `spawn_subagents`. `get_volume` reads the state; `set_volume` takes optional `level` (0-1)
  and/or `mute`. Both `gated=False` (volume is reversible) and every result is `Trust.TRUSTED`
  (host state, never taints the turn); bad arguments and a `BodyGatewayError` both become an
  `is_error` `TRUSTED` `ToolResult`, never a raise. `BuiltinTool`s, registered in the
  `CompositeToolRegistry`.
- `CompositeToolRegistry(builtins, remote=None)` is a `ToolRegistry` merging built-in tools with
  an optional remote (MCP) registry (ADR-0010). `describe_tools` advertises every built-in then
  the remote tools none shadows; `invoke` routes by name, built-ins first, else the remote, else
  `ToolNotFoundError`. Duplicate built-in names raise `ValueError` at construction. The
  internal-tool seam (ADR-0001 Q2) the body's OS actions (Slices 9-10) will reuse. `BuiltinTool`
  is the protocol it advertises/invokes.
- `AggregateToolRegistry(registries)` is a `ToolRegistry` over several registries (ADR-0009
  refinements addendum), letting the filesystem and email sidecars coexist behind the one port.
  `describe_tools` unions in registry order, deduplicating **first-wins** (construction order is
  precedence under the composite's shadowing rule; a later duplicate is neither advertised nor
  invokable); `invoke` routes to the first registry *currently* advertising the name, resolved
  by a live `describe_tools` walk (no cached routing, so a tool dropped server-side mid-turn
  fails closed as `ToolNotFoundError`). A listing failure anywhere propagates as `ToolError`
  (one dead sidecar is loud, never a silently smaller tool set, unless that sidecar is
  explicitly marked optional, below). An empty registry sequence raises `ValueError` at
  construction.
- `SkipUnavailableToolRegistry(inner, *, name, report)` marks one registry optional: the
  skip-and-report degraded mode (ADR-0009 degraded-mode addendum). A `describe_tools`
  failure (`ToolError`) becomes an empty advertisement plus one `report(name, error)` call, and
  the reporter is mandatory, so skipping cannot be silent, and it fires on every walk. Only
  discovery is softened: `invoke` delegates untouched (execution still fails loudly); via an
  aggregate, a dead sidecar's tools are unadvertised and fail closed as `ToolNotFoundError`.
- `FilteredToolRegistry(inner, *, allow)` is a `ToolRegistry` restricted to an allowlist of names
  (ADR-0009 refinements addendum, to stop advertising the write tools a read-only mount can only
  `EROFS`). `describe_tools` intersects the inner advertisement with `allow` (inner order kept);
  `invoke` refuses any other name as `ToolNotFoundError`, so the filter is a real layer, not
  advisory, though it only *restricts*, never grants (an allowlisted name the inner lacks stays
  unadvertised and surfaces the inner not-found). An empty allowlist raises `ValueError`.
- `GatedToolRegistry(inner, *, gated)` is a `ToolRegistry` whose named tools are advertised
  `gated=True` (ADR-0022): the composition-root overlay that declares a *remote* tool
  outbound/irreversible in brain-side code/config (`CORTEX_TOOLS_GATED`), never trusting sidecar
  metadata. `describe_tools` stamps; `invoke` delegates untouched (the dispatcher enforces).
  An empty name set is rejected; a name that never appears is harmless (fail-closed default).
- `UngatedToolRegistry(inner)` is a `ToolRegistry` stripped of gated tools (ADR-0013
  subagent-exclusion addendum): `describe_tools` drops every `gated` spec; `invoke` refuses a
  name the inner registry currently advertises as gated (live walk, no cached view) as
  `ToolNotFoundError`, failing closed as a real layer. Wraps the subagent tool subset in the wiring
  so a subagent is never *handed* an outbound/gated tool, whatever the shared registry grows.

Reference implementations (pure, shipped in core; the runtime wiring until Slice 4):

- `InMemorySessionStore` is a dict-backed `SessionStore` (append/history/`list_sessions`);
  contract-test twin of the Redis adapter (`cortex_session`), intentionally does not
  survive a restart.
- `EchoInferenceBackend` is the scripted fake: for a history with `n` user messages
  (including the current one, counted from the store-backed history alone) whose
  latest user text is `T`, streams exactly `"reply {n}: {T}"` as three `TextChunk`s
  (tool-independent, since it never calls a tool); raises `InferenceError` if the history has no
  user message. Because `n` comes from the store, it keeps counting across a process
  restart. That is observable state survival.
- `SingleResidentModelManager(resident_model, endpoint)` is the `ModelManager` v1
  (ADR-0007 d3): pure policy, no I/O. `acquire` serializes callers with an
  `asyncio.Lock` (its waiter queue is the "queue API") and yields a `ModelLease` for the
  `endpoint`; acquiring any model other than `resident_model` raises
  `ModelUnavailableError` (v1 performs no swap, since that lands in Slice 11). Lives in the
  core because it does no I/O; the process-lifecycle adapter arrives later behind the
  same port.
- `InMemoryMemoryStore` is a list-backed `MemoryStore` ranking by cosine similarity in Python;
  behavioral twin of the pgvector adapter (Slice 5 host half) behind the same contract. A
  zero-magnitude vector scores 0.0; `scopes` filters candidates by namespace before ranking
  (the `WHERE scope = ANY` twin). Does not survive a restart, by design.
- `HashEmbedder(dimension=16)` is a deterministic, I/O-free `Embedder`: identical text always
  yields the identical vector (so a stored memory is its own strongest cosine match), distinct
  text a distinct vector. Carries no semantics. It is the CI/tests stand-in for the real nomic
  adapter (Slice 5 host half). Never emits an all-zero vector.
- `InMemoryToolRegistry({name: (spec, handler)})` is a dict-backed `ToolRegistry`; contract
  twin of the MCP adapter (Slice 6). A handler maps call arguments to result text; `invoke`
  raises `ToolNotFoundError` for an unknown name. No server, fully deterministic.
- `RecordingAuditSink` is a `ToolAuditSink` that keeps invocations in a list (`.records`) so
  tests can assert the audit trail.
- `RecordingConfirmer(*, answer)` is a `Confirmer` returning a fixed `answer` and recording each
  `ConfirmationRequest` in `.requests`, so gate tests can assert what was confirmed (ADR-0013).
- `InMemoryBodyGateway` fakes `BodyGateway` in memory: `get_volume` returns the held `VolumeState`
  and `set_volume` clamps a present `level` to `[0,1]` before applying the given fields; a `fail`
  kwarg scripts an unreachable body (`BodyGatewayError`). Contract twin of `cortex_body_client`'s
  `GrpcBodyGateway`, no live body.
- `InMemoryTaskStore` is a dict-backed `TaskStore`; contract twin of the Redis adapter (Slice 7
  CI half). Unknown ids return `None`. Does not survive a restart, by design.
- `VramBudgetPlacer(*, soft_cap_gb, cortex_reservation_gb)` is the `SubagentPlacer` v1 (ADR-0012):
  pure GPU-first policy, no I/O. `place` returns a GPU `Placement` (reserving `vram_gb`) when the ask
  fits `soft_cap − cortex_reservation − placed`, else a CPU one (reserving nothing); `release` credits
  it back. Sync and lock-free (single-threaded asyncio atomicity), so the concurrent batch races the
  ledger correctly. The ledger is live-resource state, rebuilt from zero. It is never durable state.
- `ResourceBudgetScheduler(cpu_budget, mem_budget_gb)` is `SubagentScheduler` v2 (ADR-0012): pure
  policy over an `asyncio.Condition`. `admit(request)` reserves the request's `cpus`/`memory_gb` while
  both summed reservations stay within targets, queuing (with `notify_all` on release) otherwise; a
  non-positive budget or a charge exceeding the whole budget raises `ValueError`. Replaces Slice 7's
  `ConcurrencyScheduler` (the bare counting semaphore), which the two-dimensional budget subsumes.
- `SystemClock` provides tz-aware UTC `now()`.

**Invariants.**
- Pure and deterministic: no I/O, no adapter or framework imports, stdlib only.
- The engine is a stateless function over the store: nothing about a conversation
  outlives `handle_turn` except what `SessionStore` holds (the one hard rule). Likewise a
  subagent is a stateless function over the `TaskStore`. `SubagentRunner` reads the task by
  id and persists the result, holding nothing between calls.
- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- The untrusted boundary is fail-closed (ADR-0013): `trust`/provenance defaults to `UNTRUSTED`,
  so unstamped content is framed as data; the `TaintLedger` is turn-local, reconstructed each turn
  from the store + live tool results, never persisted (the one hard rule holds); a tainted turn is
  dropped from memory by default (or, under `record_tainted_memory`, recorded with `tainted=True`
  and fenced on recall (ADR-0019)), so recall stays trustworthy either way; a URL sourced only from
  untrusted content never reaches the user when the guardrail is wired (ADR-0015), and the
  persisted reply equals the shown reply. Untrusted-derived content is fenced-and-tainting wherever
  the model sees it, whether live from a tool or recalled from memory.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/` (cancellation and failure
  paths included).

**Dependencies.** Python stdlib only.
