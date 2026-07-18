# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing,
the "handle a user turn" use-case, the memory remember/recall use-case, tool dispatch, and
subagent delegation live here now, and so does the brain handoff (the swap conductor, the deep
model's phase, and the escalating turn wrapper, ADR-0030). No I/O, ever. This is the hexagon's center. The bounded infer↔tool loop is one shared function
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
  `last_activity: datetime`, `pinned: bool = False`. One recent chat as the overlay's switcher
  shows it; `title`/`preview` are already derived (one line, truncated), `last_activity` tz-aware,
  `pinned` whether the user pinned it (ADR-0021 pinning addendum), which lifts it above the recency
  window and drives `merge_pinned`.
- `summarize_ends(session_id, first, last, *, title_override=None, pinned=False) -> SessionSummary`
  is the pure derivation: `title` from the first message, `preview` from the last, `last_activity`
  from the last's `at`; each collapsed to one line and truncated (`TITLE_MAX` / `PREVIEW_MAX`).
  Taking just the two ends states in the core that nothing between them is needed, which is what
  lets a store read only those two records (ADR-0021 bounded-reads addendum). A non-blank
  `title_override` (a brain-generated title a store holds, ADR-0021 titles addendum) replaces the
  first-message title, collapsed and truncated the same way; a blank/absent one falls back. `pinned`
  (a store's pinned-set membership) rides onto the summary.
- `summarize_session(session_id, messages, *, title_override=None, pinned=False) -> SessionSummary`
  is the whole-history form, which delegates to `summarize_ends`. Both `SessionStore`
  implementations derive summaries through these (so the rule never drifts). Requires a non-empty
  history.
- `merge_pinned(summaries) -> tuple[SessionSummary, ...]` (ADR-0021 pinning addendum) is the one
  shared read-path ordering rule: given a listing's already-deduplicated candidate set (the recency
  window unioned with the pinned set), it stable-sorts by recency then by `not pinned`, so pinned
  chats sort above the recency group with each group still newest-active first. It only reorders,
  never adds or drops; deduplication is the caller's job, so the fake and the Redis adapter share
  the exact order and cannot drift.
- `session_title.py` (ADR-0021 titles addendum) is brain-generated titling: `build_title_messages`
  builds the one-message prompt (instruction + opening exchange), `clean_title` collapses/strips/
  bounds a model reply to `TITLE_MAX` (empty when nothing usable), and `generate_title(backend,
  model, messages)` runs one tool-less completion and returns the cleaned title, keeping only
  `TextChunk` (a reasoning model's `ReasoningChunk` and any `ToolCall` are ignored) and letting
  `InferenceError` propagate for the caller to absorb.

Model management (Slice 4, ADR-0007; the swap's value half is ADR-0030, in `model_host.py`):

- `ModelLease` is a frozen dataclass: `endpoint: str`. A live claim on the GPU for one
  model, valid only inside the `acquire(...)` block that yields it; `endpoint` is the
  base URL of that model's `llama-server`.
- `ModelHostState` is an enum `STOPPED` / `LOADING` / `READY` / `FAILED` (string values): what
  one logical model's process is doing, as its host reports it. `start` only *begins* loading,
  so readiness is observed here and nowhere else, which is why every swap health-gates rather
  than trusting a returned `start`.
- `ResidencyPlan(cortex_model, brain_model, evict_models=(), drain_timeout_s=60.0,
  load_timeout_s=300.0, poll_interval_s=1.0)` is the frozen composition-root value the manager,
  the conductor, and boot recovery all read, so they cannot disagree about the topology: which
  model is the standing resident every exit path converges back to, which one a handoff swaps in,
  which other hosted tiers a swap must stop first (the GPU-placed subagent; while the brain is
  resident it is alone on the GPU, ADR-0030 decision 8), and the swap's three bounds. A negative
  drain bound, a negative load bound, or a non-positive poll interval raises `ValueError` at
  construction. `DEFAULT_SWAP_DRAIN_TIMEOUT_S` (60 s, long enough for a normal delegated run to
  finish and short enough that a wedged one does not hold the handoff open for minutes),
  `DEFAULT_SWAP_LOAD_TIMEOUT_S` (300 s, an 18 GB GGUF off the drvfs mount is minutes), and
  `DEFAULT_HEALTH_POLL_INTERVAL_S` (1 s) are the exported defaults.
- `await_model_ready(host, model, *, clock, sleeper, plan) -> ModelHostState` (in
  `health_gate.py`) is the one readiness gate: poll `status(model)` until it settles or
  `plan.load_timeout_s` elapses on the injected `Clock`, waiting `plan.poll_interval_s` through
  the injected `Sleeper` between polls. Returns `READY`/`FAILED` as soon as either is observed,
  else the last state seen when the bound elapses (`LOADING` for a load still grinding,
  `STOPPED` for a start that never took), so a caller can say which happened; a `ModelHostError`
  from `status` propagates rather than being guessed at. The deadline is taken once, before the
  first poll, so a zero bound is already expired: that is how the swap suite drives the timeout
  path with no wall-clock sleep. Shared by the residency scope's swap-in, its restore, and boot
  recovery, so all three agree on what "ready" means.

Memory domain (Slice 5, ADR-0008):

- `MemoryRecord` is a frozen dataclass: `id: str`, `text: str`, `embedding: tuple[float, ...]`,
  `at: datetime`, `scope: str = GLOBAL_SCOPE`, `tainted: bool = False`. One durable memory;
  rejects naive `at` with `ValueError` (memory outlives every process). `scope` is its namespace
  (ADR-0008 addendum); `tainted` is the untrusted-provenance marker (ADR-0019), set `True` when the
  exchange came from a turn that read untrusted content, so recall fences it as data. The caller
  fills every field, leaving the store a pure translator.
- `ScoredMemory` is a frozen dataclass: `record: MemoryRecord`, `score: float`. A retrieval
  hit and its similarity (higher = closer). `score` is always the store's raw cosine similarity
  in `[-1, 1]`, never the key a `RecallPolicy` ranked by, so a reranked result's order is not
  explained by it and no caller may infer a ranking from it. A second field carrying the policy's
  own blended relevance is declined while nothing reads a recall score (ADR-0008 relevance-field
  addendum).

Structured provenance (ADR-0027 addendum; `provenance.py`, stdlib-only so `tools.py` may depend
on it):

- `SourceKind` is an enum `TOOL` / `MEMORY` / `SENDER` / `URI` (string values): what kind of
  source untrusted content came from. `SourceKind.attested` is `True` for `TOOL`/`MEMORY`, whose
  values the brain authored (a registry-advertised tool name, an id we minted), and `False` for
  `SENDER`/`URI`, which are the content's own claim: a consumer renders an attested value as a
  label and a claimed one as a quotation.
- `Provenance` is a frozen dataclass: `kind: SourceKind`, `value: str`. One source, matched
  exactly on both fields (so eviction by sender cannot sweep a URI spelling the same string).
  **`value` is sanitized and bounded in `__post_init__`**, since a source string can be
  attacker-chosen and there must be no constructor that skips the pass: category-`C` characters
  dropped (whitespace exempted, so a newline collapses to a space instead of joining the words it
  separated), whitespace runs collapsed, `<`/`>` removed so a value can never spell an
  untrusted-fence marker, capped at `MAX_SOURCE_CHARS` with an overflow marker, idempotently. A
  value that sanitizes away entirely raises `ValueError`.
- `as_source(kind, raw: str | None) -> Provenance | None` is the tolerant capture form: `None`
  input, or input that sanitizes away, yields no provenance rather than raising, so losing one
  attribution never fails a turn. `MAX_SOURCE_CHARS` (per value) and `MAX_TURN_SOURCES` (per
  turn, enforced by `TaintLedger`) are the two bounds, both exported.
- `claimed_source(kind: object, value: object) -> Provenance | None` is the trust gate of the
  sidecar declaration channel (ADR-0027 sidecar addendum): a tool result may declare a source for
  its own content, but the declaration is attacker-influenceable, so this admits it only under a
  **claimed** `SourceKind` (an attested `kind` a hostile sidecar might name is dropped, so it can
  never forge a trusted-looking label), sanitizes the value via `as_source`, and yields `None` for
  any malformed input (non-`str` kind/value, unknown kind, empty value) rather than raising. The MCP
  `_meta` transport detail lives in the adapter (`cortex_tools`); the core owns only which kinds are
  declarable and the sanitization.
- Nothing the model authored is ever a source: capture sites use the advertised `ToolSpec.name`,
  never `ToolCall.name` or an argument (the `ToolStep` rule, for the same reason).

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
  `sources: tuple[Provenance, ...] = ()`, `budget: DispatchBudget | None = None` (`compare=False`),
  `progress: ProgressSink | None = None` (`compare=False`).
  What the dispatching turn hands the call (ADR-0027): its origin chat (`""` for a session-less
  caller), whether it had read untrusted content at dispatch time, which sources that content
  came from (ADR-0027 addendum), the turn's shared dispatch pool (`None` for a caller
  that runs no tool loop, e.g. the schedule ticker), the stream's progress side channel
  (`None` for a caller with no overlay stream, ADR-0010 progress addendum), and the turn's
  `escalation` handoff slot (`None` for every escalation-less caller, ADR-0030; the type is
  imported under `TYPE_CHECKING` only, keeping `tools.py` cycle-free at runtime since
  `handoff` reaches `untrusted`, which depends on `tools`). One object rather than
  parallel keywords, which is how `sources` landed without touching a call site. `budget`,
  `progress`, and `escalation` are the fields that are live handles rather than values, so all
  are excluded from equality (ADR-0009 turn-wide addendum, ADR-0010 progress addendum,
  ADR-0030): two dispatches of one turn stay comparable and no caller can read "same pool",
  "same stream", or "same slot" out of equality;
  `sources` is a fact about the turn, so it *is* compared. `UNSTAMPED` is the exported
  unattributed default.
- `ToolCall` is a frozen dataclass: `id: str`, `name: str`, `arguments: Mapping[str, Any]`,
  `stamp: TurnStamp = UNSTAMPED`. A model's request to run one tool; `id` correlates it with its
  `ToolResult`. `stamp` is never the model's to set: the dispatcher **overwrites** it at
  dispatch time with the calling turn's `TurnStamp` (ADR-0018/0027) so a built-in that spawns
  further work can propagate provenance, staying transient (the loop persists the unstamped calls)
  and never the gate's input (the gate uses the dispatcher's explicit argument).
- `ToolResult` is a frozen dataclass: `call_id: str`, `content: str`, `is_error: bool = False`,
  `trust: Trust = Trust.UNTRUSTED`, `source: Provenance | None = None`. The outcome fed back to the
  model; `is_error` marks a tool (or dispatch) failure; `trust` is the content's provenance
  (fail-closed default), read by the loop to fence untrusted content and mark taint. `source` is a
  **claimed** source the result declared for its own content (a sidecar-declared sender/locator the
  MCP adapter parsed from the result's `_meta`, ADR-0027 addendum), `None` for every result but the
  email reader's today; it rides beside `content`, so a declaration never disturbs the model-facing
  text, and the ledger notes it beside the attested tool source, only ever annotating, never
  relaxing taint.
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

Brain-handoff domain (ADR-0030, in `handoff.py`; the value half of the model swap; the
`escalate_to_brain` tool that fills the slot lives in `escalate.py` below, and `SwapConductor`
under "Use-case" is what snapshots it and runs the swap):

- `HandoffState` is an enum `PENDING` / `READY` / `BRAIN_ACTIVE` / `DONE` / `FAILED` (string
  values); `terminal` is `True` for the last two, the store-facing distinction (a terminal
  record stops being `active()` and may expire). Boot recovery marks any non-terminal record
  `FAILED`; the full transition sequence belongs to the conductor, not a store.
- `HandoffRecord` is a frozen dataclass: `handoff_id` (= the escalating `turn_id`),
  `session_id`, `requested_at` (tz-aware, rejects naive), `state`, `brief` (the cortex's
  escalation ask), `nonce` (the turn's fence id, so the tail's fenced blocks stay explained),
  `tainted` / `sources` / `untrusted_urls: frozenset[str]` (the whole serialized `TaintLedger`;
  taint that did not survive the swap would fail open, and the URL set is the guardrail's
  laundering evidence), `budget_remaining` / `budget_closed` (the turn-wide dispatch pool's
  position, so a swap never refills the allowance), `rounds_used`, and
  `loop_tail: tuple[Message, ...]` (every message the tool loop appended this turn, in order;
  tool-call stamps are transient live handles and are never persisted, so a re-read tail
  carries `UNSTAMPED` calls). Per the one hard rule it carries ONLY what is not already in a
  store. `taint_ledger()` reconstructs an exact, detached `TaintLedger` for the brain phase
  (bit, sources order, URL set), the round trip the contract test pins.
- `EscalationSlot(refs=None, brief=None)` is the mutable turn-local handle through which
  in-flight state reaches the serializer. Built **empty** by whoever orchestrates the turn (the
  escalating engine wrapper, ADR-0030 decision 5, so it can hold the slot across the delegated
  turn; one slot serves exactly one turn, the builder's contract); the engine **arms** `refs`
  at turn start with an `EscalationRefs` (frozen: references to the live `working` list,
  `taint` ledger, `nonce`, shared `budget`, and `base_len`, how many messages `working` held
  when the loop began, so everything past it is the tail); the `escalate_to_brain` tool writes
  only `brief`. `snapshot(*, turn_id, session_id, requested_at)` freezes it into a `READY`
  record (copies, not references; `rounds_used` derived as one `Role.ASSISTANT` tool-call
  message per dispatched round) and raises `ValueError` on a slot no tool filled or no engine
  armed.

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
- `ZoneResolver` (`schedule_time.py`, ADR-0025 per-rule addendum) is the port turning an IANA key
  into a `DisplayZone | None` (`None` = no such zone, a correction not an exception), needed
  because a per-rule zone is an *open* set the composition root cannot pre-resolve once at boot.
  `UTC_ONLY_RESOLVER` is the core default (knows only `UTC`); the `zoneinfo`-backed resolver is
  injected at the root. `ZoneContext(default=UTC_DISPLAY, resolver=UTC_ONLY_RESOLVER)` bundles the
  two so a tool that both renders and resolves takes one collaborator (`UTC_ZONE_CONTEXT` is the
  default), the `TickerSettings` injection-ceiling precedent.
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
- `CalendarRule(hour, minute, on: DaySelector = DAILY, zone: DisplayZone | None = None)`
  (`schedule_calendar.py`, ADR-0025 calendar + per-rule addenda) is a frozen wall-clock
  recurrence. `describe()` renders a listing phrase (`every mon, fri at 07:30`, with a
  ` (America/New_York)` suffix when a zone is set), `wall_time` the zero-padded `HH:MM`. `zone`
  is the zone the wall time means: set, the rule fires there regardless of `CORTEX_SCHEDULE_TZ`;
  `None`, it takes the deployment `DisplayZone` the occurrence math is handed (a zone-less rule
  follows the deployment zone, the "your 09:00 follows you" default). The module keeps the rule
  and the occurrence math; the day selectors it dispatches to live in `schedule_selectors.py`
  (the yearly addendum's line-cap split).
- `DaySelector = Weekdays | MonthDays | YearDays` (`schedule_selectors.py`, ADR-0025 monthly +
  yearly addenda) is which dates the wall time lands on, a closed union so the codec can
  enumerate it and a rule holds exactly one selector by shape rather than by cross-field check.
  One variant per cycle a wall-clock rule can name. `Weekdays(days: frozenset[int] = EVERY_DAY)`
  holds `date.weekday()` numbers (`DAILY` is the every-day default; `DAY_NAMES` is the
  Monday-first name tuple whose index is the weekday number). `MonthDays(days: frozenset[int])`
  holds calendar days `1..MAX_MONTH_DAY`. `YearDays(days: frozenset[MonthDay])` holds calendar
  dates, `MonthDay(month, day)` being an ordered frozen pair (so sorting **is** chronological
  order within the year) whose `day` is bounded by that month's leap-year length, so 29 February
  constructs and 30 February raises. A date its period lacks **clamps** rather than skipping the
  period (`{31}` means "the last day of every month", 29 February fires on the 28th in a common
  year), and dates that clamp together fire once. No selector is ever empty, which is what bounds
  the occurrence search; each answers `walk(start) -> (candidates, wrapped)`, the fallback being
  the next week's, month's, or year's first listed date.
- `next_calendar_due(rule, after, zone) -> datetime | None` is the pure wall-clock occurrence
  math: the rule's first occurrence strictly after `after`, resolved through the rule's own
  `zone` when it has one and the passed deployment `zone` otherwise (per-rule addendum), via
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
- `TaintLedger` is mutable, turn-local: `tainted: bool = False`, `untrusted_urls: set[str]`
  (the laundering evidence, ADR-0015), and `sources: tuple[Provenance, ...] = ()` (where that
  content came from, ADR-0027 addendum). `mark(trust)` flips `tainted` on the first `UNTRUSTED`
  result; `observe(result, *, source=None)` (what the shared loop calls) marks, collects an
  untrusted result's URLs, AND notes two sources: the attested `source` the loop passes (the
  advertised tool the content came through) and the claimed `result.source` the result declared for
  itself (a sidecar-declared sender/locator, ADR-0027 addendum). Taint is marked from `result.trust`
  before any source is noted, so a declared source can never downgrade the turn.
  `ingest_untrusted(content, *, source=None)` is
  the non-tool twin (ADR-0019). The engine calls it for a recalled tainted memory so it taints,
  contributes URLs, and names its origin like a live untrusted result. `note_source(source)` is
  the bounded accumulator both use: `None` and repeats record nothing, and past
  `MAX_TURN_SOURCES` nothing more is kept, earliest first, so attacker-influenceable values
  cannot grow the record nor push out the source the turn started from. A **trusted** result
  contributes no source, since it is our own text.
  Reconstructed each turn, never persisted. Structurally satisfies `TaintView` (below), so the
  engine passes the live ledger straight to `OutputGuardrail.open`.
- `ToolLoopContext` is a frozen bundle of a tool loop's per-invocation collaborators (`dispatcher`,
  `clock`, `turn_id`, `taint`, `nonce`, `session_id`, `schema=None`,
  `budget=DispatchBudget()` by default factory, `progress=None`, `escalation=None`), keeping
  `stream_tool_loop`
  under its argument ceiling. `session_id` is the originating chat the loop stamps onto each
  dispatch (ADR-0027; `""` for a session-less caller, e.g. a subagent); `schema` (ADR-0028), when
  set, constrains the model's output to that JSON Schema (a constrained tool-less subagent
  envelope; `None` for the cortex and every tool-enabled path); `budget` (ADR-0009 budget
  addendum) caps what may be spent dispatching across the loop's rounds. It is the one
  collaborator a caller may **share**: a context built without one gets its own pool, while a
  subagent spawned from a cortex turn is handed that turn's (ADR-0009 turn-wide addendum), so
  delegation cannot multiply the total. The default is a **factory**, never one instance, or
  every turn in the process would spend from one pool. `progress` (ADR-0010 progress addendum) is
  the stream's side channel the loop stamps onto each dispatch, so a built-in that spawns further
  work (`spawn_subagents`) surfaces a subagent's steps onto the overlay while the loop's own
  generator is suspended inside that dispatch; `None` (a subagent's own inner loop, a session-less
  caller) leaves such work unsurfaced, keeping what reaches the overlay depth-1 as the tree is.
  `escalation` (ADR-0030) is the turn's handoff slot, threaded exactly like `progress` so the
  `escalate_to_brain` built-in reads it off each dispatch's stamp; `None` (the default, every
  escalation-less caller) leaves that tool refusing honestly.
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

