# ADR-0048: Bounding a generation and reporting a cut

**Status:** Accepted (2026-09-14)

## Context

A `llama-server` completion ends for one of three reasons: the model stopped, it ended on a tool
call, or a token limit cut it. The server says which in `finish_reason` (`stop`, `tool_calls`,
`length`), and `length` is the same word for a request's own `max_tokens` and for the slot's context
window, so nothing on the wire says which limit cut it.

The stall ceiling ([ADR-0005](ADR-0005-llamacpp-engine.md) decision 7) limits silence and cannot see
a model that keeps talking. A delegated run in a repetition loop, reproduced through the shipped
runner and scheduler before anything here was designed, streamed about three million chunks in five
seconds, never returned, stored nothing, and held its admission and VRAM placement throughout. On
the user's side the context window was already cutting replies, and a cut reply was stored and read
as a finished short one. A cap on a reasoning model whose trace is unbounded does not shorten the
reply, it empties it ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md)).

This record decides how a generation is bounded on the delegated path and how a cut is reported on
every path that consumes one: a delegated run, the cortex's turn, and the deep model's phase of a
handoff.

## Decision

### What crosses the port

1. **The stop is its own event, `DecodeStop(reason)`,** not a field on `DecodeCadence`. Current
   builds send the two in one chunk and they are still separate facts: the cadence is emitted only
   when the server reports `timings`, and a `CadenceWatch` is built for rates.
2. **The reason is a closed set the core owns: `StopReason.FINISHED`, `CAPPED`, `CALLED`,
   `UNKNOWN`.** The adapter translates llama.cpp's words into it. `tool_calls` is the ordinary end
   of every tool-loop round but the last, so it needs its own member, and a word the core has not
   been taught becomes `UNKNOWN` rather than one of the other three. An unreadable reason is
   `UNKNOWN`, never a raise (a telemetry field must not kill a finished reply) and never silence.
3. **Silence stays legal, and no consumer reads it as `FINISHED`.** A build that reports no finish
   reason emits no stop; the shared contract's `check_silence_is_a_legal_answer` checks that.
   `EchoInferenceBackend` reports `FINISHED`, which is true of a scripted reply, and never a rate,
   which would be a made-up measurement.
4. **A stop never says which limit cut the completion.** A consumer quotes its own setting only when
   it has one; otherwise it says a length limit ended the reply.
5. **The tool loop collects the stop into a `StopLedger`** handed over on `ToolLoopContext.stops`,
   the way it collects a cadence. Why the machine stopped is not something the turn said, so it
   never reaches a stream a user reads, and a caller that hands over no ledger drops it. A ledger
   covers a whole attempt, turn or phase rather than one completion: a turn that lost material to a
   cap in any round did lose it.
6. **A tool call cut mid-arguments raises `MalformedToolCallError(InferenceError)`.** llama-server
   streams a partial call and says `length` while doing it, and the adapter assembles calls only
   after the stream ends, so `finish_calls` raises with the stop already delivered. Only
   `finish_calls` raises the narrow type, since a call's arguments are the model's own tokens; a
   status, a stall or an unreadable chunk stays the wide type. Every existing `except
   InferenceError` still catches it. A consumer reads a cut call as a length cut only when the
   narrow error arrives **and** its ledger saw `CAPPED`: either half alone would call a model that
   broke its own grammar a truncation, or a dead backend after a capped round one.

### A delegated run

7. **Two limits, one value: `AttemptBounds(max_tokens, timeout_s)`.** They answer one question in
   the two units a runaway is measured in. The cap binds a fast tier, where a deadline's worth of
   decoding is an essay; the deadline binds a slow one, where a small token budget is minutes of
   held admission. `UNBOUNDED_ATTEMPT` (both `None`) is the core default and the request the repo
   sent before this; the deployment's numbers come from `SubagentsConfig`, where
   `CORTEX_SUBAGENTS_MAX_TOKENS` is at least 1 and `CORTEX_SUBAGENTS_RUN_TIMEOUT_S` strictly
   positive. Neither has an off switch: a delegated run cannot be unbounded.
8. **The cap is per completion and the deadline per attempt.** `ToolLoopContext.bounds` passes the
   cap to every completion the loop asks for, and `MAX_TOOL_STEPS` (8) keeps rounds times cap
   finite. The deadline is `asyncio.timeout` around the whole consumption, tool dispatches included,
   because an attempt holds its admission slot, VRAM placement and model lease across the loop. It
   starts fresh for the CPU re-run, so a task can hold its admission for two deadlines along the
   path a dead backend opens.
9. **Either cut is `AttemptFailure.TRUNCATED`, and it is not placed again.** It reaches the cortex
   as an `ok=False` `SubagentResult` whose detail names the limit and says to narrow the subtask
   before delegating it again (`GENERATION_DEADLINE_MSG`, `GENERATION_CAP_MSG`, one instruction).
   The fragment stays on the stored result; `spawn._format` renders a failure as `FAILED: <detail>`
   and drops it, because a mid-sentence fragment reported as an answer trades a hang for a wrong
   answer. Only an expired deadline (`deadline.expired()`) is a truncation; any other `TimeoutError`
   is the backend failing to answer and stays eligible for placement again. The retry depends on the
   failure kind: a tier that filled its budget fills it again. `settle_reply` reads the cap ahead of
   the envelope, so a reply the server cut mid-envelope is not blamed on the model's grammar, and a
   cut tool call with a capped ledger reports `cap_detail`, the same refusal.
