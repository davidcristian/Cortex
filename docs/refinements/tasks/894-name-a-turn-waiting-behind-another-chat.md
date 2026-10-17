# Name a turn waiting behind another chat

**Status:** open, waiting for its trigger
**Area:** brain
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md) decision 7
**Trigger:** a shipped client runs a cortex turn beside the overlay's, such as a fired reminder that runs a model turn or a second body
**Verified:** 2026-10-17

The cortex runs with `--parallel 1`, so a turn whose chat is not first waits inside llama-server
for another chat's generation to end. That wait sits inside the turn's own `thinking` hold (the
tool loop around each model stream), so its heartbeat says "working out the reply" while nothing
of its own is being worked out. A turn waiting for an earlier turn of its own chat, in
`SessionTurnLocks.hold` (`cortex_core/session_turns.py`), holds no wait, so its heartbeat is
empty. In both cases the stream is silent until the first heartbeat, 30 s in.

Reproduction ([readings](../../readings/overlay-concurrency-flows.md)): send "Write four
sentences about rivers." and "... about mountains." on two `Converse` streams at once; the second
stream receives no event for about the length of the first reply.

## What to do

1. Hold a `queued` wait while `SessionTurnLocks.hold` waits for the lock, with a sentence such as
   "waiting for this chat's previous message to finish". `queued` is today the key for a subtask
   waiting for room, so decision 7's wording widens with it.
2. For the cortex queue, the brain needs to know the wait exists: an admission in front of the
   cortex call sized to the tier's `--parallel`, holding `queued` "waiting for another chat's reply
   to finish" while it waits. Check first that no other client than the overlay runs cortex turns
   today; if none does, this step waits for the trigger above.
3. Test both waits over fakes: the heartbeat and the immediate `StatusUpdate` name the wait, and
   the wait ends when the turn starts generating.

## History

- 2026-10-17: filed by the concurrency flows on the Linux shell, where both waits were silent.
