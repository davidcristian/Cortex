# Name a turn waiting behind another chat

**Status:** open, waiting for its trigger
**Area:** brain
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md) decision 7
**Trigger:** a shipped client runs a cortex turn beside the overlay's, such as a fired reminder that runs a model turn or a second body
**Verified:** 2026-10-25

The cortex runs with `--parallel 1`, so a turn whose chat is not first waits inside llama-server
for another chat's generation to end. That wait sits inside the turn's own `thinking` hold (the
tool loop around each model stream), so its heartbeat says "working out the reply" while nothing
of its own is being worked out, and the stream is silent until the first heartbeat, 30 s in. A
turn waiting for an earlier turn of its own chat is already named: `SessionTurnLocks.hold` holds
the `queued` wait `CHAT_AHEAD` and sends it as a status at once.

Reproduction ([readings](../../readings/overlay-concurrency-flows.md)): send "Write four
sentences about rivers." and "... about mountains." on two `Converse` streams at once; the second
stream receives no event for about the length of the first reply.

Today only the overlay runs cortex turns, and it keeps one chat in flight: a fired reminder is
pushed without a model turn, and a fired scheduled task runs on the subagent tier. So the trigger
has not fired; the reproduction above needs a second test client.

## What to do

1. Put an admission in front of the cortex call, shared across streams and sized to the tier's
   `--parallel`, holding `queued` "waiting for another chat's reply to finish" while it waits.
   The size is a new setting that must match the model host's flag, so `crosscheck` or
   `flagcheck` compares the two.
2. Test it over fakes: the heartbeat and the immediate `StatusUpdate` name the wait, the wait ends
   when the turn starts generating, and a turn that opens a second cortex stream (recall's judge,
   the recap) does not wait on itself.

## History

- 2026-10-17: filed by the concurrency flows on the Linux shell, where the wait was silent.
- 2026-10-25: checked again and not fired: no second client runs cortex turns and
  `SessionTurnLocks.hold` is unchanged; the change since added the status that clears the chip.