10. **The cap is 1024 decoded tokens and the deadline 2400 s.** On the shape a subagents-only stack
    ships (the constrained envelope with `REPLY_INSTRUCTION`), every answer the default pick writes
    stays under about three eighths of the cap, and what reaches the cap is a trace or a narration,
    never a long answer, so reaching it is itself evidence of a model talking rather than working.
    The deadline is about four times the longest whole subtask on the slow placement and about four
    times the longest hold a fully serialized batch produced. The cap is an entry of the constant
    registry ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)), tied to the runbook and module
    contract that quote it, so retuning it alone fails `just check`. How the deadline nests with the
    stall ceiling and the admission wait is [ADR-0047](ADR-0047-delegated-run-bound-ordering.md).
    The measurements are in [generation bounds](../readings/generation-bounds.md) and [delegated run
    holds](../readings/delegated-run-holds.md).
11. **The cap and the deadline are independent, and nothing orders them.** Which binds first depends
    on what else the host is doing and on whether the deployment gives its subagents tools, which
    multiplies the cap by the rounds and not the deadline. A startup check has neither fact.
    Deriving one from the other through a configured decode rate is wrong at one end of the measured
    range in each direction, so the conversion stays the operator's, taken with the table in the
    measurement record. A sentence beside both declarations in `cortex_core/subagents.py` says the
    missing fourth ordering is absent by decision. The two refusals end in the same instruction, so
    an inversion can cost only a diagnosis, never a wrong action.
12. **One pair of run limits per deployment covers every roster entry and both placements.** The cap
    is sized from the model's reply, which does not change with placement, and the deadline from the
    slow placement; on the GPU placement the whole cap decodes in seconds, so no tool-less run there
    can reach a deadline the validators accept. Two measurements would reopen this: an entry whose
    longest reply on the shipped shape exceeds the cap, or a CPU entry whose slow-end decode rate
    under the deadline admits fewer tokens than its own longest reply. Neither holds for an entry
    this repo ships.

### A user's turn

13. **Every user-facing turn reads its stop, and a capped one says so.** `TurnEngine` and
    `BrainPhase` always pass a `StopLedger`, and a turn whose completion stopped at a token limit
    ends with `REPLY_CAPPED_NOTE` on its stream and in the message it stores. The note is reply
    text, like `BRAIN_FAILED_NOTE`: a `TextDelta` appended to `parts` and stored, written by the app
    so it needs no guardrail pass, and nothing crosses [proto/body.proto](../../proto/body.proto).
    It names the machine's length limit and never which one. A deep phase that failed says only
    `BRAIN_FAILED_NOTE`. The reply's own cap is a deployment setting paired with a bounded trace
    (ADR-0049 decision 6).
14. **A cut tool call ends the cortex's turn instead of failing it.** `handle_turn` catches
    `MalformedToolCallError`, never the wide `InferenceError` (a transport failure stays an error at
    the gRPC boundary), flushes the guarded channels itself because `stream_turn_events` flushes
    only on a clean end, and falls through to the one store path. The ledger picks exactly one
    sentence: capped, `cap_note` speaks; uncapped or silent, `UNREADABLE_CALL_NOTE` says the call
    could not be read without naming a limit that never applied. `unreadable_call_note` reads the
    same boolean the opposite way, so a reader never gets two explanations. A `warning` names the
    session, the turn and `capped`, with the error as `exc_info`, since no error at the gRPC
    boundary now includes the fragment.
15. **The deep phase does the same and does not re-raise.** `BrainPhase` catches the narrow error
    ahead of its wide branch, flushes, lets the ledger pick the note, logs the model, session, turn
    and `capped`, and the handoff settles `DONE`. `FAILED` is a claim about the swap machinery (the
    host refused, a tier would not become ready, the fit check declined, the drain limit elapsed,
    the process restarted), and a completion that reached a token limit is none of those.
16. **The recap fold does not read the stop.** `clean_recap` already rejects any account that does
    not end a sentence, which catches a cut fold, a wandering one and a mangled one alike.

## Consequences

- Every backend and every consumer must handle the `DecodeStop` case, and pyright collects it: a
  consumer that ignores the event fails to type-check on the branch that assumed text.
- A cut handoff and a clean one both settle `DONE`; only the reply text and the log say which.
- Every limit is sized on measurements of one machine; how a busy host moves them is in the
  measurement record.
- A turn whose first round was capped and whose later round produced an unparsable call for its own
  reason takes the capped note (decision 5).

## Alternatives rejected

- **The reason as a field on the closing cadence**: it would go missing on every build that reports
  no `timings`.
- **Reading the ledger in the wide `InferenceError` branch**: it passes every earlier test and
  reports a dead backend after a capped round as a truncation, skipping the placement retry.
- **Re-raising from the deep phase's cut branch**, which settles the handoff `FAILED`.
- **Deriving the deadline from the cap, or the cap from the deadline**, through a configured rate.
- **A limit pair per roster entry or per placement**: numbers nothing measured asks for, and each
  ordering at startup would become a relation per entry.
- **Bounding a user's turn by default**: a cortex turn holds a lease the user is watching.

## Related

- [ADR-0005](ADR-0005-llamacpp-engine.md), [ADR-0010](ADR-0010-subagents.md),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md) (the envelope),
  [ADR-0030](ADR-0030-brain-handoff.md) (the handoff record),
  [ADR-0047](ADR-0047-delegated-run-bound-ordering.md),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md).
- Module contracts: [brain-core](../modules/brain-core.md),
  [brain-inference](../modules/brain-inference.md),
  [brain-orchestrator](../modules/brain-orchestrator.md).
- Runbooks: [subagents-cpu](../runbooks/subagents-cpu.md),
  [llamacpp-gpu](../runbooks/llamacpp-gpu.md), [model-swap](../runbooks/model-swap.md).
- Readings: [generation bounds](../readings/generation-bounds.md),
  [delegated run holds](../readings/delegated-run-holds.md).
