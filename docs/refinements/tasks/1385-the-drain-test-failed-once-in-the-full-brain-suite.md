# The drain test failed once in the full brain suite

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [brain orchestrator](../../modules/brain-orchestrator.md)
**Verified:** 2026-11-28

`test_a_turn_that_ends_within_the_drain_is_stored_whole` in
`brain/packages/orchestrator/tests/test_server_shutdown.py` failed in one of three full `just check`
runs on 2026-11-28, all on the brain suite's fixed pytest-randomly seed (9973) and the same brain
sources. The client's read failed before `turn_complete` with `StatusCode.UNAVAILABLE` and the
details `Stream removed (recvmsg:Connection reset by peer (GOAWAY received; Error code: 0; Debug
Text: Server shutdown))`. The log of that run is `~/.cache/cortex-run/2026-11-28/c0/gc1.log`.

## What the failure shows

- The client's socket read returned a TCP reset. The last GOAWAY the client had received was the
  one gRPC sends when `server.stop` begins: error code 0, `Server shutdown`.
- The 5 s grace in `_stop` did not end the call. When a grace ends, gRPC cancels the open calls
  and sends a second GOAWAY with error code 2 and `Cancelling all calls`, which gRPC logs on the
  client as `Got goaway [2]`. That log shows the line for three other tests and none beside the
  failing one.
- The signal reaches the right server. In every probed suite run below, the `SIGTERM` handler at
  the signal was the running loop's own and two threads were alive.
- In every probed run the client read `turn_complete` between 0.47 and 0.60 s after the signal,
  and the server's stop ended no more than 1 ms after that read. That is the backend's 0.5 s
  pause, about a tenth of the grace.

## Reproduction runs

Each probed run wrote the time from the signal to each event, to the stream's end and to the end
of the server's stop. A run loses the stream's end when the stream fails or ends before
`turn_complete`.

| Condition | Runs | Lost the end |
| --- | --- | --- |
| brain suite on its seed, nothing beside it | 5 | 0 |
| brain suite on its seed, beside two spinning processes per core | 5 | 0 |
| the scenario alone in one process, repeated, nothing beside it | 20 | 0 |
| the same, beside two spinning processes per core | 300 | 0 |
| the same, four processes at once beside the spinning processes | 600 | 0 |
| the same, on two CPUs shared with eight spinning processes | 150 | 0 |
| the same, beside `just check-body` | 40 | 0 |

The scripts and records are in `~/.cache/cortex-run/2026-11-28/c3/`.

## The likely cause, not yet shown

This is an assumption. gRPC closes the server's connection as soon as its last call ends, which
the stop ending within 1 ms of the client's last read agrees with. A socket closed while the
client's later frames, such as a window update or a ping reply, are still unread sends a reset
instead of a normal close, and the kernel then drops what the server wrote but had not yet
transmitted: here the last events and the trailers. On loopback that needs the transmit to be
deferred, which a starved CPU causes, as the parallel Rust build and coverage of `just check` do.
If this holds, the brain cannot prevent it through the grpc.aio API, and a real client could lose
the end of a turn that the store keeps whole.

## Next step

Reproduce it in the condition it came from: full `just check` runs with the probe scripts in the
directory above applied, until one fails or twenty pass, recording the time from the signal to
the reset. A reset near 0.5 s confirms the close above, and a reset near 5 s points back at the
grace. Then decide whether the test reads the end of the stream from the brain's side instead of
the client's, and whether the body shows `UNAVAILABLE` after a `Server shutdown` GOAWAY as a stop.

## History

- 2026-11-28: filed from the pre-commit run of the micro-batch test's commit, where this test was
  the one failure of 14,585; the commit's next run passed.
- 2026-11-28: not reproduced in 1,120 probed runs. The failure's own text rules out the grace,
  and the probed suite runs found no other test's signal handler at the signal.
