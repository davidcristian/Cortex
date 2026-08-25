# An announcement past the millisecond ladder arms tonic's clock short of our own bound

**Status:** landed 2026-08-25
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Opened 2026-08-25 by the close of
[R-381](381-the-header-encoding-error-is-larger-than-recorded.md), whose measurement of the header
encoding turned this up beside the thing it was measuring.

Announcing a deadline and arming tonic's own clock are one act: `Request::set_timeout` writes
`grpc-timeout`, and the channel's `GrpcTimeout` layer parses that header back off the outgoing
request and sleeps on **what it decoded**, not on the `Duration` the interceptor was handed. So the
encoding's loss comes straight out of the grace margin that makes the core's own bound win the
race.

tonic picks the most precise unit that fits in eight digits and truncates
(`duration_to_grpc_timeout`, `tonic-0.14.6/src/request.rs`): nanoseconds below 0.1 s, microseconds
below 100 s, milliseconds below 99,999,999 ms, which is about 27.8 hours, and whole seconds past
that. Below that last step the loss is under a millisecond and the 250 ms margin swallows it. Above
it the step is a second: with `announced = enforced + 250 ms`, the decoded header falls below the
enforced bound whenever `announced` has a millisecond remainder over 250, which is three
announcements in four, and it can fall as much as 749 ms short. tonic's timer then fires **first**,
and tonic's expiry classifies `Connection`, which is in the retryable set, so one abandoned call
becomes three: exactly the load amplifier the margin exists to prevent.

It is reachable from the shipped knobs. `plan_from_env` (`body/app/src-tauri/src/seam.rs`) reads
`CORTEX_BRAIN_CALL_DEADLINE_MS` as a `u64` of milliseconds with no ceiling, and `RetryPlan`'s
fields are public besides. `MAX_ANNOUNCED_DEADLINE` (`body/crates/rpc/src/call.rs`) filters only
what the header cannot spell **at all**, 99,999,999 hours, about eleven thousand years, because it
was sized against tonic's panic rather than against the margin.

**Why this is not urgent.** Nothing ships near it. The default call deadline is 5 s and the probe's
is 250 ms, and a call deadline of 27.8 hours is not a configuration anybody has a reason to write;
a body that waited that long on one unary read has a different problem. The consequence when it is
reached is bounded too: the read schedule's attempts, not an unbounded retry.

**What would close it.** The smallest honest fix is to make the filter say what it means. An
announcement this transport can spell only in whole seconds is one whose ordering it cannot
guarantee, so `MAX_ANNOUNCED_DEADLINE` becomes the millisecond ladder's own ceiling and such a
call announces nothing, which is already what this adapter does with an unspellable deadline and
already the argued answer to "announce something shorter and lose the race on purpose". The
alternative is to keep announcing and widen the margin above a second, which pays for a
configuration nobody wants with a margin every call spends. Either way the change wants a wire case
beside `a_deadline_the_header_cannot_spell_is_dropped_rather_than_sent`
(`body/crates/rpc/tests/client.rs`) at a deadline in the seconds band, and a mutation table proving
it reddens, since a filter with the wrong bound is green in both directions today.

Note before starting that the ceiling would then be a duration the adapter asserts and the core
does not know, which is the seam this repo ties with `scripts/crosscheck.py` when two trees spell
one value; check whether the registry should learn it.

## Trail

- 2026-08-25: opened by the close of
  [R-381](381-the-header-encoding-error-is-larger-than-recorded.md). Recorded in the ADR-0024
  encoding addendum dated the same day.
- 2026-08-25: landed as the candidate above, in the ADR-0024 unit-ladder addendum.
  `MAX_ANNOUNCED_DEADLINE` became `MAX_ANNOUNCED_DEADLINE_MS`, a count of milliseconds at the
  header's millisecond rung (99,999,999 ms) rather than a `Duration` at the panic rung, and an
  announcement past it is dropped exactly as an unspellable one already was. Every number in the
  entry re-derived and held, with one correction in the entry's own favour: below the rung the
  margin is not merely intact for the other quarter of remainders, it is intact only for a
  remainder of zero, since a remainder of 750 to 999 keeps the ordering but shrinks the margin to
  as little as 1 ms. The classification claim was confirmed against
  `body/crates/rpc/src/status.rs` and the live case that asserts `is_transient` on a real tonic
  expiry, not assumed. The registry question the entry raised is answered yes: the constant is now
  a `crosscheck.py` site in `scripts/shippedcouplings.py` with `docs/modules/body-rpc.md` as its
  far side. The wire case is
  `an_announcement_off_the_millisecond_rung_is_dropped_and_one_on_it_is_sent`
  (`body/crates/rpc/tests/client.rs`), which reads tonic's truncation off `Request::set_timeout`
  itself rather than off its source; the mutation table is in the addendum. Nothing deferred, so
  no new task file.
