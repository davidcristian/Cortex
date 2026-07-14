# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing,
the "handle a user turn" use-case, the memory remember/recall use-case, tool dispatch, and
subagent delegation live here now; handoff orchestration joins them in a later slice. No I/O,
ever. This is the hexagon's center. The bounded infer↔tool loop is one shared function
(`tool_loop.stream_tool_loop`) that both the cortex turn and each subagent run (ADR-0010).

**Public contract** (everything importable from `cortex_core`; the barrel's re-exports are the
API, declared with the typing spec's redundant-alias form `X as X` rather than an `__all__`
list, so a public name costs one line there instead of two):

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
- `TextDelta(text)` / `StatusUpdate(state, detail)` / `ToolActivity(tool_name, summary)` /
  `TurnCompleted(turn_id, full_text)` are frozen domain events; `TurnEvent` is their union (the
  orchestrator maps them onto the proto's `ServerEvent`). `StatusUpdate` is ephemeral mid-turn
  progress. Its first use (ADR-0020) is a reasoning model's live thinking (`state="thinking"`),
  never persisted or part of the reply, though its detail is a rendered surface and so is
  scrubbed by the output guardrail like the reply (ADR-0020 addendum, `output_channels.py`).
  `ToolActivity` (ADR-0009 addendum) is equally ephemeral:
  one per audited dispatch, emitted just before the tool runs. Both fields are registry-authored
  (`tool_name` = advertised `ToolSpec.name`, `summary` = its description first line); the loop
  emits none for a call that matched no advertised spec, so nothing the model authored, name or
  arguments, ever reaches the chip.
- `TextChunk(text)` / `ReasoningChunk(text)` carries one streamed reply / thinking delta from a
  backend; `InferenceEvent` is the union `TextChunk | ReasoningChunk | ToolCall`, what an
  `InferenceBackend` yields (ADR-0009/0020).

Session listing (Slice 8.7, ADR-0021; `sessions.py`):

- `SessionSummary` is a frozen dataclass: `session_id: str`, `title: str`, `preview: str`,
  `last_activity: datetime`. One recent chat as the overlay's switcher shows it; `title`/
  `preview` are already derived (one line, truncated), `last_activity` tz-aware.
- `summarize_ends(session_id, first, last) -> SessionSummary` is the pure derivation: `title`
  from the first message, `preview` from the last, `last_activity` from the last's `at`; each
  collapsed to one line and truncated (`TITLE_MAX` / `PREVIEW_MAX`). Taking just the two ends
  states in the core that nothing between them is needed, which is what lets a store read only
  those two records (ADR-0021 bounded-reads addendum).
- `summarize_session(session_id, messages) -> SessionSummary` is the whole-history form, which
  delegates to `summarize_ends`. Both `SessionStore` implementations derive summaries through
  these (so the rule never drifts). Requires a non-empty history.

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
- `TurnStamp` is a frozen dataclass: `session_id: str = ""`, `tainted: bool = False`,
  `budget: DispatchBudget | None = None` (`compare=False`). What the dispatching turn hands the
  call (ADR-0027): its origin chat (`""` for a session-less caller), whether it had read
  untrusted content at dispatch time, and the turn's shared dispatch pool (`None` for a caller
  that runs no tool loop, e.g. the schedule ticker). One object rather than parallel keywords, so
  future facts (source URI, sender) join it and call sites ride along. `budget` is the one field
  that is a live handle rather than a value, so it is excluded from equality (ADR-0009 turn-wide
  addendum): two dispatches of one turn stay comparable and no caller can read "same pool" out of
  equality. `UNSTAMPED` is the exported unattributed default.
- `ToolCall` is a frozen dataclass: `id: str`, `name: str`, `arguments: Mapping[str, Any]`,
  `stamp: TurnStamp = UNSTAMPED`. A model's request to run one tool; `id` correlates it with its
  `ToolResult`. `stamp` is never the model's to set: the dispatcher **overwrites** it at
  dispatch time with the calling turn's `TurnStamp` (ADR-0018/0027) so a built-in that spawns
  further work can propagate provenance, staying transient (the loop persists the unstamped calls)
  and never the gate's input (the gate uses the dispatcher's explicit argument).
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

Schedule domain (Slice 9.5, ADR-0025, in `schedule.py` for the value types and the recurrence
math, `schedule_transitions.py` for the pure in-place transitions both stores apply; named
`schedule`/`ScheduleTicker` throughout, never "Scheduler", which means resource *admission*
here):

