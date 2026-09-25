# brain/packages/core: tools and schedules

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers what a model can ask for: the tool values and ports,
the dispatcher, the tool loop, the registry combinators, the built-in tools, and the schedules
three of those tools write into. The turn itself is in [brain-core-turn.md](brain-core-turn.md); a
spawned subtask or a model swap is in [brain-core-residency.md](brain-core-residency.md).

## Tool values

- `ToolSpec(name, description, parameters, confirm_required=False)` is what a tool advertises. `parameters`
  is the JSON Schema the model fills, passed through and never interpreted here, and `confirm_required` marks
  an action that needs confirmation; `escalate_to_brain` is the only tool that sets it itself.
- `ToolCall(id, name, arguments, stamp=UNSTAMPED)` is a model's request to run one tool; `id`
  matches it to its `ToolResult`. The dispatcher overwrites `stamp` at dispatch time, so a stamp
  the model wrote never reaches a tool (ADR-0018, ADR-0027).
- `ToolResult(call_id, content, is_error=False, trust=UNTRUSTED, source=None, images=())` is the
  outcome fed back to the model. `source` is what the result declared for its own content, and
  `images` (ADR-0029) travel beside `content`, which alone is audited, scanned and fenced.
- `TurnStamp(session_id, turn_id, task_id, item_id, tainted, sources, budget, progress,
  escalation)` is what the dispatching turn gives the call (ADR-0027). The four ids are the work
  the call was made for, each `""` when there is none (ADR-0009 decision 16). The three live
  handles are left out of equality; `sources` is compared. `UNSTAMPED` is the default.
- `ToolInvocation(name, arguments, ok, detail, at, trust, call_id, session_id, turn_id, task_id,
  item_id)` is one audit record, keeping the stamp's four ids and never the stamp itself, since a
  record that outlives its process must contain no live handle.

## Ports

- `ToolRegistry` provides `describe_tools()` and `invoke(call)`. An unknown tool or a transport
  failure raises `ToolError` (`ToolNotFoundError` for the name), and the dispatcher, not the
  registry, turns that into an error result. Two obligations are checked by the shared contract in
  `packages/tools/tests/registry_contract.py`: a listing is read at the call and never remembered,
  and a name an implementation does not serve never comes back as a success. Fake:
  `InMemoryToolRegistry`; real adapter: `cortex_tools`.
- `ToolAuditSink` provides `record(invocation)`: every dispatched call is written here, success or
  failure. Fake: `RecordingAuditSink`.
- `Confirmer` provides `confirm(request) -> bool` (ADR-0013) over a
  `ConfirmationRequest(tool_name, arguments, reason)`: the user's decision, never the model's, and
  a missing confirmer denies. Real adapter: `RpcConfirmer` (ADR-0022).
- `ProgressSink` (`progress.py`, ADR-0010 decision 13) is the side channel for progress a
  suspended turn cannot yield itself. `emit(event)` sends a `ToolActivity` or `StatusUpdate`, best
  effort. `hold(wait, *, announce=True)` records what the turn waits on, innermost first, in the
  core's `TurnWaits` (`waits.py`), and sends each change other than `thinking` as a status
  (ADR-0069 decisions 9 and 10). Fake: `RecordingProgressSink`; list: `progress_contract.py`.

## Dispatching one call

