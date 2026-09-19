# A real connection indicator

**Status:** done 2026-07-16
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`Health` existed but `BrainBridge` did not use it, so the v1 dot reported a state nobody had
established. The entry assumed the indicator had to wait for a slice that streams brain status; it
did not, and a liveness poll was the design to avoid rather than to build, since it costs a
request per interval forever, mostly while nobody is looking, and is still stale in exactly the
window a turn covers for free.

What shipped, in order of cost: every `TurnEvent` is proof the brain is serving and every
transport failure is proof it is not, both already in the reducer, so a live turn keeps the dot
exact for nothing; one probe per summon, on the rising edge of visibility (`useSummonEffect`,
shared with the reminder pull); and a recovery re-check every 5 s only while the overlay is
visible and the link is not ready, which stops the moment it answers ready.

Four states rather than three: `ready` (green), `degraded` (amber, the brain answered and is not
serving, such as a non-OK status like `Unauthenticated` for a bad token, an unreadable reply, or a
future `ready = false`), `down` (red, `Connection`, the only failure where nothing answered), and
`unknown` (neutral, not asked yet). "Connecting" is a modifier rather than a state: the dot keeps
its last known colour and pulses, and the probe uses the retrying transport, so one probe spans
the reconnect window.

Classification is pure (`body_core::link`), covered at 100% in CI on both sides, checked in a
browser in both themes, and checked against a real brain by the `body-rpc` live suite (`Ready`
from a running brain, `Down` from a dead address). One defect the tests caught: restarting the
recovery check off each answer stops after a single retry when the probe resolves inside one React
batch, since the in-flight flip is never rendered. It is therefore an interval keyed on "visible
and unhealthy".

## History

- 2026-07-16: Shipped with four states and no status stream, and opened the push half behind it as
  the streamed brain status entry ([R-129](129-streamed-brain-status.md)), so the area count held
  at 3. Its sibling in the session read boundary closed the same day, the two having been one
  deferral written down twice whose shared premise, waiting for a slice that streams brain status,
  was wrong for both.