- `DisplayZone(name, tz)` (`schedule_time.py`, ADR-0025 display addendum) is the frozen value
  every model-facing schedule datetime renders through: `render(moment)` is the one canonical
  string (ISO-8601, seconds precision, offset included), `resolve(naive)` reads an offset-less
  `at` as that zone's wall time and returns the **UTC instant** (`fold=0`, so an ambiguous
  time takes the earlier offset and a nonexistent one the pre-transition offset). Both hop
  through UTC deliberately: `astimezone` is a no-op when the input already carries the target
  zone, which would otherwise print a wall time that does not exist. `UTC_DISPLAY` is the
  default, so an unconfigured deployment renders exactly what the UTC-only v1 rendered.
  The core never imports `zoneinfo`: turning `CORTEX_SCHEDULE_TZ` into a `tzinfo` reads the
  system tz database and so belongs to the composition root. **Display only:** stored `due_at`
  / `anchor` stay UTC instants, and no record, codec, or recurrence arithmetic is affected.
- `ScheduleKind` is an enum `REMINDER` / `TASK` (string values) whose firing means: deliver text
  to the user, or run an autonomous subagent.
- `ScheduleStatus` is an enum `PENDING` / `FIRING` / `DONE`. No `CANCELLED`: cancel deletes the
  record outright, and `DONE` persists only while a fired one-shot reminder awaits delivery
  (terminal cleanup).
- `ScheduledItem` is a frozen dataclass: `id`, `kind`, `text`, `session_id` (the origin chat,
  filled from the dispatcher's `TurnStamp` at creation, ADR-0027; `""` for a session-less
  caller), `due_at`/`created_at` (tz-aware, rejects
  naive), `every: timedelta | None = None` (interval recurrence; must be positive),
  `rule: CalendarRule | None = None` (wall-clock recurrence; **at most one of `every`/`rule`
  is set**, enforced in `__post_init__`, ADR-0025 calendar addendum),
  `anchor: datetime | None = None` (the *interval* grid origin, set only by an occurrence
  snooze so the series keeps its cadence; tz-aware when present, ADR-0025 occurrence-snooze
  addendum; a calendar item needs none, its rule being the grid), `model: str = ""` (task-only roster hint), `tainted: bool = False` (creation taint, OR'd
  with fire-time taint at `finish`), `status`, `deliverable_since: datetime | None = None`,
  `last_outcome: str | None = None`.
- `ScheduleClaim` is a frozen dataclass: `item` (as of the claim, FIRING) + the fencing `token`
  minted per claim; `finish`/`release` apply only under it.
- `FireOutcome` is a frozen dataclass: `fired_at`, `next_due: datetime | None` (None = terminal),
  `deliverable: bool`, `outcome: str | None = None`, `tainted: bool = False` (the fire consumed
  untrusted content).
- `next_due(due_at, every, now) -> datetime | None` is the pure coalescing recurrence: the
  first anchored occurrence (`due_at + k * every`, integer `k >= 1`) strictly after `now`,
  so occurrences missed while down coalesce into the single fire that just happened; `None`
  for one-shots; a non-positive `every` raises `ValueError`. The ticker feeds it
  `recurrence_base(item)` (the `anchor` if set, else `due_at`), so a snoozed recurring item
  re-arms on its original grid, not `until + every`.
- `CalendarRule(hour, minute, on: DaySelector = DAILY)` (`schedule_calendar.py`, ADR-0025
  calendar addendum) is a frozen wall-clock recurrence. `describe()` renders a listing phrase
  (`every mon, fri at 07:30`), `wall_time` the zero-padded `HH:MM`. The rule carries no zone:
  the deployment's one `DisplayZone` is it.
- `DaySelector = Weekdays | MonthDays` (ADR-0025 monthly addendum) is which dates the wall time
  lands on, a closed union so the codec can enumerate it and a rule holds exactly one selector
  by shape rather than by cross-field check. `Weekdays(days: frozenset[int] = EVERY_DAY)` holds
  `date.weekday()` numbers (`DAILY` is the every-day default; `DAY_NAMES` is the Monday-first
  name tuple whose index is the weekday number). `MonthDays(days: frozenset[int])` holds
  calendar days `1..MAX_MONTH_DAY`, and a day the month lacks **clamps to that month's last
  day** rather than skipping the month, so `{31}` means "the last day of every month" and days
  that clamp together fire once. Neither is ever empty, which is what bounds the occurrence
  search; each answers `walk(start) -> (candidates, wrapped)`, the fallback being next week's
  first listed weekday or next month's first listed day.
