# A real connection indicator

**Status:** landed 2026-07-16
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**Without the status stream this entry expected.**
The entry text was accurate about the code
(`Health` exists, `BrainBridge` did not carry it) and wrong about the shape of the answer: it
assumed the indicator had to wait for a slice that *streams* brain status. It did not. The
honest signal was already derivable from what the overlay does anyway, and a poll was the
design to avoid, not the design to build. What shipped, in order of cost: every `TurnEvent`
is proof the brain is serving and every transport failure is proof it is not, both already in
the reducer (so a live turn keeps the dot exact for free); one probe per **summon**, latched
on the rising edge of visibility (`useSummonEffect`, shared with the reminder pull); and a
recovery re-check every 5 s **only while the overlay is visible and the link is not ready**,
which stops the moment it answers ready, so a healthy system spends nothing. A liveness poll
was rejected outright: it burns a request per interval forever, mostly while nobody is
looking, and is still stale in exactly the window the turn covers for free.
**Four states, not three:** `ready` (green), `degraded` (amber, the brain **answered** and is
not serving: a non-OK status such as `Unauthenticated` for a bad seam token, an unreadable
reply, or a future `ready = false`), `down` (red, `Connection`, the only failure where nothing
answered), and `unknown` (neutral, not asked yet, because the v1 dot's sin was claiming a
state it had not earned). "Connecting" is deliberately a modifier rather than a state: the dot
keeps its last known colour and pulses, and the probe itself rides the retrying transport, so
one probe already spans the reconnect window. Classification is pure and gated
(`body_core::link`), CI-gated at 100% on both sides, browser-validated in both themes, and
checked against a real brain by the `body-rpc` live suite (`Ready` from a running brain,
`Down` from a dead address). **One defect the gate caught:** re-arming the recovery check off
each answer dies after a single retry when the probe resolves inside one React batch, since
the in-flight flip is never rendered; it is an interval keyed on "visible and unhealthy"
because of that.

## Trail

- 2026-07-16: Landed with four states and no status stream, and opened the push half behind it as
  the streamed brain status entry, so the area count held at 3. Its sibling in the session read seam
  closed the same day, the two having been one deferral written down twice whose shared premise,
  waiting for a slice that streams brain status, turned out to be wrong for both.
