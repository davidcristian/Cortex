# The grace margin was sized on a header rounding error far smaller than one measured

**Status:** done 2026-08-25
**Area:** rpc-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

`ANNOUNCED_DEADLINE_GRACE_MS` is 250 ms. The decision that added it described one of the three
terms in that number as "the header encoding's truncation to whole units, at most a millisecond
and exactly zero for every value the shipped plan produces". Measurements taken while working on
something else contradicted that.

On a bare loopback `grpc.aio` server, the window at handler entry was 0.200092 s for an announced
0.2 s, 1.05897 s for 1.05 s and 3.008877 s for 3.0 s. Over a real `BrainService`, 41 of 200
replays announcing 10 s gave an abandonment reading above 10 s, the largest 10.0993 s. The
difference is about 9 ms at 1.05 s and about 100 ms at 10 s, not "at most a millisecond".

Every measured difference is in the safe direction: the server's window is longer than the
announcement, so the brain waits past the point where the body stopped waiting. No bound in the
repo was at risk.

## History

- 2026-08-22: opened by the close of
  [R-351](351-two-readings-only-a-fake-ever-produced.md),
  [R-371](371-a-floor-and-a-sliver-are-indistinguishable.md) and
  [R-372](372-the-sliver-is-unsampled-over-time.md), whose measurement of the abandonment reading
  found this beside it.
- 2026-08-25: closed by [ADR-0024](../../adr/ADR-0024-transport-retry.md) decision 15 and
  [the deadline readings](../../readings/rpc-deadlines.md), which measured both halves and
  corrected the sentence rather than the number. One claim above was wrong:
  `body/crates/rpc/tests/client.rs` has read the shipped announced values back off the wire since
  the first version, parsed as durations, and compares them with `announced_deadline_for`. What
  had never been measured is the pair that ships against a grpc-python brain: 500 ms and 5.25 s
  cross as `500ms` and `5250ms`, and the brain's window at handler entry is 0.16 ms to 1.16 ms
  *shorter* than the announcement, never longer, in 39 warm calls. The cause of this entry's
  readings is grpc-python's own client, which rounds a `timeout=` up to the next value on a coarse
  unit scale before encoding it (`timeout=10.0` arrives as `10100ms`, read off the wire under
  `GRPC_TRACE=all`); the server's receipt timestamp only subtracts transit. tonic truncates
  instead, by under a microsecond below 100 s, so the body's direction cannot produce the excess.
  The margin stays 250 ms, because the term that sizes it is the scheduler stall and the two terms
  this entry doubted are a millisecond and a microsecond. The measurement opened
  [R-436](436-an-announcement-past-the-millisecond-ladder-loses-the-race.md), the one range where
  tonic's rounding can exceed the margin.
