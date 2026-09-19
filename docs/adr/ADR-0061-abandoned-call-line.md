# ADR-0061: The brain logs a call its caller abandoned

**Status:** Accepted (2026-08-22)

## Context

The body announces a deadline on every unary call it makes over gRPC, a margin longer than the limit
it enforces, and drops the call when its own clock wins
([ADR-0024](ADR-0024-transport-retry.md)). `grpc.aio` turns the client's stream reset into an
`asyncio` cancellation of the servicer coroutine, so the abandoned work is already cut by the
transport. That cancellation unwinds the handler's own `finally` blocks and disappears: nothing is
logged by grpc or by this repo, so an operator watching a slow brain sees the body's timeouts in one
process and nothing at all in the other.

The announced deadline also lets a handler read the time it has left. What a handler should do with
it (decline a listing it cannot finish, return a transcript without a cascade, pass the remainder on
to the model host or a tool) is a policy per RPC or per downstream port. Recording that a call was
abandoned needs no such policy, so it is decided first and alone.

## Decision

1. **One interceptor watches every unary call.** `AbandonedCallInterceptor`
   (`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py`) wraps each unary-unary
   behavior in a wrapper that logs on `asyncio.CancelledError`, for the reason the token check is
   one interceptor (`auth.py`): a `try` block per RPC would be ten today, and the eleventh would
   depend on somebody remembering. `create_server` registers it unconditionally, since there is
   nothing to configure, and second, after the token interceptor, so an unauthenticated call is
   refused rather than watched: work never started is not work abandoned.

2. **The line prints the reading and nothing branches on it.** One `WARNING`, `ABANDONED_MESSAGE`,
   with the RPC's wire `method` and `context.time_remaining()`. The reading covers three different
   facts, which an operator tells apart by the value:

   | Reading | What ended the call |
   | --- | --- |
   | a float well above zero | the caller stopped waiting early, which the shipped body does on every call, since it enforces a limit strictly shorter than the one it announces |
   | an integer `0` | the announced deadline, enforced by the brain's own clock: the body was killed or the connection half opened, so its cancellation never arrived |
   | `None` | the caller announced no deadline, so what arrived was a disconnect |

   The type makes the distinction the value cannot. grpc floors the reading at zero, and
   `max(deadline - now, 0)` answers with its own second argument, an `int`, only once the deadline
   has passed, so a reading still counting down is a float whatever its size. When a caller starts
   its own clock on the deadline it announced, the two race and a cancellation can arrive with a
   little of the window unspent. The reading is not bounded above by the caller's announcement: a
   grpc-python client rounds its header up onto a coarse unit ladder, so a test client's 10 s can
   reach the server as `10100ms`
   ([abandoned-call readings](../readings/abandoned-call-remaining.md)). `WARNING` rather than
   `INFO`, because an abandoned call is work spent on a reply nobody read and should be rare; if it
   becomes routine, that is a fact about the timeouts worth being told loudly.

3. **The cancellation is re-raised on every path.** A coroutine that swallows its cancellation is a
   task that outlives its request; the wrapper makes an abandonment visible and never changes it.

4. **Which methods are wrapped follows from the method's shape, not a list of names.** A handler
   with no unary-unary behavior is handed back untouched, and so is an unserviced method (the
   continuation resolving to `None`). `Converse` is the service's only stream and announces no
   deadline, and a stream reporting an abandonment against a deadline would be the first half of
   enforcing a limit on a turn's length, which the gRPC contract deliberately does not have. A list
   of ten method names would cover nothing on the day it went stale.

5. **Each reading is asserted over a real wire, in the shape that produces it in production.** The
   cases in `brain/packages/orchestrator/tests/test_abandon.py` drive a loopback `grpc.aio`
   `BrainService` built by `create_server` whose store never answers:
   - the caller stops early: announce wide, cancel once the handler is entered, assert a float above
     zero and a lower bound only, since an upper bound at the announcement would assert something
     grpc does not promise;
   - the brain's clock alone: `grpc-timeout` sent as metadata with no `timeout=` beside it, so no
     clock exists that could fire early; assert `isinstance(remaining, int)`, `remaining == 0` and
     the rendered tail `time_remaining=0`. The `int` separates the floor from a small remainder on a
     reading grpc produced;
   - no deadline: cancel once the handler is entered, assert `None`;
   - both clocks started on one announcement: assert the floor, `remaining >= 0`, and that the
     window ran down, `remaining < _ANNOUNCED_S / 2`, and nothing exact, since under load this case
     produces small remainders.

   The store sets an `asyncio.Event` from inside the handler, so "the handler is running" is a fact
   the case knows; no case sleeps to order two events. The parameterized cases assert how each
   reading renders on a value the file hands the wrapper.

6. **The brain acts on the announced deadline nowhere else.** No unary handler on the gRPC contract
   reaches a model host or a tool sidecar: the ten read and write the session, schedule and
   preference stores, the residency report and, for a delete's cascade, the memory store. Every
   model-host and tool call is made from a `Converse` turn, startup recovery or a background loop,
   and `Converse` announces nothing, so there is no deadline for a downstream call to inherit. A
   downstream call is bounded on its own terms instead: every `ModelHost` verb uses
   `CORTEX_MODELHOST_TIMEOUT_S`, and one tool call is bounded by a wrapper
   ([ADR-0009](ADR-0009-tools-mcp.md), decision 10). The two per-RPC behaviours stay unbuilt,
   waiting for something to need them: an early `DEADLINE_EXCEEDED` from `ListSessions` would turn
   on a store-read minimum nobody has measured and would answer a deadline that has not expired
   ([R-360](../refinements/tasks/360-a-read-that-will-not-fit-declines-early.md)), and a partial
   session read describes a memory cascade no read path here has
   ([R-361](../refinements/tasks/361-a-read-rpc-recalls-nothing-to-omit.md)).

## Consequences

- A slow brain is visible from its own logs: the line names which RPC was dropped and how much of
  the announced window was left.
- The suite checks every claim the module docstring and
  [brain-orchestrator.md](../modules/brain-orchestrator.md) make about the reading. A grpc release
  that stopped flooring, reported a negative remainder, or folded the no-deadline case into `0`
  fails a wire case rather than passing under a bound.
- The two-clock case's half-window bound is not sampled over time. The remainder is bounded by the
  gap between the client's clock firing and the server's window, which call setup sets; a remainder
  approaching half the window would mean the handler is not entered before the deadline, and the
  case then fails on the event it waits on, a louder failure naming a real problem.
- The suite pays the announced 0.2 s twice, in the header-only and two-clock cases; the other wire
  cases cancel as soon as the handler is entered.

## Alternatives rejected

- **A `try` block per handler.** It depends on somebody remembering; the interceptor covers every
  handler whatever is added.
- **Driving the two-clock scenario N times and asserting one integer floor.** It lowers the flake
  rate rather than removing it; the header-only shape removes the second clock instead.
- **Holding the event loop so the deadline passes before the cancellation.** It works and costs
  suite time to force an ordering the header-only shape gets for free.
- **Tightening the half-window bound toward the widest measured remainder.** That turns one
  machine's worst case under one load into a rule for the whole suite.

## Related

- [ADR-0024](ADR-0024-transport-retry.md): the deadlines the body enforces and announces.
- [ADR-0016](ADR-0016-seam-token.md): the token interceptor this one sits behind.
- [brain-orchestrator.md](../modules/brain-orchestrator.md),
  [abandoned-call readings](../readings/abandoned-call-remaining.md).
