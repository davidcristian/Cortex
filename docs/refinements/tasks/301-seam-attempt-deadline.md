# A per-attempt deadline on the body-to-brain seam

**Status:** landed 2026-08-18
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Nothing on the body's side of this seam set a gRPC deadline: no `Endpoint::timeout`, no
per-request timeout, and no wall-clock around the call. Every resilience the retry work built
bounded the *waiting between* attempts and never an attempt itself, so the whole design assumed a
brain that answers or fails, and had nothing to say about one that accepts the connection and
then goes quiet. The origin decision's own consequence, that `Down` arrives within `probe_budget`
of the probe starting, held only for a brain that answers.

**What landed** is the bound expressed as a property of the call: `RetryPlan` carries
`probe_deadline` (250 ms) and `call_deadline` (5 s) beside `probe_budget`, `deadline_for(method)`
resolves them the way `policy_for` resolves the schedule, and the decorator wraps every attempt in
`within_deadline`. The turn is the single exemption and it is a decision rather than a gap; the
writes are bounded although they are never retried, because bounding a call is not repeating it.
The shell's eager `converse` dial takes the same helper, so no attempt the body makes on this seam
is unbounded.

**The enforcement point moved, and the reason is the interesting half.** The shape the entry
proposed, a request timeout in the adapter, is a trap. tonic attaches its `transport::Error` to
the `Status::cancelled` it raises on its own expiry, so `body/crates/rpc/src/status.rs` classifies
that as `TransportError::Connection` and the indicator draws `Down`, which is honest. `Connection`
is in the *retryable* set, though, so a transport-armed deadline would have been retried, two more
times on the shipped schedule, against a brain that had just proved too slow or too stuck to
answer. That is the load amplifier this same entry classifies a timeout terminal to avoid, reached
through a back door and with nothing in the indicator looking wrong while it happened. So
the bound is enforced in the core over the `Sleeper` port, which gained a second question,
`bounded(deadline, call)`, whose real implementation is one line of `tokio::time::timeout` in the
ungated shell beside the existing `sleep`. The failure is its own variant,
`TransportError::Timeout { after }`, and the indicator draws it `Down`, since `Degraded` means the
brain answered and a timeout is exactly the absence of an answer.

**The retryability decision, made deliberately rather than inherited:** an expired deadline is
**terminal**. A retried deadline is the classic load amplifier, and it amplifies when the peer is
least able to take it, but the argument that decided it is narrower: a timeout is not the brain's
report about the call, it is this side's decision to stop waiting, so unlike `Unavailable` it
cannot say a second attempt would be faster. The cure for a call that needs longer is a longer
deadline, which is a knob rather than a repeat. The decline of `DEADLINE_EXCEEDED` at
[022](022-retryable-code-table.md) rested on there being no producer, and that ground is gone, so
the classification now stands on its merits and is pinned by test alongside the local variant.

**The probe budget now counts the attempts**, which is what makes its promise true rather than
approximately true: `RetryPolicy::within` takes the per-attempt cost and trims until
`attempts × deadline + backoff` fits, so `Down` arrives within `max(probe_budget, probe_deadline)`.
That changes the shipped default deliberately, from three probe attempts to two, so the dot
resolves inside 700 ms worst case and still spends one real retry on a restarting brain.

## Trail

- 2026-08-17: opened as the residue of the retryable-code table
  ([022](022-retryable-code-table.md)), which declined `DEADLINE_EXCEEDED` on the ground that
  nothing sets a deadline and found, in checking it, that the absence is itself the gap. Verified
  by reading `body/crates/rpc/src/` and the shell's `link.rs` and `seam.rs`: the only durations
  either spends are the retry knobs.
- 2026-08-18: landed as a deadline on the plan, enforced in the core, classified terminal, with
  the budget arithmetic corrected to count the attempts it now bounds. Two things the re-derivation
  found that the entry did not predict. The adapter is the wrong place for the bound, for the
  tonic reason above, so the shape this entry proposed would have amplified load exactly when the
  brain could least take it. And the harm at the far end was worse than a slow answer: the overlay's `useLink`
  clears its `inFlight` latch in the promise's `finally`, so a single probe that never resolved
  disabled every later probe for the rest of the session and the recovery interval fired into a
  no-op, which the bound now prevents on every path. Two follow-ups: the brain is still never told
  the deadline ([302](302-brain-learns-the-deadline.md)), and the turn stream itself is
  deliberately unbounded, which is right for a working turn and says nothing about a stalled one
  ([303](303-turn-stream-stall.md)).
- 2026-08-18, later: the tonic claim above was corrected. As landed, this entry recorded that an
  expired client-side timeout arrives *sourceless* and so classifies `Rpc`, drawing `Degraded`.
  That was read out of tonic's source and it is false: `find_status_in_source_chain` does mint the
  cancelled status without a source, and its caller then attaches the originating error, so the
  expiry classifies `Connection`. A probe against the hanging fake brain reported
  `code=Cancelled has_transport_source=true chain=["transport error", "Timeout expired"]`. The
  conclusion survives on the retryability hazard now written above, and the fact is pinned by
  `tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure` in
  `body/crates/rpc/tests/client.rs` rather than left as prose. No shipped behaviour changed.