Ports (`typing.Protocol`; failures cross them only as the typed errors below; the five
state-store ports `SessionStore` / `MemoryStore` / `TaskStore` / `ScheduleStore` /
`HandoffStore` live in `ports_stores.py` and are re-exported from `ports.py`, a line-cap
split, so every `from cortex_core.ports import ...` and the `cortex_core` barrel are
unchanged):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown),
  `async list_sessions(*, limit) -> Sequence[SessionSummary]` (recent chats newest-active
  first, at most `limit`; ADR-0021 adds a read over the same state, no write path),
  `async set_title(session_id, title) -> None` (persist a brain-generated display title that
  `list_sessions` prefers over the first-message derivation, ADR-0021 titles addendum; a derived
  display value, overwritten by a later call, not conversation content),
  `async delete(session_id) -> None` (HARD-delete a whole chat, its history, title, recency-index
  entry, and pinned membership, the destructive "forget this chat" write, ADR-0021 delete addendum;
  idempotent, leaves nothing orphaned, and needs no tombstone since an unknown session already
  reads as empty history), and `async set_pinned(session_id, *, pinned) -> None` (pin/unpin a chat,
  ADR-0021 pinning addendum; a pinned chat is unioned into `list_sessions` regardless of recency and
  sorts above the recency group via `SessionSummary.pinned`, idempotent by value). The source of
  truth for conversation state; survives swaps and restarts.