- `next_calendar_due(rule, after, zone) -> datetime | None` is the pure wall-clock occurrence
  math: the rule's first occurrence strictly after `after`, resolved through
  `DisplayZone.resolve` so it follows daylight saving rather than drifting against it (a
  spring-forward gap fires just past the gap, a fall-back repeat fires once); `None` past
  `datetime.max`, matching `next_due`.
- `next_occurrence(item, now, zone) -> datetime | None` is the single entry point the ticker
  calls: a calendar item answers from its rule, an interval item from anchored `next_due`, a
  one-shot is terminal.
- `apply_snooze(item, until) -> ScheduledItem` and `apply_edit(item, edit) -> ScheduledItem`
  (`schedule_transitions.py`) are the two pure transitions both stores share (the
  ports-before-adapters guarantee): `apply_snooze` moves `due_at` to `until`, re-arms `PENDING`,
  clears deliverability, and pins `anchor` to the pre-snooze `due_at` on a recurring item's first
  snooze (a one-shot and a calendar item both keep `anchor` unset). `apply_edit` clears `rule`
  whenever it sets `every`, keeping the one-shape invariant true, and leaves `due_at` where it
  was. Setting a **rule** is its one timing-moving branch: the item takes the rule's own next
  occurrence, drops `every` and `anchor`, and re-arms `PENDING` with deliverability cleared
  exactly as `apply_snooze` does, so a fired reminder never reaches the due index still `DONE`
  (ADR-0025 rule-edit addendum).
- `RuleChange(rule, due_at)` (`schedule_transitions.py`) is what an edit carries to set a
  calendar rule: the rule plus the first occurrence derived from it. They travel as one value
  because `apply_edit` and both stores are clockless, so the derivation happens at the tool
  boundary, and because binding them keeps `due_at` unreachable except as some rule's own
  occurrence.

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
  `clock`, `turn_id`, `taint`, `nonce`, `session_id`, `schema=None`,
  `budget=DispatchBudget()` by default factory), keeping `stream_tool_loop`
  under its argument ceiling. `session_id` is the originating chat the loop stamps onto each
  dispatch (ADR-0027; `""` for a session-less caller, e.g. a subagent); `schema` (ADR-0028), when
  set, constrains the model's output to that JSON Schema (a constrained tool-less subagent
  envelope; `None` for the cortex and every tool-enabled path); `budget` (ADR-0009 budget
  addendum) caps what may be spent dispatching across the loop's rounds. It is the one
  collaborator a caller may **share**: a context built without one gets its own pool, while a
  subagent spawned from a cortex turn is handed that turn's (ADR-0009 turn-wide addendum), so
  delegation cannot multiply the total. The default is a **factory**, never one instance, or
  every turn in the process would spend from one pool.
  What a given call spends comes from the dispatcher's `ToolCostPolicy` (ADR-0009 cost addendum),
  so a tool's price travels with the gateway that runs it and is not restated per loop.

Output guardrail (ADR-0015; the pure laundering defense built from the redactor + policies in
`guardrail.py`, the URL grammar in `urls.py`, and one URL's canonical identity in `url_identity.py`,
the two having split at the line cap as the seventh addendum landed):

