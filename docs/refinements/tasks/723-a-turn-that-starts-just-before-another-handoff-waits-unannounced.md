# A turn that starts just before another handoff waits unannounced

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md)
**Verified:** 2026-09-24

A turn announces a wait for another turn's handoff only when that handoff's residency scope is
already active: `TurnEngine._wait_out_handoff` (`cortex_core/engine.py`) asks
`ResidencyQueue.blocks(model)` once, after storing the user message. A scope that begins after that
check and before the turn's first model call still makes the call's `acquire` wait in
`ResidencyBoard.await_resident`, with nothing sent but `thinking` heartbeats, which the body counts
toward the ten-minute first gap (ADR-0069 decision 4). Two windows reach it. The other turn's pool
drain holds the handoff claim for up to `DEFAULT_SWAP_DRAIN_TIMEOUT_S` (60 s) before its scope
starts, and this turn's own history read and recall come between the check and the first
generation, where with memory on the default `judge` recall asks the cortex.

Two remedies, neither built:

- Count a held handoff claim as blocking too. `HandoffClaim.held` clears its flag in a `finally`
  without waking anything, and notifying the board's condition there would await its lock under
  cancellation, so the waiter needs a synchronous signal such as an `asyncio.Event`. This closes the
  drain window and not the recall one.
- Announce at the lease itself, by giving the waiting `acquire` the turn's `ProgressSink`. This
  closes both, and changes `ModelManager.acquire` and `InferenceBackend.stream`, which many fakes
  implement.

## History

- 2026-09-24: Opened by the change that makes a turn announce a handoff already holding the card,
  which checks once, at the turn's start.
