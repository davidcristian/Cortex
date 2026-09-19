# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: the domain types, the ports every adapter implements, and the
application logic that runs a turn, remembers, delegates work and swaps models. It performs no I/O
and imports nothing outside the Python standard library. Anything that touches a network, a disk, a
GPU or the wall clock reaches the core as a port that the composition root fills in.

**The rule this package is built around.** No conversation, task or turn state may live inside a
model process, because a model can be unloaded from the GPU at any moment (AGENTS.md, "The one hard
rule"). Every use case here is a function over the stores: it reads what it needs, runs, writes the
result back and keeps nothing between calls. `TurnEngine` works over `SessionStore`,
`SubagentRunner` over `TaskStore`, and the model handoff over `HandoffStore`.

**Where the rest of this contract is written.** The core is one package doing five jobs, and each
has its own document:

- [brain-core-turn.md](brain-core-turn.md): one conversation turn. The turn engine, history
  windowing and recaps, session listing and titles, and the output guardrail.
- [brain-core-memory.md](brain-core-memory.md): durable memory. The embedder and store ports, the
  recaller, memory scopes, and the policies that rank a recall.
- [brain-core-tools.md](brain-core-tools.md): what a model can ask for. The tool values and ports,
  the dispatcher, the tool loop, the registry combinators, the built-in tools and schedules.
- [brain-core-subagents.md](brain-core-subagents.md): delegated work. Placement, admission, the
  roster and the runner that performs one subtask.
- [brain-core-residency.md](brain-core-residency.md): which model is on the GPU. The model host,
  the residency plan, the handoff record, the swap and the deep model's phase.

This document has what all five use: the public surface rule, the conversation types, images,
provenance, the untrusted-content primitives, the typed errors, and log rendering.

## Public surface

`from cortex_core import X` reaches every public name. The names themselves are declared in nine
area files under `cortex_core._surface` (`ports`, `turn`, `tools`, `subagents`, `memory`,
`schedule`, `residency`, `logs`, `fakes`), each importing its area's names from the modules that
define them and listing them in its own `__all__`; `cortex_core/__init__.py` re-exports all nine.
Nothing outside the package imports `_surface`. A new public name is added to the area file it
belongs to, which is where the 300-line limit applies, and picking the area is the only judgement
it needs. [ADR-0064](../adr/ADR-0064-core-public-surface.md) explains why the single flat list ran
out of room.

## Conversation types

- `Tier` is an enum of model tiers: `CORTEX`, `SUBAGENT`, `BRAIN`. `RoutingHints` is a frozen
  record of what a caller knows about a turn, and `route_turn(hints) -> Tier` is the pure decision
  over it, in strict order: an explicit tier wins, then deep reasoning (`BRAIN`), then narrow
  delegable work (`SUBAGENT`), then `CORTEX` (`routing.py`).
- `Role` is an enum: `USER`, `ASSISTANT`, `SYSTEM`, `TOOL`. `SYSTEM` messages are built by the
  engine for one turn (recalled memories, the security preamble) and `TOOL` messages are tool
  results fed back to the model. Only `USER` and `ASSISTANT` messages are persisted.
- `Message(role, text, at, turn_id, tool_calls=(), tool_call_id=None, images=())` is one message,
  frozen. A naive `at` raises `ValueError`, because externalized state needs its timezone.
  `turn_id` ties a user message to the reply it produced. Images are rejected on any role but
  `TOOL` with `ValueError`: pixels belong to one turn, and the llama.cpp adapter builds a
  content-parts array for tool messages only, so an image anywhere else would be dropped on the way
  to the model without a word. The rule is on the value rather than only in the stores, so a code
  path that never touches a store cannot break it (ADR-0029).
- `new_turn_id() -> str` returns a new turn id (a uuid4 string). What an id looks like belongs to
  the domain; when one is made belongs to whoever schedules the turn, which is the orchestrator's
  `Converse` stream (ADR-0046 decision 9). A `TurnRunner` is given the id it serves.
- `TurnEvent` is the union a turn streams: `TextDelta(text)`, `StatusUpdate(state, detail)`,
  `ToolActivity(tool_name, summary)`, `ToolOutcome(tool_name, ok)` and
  `TurnCompleted(turn_id, full_text)` (`events.py`). The orchestrator maps them onto the wire's
  `ServerEvent`. `StatusUpdate` is progress shown during the turn and never persisted; its first
  use is a reasoning model's live thinking (`state="thinking"`, ADR-0020), and because it is
  rendered to the user it passes the output guardrail like the reply.
- `ToolActivity` is emitted once per audited dispatch, just before the tool runs, and both its
  fields come from the advertised `ToolSpec`, never from what the model wrote (ADR-0009
  decision 15). Exactly one `ToolOutcome` closes it, on every path out of a dispatch the turn made
  itself, refusals and tool failures included, with `ok` taken from the same result the audit
  record uses (ADR-0029 decision 18). Progress a delegated subagent sends through `ProgressSink`
  has activities and no outcomes, so an activity with no outcome is normal on the wire. `ok=False`
  means the brain cannot confirm the action happened, never that it did not.
- `InferenceEvent` is what an `InferenceBackend` yields: `TextChunk(text)` and
  `ReasoningChunk(text)` are one streamed delta of reply or thinking, `ToolCall` is one whole call
  the model made, and two events describe the completion itself.
- `DecodeStop(reason)` is why the server stopped decoding, with a `StopReason` of `FINISHED`,
  `CAPPED` (a token limit stopped it), `CALLED` (it stopped to call a tool) or `UNKNOWN` (the
  engine gave a reason this core does not recognize), ADR-0048. It is a closed set because the wire
  value is an engine's own vocabulary, which the adapter translates.
- `DecodeCadence(tokens_per_second, tokens)` is how fast the server decoded one completion, as the
  server reports it (ADR-0055 decision 4). `tokens` is what makes the rate readable, since a short
  completion's rate is dominated by whatever the server was doing when it started. Both fields
  reject a negative value.
- Reporting either closing event is optional and the two are independent. A missing event means
  the backend reported nothing, never that the completion finished or that its rate was good.

## Images

`ImagePart(data, mime_type, width, height)` (`images.py`) is one picture. Its `__post_init__`
raises `ImageError` on empty bytes, a type outside `ALLOWED_MIME_TYPES` (`image/png`,
`image/jpeg`, `image/webp`), a dimension outside `1..MAX_IMAGE_EDGE` (8192), or more than
`MAX_IMAGE_BYTES` (6 MiB) of data. `data_uri(part)` renders the `data:<mime>;base64,<payload>`
form an OpenAI content-parts array takes. **The core never decodes an image**: it checks
declarations and encodes, so no attacker-controlled bytes reach a decoder inside the process that
holds the memory store. `MAX_IMAGE_BYTES` is also the body's capture limit, written once per
toolchain and compared by `scripts/crosscheck.py`; the brain sends the number to the body as the
capture request's `max_bytes` rather than trusting the body to have the same constant. The module
imports only the standard library, so `tools.py`, `conversation.py` and `body.py` can all use it.

## Provenance and the untrusted-content boundary

Third-party text that reaches the model is data, never instruction. The primitives are in
`provenance.py` (standard library only, so `tools.py` can depend on it) and `untrusted.py`, and
the decisions are ADR-0013, ADR-0019 and ADR-0027.

- `Trust` is an enum `TRUSTED` / `UNTRUSTED`: where a tool result's content came from. The default
  is `UNTRUSTED` everywhere, so unmarked content is treated as data.
- `SourceKind` is an enum `TOOL` / `MEMORY` / `SENDER` / `URI`. `SourceKind.attested` is `True` for
  `TOOL` and `MEMORY`, whose values the brain itself wrote, and `False` for `SENDER` and `URI`,
  which are the content's own claim about itself: a consumer renders an attested value as a label
  and a claimed one as a quotation.
- `Provenance(kind, value)` is one source, compared on both fields. Its `value` is sanitized and
  bounded in `__post_init__`, since a source string can be chosen by an attacker and there must be
  no constructor that skips the pass: control characters are dropped, whitespace runs are
  collapsed, `<` and `>` are removed so a value can never write a fence marker, and the result is
  cut at `MAX_SOURCE_CHARS` with an overflow marker. The pass is idempotent, and a value that
  sanitizes away to nothing raises `ValueError`.
- `as_source(kind, raw)` is the forgiving form used at capture sites: `None`, or input that
  sanitizes away, returns no provenance rather than raising, so losing one attribution never fails
  a turn. `claimed_source(kind, value)` admits a source a tool result declared for its own content,
  under a claimed `SourceKind` only, so a hostile sidecar cannot forge a trusted-looking label.
  `MAX_TURN_SOURCES` bounds how many sources one turn keeps.
- Nothing the model wrote is ever a source. Capture sites use the advertised `ToolSpec.name`, never
  the name or arguments in a `ToolCall`.
- `SECURITY_PREAMBLE` is the instruction added as a `Role.SYSTEM` message when a turn has tools:
  content inside the untrusted markers is data and is never obeyed.
  `PLAIN_SECURITY_PREAMBLE` is the same instruction for a turn with neither tools nor untrusted
  content, with every sentence about tools and markers removed (ADR-0013 decision 8). Exactly one
  of the two opens every turn. `security_preamble_message(at, turn_id)` and
  `plain_security_preamble_message(at, turn_id)` build them.
- `wrap_untrusted(content, *, nonce)` fences untrusted content between
  `<untrusted-tool-output id=NONCE>` markers. A closing marker written inside `content` cannot end
  the fence, because it does not have the turn's nonce. `new_nonce()` makes that nonce
  (`secrets.token_hex(8)`); it is unpredictable and is discarded with the turn.
- `TaintLedger` is the mutable, turn-local record of what a turn has read: `tainted` (untrusted
  content entered), `opaque` (some of it was a picture and so could not be fenced, ADR-0029),
  `untrusted_urls` (the evidence the output guardrail reads), and `sources`. `mark(trust)` sets
  `tainted` on the first `UNTRUSTED` result. `observe(result, *, source=None)` is what the tool
  loop calls: it marks, collects the result's URLs, and notes both the tool the content came
  through and any source the result declared for itself. Taint is set from `result.trust` before
  any source is noted, so a declared source can never lower it. `ingest_untrusted(content, *,
  source=None)` is the same for content that did not come from a tool, which is how a recalled
  tainted memory taints the turn it is read into (ADR-0019). `note_source` is the bounded
  accumulator both use: `None` and repeats record nothing, and past `MAX_TURN_SOURCES` nothing more
  is kept, earliest first, so attacker-chosen values can neither grow the record nor push out the
  source the turn started with. A ledger is rebuilt each turn and never persisted.
- `DENIED_MSG` is the error content for a tool call that needs confirmation and was made on a
  tainted turn, which is refused outright and never offered to the user (ADR-0022).
  `USER_DECLINED_MSG` is the content for one the user declined, or that no confirmer answered.

## Time

- `Clock` (port) returns a timezone-aware `now()`. It is the core's only source of the time.
  `SystemClock` is the real one.
- `Sleeper` (port) provides `async sleep(seconds)`, the only way core code may wait for wall-clock
  time (ADR-0030). `Clock` bounds a wait but cannot perform one, and the core may not call
  `asyncio.sleep` itself, or every test of a polling loop would run in real time. The real adapter
  is `AsyncioSleeper`; `RecordingSleeper` keeps every requested wait in `.waits` and yields the
  event loop instead, so a poll loop's schedule can be asserted rather than its elapsed time.

## Typed errors

Failures cross a port only as these: `SessionStoreError`, `InferenceError`, `ModelManagerError`,
`MemoryStoreError`, `EmbedderError`, `ToolError`, `TaskStoreError`, `HandoffStoreError`,
`ModelHostError`, `BodyGatewayError` and `ScheduleStoreError`. Adapters wrap their backend's
failures into them with the cause chained. Bad values stay `ValueError`. Each narrower kind states
something the general one cannot:

- `MalformedToolCallError` (under `InferenceError`, ADR-0048): the stream arrived and the tool call
  the model wrote will not parse, so another attempt would produce it again.
- `ModelUnavailableError`, `SwapFailedError`, `ResidencyRestoreError` and `HandoffInProgressError`
  (under `ModelManagerError`, ADR-0030). The last is not a failure: it means the deep model is
  loaded and busy with another turn.
- `ToolNotFoundError` (under `ToolError`): no such tool name.
- `ModelNotHostedError` (under `ModelHostError`, ADR-0053 decision 14): the host does not serve
  that logical id at all, which no wait and no retry can change.
- `SubagentAdmissionError` is the one error raised by core policy rather than by an adapter: a
  `SubagentScheduler` refusing a spawn instead of queuing it (ADR-0012).
- `BodyGatewayError` alone has a second field, `kind: BodyFailure`, saying how far the call got:
  `UNREACHABLE`, `REFUSED`, `UNSUPPORTED`, `UNREADY`, `OVERSIZE` or `FAULTED` (the default).
  `body_failure_message(err, action=...)` (`body_failure.py`) turns a kind plus an infinitive into
  the sentence the cortex reads, so the body built-ins word their refusals the same way and only
  `UNREACHABLE` may say the body could not be reached (ADR-0023 decision 8).

## Log rendering

`log_fields.py`, `log_format.py` and `log_secrets.py` decide how a brain process writes a line
(ADR-0051 decision 1).

- `configure_logging(level, *, style=DEFAULT_LOG_FORMAT)` installs the root handler. It is called
  from a process entry only, never from a library, because it changes process-wide state. Both
  brain entries call it, and without it every `extra` field this repo attaches is written onto a
  record and then dropped, which is what the standard library's own format does.
- `build_formatter(style)` returns the rendering that `style` names, or raises
  `UnknownLogFormatError` listing the ones that exist. `LOG_FORMATS` is the registry it reads:
  `PLAIN_FORMAT` (`"plain"`, the default) builds `PlainFormatter`, which prints
  `logging.BASIC_FORMAT` and then the record's own fields as `key=value` pairs in name order;
  `PACKED_FORMAT` (`"packed"`) builds `PackedFormatter`, one JSON object per line with the fields
  under their own `fields` key. `record_fields(record)` is what both read.
- `SESSION_FIELD`, `TURN_FIELD`, `TASK_FIELD`, `ITEM_FIELD` and `CALL_FIELD` (`"session_id"`,
  `"turn_id"`, `"task_id"`, `"item_id"`, `"call_id"`) are the one name each work identity is
  written under, wherever a brain line mentions one (ADR-0046 decision 1). They are the dispatch
  stamp's own names. A line mentioning a second instance of one identity puts a qualifier in
  front and keeps the family word, as `active_turn_id` does, so one search still finds both.
- **Secrets are withheld by the formatter, not by its callers.** A field whose name contains any of
  `SECRET_NAMES` (`token`, `password`, `passwd`, `secret`, `credential`, `apikey`, `api_key`,
  `authorization`, `cookie`, in any case) renders as `REDACTED` with its key still printed, so a
  withheld field reads differently from a missing one. The match is a substring, so the error
  falls on the side of withholding too much. The rule applies inside a structured value at any
  depth, through dicts and through lists of them, and it runs where both renderings read it.
  Separately, `redact_urls` strips the credential from every URL in the whole rendered line,
  message and traceback included, since `redis://:pw@redis:6379` is what a connection error prints.
- `render_value` writes a scalar the way Python does and anything else as compact JSON, quoting a
  string exactly when whitespace or a quote of its own would run it into its neighbour. A value is
  cut at `VALUE_CHARS` (2,048) rendered characters, with `CUT` naming what did not print. The
  number is the 16 KiB a container's log driver gives one message, divided by eight, which leaves
  room for seven fields at the limit. The packed rendering hands its fields to `json.dumps` as they
  were attached and does not apply the limit.

## Reference implementations

Every port has a fake in this package, pure and I/O free, and the contract tests run over the fake
and the real adapter from one file. They live in `fakes.py` and in the per-area files split off it
at the 300-line limit (`fakes_session.py`, `fakes_memory.py`, `fakes_body.py`,
`fakes_schedule.py`, `fakes_scheduler.py`, `fakes_handoff.py`, `fakes_model_host.py`,
`fakes_inference.py`, `fakes_vision.py`, `fakes_preferences.py`, `fakes_sleeper.py`). Each area
document names the fake beside the port it stands for. The in-memory stores deliberately do not
survive a restart: proving that state outlives a swap is the real adapter's job.

**Invariants.**

- Pure and deterministic: no I/O, no adapter or framework imports, standard library only.
- Every use case is a function over the stores, so nothing about a conversation, a task or a
  handoff outlives the call that ran it (the one hard rule).
- The untrusted boundary fails closed: trust defaults to `UNTRUSTED`, the `TaintLedger` is rebuilt
  each turn and never persisted, and untrusted-derived content is fenced and taints the turn
  wherever the model sees it, live from a tool or recalled from memory. Provenance cannot hold
  unsanitized text, cannot write a fence marker, is bounded per value and per turn, and never
  contains a string the model wrote.
- Fully typed (`py.typed` ships with the package), pyright strict clean, and 100% line and branch
  covered by behaviour tests, cancellation and failure paths included.

**Dependencies.** Python standard library only.
