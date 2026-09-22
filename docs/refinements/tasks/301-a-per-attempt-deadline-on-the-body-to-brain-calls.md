# A per-attempt deadline on the body-to-brain calls

**Status:** done 2026-08-18
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Nothing on the body's side set a gRPC deadline: no `Endpoint::timeout`, no per-request timeout, and
no wall clock around the call. Every resilience the retry work built bounded the waiting between
attempts and never an attempt itself, so the design assumed a brain that answers or fails and had
nothing to say about one that accepts the connection and then goes quiet. The origin decision's own
consequence, that `Down` arrives within `probe_budget` of the probe starting, held only for a brain
that answers.

What was built is the bound as a property of the call: `RetryPlan` has `probe_deadline` (250 ms)
and `call_deadline` (5 s) beside `probe_budget`, `deadline_for(method)` resolves them the way
`policy_for` resolves the schedule, and the decorator wraps every attempt in `within_deadline`. The
turn is the single exception, deliberately; the writes are bounded although they are never retried,
because bounding a call is not repeating it. The shell's eager `converse` call takes the same
helper.

The enforcement point moved, and that is the interesting half. A request timeout in the adapter,
which the entry proposed, is the wrong place: tonic attaches its `transport::Error` to the
`Status::cancelled` it raises on its own expiry, so `body/crates/rpc/src/status.rs` classifies that
as `TransportError::Connection` and the indicator draws `Down`, which is accurate. But `Connection`
is in the retryable set, so a deadline enforced by the transport would have been retried, twice
more on the shipped schedule, against a brain that had just proved too slow or too stuck to answer,
with nothing in the indicator looking wrong. So the bound is enforced in the core over the
`Sleeper` port, which gained a second method, `bounded(deadline, call)`, whose real implementation
is one line of `tokio::time::timeout` in the shell. The failure is its own variant,
`TransportError::Timeout { after }`, drawn as `Down`, since `Degraded` means the brain answered.

An expired deadline is terminal, decided rather than inherited. A retried deadline amplifies load
when the peer is least able to take it, and the narrower argument is that a timeout is not the
brain's report about the call but this side's decision to stop waiting, so unlike `Unavailable` it
cannot say a second attempt would be faster. The cure for a call that needs longer is a longer
deadline. The earlier decline of `DEADLINE_EXCEEDED` at [022](022-retryable-code-table.md) rested
on there being no producer, which is no longer true, so the classification now stands on its own
merits and is asserted by test.

The probe budget now counts the attempts, which makes its bound exact: `RetryPolicy::within` takes
the per-attempt cost and trims until `attempts x deadline + backoff` fits, so `Down` arrives within
`max(probe_budget, probe_deadline)`. That deliberately changes the shipped default from three probe
attempts to two, so the dot resolves inside 700 ms worst case and still spends one real retry on a
restarting brain.

## History

- 2026-08-17: Opened by the retryable-code table ([022](022-retryable-code-table.md)), which
  declined `DEADLINE_EXCEEDED` because nothing sets a deadline, and found in checking it that the
  absence is itself the gap.
- 2026-08-18: Done. Two things found while building it that the entry did not predict. The adapter
  is the wrong place for the bound, for the tonic reason above, so the proposed shape would have
  amplified load exactly when the brain could least take it. And the harm at the far end was worse
  than a slow answer: the overlay's `useLink` clears its `inFlight` latch in the promise's
  `finally`, so a single probe that never resolved disabled every later probe for the rest of the
  session and the recovery interval fired into a no-op. Two follow-ups: the brain is still never
  told the deadline ([302](302-brain-learns-the-deadline.md)), and the turn stream itself is
  deliberately unbounded ([303](303-turn-stream-stall.md)).
- 2026-08-18, later: The tonic claim was corrected. As first written, this entry recorded that an
  expired client-side timeout arrives with no source and so classifies `Rpc`, drawing `Degraded`.
  That was read out of tonic's source and is false: `find_status_in_source_chain` does create the
  cancelled status without a source, and its caller then attaches the originating error, so the
  expiry classifies `Connection`. A probe against the hanging fake brain reported `code=Cancelled
  has_transport_source=true chain=["transport error", "Timeout expired"]`. The conclusion survives
  on the retry hazard above, and the fact is asserted by
  `tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure` in
  `body/crates/rpc/tests/client.rs`. No shipped behaviour changed.