- `InferenceBackend` has `stream(model, messages, *, tools=(), schema=None) ->
  AsyncIterator[InferenceEvent]`: one stateless streamed completion, yielding `TextChunk` deltas
  interleaved with `ToolCall`s the model makes from the offered `tools` (ADR-0009). `model` is a
  logical id (ADR-0004). `schema` (a `JsonSchema`, `Mapping[str, object]`), when set, constrains
  decoding to that JSON Schema (ADR-0028); `None` (every caller but a constrained tool-less
  subagent) leaves output unconstrained.
- `ModelManager` provides `acquire(model) -> AbstractAsyncContextManager[ModelLease]`: owns the
  GPU, queues for access, yields a `ModelLease`; leaving the block releases it to the
  next waiter. Consumed by the inference adapter (and, later, the handoff use-case).
  **Unchanged by the swap** (ADR-0030 decision 5 / ADR-0012 decision 1): residency is a
  separate, segregated port rather than a widened `acquire`.
- `ModelHost` (in `ports_models.py`, re-exported here) provides `async start(model)`,
  `async stop(model)`, `async status(model) -> ModelHostState` (ADR-0030 decision 3): the
  process-lifecycle half ADR-0007 deferred. Both verbs are idempotent and `start` only *begins*
  loading, so readiness is observed only through `status`. `model` is a logical id (ADR-0004):
  artifact paths, ports, `-ngl`, and context flags never cross it, so a deployment re-points a
  tier without touching the core. Failures surface as `ModelHostError`. `ScriptedModelHost` is
  the twin CI and the chaos suite drive; the real supervisor adapter's live tests are
  `integration`-marked.
- `ResidencyController` (same module) provides
  `swap_scope(model) -> AbstractAsyncContextManager[None]` (ADR-0030 decision 5): waits for the
  GPU lease to fall free (v1 never preempts a mid-stream round), performs the process swap
  through `ModelHost`, serves `model` for the scope's duration, and **in a `finally`** restores
  the **standing residency**, because the swap back is the recovery path and not an
  optimization. Standing residency is the cortex plus every `plan.evict_models` tier the swap
  in stopped, so a subagent tier is running again by the time admission reopens. Entering may
  raise `SwapFailedError` (the cortex having already been restored by that same `finally`); a
  restore that fails even after its one retry raises `ResidencyRestoreError` from the exit,
  loudly logged. While a scope is active, `acquire` of any other model **waits** rather than
  raising; at most one scope exists at a time, there being one GPU, and a second entry raises
  `HandoffInProgressError`.
