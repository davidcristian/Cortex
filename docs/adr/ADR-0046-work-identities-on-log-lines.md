# ADR-0046: Work identities on log lines

**Status:** Accepted (2026-09-19)

## Context

The brain's log lines are how an operator reconstructs what happened to one chat, one turn or one
scheduled run, usually with a single `grep`. That only works if a given piece of work is named the
same way on every line that mentions it. The tool audit ([ADR-0009](ADR-0009-tools-mcp.md)) records
five identities for each dispatch, and other lines named the same things differently: the
conversation as `session` on some lines, the schedule item that ran as `reminder_id` in the ticker,
the escalating turn as `turn` or `handoff` on the swap path. The runbooks also told operators to
grep for ids with a `t-` prefix that no real id has.

Under `CORTEX_LOG_FORMAT=packed` a field name is a JSON path (`jq .fields.turn_id`), so a second
name for one identity is a second query, not a cosmetic difference.

## Decision

1. **Five names, the dispatch stamp's own.** A log line names a unit of work as `session_id` (the
   conversation), `turn_id` (the conversation turn), `task_id` (a delegated subagent task),
   `item_id` (a schedule item that ran) or `call_id` (one tool call). These are the names
   `TurnStamp` and `ToolInvocation` already use. `session_id` is also what the proto declares and
   every Redis codec writes.
2. **Declared once, used by one sink, compared everywhere else.** `cortex_core.log_fields` declares
   `SESSION_FIELD`, `TURN_FIELD`, `TASK_FIELD`, `ITEM_FIELD` and `CALL_FIELD`, beside
   `RESERVED_ATTRS` and `SECRET_NAMES`. `LoggingAuditSink`, which writes the whole vocabulary out as
   a list, uses the constants; every other place writes the name as the literal key of its own
   `extra=` dict, because that literal is what an operator greps for. `scripts/logcouplings.py`
   compares each declaration with every module and runbook that writes it
   ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)), with an exact count where one module's
   lines are its whole account of one thing, so a line leaving the set is noticed.
3. **A log field may differ from a wire field or a store key.** The proto's
   `NotifyRequest.reminder_id`, `HandoffRecord.handoff_id`, its codec's hash key and the Redis key
   `cortex:handoff:<turn id>` keep their names: a record's schema and address outlive the deployment
   that wrote them. A log line is the brain's account of its own work, so the ticker's lines say
   `item_id`. Putting both names on one record was rejected, since the formatter prints every field
   and a reader would meet two names for one id on one line.
4. **A handoff id is a turn id.** `EscalationSlot.snapshot` builds `HandoffRecord(handoff_id=turn_id,
   ...)`, one handoff per turn at most, so every swap-path line names the escalating turn as
   `turn_id` and the vocabulary stays at five.
5. **A line naming two of one identity qualifies the second in front of the family word.** The
   conductor's refusal while the store still holds another handoff names its own turn `turn_id` and
   the stored one `active_turn_id`. A prefix keeps `grep turn_id=` finding both; a suffix would hide
   the line from that grep. The registry compares the qualified name with the same declaration
   through the template `"active_{value}":`, so a rename moves it too.
6. **A line about one handoff names the conversation and the turn; a line about the card names
   neither.** The conductor's refusals, the settler's three lines, boot recovery's stranded record
   and the deep phase's progress lines include `session_id` beside `turn_id`: the reader arrives
   from a chat, and the progress report is the only record a successful handoff writes. The
   residency lines (`_clear_deep`, `_clear_peer`, `_settle_cortex`, `residency_moves.py`) name the
   `model` and no work identity, since a tier's state is the deployment's fact and not one chat's.
   A line naming two turns still names only its own conversation; `active_turn_id` points at the
   other's lines. A write that logs its work takes the record the work is, not one of its fields,
   which is what made the conversation available on those lines.
7. **Ids have no prefix, and the runbooks say what one looks like.** `new_turn_id`, the spawn tool's
   task id and a scheduled item's id are bare `uuid4` strings, and the overlay creates a chat id
   with `crypto.randomUUID()`. The `t-handoff` and `s-handoff` ids in the swap tests are fixtures.
   The one id that can have a prefix is a `call_id` the ticker creates, `schedule-<item>`, which is
   read as what was asked for. The registry's search text quotes the corrected grep sentences, so a
   prefix cannot come back unnoticed.
8. **The names could change while nothing outside this repo read them.** Renaming these fields cost
   only runbook sentences, because the logs had no consumer beyond this tree; once one exists, the
   names are frozen under AGENTS.md's naming rule.
9. **The stream creates a turn's id, when the turn starts.** `TurnRunner.handle_turn(session_id,
   text, *, turn_id)` takes the id; `ConverseStream` creates it in `_turn_task` through an
   injectable `TurnIdFactory` defaulting to the core's `new_turn_id`, not in `_enqueue_turn`, so a
   turn a `Cancel` dropped from the queue never ran and has no id. `TurnEngine` has no id factory,
   and `EscalatingTurnEngine` keeps the id from its first statement for the handoff claim and its
   completion. The stream sees a turn start, fail and complete, where a runner sees only a turn that
   survives, so an id created in the runner was unreachable on exactly the failure lines. What an id
   looks like stays in the core; `TurnCompleted.turn_id` echoes what the caller already knew. The
   wrapper's non-escalating exit still yields the inner runner's completion unchanged (R-347).

## Consequences

- One grep by `turn_id` returns a turn's failures, its tool calls, its subagents' tool calls and
  every line about the handoff it asked for; one grep by `session_id` reaches the same chat's
  recalls, summaries, handoffs and tool calls; one grep by `item_id` reaches one run of a scheduled
  item, its delegates' calls, the ticker's account of it and the claim path's failures.
- A new line naming a second instance of an identity has a rule and a template to follow.
- A new module that names its work under an unregistered key is invisible to the scan, since a
  mention covers only the files it names.
- A sample's field order is checked by the log-sample scan
  ([ADR-0045](ADR-0045-documented-log-lines.md)), which compares names in rendered order.

## Alternatives rejected

- **One field for "the unit of work":** its meaning would vary by row, and a task id resolves
  against nothing else a reader can reach.
- **A sixth name, `handoff_id`, for the swap path:** a second number to grep for a fact that is one
  number.
- **A check that re-renders samples, or generated samples, to catch a wrong order:** the log-sample
  scan compares membership and order without importing the brain.
- **The engine reporting a turn's id as a first event or a started-turn record:** such an event
  narrows to the completion branch of `to_server_event` and typechecks, so it would reach a client
  as a completion; the stream's id would be optional until it arrived; and the escalating wrapper
  would still read its own id out of its inner runner's events.

## Related

- [brain-core module contract](../modules/brain-core.md) (`log_fields`), the
  [repo checks module contract](../modules/repo-checks.md) (`logcouplings.py`).
- Runbooks: [tools-mcp](../runbooks/tools-mcp.md), [model-swap](../runbooks/model-swap.md),
  [memory-pgvector](../runbooks/memory-pgvector.md), [scheduling](../runbooks/scheduling.md).
- [ADR-0009](ADR-0009-tools-mcp.md) (the audit line), [ADR-0030](ADR-0030-brain-handoff.md) (the
  handoff record), [ADR-0051](ADR-0051-log-line-rendering.md) (rendered field order).
