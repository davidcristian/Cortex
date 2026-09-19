# Readings: the time an abandoned call had left

What `context.time_remaining()` reads when `grpc.aio` cancels a unary handler, for each way a call
ends. Cited by [ADR-0061](../adr/ADR-0061-abandoned-call-line.md), decisions 2 and 5, and by
[ADR-0024](../adr/ADR-0024-transport-retry.md), decision 15, for the widest racing sliver.

## Four ways a call ends, under load

**2026-08-22.** Each scenario replayed 200 times against a real loopback `grpc.aio` `BrainService`
built by `create_server`, whose store never returns.

| Scenario | Readings | Spread |
| --- | --- | --- |
| both clocks set: the client's `timeout=` on the deadline it announced | 178 integer `0`, 22 positive floats | slivers 0.00037 s to 0.0107 s, median 0.0036 s, against a 0.2 s announcement |
| the brain's clock alone: `grpc-timeout` sent as metadata, no `timeout=` | 200 integer `0`, no floats | no sliver at any replay |
| the caller stops early: announce 10 s, cancel once the handler is entered | 200 floats, no integers | 9.9789 s to 10.0993 s |
| no deadline announced, cancel once the handler is entered | 200 `None` | not applicable |

An earlier run the same hour under the busy loops alone read 171 integer `0` and 29 slivers in the
two-clock scenario, widest 0.0076 s. Across both runs that is 400 two-clock replays with 51 slivers,
about one in eight, and the widest is about a nineteenth of the 0.2 s window, a ninth of the
half-window bound the two-clock case asserts. Idle, every two-clock reading was an integer `0`
(20 of 20, 2026-08-21).

41 of the 200 early-stop readings were above the 10 s the client announced. That is the grpc-python
client's encoder rounding the header up (a `timeout=10.0` crosses as `10100ms`, see [deadlines on
the wire](rpc-deadlines.md)), minus the transit the server subtracts; the body's tonic client never
produces it.

Method: load of 48 busy shell loops on a 24-core machine, twice oversubscribed, with a full brain
`pytest` run restarted in a loop beside them (load average 45 to 49); the scenarios are the four
wire cases in `brain/packages/orchestrator/tests/test_abandon.py`, replayed by a throwaway driver.
The whole suite, run 40 times one process each under the same load, did not fail.