- Same port, `handoff_claim() -> AbstractAsyncContextManager[None]`: the one-GPU-one-handoff
  rule taken **before** anything is drained or evicted. Entering claims the whole swap sequence
  for its block or raises `HandoffInProgressError` at once (refuse, never queue). The check and
  the claim happen with nothing awaited between them, which is what makes it a claim and not a
  read: a precondition read from a store and acted on a later await is a race two escalating
  turns on separate streams both pass, after which the loser drains the pool and reopens it in
  its own `finally` while the winner's deep model is resident. The claim does not queue other
  acquires the way a scope does, because the cortex is still serving throughout the drain.
- `TurnRunner` provides
  `handle_turn(session_id, text) -> AsyncGenerator[TurnEvent, None]`: one user turn as a stream
  of domain events. The seam between the orchestrator's stream plumbing and whichever engine
  serves a turn (`TurnEngine`, or `EscalatingTurnEngine` when a turn may hand itself to the deep
  model, ADR-0030), which is why the servicer's engine factory is typed to it rather than to the
  concrete engine.
- `Sleeper` provides `async sleep(seconds) -> None`: the only way core code may wait for
  wall-clock time (ADR-0030). `Clock` says what time it is, which bounds a wait but cannot
  perform one, and the core may not reach for `asyncio.sleep` itself, or every test of a poll
  loop would be a real-time test. The body side has had the same port since the transport's
  retry backoff. Real adapter `AsyncioSleeper`; twin `RecordingSleeper`.
- `Embedder` provides `async embed(text) -> Sequence[float]`: one stateless call, text to vector.
  Dimension is fixed by the deployment's model (ADR-0008); the core assumes no value.
- `MemoryStore` provides `async add(record) -> None`, `async search(embedding, *, k, scopes=None) ->
  Sequence[ScoredMemory]` (top-`k` by similarity, most-similar first), and `async delete_scope(scope)
  -> int`. `scopes` restricts the candidate set to those namespaces (ADR-0008 scoping addendum);
  `None` (the default) ranks over ALL memories (the global-space behavior). `delete_scope` hard-deletes
  every memory in one namespace and returns how many it removed (0 when empty), the forget primitive a
  session-delete cascade and a per-scope eviction policy each named (ADR-0008 delete-scope addendum);
  it takes a single required scope and no wildcard, so a namespace is dropped only when named, and a
  caller mapping a session to `GLOBAL_SCOPE` under global scoping must never pass it (that would erase
  the shared space). Durable, cross-session; the caller builds each record (including its `scope`).
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
- `ProgressSink` (in `progress.py`, a port-free module so `tools.py` may depend on it) has
  `async emit(event: ProgressEvent) -> None`, where `ProgressEvent = ToolActivity | StatusUpdate`
  (ADR-0010 progress addendum): a side channel for the ephemeral progress a suspended turn cannot
  yield itself. While a spawned subagent runs, the cortex turn's generator is suspended inside the
  spawn dispatch, so `SpawnSubagentsTool`/`SubagentRunner` surface the batch's scale (a
  `StatusUpdate`) and each subagent's audited tool steps (a `ToolActivity`) onto this sink instead.
  `emit` is best-effort and non-blocking (a saturated consumer drops rather than stalling the
  subagent). Only registry- or brain-authored fields ride it, so it needs no guardrail pass, the
  same argument the cortex's own `ToolActivity` makes. The real adapter is the orchestrator's
  `SeamProgressSink`; `RecordingProgressSink` is the fake. Reaches the tool off `TurnStamp.progress`,
  so the one shared spawn tool serves every stream without a per-stream field to leak across turns.
- `TaskStore` has `async put_task(task) -> None`, `async get_task(task_id) -> SubagentTask | None`,
  `async put_result(result) -> None`, `async get_result(task_id) -> SubagentResult | None`. The
  hot store (Redis) a subagent is a stateless function over: task and result live here, never in
  a model process (ADR-0010). Unknown ids return `None`.
- `HandoffStore` holds the one in-flight brain handoff (ADR-0030): `async put(record) -> None`
  (persist a `HandoffRecord` snapshot), `async get(handoff_id) -> HandoffRecord | None`,
  `async transition(handoff_id, state) -> bool` (rewrite just the state; `False` for an
  unknown/expired id, never an error), `async delete(handoff_id) -> None` (idempotent), and
  `async active() -> HandoffRecord | None` (the one non-terminal record; at most one handoff is
  in flight at a time, one GPU). The record is the mid-turn state the swap must not lose (brief,
  nonce, taint ledger, budget position, tool-loop tail); everything else is already in the other
  stores, so the swap protocol is a stateless function over this one. The conductor checks
  `active()` before snapshotting, and boot recovery reads it to mark a crash-stranded handoff
  `FAILED`; terminal records are never `active` and the adapter expires them after a diagnosis
  window.
- `SubagentPlacer` has `place(request) -> Placement`, `release(placement) -> None` (both sync): the
  VRAM-budget accountant (ADR-0012). `place` fit-tests `request.vram_gb` against the live headroom
  (`soft_cap − cortex_reservation − placed`), reserving it on GPU or spilling to CPU; `release`
  frees it. The GPU/VRAM contract, separate from `ModelManager`'s lease and `SubagentScheduler`'s
  budget. The three compose at `SubagentRunner`.
- `SubagentScheduler` (`admit(request) -> AbstractAsyncContextManager[None]`,
  `async drain(*, timeout_s) -> bool`, `undrain()`): a soft two-dimensional
  CPU/RAM budget for spawns (yields once the request's `cpus`/`memory_gb` fit the summed targets,
  queues over budget, releases both on exit). A charge larger than the whole budget can never be
  admitted, so it raises `SubagentAdmissionError`: a wall owed by any
  implementation, since `SubagentRunner` catches exactly it (ADR-0012 admission-wall addendum). The
  charge is placement-blind by construction, because `admit` is entered before `place` decides a
  target. A counting budget, not the GPU lease (ADR-0012, revising ADR-0010). `drain` quiesces the
  pool for a model handoff (ADR-0030 decision 4, the additive method ADR-0012 deferred): it stops
  admission at once and waits, bounded by `timeout_s` seconds, for in-flight admissions to release.
  From the call until `undrain`, every `admit` refuses with the same typed error instead of queuing
  (a brain-phase spawn queued against its own drain would deadlock the turn against its own swap),
  and a caller already waiting on a full budget is woken so it refuses rather than sleeps through
  the swap. True means drained clean; False means the bound elapsed with work still in flight and
  nothing killed (v1 never kills a subagent mid-stream), so the swap conductor must abort the
  handoff before evicting anything. `undrain` reverses the window; the conductor owes it in a
  `finally` (swap-back and abort alike), so admission always resumes. Both are idempotent.
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
  `ModelUnavailableError`, `SwapFailedError`, `ResidencyRestoreError`, and
  `HandoffInProgressError`, ADR-0030: the two swap failures, plus the refusal that is not a
  failure at all, since it means the deep model IS loaded and working on another turn, which is
  the opposite of what a failed swap means and so owes the user the opposite note) /
  `MemoryStoreError` / `EmbedderError` / `ToolError` (+ its
  `ToolNotFoundError`) / `TaskStoreError` / `HandoffStoreError` / `ModelHostError` /
  `BodyGatewayError` / `ScheduleStoreError` are typed
  errors; adapters wrap their backend's failures into these with the cause chained.
  `SubagentAdmissionError` is the one raised by pure-core policy rather than an adapter: a
  `SubagentScheduler` refusing a spawn outright (ADR-0012 admission-wall addendum). Bad *values*
  stay `ValueError` (a non-positive budget or ask, an empty roster), as everywhere else.

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
  the `SECURITY_PREAMBLE` is added even on a tool-less turn to explain the markers. It names its
  own record id as the turn's source (`SourceKind.MEMORY`, ADR-0027 addendum), the honest locator
  there: what originally tainted that memory is not stored beyond the bit. After
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
  Title generation (optional, ADR-0021 titles addendum): when `capabilities.generate_titles` is set
  and this is the session's first turn (the pre-turn history held exactly the just-appended user
  message), after persisting the reply the engine generates a switcher title from the opening
  exchange (`generate_title`) and persists it (`set_title`) **before** yielding `TurnCompleted`.
  It runs after the reply's own stream closed, so the GPU lease is a sequential acquire (never the
  reranker's re-entrant hazard) and it never touches the read/list path; persisting before
  completion means the overlay's turn-completion refresh already sees the final title (no race). A
  generation `InferenceError` is absorbed and an empty title is not persisted, either leaving the
  first-message derivation in place, so a failed title never fails the turn.
  Its output half (mapping the loop's deltas onto events, flushing the guarded channels, and
  recording the exchange under the taint policy) lives in `turn_output.py`, shared verbatim
  with the deep model's `BrainPhase` so the two cannot diverge (ADR-0030).
