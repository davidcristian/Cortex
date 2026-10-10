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

## Consequences

- With the replay, the same rows sent the second email in 5 of 5 chats, and the question "What was
  the subject of the email you just sent?" was answered from history with no call in 5 of 5.
- Each replayed run adds one call and one short result to every later request of that chat.
- A replayed run of a read tool holds no content: what a later turn knows of that result is what
  the reply said.

## Alternatives rejected

- **A record kind beside `message`.** The listing reads a chat's first and last records, and a
  recap counts stored messages by index, so every reader would have to skip the new kind.
- **Replaying the arguments.** A tainted turn's arguments can hold what taint and redaction keep
  out of later turns; the rows passed without them.
- **A check on the reply**, reading the model's prose for a claim of an action: wording varies,
  and a check after the reply cannot make the call the person asked for.

## Related

[brain-core](../modules/brain-core.md), [brain-core-turn](../modules/brain-core-turn.md),
[brain-session](../modules/brain-session.md),
[ADR-0022](ADR-0022-email-write-confirmer.md) (the confirmation card a replayed send does not skip).
