# ADR-0074: A reply keeps its turn's tool runs, and later turns replay them as calls

**Status:** Accepted (2026-10-10)

## Context

A chat's stored history holds the user's messages and the assistant's replies, and nothing of the
tool loop between them ([ADR-0021](ADR-0021-session-read-rpcs.md) decision 2,
[ADR-0009](ADR-0009-tools-mcp.md) decision 3). A later turn's model therefore read a send request
followed by "I've sent that email" with no call between them, and copied that shape: asked for a
second send in the same chat, the cortex wrote that the email was sent and made no call, so no card
was shown and nothing was sent. On the shipped cortex this happened in 3 of 5 chats
([readings](../readings/overlay-email-flows.md#a-second-send)). Any tool with a visible effect can
be claimed this way, and the person sees no sign that no call was made.

The tool loop's raw results are never stored, because an untrusted result must not reach a later
turn as trusted text ([ADR-0019](ADR-0019-tainted-memory-recording.md)), and the arguments a model
wrote on a tainted turn can hold injected text or a link the output guardrail removed from the reply
([ADR-0015](ADR-0015-output-guardrail.md)).

## Decision

1. **A reply records its turn's tool runs.** `Message.runs` is a tuple of `ToolRun(name, ok)`
   (`cortex_core/conversation.py`), allowed only on an `ASSISTANT` message. `RunLog`
   (`cortex_core/tool_replay.py`) reads them off the turn's own `ToolOutcome` events, so a run is
   recorded for each call that was admitted and whose tool is advertised: the name is the
   registry's, never a name the model wrote, and `ok` is `not result.is_error`, so a refused,
   declined or failed call is `ok=False`. The cortex's `TurnEngine` and the deep tier's
   `BrainPhase` both store them on the reply they append. A subagent's steps are not runs of the
   turn.
2. **Only the name and the outcome are kept.** No argument and no result is stored, so a run holds
   nothing the turn read and nothing the model wrote, and a tainted turn's runs are stored like an
   untainted one's.
3. **A later turn replays them as calls.** `replay_runs` puts, before each reply with runs, one
   assistant step whose `tool_calls` name each run with empty arguments and ids
   `replay-<index>-<n>`, and one `TOOL` message per call holding a fixed text, `REPLAYED_OK` or
   `REPLAYED_FAILED`, which says the result is not kept. `assemble_inference_messages` applies it
   after the history window, so the window and the recap still count stored messages only. The
   model reads the shape the tool loop gives it within a turn, so a request answered by a call is
   what it copies.
4. **The record stays version 1.** The Redis adapter writes `"runs": [{"name", "ok"}]` only on a
   reply that has runs, and reads a missing key as none. A reader that predates the key ignores it
   as an unknown key, so an older brain still reads a newer chat and an older chat reads as before.
   A malformed `runs` value makes the record corrupt at its index, like any other field.
5. **The wire does not show runs.** `GetSessionMessages` maps role, text, turn and time as before.
6. **A recorded memory names its turn's runs too.** Recall gives a later chat an earlier chat's
   exchange as system context, which has no calls to replay, and a recalled reply saying a
   reminder was set led the cortex to list the schedule and copy that reply with no call.
   `record_exchange` takes the turn's `RunLog.runs` from `TurnEngine` and `BrainPhase`, and
   `render_exchange` writes them on a line between the message and the reply, `Tools run:
   list_scheduled (succeeded), schedule_task (failed)` (`runs_line`); a turn with no runs is
   written as before. The recalled block opens with `RECALLED_RUNS_NOTE`: a tool named on that
   line ran in that earlier conversation only, and a request made now needs its own call. The
   note ends the trusted section's header. With no trusted section, it is its own line above the
   fenced section's header, so the line just before the fence is the one that frames the quoted
   memories as data ([ADR-0013](ADR-0013-untrusted-content.md)). A row stored before this has no
   line and reads as before. No schema changes.
7. **A reply that says something was scheduled is checked against its turn's runs.** The replay
   does not remove every claim: over a chat that read a file, the cortex still wrote that a task
   was scheduled with no call, or after a refused one, in 8 of 40 third turns that asked for one
   ([readings](../readings/task-claimed-without-call.md)). `limit_notes`
   (`cortex_core/turn_output.py`) appends `UNSCHEDULED_CLAIM_NOTE`, "Nothing was scheduled in
   this turn: no scheduling call in it succeeded. Ask again to schedule it.", when
   `unscheduled_claim(runs, reply, said)` (`cortex_core/schedule_claim.py`) holds: no run of
   `schedule_task`, `edit_scheduled` or `snooze_scheduled` succeeded, and `claims_scheduled`
   finds a statement in the model's text, read before any other note, saying something was
   scheduled. That is "I scheduled", "I've scheduled" or "I have scheduled", or "has been", "have
   been" or "is now" before "scheduled", or the same forms with "set", "created", "added" or
   "booked" in a sentence that names a reminder, a task, an alarm or the schedule. A question, a
   future or offered form, a negated one and a stored item described do not match. A sentence
   matching only the "scheduled" forms and naming none of those nouns does not count when one of
   `said`, the person's own messages in the chat (`said_by_person`), makes such a claim, since a
   message drafted in the person's voice repeats their claim
   ([readings](../readings/claim-note-on-a-drafted-message.md)). The runs half
   is exact, so the note is true whenever it is shown. Both tiers share `limit_notes`, and the
   stored reply holds the note, so a later turn reads it too. The deep phase also counts the runs
   of the cortex's stored reply to the same turn (`cortex_runs`, `handoff_view.py`), since a task
   the cortex scheduled before it handed off was scheduled in this turn.

## Consequences

- With the replay, the same rows sent the second email in 5 of 5 chats, and the question "What was
  the subject of the email you just sent?" was answered from history with no call in 5 of 5.
- Each replayed run adds one call and one short result to every later request of that chat.
- With recorded exchanges naming their runs, a fresh chat asking for a reminder the schedule held
  called `schedule_task` in 50 of 50 chats and claimed a reminder it had not set in none, against
  4 of 50 over the same exchanges without the line
  ([readings](../readings/recalled-tool-runs.md#results-over-the-stored-reminder)).
- Over recalled tainted exchanges that name a `schedule_task` run, 8 chats with the note and 8
  without it each scheduled the task again, with no false claim, so these rows show no effect of
  the note there; no chat acted on a quoted injection with or without it
  ([readings](../readings/recalled-tool-runs.md#results-over-tainted-rows)).
- A replayed run of a read tool holds no content: what a later turn knows of that result is what
  the reply said.
- Over 50 third turns, the reply check of decision 7 fired on all 8 claims, 5 with no call and 3
  that said the task was scheduled and then that it was not, and on none of 42 other replies,
  among them 10 listings of stored reminders and 26 offers to set one
  ([readings](../readings/task-claimed-without-call.md#results-2)).
- With the person's messages read, the check fired on none of 16 drafted messages with no call,
  11 of them repeating the person's own "I have scheduled", against 14 of 19 before, and still
  fired on every claim of its corpus
  ([readings](../readings/claim-note-on-a-drafted-message.md#results)).

## Alternatives rejected

- **A record kind beside `message`.** The listing reads a chat's first and last records, and a
  recap counts stored messages by index, so every reader would have to skip the new kind.
- **Replaying the arguments.** A tainted turn's arguments can hold what taint and redaction keep
  out of later turns; the rows passed without them.
- **A check on every reply for any claimed action**: wording varies by tool, and a check after
  the reply cannot make the call the person asked for, so the replay is the remedy wherever it
  removes the claim. Decision 7 checks scheduling only, where claims remained under the replay.
- **A rule in `TAINTED_TASK_MSG` or the replayed text**: a claim came with no call at all, so no
  result text reached it, and a claim after a refused call followed a result that already said
  not to claim.

## Related

[brain-core](../modules/brain-core.md), [brain-core-turn](../modules/brain-core-turn.md),
[brain-session](../modules/brain-session.md),
[ADR-0022](ADR-0022-email-write-confirmer.md) (the confirmation card a replayed send does not skip).