- `stream_turn_events(loop, channels, parts)` / `flush_channels(channels, parts)` /
  `record_exchange(caps, taint, *, session_id, query, reply)` / `render_exchange(user, assistant)`
  (`turn_output.py`) are that shared output half. `stream_turn_events` maps one tool loop's
  deltas onto `TextDelta` / `StatusUpdate` (a reasoning trace) / `ToolActivity`, accumulating
  only reply text into `parts`, closes the loop in a `finally`, and flushes the channels on a
  clean end; `flush_channels` is that flush on its own, for a caller that has to persist a
  partial reply after a mid-stream failure. `record_exchange` applies the one tainted-memory
  policy (ADR-0013/0019) both phases share.
- `SwapConductor(handoffs, residency, brain_phase, plan, clock, scheduler=None)` (ADR-0030
  decision 4, `swap_conductor.py`) runs one brain handoff end to end as a stream of turn events:
  `run_handoff(slot, *, session_id, turn_id)` takes the residency `handoff_claim` **first**, so
  a concurrent handoff is refused with the honest note before anything is read, written,
  drained, or evicted (the store's `active()` check stays as the second line, for a record the
  store still holds); then it snapshots the
  slot into a `READY` record, drains the subagent pool (bounded by `plan.drain_timeout_s`;
  a timeout **aborts before anything is evicted**), enters the residency scope, marks the record
  `BRAIN_ACTIVE` only once the deep model is actually serving, streams `BrainPhase`, and settles
  the record `DONE` (then deletes it) or `FAILED`. Settling is also what releases the store's
  active pointer, so a settling write the store **refuses** is followed by deleting the record
  anyway: a finished handoff left holding that pointer would make `active()` refuse every later
  escalation in the process, with a note saying a handoff is in flight when none is, until a
  restart. A refused *intermediate* write keeps its record, the handoff being genuinely live
  there, and boot recovery settles it. `undrain` is owed in a `finally` on every
  path, swap-back and abort alike, and **after** the swap generator's teardown, never beside it:
  closing that generator is what restores the standing residency, and admission reopens onto the
  subagent tier, so a window lifted first would hand delegated work to a server nothing has
  restarted yet. Every failure, cancellation, and stream teardown leaves the
  record terminal and the standing residency back, and says what happened on the turn's own
  stream. Every nested generator is `aclose`d in a `finally`, the deep model's own round
  included, because a consumer that closes the stream (which is how the seam tears a turn down
  when the client goes away, rather than by cancelling) must unwind all three teardowns rather
  than leave any of them to the collector. The window's four `StatusUpdate`s are each emitted
  where they are true: the drain is announced before it starts, the load before the deep model
  is started, "working on this" only once the health gate has passed and the record says
  `BRAIN_ACTIVE`, and the restore before the cortex is asked back.
  `scheduler=None` is a deployment with no subagent pool: there is nothing to quiesce.
- `BrainPhase(store, backend, clock, brain_model, capabilities)` (`brain_phase.py`) is the deep
  model's half: it rehydrates from the stores and the record alone (history from `SessionStore`,
  the working set as preamble + recalled context + history + the record's `loop_tail`, the
  `TaintLedger` and fence nonce from the record, the dispatch budget resumed at its carried
  position), runs the shared `stream_tool_loop` against the brain model with a **fresh rounds
  allowance and no escalation slot** (it cannot escalate to itself), then persists its reply as
  a second assistant message under the same `turn_id` and records the exchange under the same
  taint policy. A mid-work `InferenceError` persists the partial text with an honest note and
  re-raises, so the conductor fails the record and converges.
- `EscalatingTurnEngine(make_inner, conductor)` (`escalating_engine.py`) is the `TurnRunner` a
  deployment with escalation enabled serves turns through (ADR-0030 decisions 5/6). Per turn it
  builds an `EscalationSlot`, constructs the inner engine around it, passes every event through,
  **suppresses the inner `TurnCompleted`**, and, only if the cortex actually asked to escalate,
  runs the conductor's phase on the same stream before emitting one real `TurnCompleted` whose
  text is the whole turn's. With no escalation requested it is transparent, completion included.
- `recover_handoffs(handoffs, host, plan, *, clock, sleeper)` and
  `converge_residency(host, plan, *, clock, sleeper)` (`swap_recovery.py`) are boot recovery: the
  composition root calls the first once at startup, and it marks any non-terminal record `FAILED`
  (a handoff cannot outlive its process; a live record would otherwise refuse every later
  escalation) and converges the GPU back onto the standing residency. Convergence is the
  conductor's own order: clear the GPU (stop every `plan.evict_models` tier, since a crash can
  leave one holding VRAM the cortex needs, then the deep model), settle the cortex to `READY`,
  and start the evicted tiers back, so a boot leaves the machine where the scope's `finally`
  would have. It deliberately does not resume a deep
  phase, and it never raises: a dead host or store is logged loudly and served around.
- `SWAPPING_STATE` plus the swap window's detail and note texts (`swap_notes.py`) are every
  app-authored string a handoff can put on a turn's stream. Status details are ephemeral
  progress; notes are reply text, streamed but not persisted, except `BRAIN_FAILED_NOTE`, which
  is appended to the deep model's partial reply and persisted with it. `note_for(error)` is the
  same module's mapping from a `ModelManagerError` to the note that is true of the GPU at that
  moment: `ResidencyRestoreError` wins over everything (it is the graver statement, and true
  even when it happened while unwinding another failure); `HandoffInProgressError` (the scope's
  backstop guard, for a caller that swapped without claiming) says a handoff is already running,
  because the deep model IS loaded and the cortex is NOT back, which is the opposite of what the
  swap-failure note asserts; anything else is a swap that genuinely broke.
