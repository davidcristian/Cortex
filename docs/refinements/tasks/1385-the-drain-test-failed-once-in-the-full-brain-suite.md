# The drain test failed once in the full brain suite

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [brain orchestrator](../../modules/brain-orchestrator.md)
**Verified:** 2026-11-28

`test_a_turn_that_ends_within_the_drain_is_stored_whole` in
`brain/packages/orchestrator/tests/test_server_shutdown.py` failed in one of three full `just check`
runs on 2026-11-28, all on the same pytest-randomly seed (9973) and the same brain sources. The
stream ended with `StatusCode.UNAVAILABLE`, `GOAWAY received; Error code: 0; Debug Text: Server
shutdown`, before `turn_complete`. Five runs of that test file alone passed.

The test passes `drain_s=60.0` to `serve`, and its backend pauses 0.5 s between two chunks. `_stop`
in `cortex_orchestrator/server.py` calls `server.stop(grace=5.0)`, and gRPC cancels every call
still open when that grace ends, so the bound the test depends on is the 5 s grace and not its 60 s
drain. A turn that needs about half a second should finish well inside 5 s, so the cause is not
known. The first step is to reproduce it: run the brain suite at least ten times, half of them
beside a second suite that loads every core, count the failures, and record in each one the time
from the signal to the reset. A reset near 5 s points at the grace; one well under it does not.

## History

- 2026-11-28: filed from the pre-commit run of the micro-batch test's commit, where this test was
  the one failure of 14,585; the commit's next run passed.
