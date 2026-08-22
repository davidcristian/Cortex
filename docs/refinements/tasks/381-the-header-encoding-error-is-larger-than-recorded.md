# The grace margin's sizing cites a header error two orders of magnitude smaller than one measured

**Status:** open, actionable
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Opened 2026-08-22 by the close of
[R-351](351-two-readings-only-a-fake-ever-produced.md),
[R-371](371-a-floor-and-a-sliver-are-indistinguishable.md) and
[R-372](372-the-sliver-is-unsampled-over-time.md), whose measurement of the abandonment reading
turned this up beside the thing it was measuring.

`ANNOUNCED_DEADLINE_GRACE_MS` is 250 ms and the addendum that landed it sizes that number on three
things in ascending order. The middle one is "the header encoding's truncation to whole units, at
most a millisecond and exactly zero for every value the shipped plan produces".

A probe run while measuring something else read the server side window at handler entry, on a bare
loopback `grpc.aio` server, for three announcements a client made with `timeout=`: 0.200092 s for
0.2 s, 1.05897 s for 1.05 s, and 3.008877 s for 3.0 s. Over a real `BrainService`, 41 of 200
replays announcing 10 s produced an abandonment reading above 10 s, the widest 10.0993 s. So the
window the server enforces differs from the number the client announced by roughly 9 ms at 1.05 s
and roughly 100 ms at 10 s, which is not "at most a millisecond" and is not zero.

**Why this is not urgent.** Every difference measured runs the safe way. The server's window is
*longer* than the announcement, meaning the brain waits past the moment the body stopped waiting
rather than expiring before the body's own bound, and the ordering the grace margin exists to
guarantee ("a strictly longer announcement cannot fire first") is helped rather than threatened. No
bound in the repo is at risk from what was measured.

**What would close it.** Two halves, and the second is the one with teeth. The sentence in the
grace margin addendum comes down to what is true, which needs the mechanism named rather than
guessed at: the readings above were taken from grpc-python's client, and the difference was not
traced to the encoder, to the server's receipt-time stamping, or to both. And the shipped plan's
own announced values, which are what the sentence actually claims zero for, were never among the
three measured; measuring those is what says whether the claim is wrong about this seam or only
about the numbers a probe happened to pick.

## Trail

- 2026-08-22: opened by the close of the three abandonment reading entries. Recorded in the
  ADR-0024 addendum dated the same day.
