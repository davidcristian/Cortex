# An announcement past the millisecond ladder sets tonic's clock short of our own bound

**Status:** done 2026-08-25
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Announcing a deadline and starting tonic's own clock are one act: `Request::set_timeout` writes
`grpc-timeout`, and the channel's `GrpcTimeout` layer parses that header back off the outgoing
request and sleeps on what it decoded, not on the `Duration` the interceptor was handed. So the
encoding's loss comes straight out of the grace margin that makes the core's own bound win the
race.

tonic picks the most precise unit that fits in eight digits and truncates
(`duration_to_grpc_timeout`, `tonic-0.14.6/src/request.rs`): nanoseconds below 0.1 s, microseconds
below 100 s, milliseconds below 99,999,999 ms, which is about 27.8 hours, and whole seconds past
that. Below that last step the loss is under a millisecond and the 250 ms margin covers it. Above
it the step is a second: with `announced = enforced + 250 ms`, the decoded header falls below the
enforced bound whenever `announced` has a millisecond remainder over 250, which is three
announcements in four, and it can fall as much as 749 ms short. tonic's timer then fires first, and
tonic's expiry classifies `Connection`, which is in the retryable set, so one abandoned call
becomes three.

It is reachable from the shipped settings. `plan_from_env` (`body/app/src-tauri/src/seam.rs`) reads
`CORTEX_BRAIN_CALL_DEADLINE_MS` as a `u64` of milliseconds with no ceiling, and `RetryPlan`'s
fields are public besides. `MAX_ANNOUNCED_DEADLINE` (`body/crates/rpc/src/call.rs`) filters only
what the header cannot encode at all, 99,999,999 hours, because it was sized against tonic's panic
rather than against the margin.

Nothing ships near it. The default call deadline is 5 s and the probe's is 250 ms, and a call
deadline of 27.8 hours is not a configuration anybody has a reason to write. The smallest fix is to
make the filter say what it means: an announcement this transport can encode only in whole seconds
is one whose ordering it cannot guarantee, so `MAX_ANNOUNCED_DEADLINE` becomes the millisecond
ladder's own ceiling and such a call announces nothing.

## History

- 2026-08-25: opened by the close of
  [R-381](381-the-header-encoding-error-is-larger-than-recorded.md), whose measurement of the
  header encoding found this beside it.
- 2026-08-25: closed as the candidate above, as
  [ADR-0024](../../adr/ADR-0024-transport-retry.md) decision 16. `MAX_ANNOUNCED_DEADLINE` became
  `MAX_ANNOUNCED_DEADLINE_MS`, a count of milliseconds at the header's millisecond step
  (99,999,999 ms) rather than a `Duration` at the panic step, and an announcement past it is
  dropped exactly as an unencodable one already was. Every number in the entry was checked again
  and held, with one correction in the entry's own favour: below that step the margin is intact
  only for a remainder of zero, since a remainder of 750 to 999 keeps the ordering but shrinks the
  margin to as little as 1 ms. The classification claim was confirmed against
  `body/crates/rpc/src/status.rs` and the live case that asserts `is_transient` on a real tonic
  expiry, not assumed. The registry question the entry raised is answered yes: the constant is now
  a `crosscheck.py` declaration in `scripts/shippedcouplings.py` with `docs/modules/body-rpc.md` as
  the place restating it. The wire case is
  `an_announcement_off_the_millisecond_rung_is_dropped_and_one_on_it_is_sent`
  (`body/crates/rpc/tests/client.rs`), which reads tonic's truncation off `Request::set_timeout`
  itself rather than off its source. Nothing deferred, so no new task file.
