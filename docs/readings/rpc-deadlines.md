# Readings: call deadlines on the wire

What a deadline on the body to brain link does between tonic, grpc-python and the host's network
stack. Cited by [ADR-0024](../adr/ADR-0024-transport-retry.md), decisions 14, 15, 16 and 24.

## tonic's own expiry

**2026-08-18.** A raw `BrainServiceClient` given a `Request::set_timeout` against the hanging fake
brain (`Script::Hanging`, which accepts the connection and never replies). The status contains the
originating `tonic::transport::Error` on its source chain, so the adapter classifies it
`TransportError::Connection`, which is in the retryable set:

```
PROBE code=Cancelled msg="Timeout expired" elapsed=81.302086ms has_transport_source=true chain=["transport error", "Timeout expired"]
```

`Request::set_timeout` only inserts the `grpc-timeout` metadata (`tonic/src/request.rs`); the
channel's `GrpcTimeout` layer parses the header back off the outgoing request and starts the local
clock from it (`tonic/src/transport/service/grpc_timeout.rs`). Method: now a permanent check,
`tonics_own_expired_timeout_classifies_as_a_retryable_connection_failure`
(`body/crates/rpc/tests/client.rs`).

## An announced deadline, end to end

**2026-08-19.** A real `grpc.aio` `BrainService` on loopback whose `ListSessions` sleeps for twenty
seconds, driven from a real `BrainSeamClient` enforcing 800 ms and announcing 1.05 s. Both ends:

```
PROBE elapsed=801.000257ms error=Timeout { after: 800ms } announced=Some(1.05s)
{"time_remaining": 1.0484976768493652, "cancelled_after": 0.8001443940156605}
```

The header reaches grpc-python as a real deadline; the body's clock won by the grace margin, the
failure arriving as `Timeout` rather than as tonic's `Connection` at the announcement; and the
handler was cancelled at the moment the body dropped the call, since `grpc.aio` turns the client's
stream reset into an `asyncio` cancellation of the servicer coroutine. Method: a throwaway probe;
the header value is asserted by `an_announcing_client_tells_the_brain_each_call_s_own_deadline`.

## How each client writes `grpc-timeout`

**2026-08-25.** A loopback `grpc.aio` `BrainService` run under `GRPC_TRACE=all`, so its HPACK
parser prints each header as received, driven from grpc-python's own client with `timeout=`:

| `timeout=` | `grpc-timeout` as the server received it | excess |
| --- | --- | --- |
| 0.2 s | `201ms` | 1 ms |
| 0.25 s | `251ms` | 1 ms |
| 0.5 s | `501ms` | 1 ms |
| 1.05 s | `1060ms` | 10 ms |
| 3.0 s | `3010ms` | 10 ms |
| 5.25 s | `5260ms` | 10 ms |
| 10 s | `10100ms` | 100 ms |
| 30 s | `30100ms` | 100 ms |
| 99 s | `99100ms` | 100 ms |
| 120 s | `121000ms` | 1000 ms |

grpc-python rounds **up** onto a ladder whose step is 1 ms below a second, 10 ms up to ten seconds,
100 ms up to a hundred and a second beyond. The excess is at most one step and not constant: the
encoder uses the time left when it runs, so a deadline already past a step boundary by then is
encoded one step lower (the same 1.05 s read `1060ms` idle and `1050ms` traced). The server's
`time_remaining()` at handler entry was always a fraction of a millisecond below the header, never
above it.

tonic truncates instead, onto the most precise unit whose count fits in eight digits
(`duration_to_grpc_timeout`, `tonic-0.14.6/src/request.rs`): nanoseconds below 0.1 s,
microseconds below 100 s, milliseconds up to 99,999,999 ms (about 27.8 hours), whole seconds past
that. The millisecond rung is read off `Request::set_timeout` itself by
`an_announcement_off_the_millisecond_rung_is_dropped_and_one_on_it_is_sent`
(`body/crates/rpc/tests/client.rs`), so a ladder that moves under a version bump fails that check.

## The shipped announcements against a grpc-python brain

**2026-08-25.** The loopback `grpc.aio` server dialed by the repo's own `BrainSeamClient`
announcing `RetryPlan::default()`: twenty warm rounds of a probe and a read, idle.

| Announced | Header the brain received | Window at handler entry | Readings above the announcement |
| --- | --- | --- | --- |
| 500 ms | `500ms` | 0.498910 s to 0.499821 s | 0 of 20 |
| 5.25 s | `5250ms` | 5.248842 s to 5.249842 s | 0 of 19 |

The encoding is lossless for both. The brain's window is 0.16 ms to 1.16 ms shorter than the
announcement (the loopback round trip plus the header parse), under half a percent of the
grace margin at most, and never longer. Method: a throwaway probe.

## A dead address on a mirrored-networking host

**2026-08-25.** On a WSL host in mirrored networking mode, a dial to `127.0.0.1:1` does not
refuse: it waits out the caller's own clock (2001.9, 2000.6 and 2001.5 ms against a 2 s socket
timeout). Port 45999, inside the distro's ephemeral range (44620 to 48715,
`/proc/sys/net/ipv4/ip_local_port_range`), refuses in 0.3 ms, while ports 1, 2, 7, 9, 79, 1023,
1024, 1234, 8099 and 65000 all hang. The reading that fits: the Linux stack answers for the ports
it owns and the Windows host is handed the rest, where nothing answers a SYN to a closed port.

On that host the probe against `127.0.0.1:1` answers at its first attempt's deadline (251.4 to
251.6 ms against a 250 ms deadline, one attempt), and a probe over a bare client with no deadline
waited until the kernel stopped retransmitting: the live suite took about twenty times as long with
that check pointed at the dead address as after it moved to a peer the suite owns (133.54 s
against 6.41 s). With 48 busy loops on 24 cores, twice oversubscribed, the counted check moved by
under one percent (6.46, 6.45 and 6.45 s). Method: a raw socket probe per port, and
`cargo test -p body-rpc --test live -- --ignored` against a brain served with a token.