- `extract_urls(text) -> frozenset[str]` (in `urls.py`) finds every clickable URL in `text` (schemes
  `http(s)`, `ftp`, `mailto:`, `tel:`, and `data:` behind a MIME-type anchor so `data:the results`
  prose stays out), normalized for identity (scheme+authority lowercased, trailing prose punctuation
  dropped, path/query case kept; an opaque `mailto:`/`tel:`/`data:` has no `://` so it folds whole).
  Every scheme is anchored at a word boundary, so `sftp://`/`hotel:` are not partial-matched. Six
  **obfuscation-resistant** passes (in `url_identity.py`) reduce a rewritten link to its plain
  identity, in a fixed order so each feeds the next (ADR-0015 addenda):
  **escape decoding** to a bounded fixpoint (HTML character references `evil&#46;com`→`evil.com` the
  way HTML email renders them, and percent-escapes `evil%252ecom`→`evil%2ecom`→`evil.com`), **defang**
  refanging (`hxxp(s)`→`http(s)`, a bracketed `://` or `:` separator and bracketed dots
  `[.]`/`(.)`/`{.}`/`[dot]`/`(dot)` inside a scheme'd URL; run after decode so an entity-hidden bracket
  refangs too, and the matcher captures a whole bracket *chunk* so an encoded inner behind a literal
  closer like `evil[&#46;]com` is consumed and folded, not cut short, ADR-0015 sixth addendum),
  **format-character stripping** (Unicode category `Cf`: zero-width space/joiner, soft hyphen, BOM,
  which render as nothing yet survive NFKC), **punycode decoding** of `xn--` labels via the stdlib
  `idna` codec (so a *registered* IDN homoglyph host feeds the confusable table), **NFKC**
  folding (fullwidth/compatibility homoglyphs → ASCII), and a **curated cross-script confusable** fold
  (Cyrillic/Greek Latin-lookalikes → ASCII, e.g. Cyrillic `расе`→`pace`). So a defanged, encoded,
  zero-width-split, punycoded, fullwidth, or homoglyph link normalizes to the same identity as its
  plain twin. A *transform* in
  the reply is caught, not only verbatim reproduction. The passes compose (a percent-encoded
  homoglyph decodes, then folds). Both sides of the defense use it, namely collection
  (`TaintLedger.observe`) and the user-message allowlist, so a collected URL and its reappearance
  always compare equal. The matcher also admits an **encoded defang separator**
  (`http[&#58;//]evil.com`) as a bracket chunk carrying an escape marker (`&`/`%`), the marker being
  what keeps prose like `http(s)-only` out; the decode fixpoint then resolves whichever encoding it
  was, so no table of encodings lives in the anchor (ADR-0015 seventh addendum). Held deliberately
  out (they would over-redact prose or need a dependency): bare addresses/domains, whitespace-split
  defang (`evil dot com`), and the *full* UTS-39 confusables set.
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
- `ThinkingChannel` + `open_output_channels(guardrail, taint, user_text)` (`output_channels.py`,
  ADR-0020 addendum) extend the same defense over the second display surface, the thinking status
  the overlay renders. `open_output_channels` opens one turn's reply `OutputFilter` plus a
  `ThinkingChannel` under the same policy and user-URL allowlist, one filter instance each so the
  two carry buffers never mix; the channel's `feed(text)` maps one reasoning delta to the
  `StatusUpdate(state=THINKING_STATE)` to show now (`None` = wholly carried). One turn's trace is
  one stream: the carry survives tool steps and reply deltas between thinking bursts, so a URL
  split around a dispatch is joined before matching (per-burst flushing would pass its fragments),
  and `release()` drains the scrubbed carry exactly once, at end of stream. With no guardrail both
  channels pass text through unchanged (an empty delta emits no event on either path).

Ports (`typing.Protocol`; failures cross them only as the typed errors below):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown),
  `async list_sessions(*, limit) -> Sequence[SessionSummary]` (recent chats newest-active
  first, at most `limit`; ADR-0021 adds a read over the same state, no write path).
  The source of truth for conversation state; survives swaps and restarts.
- `InferenceBackend` has `stream(model, messages, *, tools=(), schema=None) ->
  AsyncIterator[InferenceEvent]`: one stateless streamed completion, yielding `TextChunk` deltas
  interleaved with `ToolCall`s the model makes from the offered `tools` (ADR-0009). `model` is a
  logical id (ADR-0004). `schema` (a `JsonSchema`, `Mapping[str, object]`), when set, constrains
  decoding to that JSON Schema (ADR-0028); `None` (every caller but a constrained tool-less
  subagent) leaves output unconstrained.
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
- `ScheduleStore` holds durable schedules with the fenced claim→finish protocol (ADR-0025):
  `async add(item)`, `async get(item_id) -> ScheduledItem | None`, `async list_active()`,
  `async cancel(item_id) -> bool` (deletes outright, so it sticks through an in-flight fire),
  `async claim_due(now, *, lease, limit) -> Sequence[ScheduleClaim]` (due PENDING plus
  lease-expired FIRING, oldest-due-first, fresh fencing token per claim; undecodable records
  quarantined, never a poison pill), `async finish(claim, outcome) -> bool` /
  `async release(claim) -> bool` (both apply only under the claim's token, so a stale claimant
  no-ops `False`; finish ORs fire-time taint onto the item, re-arms at `outcome.next_due` or
  terminates, with terminal records deleted unless deliverable), `async deliverable()`,
  `async ack(item_id) -> bool`, `async snooze(item_id, *, until) -> bool` (postpones the next
  fire via the pure `apply_snooze`; a recurring item moves only its next occurrence and pins
  `anchor` so the series keeps its cadence; a fired-but-undelivered reminder re-arms with
  deliverability cleared; FIRING and unknown answer `False`, fenced like the rest, ADR-0025
  occurrence-snooze addendum), and
  `async edit(item_id, edit) -> bool` (retexts / re-recurs a non-FIRING item via the pure
  `apply_edit`; an interval change leaves `due_at` untouched so only future re-arms take the new
  cadence, while a `RuleChange` moves it to the rule's next occurrence and re-arms; the editing
  turn's taint ORs on; FIRING and unknown answer `False`, WATCH-fenced, ADR-0025 edit and
  rule-edit addenda). A schedule outlives every model swap and restart, and the one hard rule is the
  reason this port exists.
