# A turn behind another turn's handoff can outlast the first gap

**Status:** open, waiting for its trigger
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Verified:** 2026-09-24
**Trigger:** a stack running handoffs. No shipped file enables one:
`grep -rnE 'CORTEX_ESCALATION: *[^ ]' docker/` finding nothing says so, and the gpu overlay passes
the switch through by name, so a host `.env` can turn it on.

The body gives a turn ten minutes to send its first event (`DEFAULT_TURN_FIRST_GAP_MS` in
`body/crates/core/src/retry/gap.rs`), and ADR-0024 decision 19 sizes that on the brain's own bounds
for the turn: the pool drain, the model load and the first-token stall. It does not count a wait
behind another turn's handoff, which the shipped body can start. A stop in the overlay only stops
delivery and leaves the turn running to its end (`TauriBridge.converse`), and each turn opens a
fresh `Converse` stream, so a user who stops a turn during its handoff and sends another has two
turns in the brain. The second turn's model acquire waits in `ResidencyBoard.await_resident`
until the first one's scope ends: the rest of the deep phase, then the swap back, whose readiness
checks alone can take `_RESTORE_ATTEMPTS` times `DEFAULT_SWAP_LOAD_TIMEOUT_S`, 600 s.
[R-127](127-multi-turn-and-proto-cancel.md), which would stop the first turn at the brain,
shortens the wait to the swap back and does not remove it.

Nothing tells the body about that wait. The waiting turn holds its `thinking` wait, which
`TurnWaits.changed` sends only inside a heartbeat, and the body counts each heartbeat as 30 s of the
turn's own silence (`GapClock` in `gap.rs`, ADR-0069 decision 4). So the first gap runs on and can
end the turn before it starts. Not checked: what the brain does with that turn once the body drops
its stream.

A fix that keeps the bound is an announced wait while a turn waits on another turn's scope: a
`StatusUpdate` is a turn event, so it ends the first gap, and the `swapping` key already names a
handoff. `SwappingModelManager` has no progress sink, so the wait has to be held by a caller that
has one.

## History

- 2026-09-24: Opened by a check of [R-024](024-disconnect-mid-handoff-teardown.md), whose
  2026-09-17 line gave this concern to [R-421](421-a-silent-turn-owes-the-body-a-heartbeat.md).
  That entry closed on 2026-09-22 keeping the ten-minute first gap.
