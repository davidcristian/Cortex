# A queued status stays after the turn ahead ends

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0069](../../adr/ADR-0069-turn-heartbeat.md) decision 7
**Verified:** 2026-10-17

`SessionTurnLocks.hold` holds the `queued` wait `CHAT_AHEAD` while a turn waits for its own chat's
previous turn, and sends it as a status. When the lock is taken the wait closes, but
`TurnWaits.changed` sends nothing when no wait is left open, and nothing the turn does before its
first reasoning (recall, the tool listing) sends a status, since a `thinking` wait reaches the body
only in a heartbeat. So the overlay's chip, which keeps the last status until the next one, goes on
reading "waiting for this chat's previous message to finish" through the waiting turn's own
recall, until its first reasoning arrives. An empty heartbeat does not clear the chip either, and
the first one comes 30 s in.

Reproduction ([readings](../../readings/overlay-concurrency-flows.md)): on one session id, send
"Write eight sentences about rivers, one per line." on one stream and 4.5 s later "Name one
fruit." on a second. The second stream received the queued status at once; the first turn's reply
ended 2.0 s later, and the second turn's first `thinking` status came 6.2 s after that, of which a
turn with nothing ahead of it spends about 4 s before its first status. Two runs, chats
`s12-q-cancel` and `s12-q-drop`, gave the same shape.

## What to do

1. Decide what the chip shows between the lock and the first model output: a wait key for the
   turn's own preparation held from the lock to the first stream, or a status that clears the
   chip when the outermost wait closes. Either changes ADR-0069 decision 7 and the overlay's
   `applyHeartbeat`, so write the decision first.
2. Test over fakes that the status after `CHAT_AHEAD` closes is the new one, and on the Linux
   shell that the chip changes when the turn ahead ends.

What the second option needs, checked against the code on 2026-10-17:

- Brain: `TurnWaits.changed` (`cortex_core/waits.py`) sends a `StatusUpdate` with an empty
  `state` and `detail` when the last open wait closes. Sent for every outermost close, that
  rule fails 16 tests in 8 files (`test_waits.py`, `test_progress_contract.py`, `test_spawn.py`,
  `test_summarizing.py`, `test_converse_heartbeat.py`, `test_escalating_engine.py`,
  `test_load_wait.py`, `test_delegation_wait.py`), each asserting the statuses sent today. It
  also sends a clear when a quiet hold (`announce=False`, the swap conductor's) closes, so each
  `WaitHold` has to record whether it was announced, and only an announced close clears.
- Body: `converse.rs` passes a status through with its `state` unchanged, so no Rust change.
- Overlay: `Message.tsx` shows the chip while `status !== null`, so `turnState.ts` maps a
  status whose `state` is `""` to `status: null`, and `applyHeartbeat` clears a chip that is not
  `thinking` on an empty wait.

## History

- 2026-10-17: filed by the closing audit of the queued status, from two runs on the `cortexn7`
  stack.
- 2026-10-17: checked against the code and left open: the fix changes three ADR-0069 decisions,
  16 brain tests and the overlay, more than the last slot of the night had time to finish.