- `TurnCapabilities(memory=None, tools=None, window=None, guardrail=None,
  record_tainted_memory=False, generate_titles=False, progress=None, escalation=None)` is a
  frozen bundle of the
  optional per-turn collaborators (a `MemoryRecaller`, a `ToolDispatcher`, a `HistoryWindow`, and
  an `OutputGuardrail`) plus the tainted-turn recording policy (ADR-0019), keeping the engine
  within its DI ceiling. The bool governs only writing. A stored tainted memory is always fenced
  on recall regardless. `generate_titles` (ADR-0021 titles addendum), when `True`, generates a
  switcher title on a session's first turn (see the engine's title step below); `False` (default)
  keeps the first-message derivation. `progress` (ADR-0010 progress addendum) is this stream's
  `ProgressSink`: the engine stamps it onto each dispatch so a spawned subagent's steps reach the
  overlay while the turn's own generator is suspended inside the spawn dispatch; `None` (the
  default, a stream-less turn) leaves delegated work unsurfaced. `escalation` (ADR-0030) is the
  turn's `EscalationSlot`: the engine arms its refs at turn start (live working list, ledger,
  budget, nonce, pre-loop `base_len`) and stamps it onto each dispatch so `escalate_to_brain`
  can write the brief; unlike the stream-lived `progress`, a slot serves exactly ONE turn (the
  escalating wrapper constructs a fresh inner engine, and slot, per turn); `None` (the default)
  is every escalation-less deployment. It lives in `turn_context.py` (with the turn-context
  assembly `assemble_inference_messages`, the mechanical split out of `engine.py` that ADR-0029
  decision 15 planned), re-exported unchanged from the barrel.
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
  call surfaces no step; the engine maps it to `ToolActivity`, and a subagent maps it onto the
  spawning stream's `ProgressSink` when it has one, else drops it, ADR-0010 progress addendum).
  The yield vocabulary (`ReasoningDelta`, `ToolStep`, `step_summary`, `MAX_STEP_SUMMARY_CHARS`)
  lives in `loop_events.py`, the line-cap split made when the escalation threading landed.
  It stamps each dispatch with `context.progress`, so a built-in that spawns further work reaches
  the overlay while this loop is suspended inside that dispatch, and with `context.escalation`
  (ADR-0030), so the escalate built-in reads the turn's handoff slot per call. Mutates
  `working` in place with
  the tool-call and `Role.TOOL` result messages; ends on a tool-free step, a `None` dispatcher,
  or `MAX_TOOL_STEPS` (8) rounds. Four independent bounds apply (ADR-0009 budget addendum):
  rounds cap how long the loop runs, `context.budget` (`MAX_TOOL_DISPATCHES`, 32) caps what
  it may *spend* dispatching across those rounds, the dispatcher's `SaliencePolicy` refuses a
  call this loop has already made (salience addendum), and `plan_round` (`tool_round.py`, ADR-0009
  round-cap addendum) caps how *wide* one round may be at `MAX_CALLS_PER_ROUND` (16): the budget
  and salience both leave context growth open, since a round appends a `Role.TOOL` message per
  call whether it ran or was refused, so the cap **drops** the calls a round emits past the limit
  (the assistant message's own `tool_calls` truncated with them, so the conversation stays well
  formed) and keeps one slot past the cap that the dispatcher refuses as `ROUND_OVERSIZED_MSG`,
  which is how the model reads that its round was truncated rather than re-emitting the dropped
  calls forever. Distinctness never enters it: growth is driven by calls *emitted*, so the cap
  counts emitted calls and needs no notion of argument identity (that is the separate structural
  salience refinement). The loop keeps its dispatched calls **grouped by round** and asks
  `dispatcher.admits(call, dispatched)` **before** charging, so a refused repeat costs nothing;
  the history is a loop local and deliberately not turn-wide like the pool, since a repeat is
  redundant only against the `working` messages holding its answer, which a sibling subagent
  cannot see. Each call is charged `dispatcher.cost_of(name)` (ADR-0009 cost addendum), 1 unless
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
  evidence the output guardrail reads, ADR-0015, + the advertised tool it came through as that
  content's source, ADR-0027 addendum, which the next dispatch's stamp carries; a call matching no
  advertised spec attributes nothing rather than falling back to the model's chosen name), and an
  `UNTRUSTED` result is fenced by `wrap_untrusted` before it re-enters `working`. `MAX_TOOL_STEPS` and `ToolLoopContext` are here.