- `Clock` provides `now() -> datetime`, always tz-aware. The core's only time source.
- `SessionStoreError` / `InferenceError` / `ModelManagerError` (+ its
  `ModelUnavailableError`) / `MemoryStoreError` / `EmbedderError` / `ToolError` (+ its
  `ToolNotFoundError`) / `TaskStoreError` / `BodyGatewayError` / `ScheduleStoreError` are typed
  errors; adapters wrap their backend's failures into these with the cause chained.

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
  the reply shown. The reasoning status passes through its own second filter under the same
  policy (`open_output_channels`, ADR-0020 addendum): a wholly-carried delta emits no status,
  the carry survives burst boundaries (a URL straddling a tool call is joined, then matched),
  and the scrubbed carry is released once at end of stream, so the thinking surface carries
  the same laundering guarantee as the reply. With a bare `TurnCapabilities()` (the default)
  the turn behaves exactly as Slice 3.
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
  async generator yielding assistant text deltas (`str`), `ReasoningDelta`s (ADR-0020), and a
  `ToolStep(tool_name, summary)` immediately before each audited dispatch *of an advertised
  tool* (ADR-0009 addendum; both fields copied off the matched `ToolSpec`, so an unadvertised
  call surfaces no step; the engine maps it to `ToolActivity`, a subagent drops it), mutating `working` in place with
  the tool-call and `Role.TOOL` result messages; ends on a tool-free step, a `None` dispatcher,
  or `MAX_TOOL_STEPS` (8) rounds. Two independent bounds apply (ADR-0009 budget addendum): rounds
  cap how long the loop runs, and `context.budget` (`MAX_TOOL_DISPATCHES`, 32) caps what
  it may *spend* dispatching across those rounds, since one round can carry unboundedly
  many calls. Each call is charged `dispatcher.cost_of(name)` (ADR-0009 cost addendum), 1 unless
  a user priced the tool, so with nothing priced the budget is a plain call count. A call that
  no longer fits **closes** the budget rather than being stepped over so
  cheaper calls trickle through behind it: the refusal tells the model to stop calling tools, and
  the turn's spend must not depend on the order the model emitted its calls in. Both the spend
  and the closure are **turn-wide** when the pool is shared with spawned subagents (ADR-0009
  turn-wide addendum), which is what keeps `BUDGET_EXHAUSTED_MSG`'s "this turn has reached its
  limit" literally true.
  Past the budget each further call is still handed to the dispatcher, which refuses it
  as `BUDGET_EXHAUSTED_MSG` and audits it (skipping the dispatch would strand the round's
  `tool_calls` without their `Role.TOOL` answers and leave refusals unaudited), and it yields no
  `ToolStep`, so a chip still means a tool is running.
  It draws the untrusted boundary (ADR-0013): each call is dispatched
  with the turn's `tainted` state and the tool's `gated` flag (the ADR-0022 gate: tainted denies
  outright, untainted confirms), its result is observed by `context.taint` (taint bit + the untrusted-URL
  evidence the output guardrail reads, ADR-0015), and an `UNTRUSTED` result is fenced by
  `wrap_untrusted` before it re-enters `working`. `MAX_TOOL_STEPS` and `ToolLoopContext` are here.
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.
- `MemoryRecaller(store, embedder, clock, *, scope=GLOBAL_MEMORY_SCOPE, policy=RAW_RECALL_POLICY,
  id_factory=<uuid4>)` is the memory use-case (ADR-0008). `record(text, *, session_id,
  tainted=False)` embeds `text`, persists a `MemoryRecord` (id from the factory, `at` from the clock,
  embedding from the embedder, `scope` from the policy's `write_scope(session_id)`, `tainted` from
  the caller per ADR-0019), and returns it; `recall(query, *, k, session_id)` embeds `query`, fetches
  the store's `policy.candidate_k(k)` `ScoredMemory` within the policy's `read_scopes(session_id)`,
  and returns `policy.select(...)` reranked and pruned to `k`. Stateless over the store: every memory
  lives in `MemoryStore`, so recall is identical across restarts and swaps. Wired into `TurnEngine`
  (retrieve-into-context, record-at-turn-end) when injected. The engine threads its `session_id`
  through both calls.
