# No test checks that the brain gives schedule_task the session store

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Verified:** 2026-10-29

`run_from_env` (`wiring.py`) passes `sessions=stores.sessions` to `build_schedule_tools`, which
`schedule_task` needs to clear a chat deleted while its add ran. With that argument removed, the
whole orchestrator suite still passed (825 tests on 2026-10-29), because no test runs
`run_from_env` with the schedule backend on and makes a `schedule_task` call. The builder and the
tool are each tested over fakes.

## What to do

1. Add a wiring test in the pattern of `test_swap_wiring.py` (fakeredis behind `Redis.from_url`,
   `CORTEX_SCHEDULE_BACKEND=redis`) that records the tools `build_schedule_tools` returns and checks
   a `schedule_task` add in a deleted chat stores an empty `session_id`.

## History

- 2026-10-29: filed from the build of the deleted chat check after a schedule add.