`ToolDispatcher(registry, audit, clock, *, confirmer=None, policy=DEFAULT_DISPATCH_POLICY)` is the
turn's tool gateway and its capability check (ADR-0009, ADR-0013). `dispatch(call, *,
stamp=UNSTAMPED, confirm_required=False, refusal=None)` runs the call through the registry, writes exactly one
`ToolInvocation` to the audit sink, and returns a `ToolResult`; a `ToolError` becomes a `TRUSTED`
`is_error` result, the brain's own text, which neither fences nor taints. `cost_of(name)` and
`admits(call, dispatched)` report what a call spends and whether it is worth running. The
dispatcher is stateless; the loop drives it and keeps the history.

- `refusal` (a `DispatchRefusal`) is the caller's statement that the call must not run: `BUDGET`
  when the dispatch allowance is spent, `REDUNDANT` for a repeat the salience policy recognized, or
  `ROUND_OVERSIZED` for a truncated round's overflow slot. The tool is not invoked, the member's
  message is returned, and the attempt is audited. A refusal is checked **before** the confirmation
  rule, so a flood of confirmable calls cannot reach the user as prompts.
- The confirmation rule (ADR-0013, revised by ADR-0022): a `confirm_required` call on a tainted turn is
  refused outright with `DENIED_MSG` and the confirmer is not consulted; on an untainted turn it
  runs only when the `Confirmer` approves, else `USER_DECLINED_MSG`. Both refusals skip the tool
  and are audited.

`DispatchPolicy(confirm_names=(), costs=UNIFORM_COST, salience=REPEAT_SALIENCE, confirm_reasons={})`
(`dispatch.py`, default `DEFAULT_DISPATCH_POLICY`) is everything the composition root declares
about dispatching: which tools need confirmation, the prices, the salience rule, and the per-tool
card text, where `confirm_reasons[name]` replaces the generic reason in `ConfirmationRequest.reason`
so the escalate card can name the model swap.

- `RepeatSalience(limit=MAX_IDENTICAL_DISPATCHES)` (`tool_salience.py`, the default
  `REPEAT_SALIENCE`, limit 2) refuses a call identical to one already made in this round, or made
  `limit` times in this loop; `name` and `arguments` are compared, `id` and `stamp` are not.
  Attempts are counted rather than answers, so a denial counts too, which bounds confirmation
  re-prompting. `ALWAYS_SALIENT` (`CORTEX_TOOLS_SALIENCE=off`) turns it off.
- `ToolCostPolicy(costs={})` and `DispatchBudget(limit=MAX_TOOL_DISPATCHES)` (`tool_budget.py`,
  ADR-0009 decision 11) are the price list and one turn's allowance of 32. `cost_of(name)` returns
  the named positive price or `DEFAULT_TOOL_COST` (1), so under the empty `UNIFORM_COST` an
  allowance of N is N calls. `charge(cost)` spends what fits and closes the pool permanently when a
  call does not. The budget is mutable and compared by identity, because the cortex loop and every
  subagent it spawns draw on one pool, reached through the dispatch stamp, and `resume(*,
  remaining, closed)` rebuilds one from a handoff record, so a swap never refills it.

## The tool loop

`stream_tool_loop(backend, model, working, context)` (`tool_loop`) is the bounded inference and
tool loop shared by `TurnEngine` and `SubagentRunner` (ADR-0010). It is an async generator yielding
assistant text deltas, `ReasoningDelta`s (ADR-0020), a `ToolStep(tool_name, summary)` immediately
before each audited dispatch of an advertised tool, and the `StepOutcome(tool_name, ok)` that
closes that step. Both fields of a step are copied off the matched `ToolSpec`, so an unadvertised
call produces no step, and the only exit from a dispatch without its outcome is the generator being
closed mid-dispatch. The turn engine maps the pair onto `ToolActivity` and `ToolOutcome`; a
subagent puts steps on the spawning stream's `ProgressSink` and drops outcomes (ADR-0029
decision 18). The yield vocabulary is in `loop_events.py` and one round's dispatches in
`dispatch_round.py`.

The loop appends the tool-call and `Role.TOOL` result messages to `working` in place, and ends on a
tool-free step, a `None` dispatcher, or `MAX_TOOL_STEPS` (8) rounds. Five independent bounds apply
(ADR-0009 decision 11, ADR-0048): rounds cap how long it runs; `context.budget` caps what it may
spend across those rounds; `context.bounds` caps how far any one completion decodes, so the two
together bound the whole loop's decoding; the salience policy refuses a repeat; and `plan_round`
caps how wide one round may be. A call is charged only after `dispatcher.admits` passes, so a
refused repeat costs nothing, and calls past the allowance are still dispatched, so their
`Role.TOOL` answers exist and their refusals are audited.

`plan_round(calls) -> RoundPlan` (`tool_round.py`, ADR-0009 decision 13) is the pure per-round cap.
A round at or under `MAX_CALLS_PER_ROUND` (16, half of `MAX_TOOL_DISPATCHES`) passes through; a
wider one is cut to the cap plus one overflow slot, and the rest are dropped rather than refused.
The overflow slot is refused as `ROUND_OVERSIZED` ahead of every other bound. The module also owns
`call_message` and `result_message`, the two messages a round appends.

The loop draws the untrusted boundary (ADR-0013): each call is dispatched with the turn's taint
state and the tool's `confirm_required` flag, each result is observed by `context.taint`, and an `UNTRUSTED`
result is fenced by `wrap_untrusted` before it re-enters `working`. A call matching no advertised
spec contributes no source.

## Registry combinators

Each is a `ToolRegistry` wrapping others, so the root builds a tool set the core knows nothing of.

- `CompositeToolRegistry(builtins, remote=None)` merges built-in tools (each a `BuiltinTool`, a
  `.spec` plus an async `invoke`) with an optional MCP registry: built-ins are advertised first and
  win on name, and duplicates raise `ValueError` at construction.
- `AggregateToolRegistry(registries)` unions several registries in order, keeping the first of any
  duplicate name, and routes an invoke by a live `describe_tools` walk, so a tool dropped
  server-side mid-turn fails closed; a listing failure propagates as `ToolError`.
- `SkipUnavailableToolRegistry(inner, *, name, report)` marks one registry optional: a listing
  failure becomes an empty advertisement plus one required `report(name, error)` call, so a skip is
  never silent, and only discovery is softened, `invoke` still failing loudly.
- `FilteredToolRegistry(inner, *, allow)` restricts the advertisement to an allowlist, refusing any
  other name as `ToolNotFoundError`. It only restricts and never grants.
- `ConfirmRequiredToolRegistry(inner, *, names)` advertises the named tools as `confirm_required=True`
  (`CORTEX_TOOLS_GATED`), so the brain decides which remote tool needs confirmation rather than
  trusting sidecar metadata. `ConfirmFreeToolRegistry(inner)` is the reverse, dropping every `confirm_required`
  spec and refusing such a name; it wraps the subagent tool set so a subagent is never handed one.
- `OwnTextToolRegistry(inner, *, own)` (`own_text.py`, ADR-0013 decision 10) re-marks a result
  `TRUSTED` exactly when its whole `content` equals the text a declared `OwnText(tool, render)`
  builds from the call's own arguments and the result has no image. It is the only place a remote
  result is trusted, and the root declares the email sidecar's four own answers through it.
- `BoundedToolRegistry(inner, *, timeout_s=DEFAULT_TOOL_CALL_TIMEOUT_S)` (`tool_deadline.py`)
  gives up on either verb after `timeout_s` and raises `ToolError` naming the tool and the bound.
  The bound is `asyncio.timeout`, so an overrun cancels the inner call, and a `TimeoutError` from
  beneath it propagates untouched. `DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0`
  (`CORTEX_TOOLS_CALL_TIMEOUT_S`) is some four hundred times the slowest healthy call measured on
  this deployment. Only remote registries are wrapped; the built-ins are deliberately slow.
- `SightedToolRegistry(inner, probe)` both hides and refuses `capture_screen` while a
  `VisionProbe` answers no (ADR-0029 decision 13). `VisionProbe` (`sighted.py`) reports whether the
  model serving this tier right now can read a picture; it never raises, returns `False` when it
  cannot tell, and caches nothing, a `/props` call costing about 1.5 ms. Fake:
  `ScriptedVisionProbe`.

## Built-in tools

All are cortex-only, so delegation is one level deep and a subagent can neither schedule nor
escalate. Each is a `BuiltinTool` registered in the `CompositeToolRegistry`.

- `SpawnSubagentsTool(runner, store, clock, *, task_id_factory=<uuid4>)` is `spawn_subagents`
  (ADR-0010, ADR-0018). Its spec is built from the runner's roster by `build_spawn_spec`
  (`spawn_spec.py`): an item is a bare string or `{instruction, model?, context?}`, at most
  `MAX_SPAWN_BATCH` (8) per call, and the `model` enum lists every roster entry, left out when the
  runner is tools-enabled or the roster has one entry. `invoke` checks the batch size before
  parsing any item, persists one `SubagentTask` per item stamped with the call stamp's taint and
  its three work ids, runs the batch together, and returns one aggregated `ToolResult` with a
  `[subagent N] …` block per subtask, `UNTRUSTED` when any result is tainted, as on every tainted
  call. A progress sink on the stamp gets one `StatusUpdate(state="delegating", …)` and is passed on.
- `GetVolumeTool(body)` and `SetVolumeTool(body)` (`volume.py`, ADR-0023) read and set the host's
  system volume over a `BodyGateway`. Neither needs confirmation and every result is `TRUSTED`;
  bad arguments and a `BodyGatewayError` become an `is_error` result, worded by
  `body_failure_message`.
- `CaptureScreenTool(body, *, max_edge=0, max_bytes=0)` (`screen_tool.py`, ADR-0029) takes one
  required `target` argument, a string enum derived from `CaptureTarget`. A missing target is
  refused rather than defaulted and an unrecognized one is refused exactly, which with
  `RepeatSalience` fixes the ceiling at two captures per target and four per loop. Success is
  `UNTRUSTED` and includes the picture, its text being a brain-written description of sizes and a
  time that names no window title and no coordinates; every failure is `TRUSTED` with no image.
- `EscalateToBrainTool()` (`escalate.py`, ADR-0030 decision 1) is `escalate_to_brain`. It reads the
  turn's `EscalationSlot` off the dispatch stamp, checks the model-written `brief` (non-empty, at
  most `MAX_BRIEF_CHARS` of 4000, refused whole rather than truncated), writes `slot.brief`, and
  answers `ESCALATION_QUEUED_MSG`; the swap happens at the loop boundary. Its spec sets
  `confirm_required=True`, which buys the confirmation card on an untainted turn, under its own
  `ESCALATE_CONFIRM_REASON` text, and the dispatcher's refusal on a tainted one.
- `ScheduleTaskTool`, `ListScheduledTool`, `CancelScheduledTool`, `SnoozeScheduledTool` and
  `EditScheduledTool` (`schedule_tools.py` and `schedule_verbs.py`, with argument parsing in
  `schedule_args.py`, `schedule_verb_args.py` and `schedule_day_args.py`) are the five schedule
  verbs (ADR-0025). `schedule_task` takes `{kind: reminder|task, text, at | in_seconds,
  every_seconds? (at least 60), model? (task only)}`, or `at_time` (`HH:MM`) with at most one of
  `on_days`, `on_month_days` or `on_dates` plus an optional `in_zone` for a calendar rule. Its spec
  is rebuilt on every `describe_tools` walk and includes the current time, which the model cannot
  otherwise compute an absolute `at` from. Two creation bounds apply: the `max_active` cap, and a
  refusal to create a `task` item on a tainted turn (`TAINTED_TASK_MSG`). Creation, cancel and
  snooze results are `TRUSTED` and never echo stored text; the listing echoes text and so is
  `TRUSTED` only when every item listed is clean. `edit_scheduled` adds the editing turn's taint
  and refuses editing a task on a tainted turn; none of the five raises.

## Schedules

The value types and the recurrence arithmetic are in `schedule.py`, the pure transitions both
stores apply in `schedule_transitions.py`, and the wall-clock rules in `schedule_calendar.py` and
`schedule_selectors.py`. A `SubagentScheduler` admits resources; a `ScheduleTicker` fires these.

- `ScheduleKind` is `REMINDER` or `TASK`: firing delivers text to the user, or runs an autonomous
  subagent. `ScheduleStatus` is `PENDING`, `FIRING` or `DONE`; cancel deletes the record, and
  `DONE` persists only while a fired one-shot reminder awaits delivery.
- `ScheduledItem(id, kind, text, session_id, due_at, created_at, every=None, rule=None,
  anchor=None, model="", tainted=False, status, deliverable_since=None, last_outcome=None)` is one
  schedule. At most one of `every` and `rule` is set, checked in `__post_init__`, and `anchor` is
  the interval grid's origin, set only by a snooze so a recurring series keeps its cadence.
  `ScheduleClaim(item, token)` is one claim with the fencing token under which alone `finish` and
  `release` apply; `FireOutcome(fired_at, next_due, deliverable, outcome, tainted)` is one fire.
- `next_due(due_at, every, now)` is the pure interval recurrence: the first occurrence
  `due_at + k * every` strictly after `now`, so occurrences missed while the brain was down
  collapse into the single fire that just happened. `CalendarRule(hour, minute, on=DAILY,
  zone=None)` is the wall-clock form and `next_calendar_due(rule, after, zone)` its arithmetic,
  resolved through `DisplayZone.resolve` so a spring-forward gap fires just past the gap and a
  fall-back repeat fires once. The ticker calls `next_occurrence(item, now, zone)`.
- `DaySelector = Weekdays | MonthDays | YearDays` (ADR-0065 decision 3) is which dates a wall time
  falls on, a closed union so a rule has exactly one selector: `date.weekday()` numbers, calendar
  days `1..MAX_MONTH_DAY`, or ordered `MonthDay(month, day)` pairs bounded by that month's
  leap-year length. A date its period lacks moves to the nearest earlier one in it, so `{31}` is
  the last day of every month. No selector is ever empty, which bounds the occurrence search.
- `DisplayZone(name, tz)` (`schedule_time.py`, ADR-0065 decision 1) is what every model-facing
  schedule time renders through: `render(moment)` is the one canonical string and `resolve(naive)`
  reads an offset-less time as that zone's wall time and returns the UTC instant, with `fold=0` so
  an ambiguous time takes the earlier offset. Display only: stored `due_at` and `anchor` stay UTC
  instants and `UTC_DISPLAY` is the default. `ZoneResolver` turns an IANA key into a `DisplayZone`
  or `None`, `UTC_ONLY_RESOLVER` is the core default, the `zoneinfo`-backed one is injected at the
  root, and `ZoneContext(default, resolver)` bundles the two.
- `apply_snooze(item, until)` and `apply_edit(item, edit)` (`schedule_transitions.py`) are the two
  pure transitions both stores share. `apply_snooze` moves `due_at`, returns the item to `PENDING`,
  clears deliverability, and sets `anchor` to the pre-snooze `due_at` on a recurring item's first
  snooze. `apply_edit` clears `rule` whenever it sets `every` and leaves `due_at` alone; setting a
  rule is its one timing-moving branch, passed as a `RuleChange(rule, due_at)`. `acks_fire(item,
  fired_at)`, `fire_stamp(moment)` and `stamp_instant(stamp)` name one fire, `fire_stamp` being
  whole unix milliseconds and `stamp_instant` its inverse.
- `ScheduleStore` is the durable port with a fenced claim-then-finish protocol (ADR-0025): `add`,
  `get`, `list_active`, `cancel` (deletes outright, so it sticks through an in-flight fire),
  `claim_due(now, *, lease, limit)` (due `PENDING` plus lease-expired `FIRING`, oldest first, a
  fresh token per claim, undecodable records quarantined), `finish(claim, outcome)` and
  `release(claim)` (both apply only under the claim's token, so a stale claimant gets `False`),
  `deliverable`, `ack(item_id, *, fired_at)` (clears the slot only while it holds the fire
  `fired_at` names), `snooze` and `edit`. A schedule outlives every swap and restart, which is why
  this port exists. Fake: `InMemoryScheduleStore`; adapter: `cortex_session`.

**Invariants.**

- Every dispatched call is audited, refusals included, and no audit record contains a live handle.
- A tool result marked `UNTRUSTED` is fenced before the model sees it and taints the turn.
- One turn's dispatch allowance is shared with every subagent it spawns and is never refilled.
