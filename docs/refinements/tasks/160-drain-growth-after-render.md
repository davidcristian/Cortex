# Drain growth after the turn's last render

**Status:** landed 2026-07-21
**Area:** body-overlay
**Origin:** [ADR-0037](../../adr/ADR-0037-whisper-streaming.md)

The front trails arrivals by
its catch-up time, so the box can gain its last line inside the half second after `complete`,
when nothing re-renders and no measured move of the panel is running (ADR-0037
consequences). The history's min-height floor hides it today (short chats sit inside the
floor, long ones scroll), and the tail pin rides the whisper's own `onGrow`. Trigger: the
chat floor changing, or a between-render growth visibly outrunning the panel on some future
layout. The fix is the panel hearing between-render growth the way it hears a roll
(`cortex:morphstart`'s lesson). Placed here 2026-07-21. **Landed 2026-07-21, the same day,
by exactly that fix**: the first live look found the panel's top edge snapping
backwards on every token of a reply past the chat floor (the same stale-measurement root,
seen from the other side), so the whisper bubble now carries `data-morphing` from its first
spoken letter to its settle and dispatches the contract's start and end events. Placements
defer for the length of the stream, the panel's auto height follows the box frame by frame
(the drain included), and the end event is the re-measure this entry asked for (ADR-0037
addendum has the before and after traces).

## Trail

- 2026-07-21: Filed with the whisper streaming redesign and landed the same day, when the first live
  look surfaced the same stale-measurement root as the per-token jitter, fixed by the bubble joining
  the roll contract (ADR-0037 addendum).