- `MemoryScope` (port, `scope.py`) + `GlobalMemoryScope` / `SessionMemoryScope` (ADR-0008 scoping
  addendum) are the pure policy mapping a turn's `session_id` to its `write_scope` and `read_scopes`
  (the `HistoryWindow` pattern). `GlobalMemoryScope` (the `GLOBAL_MEMORY_SCOPE` singleton, the
  default) writes `GLOBAL_SCOPE` and reads `None` (all), keeping recall cross-session;
  `SessionMemoryScope` writes/reads the `session_id`, isolating a conversation's memory to itself.
  Selected at the composition root via `CORTEX_MEMORY_SCOPE`; the store filters, the policy decides.
- `RecallPolicy` (port, `rerank.py`) turns an over-fetched candidate pool into the final `k` hits
  (the `MemoryScope` / `HistoryWindow` pattern): `candidate_k(k)` sizes the pool the recaller fetches,
  `select(hits, *, now, k)` reranks and prunes it. The port and the default `RawRecallPolicy` (its
  `RAW_RECALL_POLICY` singleton keeps v1 top-`k` cosine exactly) live in `rerank.py`; the three opt-in
  policies and their shared `_recency_blend` / `_redundancy` / `_greedy_mmr` math live in
  `rerank_policies.py` (ADR-0008 rerank + MMR + recency-and-diversity addenda; split at the 300-line
  cap). `RerankingRecallPolicy` blends similarity with an exponential recency decay and drops
  near-duplicate memories; `MmrRecallPolicy` selects greedily for maximal marginal relevance
  (`relevance_weight` trading query-relevance against redundancy to an already-kept hit), diversifying
  beyond the reranker's near-duplicate cutoff; `RecencyMmrRecallPolicy` runs that MMR selection over
  the recency blend rather than raw similarity, combining both axes. Selected at the composition root
  via `CORTEX_MEMORY_RECALL`; the reported `ScoredMemory.score` stays the raw cosine, only order and
  membership change.
- `ToolDispatcher(registry, audit, clock, *, confirmer=None, gated_names=(), costs=UNIFORM_COST)`
  is the turn's tool gateway and
  capability gate (ADR-0009/0013). `dispatch(call, *, stamp=UNSTAMPED, gated=False,
  over_budget=False)` runs `call`
  through the `ToolRegistry`, writes exactly one `ToolInvocation` (with the result's `trust`) to
  the `ToolAuditSink`, and returns the `ToolResult`; a `ToolError` becomes a `TRUSTED` `is_error`
  result (our own message, so it neither frames nor taints). `over_budget` (ADR-0009 budget
  addendum) is the caller's statement that its dispatch budget is spent: it returns
  `BUDGET_EXHAUSTED_MSG` without invoking, audited like any dispatch, and is checked **ahead of
  the gate** so a model emitting hundreds of gated calls cannot flood the user with confirmation
  prompts before the budget refuses any. The gate (ADR-0013, table revised by
  ADR-0022): a `gated` call on a tainted turn (`stamp.tainted`) is blocked outright as
  `DENIED_MSG`, with the confirmer deliberately unconsulted; on an untainted turn it runs only
  when the `Confirmer` approves, else `USER_DECLINED_MSG` (the fail-closed `confirmer=None`
  default included). Both blocks return **without invoking the tool**, audited. Before the
  registry invoke it **stamps the turn's provenance onto the call** (`replace(call, stamp=stamp)`,
  ADR-0018/0027). That is provenance for built-ins, never the gate's input, and a model-forged
  stamp is overwritten. `describe_tools()` passes through to the registry. `cost_of(name)` answers
  what a call spends of the caller's budget (ADR-0009 cost addendum), from the `ToolCostPolicy` the
  composition root gave it; an unadvertised name is priced at the default rather than free.
  Stateless over the ports; the loop drives it.