- `plan_round(calls) -> RoundPlan` (`tool_round.py`, ADR-0009 round-cap addendum) is the pure
  per-round cap the loop calls before dispatching a round: a round at or under `MAX_CALLS_PER_ROUND`
  (16) passes through untouched, a wider one is cut to the cap plus one **overflow slot**, and
  everything past that is dropped (not refused, not audited, since a refusal appended would be the
  very context growth being bounded). `RoundPlan(calls, overflowed)` carries the kept calls and
  whether the last is the overflow slot; `RoundPlan.answered()` yields each `(call, is_overflow)`
  pair the loop iterates, refusing the overflow one as `ROUND_OVERSIZED` ahead of every other
  bound. This module also owns the two messages a round appends, since the cap is a cap on exactly
  them: `call_message(text, calls, at, turn_id)` (the assistant's `tool_calls` step, given the
  **plan's** calls so a recorded call is always answered) and `result_message(result, at, turn_id,
  *, nonce)` (one `Role.TOOL` result, `wrap_untrusted`-fenced when the result is `UNTRUSTED`,
  ADR-0013). `MAX_CALLS_PER_ROUND` is half of `MAX_TOOL_DISPATCHES` on purpose, so no blind
  round can spend the whole turn's reach before the model sees a result.
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
- `SessionMemoryCascade(store, scope)` (`memory_cascade.py`, ADR-0021 delete addendum) is the
  scope-aware forget behind a session delete, deliberately SEPARATE from `MemoryRecaller`: the
  turn-facing recaller exposes only record/recall so no tool or tainted turn can reach a forget verb
  (pinned by `test_the_recaller_exposes_no_forget_verb...`), while this trusted out-of-band caller
  holds the same `MemoryStore` + `MemoryScope` and exposes only `delete_session_memories(session_id)
  -> int`. It targets `write_scope(session_id)` and cascades ONLY when that scope is the session's
  own private space (`scope == session_id`, session scoping); the `GLOBAL_SCOPE` guard is checked
  FIRST, so `GLOBAL_SCOPE` can never reach `delete_scope` (which would erase the shared cross-
  conversation space) even for a session whose id equals `GLOBAL_SCOPE`. Wired into `DeleteSession`,
  never into an engine.
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
- `ToolDispatcher(registry, audit, clock, *, confirmer=None, policy=DEFAULT_DISPATCH_POLICY)`
  is the turn's tool gateway and
  capability gate (ADR-0009/0013). `dispatch(call, *, stamp=UNSTAMPED, gated=False,
  refusal=None)` runs `call`
  through the `ToolRegistry`, writes exactly one `ToolInvocation` (with the result's `trust`) to
  the `ToolAuditSink`, and returns the `ToolResult`; a `ToolError` becomes a `TRUSTED` `is_error`
  result (our own message, so it neither frames nor taints). `refusal` (a `DispatchRefusal`) is
  the caller's statement that the call must not run, because its dispatch budget is spent
  (`BUDGET`, ADR-0009 budget addendum), because its salience policy recognized a repeat
  (`REDUNDANT`, salience addendum), or because it is a truncated round's overflow slot
  (`ROUND_OVERSIZED`, round-cap addendum): it returns that member's `message` without invoking,
  audited like any dispatch, and is checked **ahead of the gate** so a model emitting hundreds of
  gated calls cannot flood the user with confirmation prompts before any bound refuses (which is
  also what caps a declined-and-retried send at two approval cards). One reason rather than one
  boolean per bound is what let the round cap land as a third member rather than a keyword. The gate (ADR-0013, table
  revised by
  ADR-0022): a `gated` call on a tainted turn (`stamp.tainted`) is blocked outright as
  `DENIED_MSG`, with the confirmer deliberately unconsulted; on an untainted turn it runs only
  when the `Confirmer` approves, else `USER_DECLINED_MSG` (the fail-closed `confirmer=None`
  default included). Both blocks return **without invoking the tool**, audited. Before the
  registry invoke it **stamps the turn's provenance onto the call** (`replace(call, stamp=stamp)`,
  ADR-0018/0027). That is provenance for built-ins, never the gate's input, and a model-forged
  stamp is overwritten. `describe_tools()` passes through to the registry. `cost_of(name)` answers
  what a call spends of the caller's budget (ADR-0009 cost addendum), from the `ToolCostPolicy` the
  composition root gave it; an unadvertised name is priced at the default rather than free.
  `admits(call, dispatched)` answers whether a call is worth running, from that policy's
  `SaliencePolicy`. Stateless over the ports; the loop drives it and keeps the history.
- `DispatchPolicy(gated_names=(), costs=UNIFORM_COST, salience=REPEAT_SALIENCE,
  gate_reasons={})` (`dispatch.py`, ADR-0009 salience addendum) is what the composition root
  declares about dispatching, in one value: the authoritative gate set, the prices, the salience
  rule, and the per-tool confirm-card reasons (ADR-0030 decision 1: `gate_reasons[name]`
  replaces the generic "outbound or irreversible" line in `ConfirmationRequest.reason` for that
  tool only, so the escalate card can say what is actually approved, the model swap; unnamed
  tools keep the generic reason). Bundled because all four are declarations *about* dispatching
  that a sidecar's own advertisement may claim none of, and because ruff's argument ceiling left
  no room for a seventh parameter on the dispatcher or its builders. It freezes `gated_names`
  and copies `gate_reasons` into a read-only proxy at construction. `DEFAULT_DISPATCH_POLICY`
  is the default.
- `SaliencePolicy` (`tool_salience.py`, ADR-0009 salience addendum) is the pure seam deciding
  which calls deserve dispatching: `admits(call, dispatched) -> bool`, where `dispatched` is the
  caller's calls **grouped by round**, last group being the round in progress (the grouping is
  the port's, because whether a repeat can inform anything turns on whether the model has seen a
  result since it last asked). `RepeatSalience(limit=MAX_IDENTICAL_DISPATCHES)` (the default
  `REPEAT_SALIENCE`, limit 2) admits a call unless an identical one (same `name`, same
  `arguments`; `id` and `stamp` excluded) already ran in this round, or already ran `limit` times
  in this loop. Two rather than one because the failure modes are asymmetric: refusing at one
  denies a legitimate retry or re-read, while allowing the second wastes at most one dispatch.
  Attempts are counted, not answers, so a gate denial or declined confirmation counts too, which
  is what bounds confirmation re-prompting. `AlwaysSalient` / `ALWAYS_SALIENT`
  (`CORTEX_TOOLS_SALIENCE=off`) is the pre-policy loop exactly.
- `ToolCostPolicy(costs={})` (`tool_budget.py`, ADR-0009 cost addendum) is the per-tool price list:
  `cost_of(name)` returns the named price or `DEFAULT_TOOL_COST` (1), and `UNIFORM_COST` is the
  empty policy every dispatcher gets by default (a budget of N is then N calls). Prices must be
  positive, rejected at construction, since a free tool is one the budget stops bounding. It
  rides the `DispatchPolicy` beside `gated_names` for the same reason: both are composition-root
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
  awaits, so a concurrent batch cannot interleave mid-charge. The pool itself is never
  persisted, but its *position* is: `DispatchBudget.resume(*, remaining, closed)` rebuilds one
  from a handoff record (ADR-0030), so the deep model continues on what the turn had left and a
  swap can never refill the allowance, and a pool that had already closed stays closed.
- `SubagentRunner(store, roster, clock, *, tools=None, constrain_output=False)` is a subagent's
  body (ADR-0010/0012/0018),
  a stateless function over the `TaskStore`. `run(task_id, *, budget=None, progress=None)` takes
  the spawning turn's dispatch pool (ADR-0009 turn-wide addendum), so this run's tool calls come
  out of the turn's allowance; `None` means the run is its own root (the ticker's fire) and it gets
  a fresh one. `progress` is the spawning stream's `ProgressSink` (ADR-0010 progress addendum):
  each audited tool step the subagent runs surfaces onto it as a registry-authored `ToolActivity`;
  `None` (the ticker, a direct caller with no overlay) drops the steps. It loads the `SubagentTask`
  **by id**
  (never from cortex memory, so a missing task is an `ok=False` "task not found" result),
  **resolves** the roster entry via `roster.resolve(task.model, tainted=task.tainted,
  tools_enabled=…)` (ADR-0017; an unknown model is an `ok=False` "unknown subagent model" result,
  fail closed), **admits** against that entry's scheduler CPU/RAM budget (outer, may wait; a
  `SubagentAdmissionError`, meaning a charge no budget could ever fit, is caught and becomes an
  `ok=False` "refused before running" result rather than an exception that would cross the spawn
  tool's `gather` and fail the turn, ADR-0012 admission-wall addendum),
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
  Its `spec` is **derived from the runner's roster** (built by `build_spawn_spec` in `spawn_spec.py`,
  which owns the advertisement after the 300-line split; `spawn.py` owns running one): an
  instructions item is a bare string or
  `{instruction, model?, context?}` (`anyOf`), at most `MAX_SPAWN_BATCH` (8) of them per call
  (advertised as the array's `maxItems` and in both descriptions, ADR-0010 batch-cap addendum);
  the `model` enum lists every entry with its
  description and the ADR-0017 caveat, omitted entirely when the runner is tools-enabled or the
  roster has one entry (a knob that cannot do anything is not advertised). The description is
  honest about the **measured** trade-off, not a blanket parallel claim (ADR-0012 admission-wall
  addendum): each roster entry holds one backend that keeps its lease for the whole stream, so
  same-model subtasks serialize and only distinct-model subtasks overlap. The choice note points
  the cortex at distinct-model spread as the wall-clock lever (and gives the model knob a reason
  to reach for beyond a directed pick); the pinned/single-entry note says the batch groups
  independent work rather than speeding it up. `invoke(call)`
  validates items against the roster (bad input / unknown model / an over-cap batch → an
  `is_error` result, not a raise; the batch check runs ahead of item parsing, so nothing is
  stored or placed); a string item that parses as a JSON object carrying an `instruction` key is diverted
  into the object path (real models sometimes stringify the object form, per the ADR-0018 addendum;
  same validation either way). It persists one `SubagentTask` per item, each stamped with the
  requested `model`, the item's `context`, and the **call stamp's `tainted`** (the dispatcher's
  `TurnStamp`, ADR-0018/0027). When the **call stamp carries a `progress` sink** (ADR-0010 progress
  addendum) it emits a `StatusUpdate(state="delegating", detail="delegating N subtask(s)")` (the
  batch's scale, brain-authored) before running, and hands the same sink to each run so the
  subagents' own tool steps surface too. It dispatches the `SubagentRunner`s
  **together** (bounded by the scheduler; genuine overlap needs distinct backends, per the
  measured trade-off above), each handed the **call stamp's `budget`** so the
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
- `EscalateToBrainTool()` (`escalate.py`) is the built-in `escalate_to_brain` tool (ADR-0030
  decision 1): the cortex's mid-turn request for the deep-model handoff, cortex-only like every
  built-in. Stateless and dependency-free: it reads the turn's `EscalationSlot` off each
  dispatch's `TurnStamp` (the `spawn_subagents` progress-sink isolation discipline, so one
  shared instance serves every stream), validates the model-authored `brief` (non-empty string,
  stripped, at most `MAX_BRIEF_CHARS` = 4000; refused whole, never truncated, since a cut-off
  handover would look complete to the deep model), writes `slot.brief`, and answers
  `ESCALATION_QUEUED_MSG` (wrap up, no more tools; the swap itself happens at the loop
  boundary, the conductor's job). Its spec is `gated=True` (its own flag, OR-ed with the
  `CORTEX_TOOLS_GATED` backstop), which buys both existing protections at zero new mechanism:
  the ADR-0022 confirm card on an untainted turn (with the per-tool `ESCALATE_GATE_REASON`
  card text, since the generic gate line would be false about a swap) and the dispatcher's
  tainted-turn hard-deny, so injected content can never force an eviction. A missing slot, a
  bad or over-long brief, and a second escalation in one turn are all trusted `is_error`
  results, never a raise. The opaque-turn (screen-capture pixels) refusal is deferred with the
  vision slice: `Message` carries no pixels yet (`docs/refinements/untrusted-content.md`).
- `ScheduleTaskTool(store, clock, *, tasks_enabled, max_active, zones=UTC_ZONE_CONTEXT,
  item_id_factory=<uuid4>)` /
  `ListScheduledTool(store, *, zone=UTC_DISPLAY)` (`schedule_tools.py`) and
  `CancelScheduledTool(store)` /
  `SnoozeScheduledTool(store, clock, *, zone=UTC_DISPLAY)` /
  `EditScheduledTool(store, clock, *, zones=UTC_ZONE_CONTEXT)`
  (`schedule_verbs.py`, the
  line-cap split that also owns the shared result helpers plus `effective_zone` (a per-zone
  calendar item renders its `due_at` in its own zone); argument parsing in
  `schedule_args.py` for creation, `schedule_verb_args.py` for the lifecycle verbs, and
  `schedule_day_args.py` for the calendar-rule vocabulary both share, which also owns how the
  day selectors and `in_zone` are **advertised** (`day_selector_properties()` /
  `in_zone_property()`) and `parse_calendar_rule` (the shared `at_time` + selector + `in_zone`
  builder), so one vocabulary has one JSON-schema definition and one parser across both verbs)
  are the built-in
  `schedule_task` / `list_scheduled` / `cancel_scheduled` / `snooze_scheduled` /
  `edit_scheduled` tools, cortex-only like `spawn_subagents`, since a subagent cannot re-schedule
  (ADR-0025). The two rule-parsing tools take a `ZoneContext` (default zone + resolver) rather
  than a bare zone. `schedule_task` takes `{kind: reminder|task, text, at | in_seconds,
  every_seconds? (≥ 60), model? (task-only)}`, or `at_time` (`HH:MM`) with at most one of
  `on_days` (weekday names) / `on_month_days` (integers `1..31`) / `on_dates` (`MM-DD` strings)
  and an optional `in_zone` (an IANA key, per-rule addendum) for a calendar rule; its spec is
  rebuilt per `describe_tools` walk and
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
  `edit_scheduled` takes `{id, text?, every_seconds?, at_time?, on_days?, on_month_days?,
  on_dates?}`
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

- `InMemorySessionStore` (in `fakes_session.py`, split from `fakes.py` for the line cap, the
  `fakes_body`/`fakes_schedule` precedent) is a dict/set-backed `SessionStore`
  (append/history/`list_sessions`/`set_title`/`delete`/`set_pinned`; the title in a second dict
  preferred by `list_sessions`, the pins in a set unioned into it the same pinned-first way the
  Redis twin lists, ADR-0021 pinning addendum); contract-test twin of the Redis adapter
  (`cortex_session`), intentionally does not survive a restart.
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
  same port. Still the wiring for a deployment that never escalates.
- `SwappingModelManager(host, endpoints, plan, clock, sleeper)` is `ModelManager` v2
  (ADR-0030 decision 5), in `residency.py`: still pure policy with no I/O of its own, it
  implements the unchanged lease port AND `ResidencyController`. `acquire` keeps v1's
  one-lock-per-GPU discipline over `endpoints` (logical id to base URL, composition-root
  config); `handoff_claim()` claims the whole swap sequence non-blockingly (a second holder
  raises `HandoffInProgressError` with nothing touched), and `swap_scope(model)` claims the one
  residency scope (a second entry raises the same error), takes
  the lease so the swap waits out any in-flight round, stops the cortex and every
  `plan.evict_models` tier, starts `model`, health-gates it, and serves it with the lease free
  so the brain's own rounds can lease normally. Its `finally` stops `model`, starts the cortex,
  gates it, and starts every evicted tier back (best effort, after the gate: a tier that will
  not come back must not be reported as the cortex being gone), retrying the whole attempt once
  before raising `ResidencyRestoreError` with a loud log; while a
  swap or restore is in flight nothing is resident, so an `acquire` racing it says so rather
  than leasing a dead endpoint. That restore runs as its own shielded task and **every**
  cancellation waits for it, not merely the first: the seam delivers two whenever a client
  `Cancel` is followed by the stream's own teardown, and one shielded wait is abandoned by the
  second, which would return the scope while the cortex was still stopped and let the conductor
  reopen subagent admission onto it. Why a scope rather than a swapping `acquire`: the brain's tool
  loop re-acquires once per round, so a swapping `acquire` would thrash minutes each way
  whenever a queued cortex turn interleaved. The two host-facing moves themselves (evict and
  start; stop and restore the standing residency) live in `residency_moves.py`, split off for
  the line cap along the seam the manager already draws: it owns *when* and *who may*, they own
  *what the host is asked to do*, with opposite failure directions (the swap in raises
  `SwapFailedError`, the restore answers a bool because its caller retries it).
- `ScriptedModelHost(*, running=(), status_override=None, fail=None, fail_once=None,
  pause_at=())` is the `ModelHost` twin (ADR-0030 decision 3, in `fakes_model_host.py`): a set
  of running models plus exactly the scripting the swap's named failure modes need.
  `status_override` is what a *running* model reports instead of `READY` (a load that never
  finishes, a model that died at load); `fail` raises `ModelHostError` for an `(op, model)`
  pair every time and `fail_once` for its first occurrence only (the restore's retry);
  `pause_at` blocks an operation at its boundary **after** its effect lands, firing
  `reached[key]` and resuming on `release[key]`, which is how a test kills the conductor at a
  named step. `calls` is the op log, which is what proves a swap requested the right things in
  the right order and at most once.
- `AsyncioSleeper` is the real `Sleeper` (production wiring, the `SystemClock` precedent);
  `RecordingSleeper` is its twin, recording every requested wait in `.waits` and yielding the
  loop instead of consuming time, so a poll loop's *schedule* is asserted rather than its
  elapsed time. Both live in `fakes_sleeper.py`.
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
- `RecordingProgressSink` is a `ProgressSink` recording each emitted `ProgressEvent` in `.events`
  (a tuple), so tests can assert the batch's scale and each subagent's tool steps a turn surfaced
  (ADR-0010 progress addendum). Records unconditionally, where the real `SeamProgressSink` drops
  on a saturated stream.
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
- `InMemoryHandoffStore` is a dict-backed `HandoffStore` plus the single active-handoff pointer;
  contract twin of `RedisHandoffStore` (ADR-0030). Lives in `fakes_handoff.py` (the
  `fakes_schedule`/`fakes_session` line-cap precedent). A non-terminal `put` claims the pointer,
  a terminal write releases it, `delete` clears it when it names the deleted record; terminal
  records stay readable (no TTL to expire them) but are never `active`. Does not survive a
  restart, by design; the Redis adapter is what proves a handoff outlives the swap.
- `AdmitAllScheduler` is the in-memory `SubagentScheduler` twin (ADR-0030), in `fakes_scheduler.py`
  (line-cap split): every `admit` is granted at once with no budget arithmetic, recorded in order
  on its public `admitted` list, while the drain contract stays real (refuse while draining, a
  bounded wait on the in-flight count, reversible via `undrain`). It passes the same drain
  contract suite as `ResourceBudgetScheduler` (`test_scheduler_drain.py`), and exists so the swap
  conductor's composition tests can stage admission without staging budgets.
- `VramBudgetPlacer(*, soft_cap_gb, cortex_reservation_gb)` is the `SubagentPlacer` v1 (ADR-0012):
  pure GPU-first policy, no I/O. `place` returns a GPU `Placement` (reserving `vram_gb`) when the ask
  fits `soft_cap − cortex_reservation − placed`, else a CPU one (reserving nothing); `release` credits
  it back. Sync and lock-free (single-threaded asyncio atomicity), so the concurrent batch races the
  ledger correctly. The ledger is live-resource state, rebuilt from zero. It is never durable state.
- `ResourceBudgetScheduler(cpu_budget, mem_budget_gb)` is `SubagentScheduler` v2 (ADR-0012): pure
  policy over an `asyncio.Condition`. `admit(request)` reserves the request's `cpus`/`memory_gb` while
  both summed reservations stay within targets, queuing (with `notify_all` on release) otherwise; a
  non-positive budget raises `ValueError`, a charge exceeding the whole budget the typed
  `SubagentAdmissionError` (the admission-wall addendum), and so does any admit inside a drain
  window, with `POOL_DRAINING_MSG` naming the transient cause. `drain(timeout_s=...)` implements
  the port's swap-time quiesce (ADR-0030): it flags the window, `notify_all`s so budget waiters
  wake and refuse, then waits for the int in-flight count (never the float residue) to reach zero
  under `asyncio.timeout`; `undrain()` is a synchronous idempotent flag flip, safe because no
  admit can be asleep during the window. Replaces Slice 7's
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
  the model sees it, whether live from a tool or recalled from memory. Its *provenance* is inert by
  construction (ADR-0027 addendum): a `Provenance` cannot hold unsanitized text, cannot spell a
  fence marker, is capped per value and per turn, and never carries a string the model authored.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/` (cancellation and failure
  paths included).

**Dependencies.** Python stdlib only.