- `ToolCostPolicy(costs={})` (`tool_budget.py`, ADR-0009 cost addendum) is the per-tool price list:
  `cost_of(name)` returns the named price or `DEFAULT_TOOL_COST` (1), and `UNIFORM_COST` is the
  empty policy every dispatcher gets by default (a budget of N is then N calls). Prices must be
  positive, rejected at construction, since a free tool is one the budget stops bounding. It
  lives on the dispatcher beside `gated_names` for the same reason: both are composition-root
  declarations *about* tools by name, so a sidecar's advertisement can claim neither. Frozen, and
  it copies the mapping it is built from, so the config object cannot edit prices afterwards.
  `MAX_TOOL_DISPATCHES` (32) lives in the same module: `tool_budget.py` owns how much one turn may
  *spend*, `tool_loop.py` (`MAX_TOOL_STEPS`) how *long* one loop runs, which is the split that
  keeps the two deliberately independent bounds from reading as one.
- `DispatchBudget(limit=MAX_TOOL_DISPATCHES)` (`tool_budget.py`, ADR-0009 turn-wide addendum) is
  one turn's allowance: `limit` / `spent` / `closed` read it, and `charge(cost) -> bool` spends
  what fits and permanently **closes** the pool when a call does not, so "closes rather than steps
  over" is the budget's property and not a rule each loop reimplements. Mutable and shared on
  purpose (the one such object in the core, compared by identity), because it must outlive a
  single `stream_tool_loop` invocation: the cortex loop and every subagent it spawns hold the
  same pool, reached over the dispatch `TurnStamp`. Safe without a lock because `charge` never
  awaits, so a concurrent batch cannot interleave mid-charge. Never persisted: it bounds one
  turn's reach and dies with the turn.
- `SubagentRunner(store, roster, clock, *, tools=None, constrain_output=False)` is a subagent's
  body (ADR-0010/0012/0018),
  a stateless function over the `TaskStore`. `run(task_id, *, budget=None)` takes the spawning
  turn's dispatch pool (ADR-0009 turn-wide addendum), so this run's tool calls come out of the
  turn's allowance; `None` means the run is its own root (the ticker's fire) and it gets a fresh
  one. It loads the `SubagentTask` **by id**
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
  the partial text. With `constrain_output` on **and** the tool-less path (`tools is None`, the
  ADR-0028 niche where a weak model is reachable), the loop's `schema` is the fixed reply
  envelope, so the reply is constrained JSON the runner unwraps to the `reply` string before
  persisting (a malformed envelope degrades to an `ok=False` result whose `output` keeps the raw
  text and whose `detail` is a fixed message, so the raw text stays in the store, not the cortex);
  a tools-enabled subagent is never constrained (the JSON grammar would fight tool-calling).
  Exposes `roster`/`tools_enabled` (read-only) so the spawn tool advertises
  exactly what it will honor. Tools-enabled but not given the delegation tool, so fan-out is
  depth-1.
- `SpawnSubagentsTool(runner, store, clock, *, task_id_factory=<uuid4>)` is the built-in
  `spawn_subagents` tool (`SPAWN_TOOL_NAME`), the cortex's delegation primitive (ADR-0010/0018).
  Its `spec` is **derived from the runner's roster**: an instructions item is a bare string or
  `{instruction, model?, context?}` (`anyOf`), at most `MAX_SPAWN_BATCH` (8) of them per call
  (advertised as the array's `maxItems` and in both descriptions, ADR-0010 batch-cap addendum);
  the `model` enum lists every entry with its
  description and the ADR-0017 caveat, omitted entirely when the runner is tools-enabled or the
  roster has one entry (a knob that cannot do anything is not advertised). `invoke(call)`
  validates items against the roster (bad input / unknown model / an over-cap batch → an
  `is_error` result, not a raise; the batch check runs ahead of item parsing, so nothing is
  stored or placed); a string item that parses as a JSON object carrying an `instruction` key is diverted
  into the object path (real models sometimes stringify the object form, per the ADR-0018 addendum;
  same validation either way). It persists one `SubagentTask` per item, each stamped with the
  requested `model`, the item's `context`, and the **call stamp's `tainted`** (the dispatcher's
  `TurnStamp`, ADR-0018/0027). It runs the `SubagentRunner`s
  **concurrently** (bounded by the scheduler), each handed the **call stamp's `budget`** so the
  whole batch draws on the spawning turn's one pool (ADR-0009 turn-wide addendum) so a batch
  cannot buy unbounded external calls (its unbounded *model runs* are what `MAX_SPAWN_BATCH`
  bounds, the pool counting a different currency), and returns one aggregated
  `ToolResult`, with a
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
- `ScheduleTaskTool(store, clock, *, tasks_enabled, max_active, zone=UTC_DISPLAY,
  item_id_factory=<uuid4>)` /
  `ListScheduledTool(store, *, zone=UTC_DISPLAY)` (`schedule_tools.py`) and
  `CancelScheduledTool(store)` /
  `SnoozeScheduledTool(store, clock, *, zone=UTC_DISPLAY)` / `EditScheduledTool(store)`
  (`schedule_verbs.py`, the
  line-cap split that also owns the shared result helpers; argument parsing in
  `schedule_args.py` for creation, `schedule_verb_args.py` for the lifecycle verbs, and
  `schedule_day_args.py` for the calendar-rule vocabulary both share) are the built-in
  `schedule_task` / `list_scheduled` / `cancel_scheduled` / `snooze_scheduled` /
  `edit_scheduled` tools, cortex-only like `spawn_subagents`, since a subagent cannot re-schedule
  (ADR-0025). `schedule_task` takes `{kind: reminder|task, text, at | in_seconds,
  every_seconds? (≥ 60), model? (task-only)}`, or `at_time` (`HH:MM`) with at most one of
  `on_days` (weekday names) / `on_month_days` (integers `1..31`) for a calendar rule; its spec is rebuilt per `describe_tools` walk and
  **carries the current time** from the `Clock` (the model cannot otherwise compute an
  absolute `at`), rendered in the display zone and labelled with its name,
  advertising `task`/`model` only when delegation is wired. Two creation bounds:
  the `max_active` cap, and the **tainted-task refusal**. A tainted turn cannot create a
  `kind: "task"` item at all (`TAINTED_TASK_MSG`; a reminder may carry attacker-influenced text
  because it only reaches a human, an autonomous instruction may not). Creation fills
  `ScheduledItem.tainted` **and** `ScheduledItem.session_id` from the dispatcher's `call.stamp`
  (the `TurnStamp`, ADR-0027); creation/cancel/snooze results
  are `TRUSTED` and never echo the stored text; the listing echoes text and so is `TRUSTED` only
  when every listed item is clean, else `UNTRUSTED` (fenced + re-tainting, the spawn aggregate
  rule). `snooze_scheduled` takes `{id, for_seconds}` (relative by meaning; `for_seconds`
  reuses the recurrence-interval bounds `[60 s, ten-year]`, not the unbounded one-shot delay)
  and postpones the next fire; a recurring item moves only its next occurrence, the store
  pinning `anchor` so the series keeps its cadence (occurrence-snooze addendum).
  `edit_scheduled` takes `{id, text?, every_seconds?, at_time?, on_days?, on_month_days?}`
  (a bounded interval sets recurrence, `0` stops it, omission leaves it; `at_time` plus at most
  one day selector sets a wall-clock rule instead, mutually exclusive with `every_seconds`; at
  least one change required) and changes text/recurrence in place. An interval change never moves `due_at`; a
  rule change re-derives it and reports the new time, since a rule is its own grid (rule-edit
  addendum); unlike cancel/snooze
  it ORs the editing turn's taint onto the item and refuses editing a *task* on a tainted turn
  (the creation-side refusal, since a retext injects content), while a reminder edit on a
  tainted turn is allowed (edit addendum). All five ungated by default
  (`CORTEX_TOOLS_GATED` is the backstop); bad arguments, a naive `at`, and a
  `ScheduleStoreError` all become `is_error` `TRUSTED` results. None ever raises.
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
- `InMemoryScheduleStore(*, token_factory=<uuid4>)` is a dict-backed `ScheduleStore` implementing
  the full fenced protocol (fresh token per claim, stale finish/release no-op `False`,
  cancel-deletes-outright, terminal cleanup, fire-time taint OR); contract twin of
  `RedisScheduleStore` (ADR-0025). Lives in `fakes_schedule.py` (`fakes.py` is at its line-cap
  budget). Does not survive a restart, by design. The Redis adapter proves the hard rule.
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
