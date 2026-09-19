# Readings: delegated run holds

How long a delegated subtask holds its admission, and how long a queued spawn waits, on a full
batch. Cited by [ADR-0047](../adr/ADR-0047-delegated-run-bound-ordering.md), decision 5.

## A full batch of eight

**2026-08-25.** One `MAX_SPAWN_BATCH` of eight subtasks of the longest shape (summarization, each
over its own report body so no two share a prompt cache), under the 1024-token cap and the 2400 s
deadline, in two regimes on one CPU server: serialized (every spawn on the CPU backend, one stream
at a time) and overlapping (the shipped placer, two backend objects in front of the server's two
slots). `held` is from admission to release, which is what the run deadline bounds and what a
queued peer waits out.

| figure | serialized | overlapping |
| --- | --- | --- |
| whole subtask, server `total time` | 222.8 to 324.3 s | n/a |
| longest hold | 595.2 s | 325.9 s |
| last spawn admitted | 1624.6 s | 893.2 s |
| whole batch | 2096.4 s | 1184.5 s |

Every subtask answered; none was cut at the cap or the deadline. A hold is longer than its subtask
because an admitted spawn queues on its entry's model lease inside its admission. A single
summarization timed on the same machine two weeks earlier took 623.8 s, about twice the slow end
above, so the whole subtask is an interval and a bound derived from it is sized on the slow end.

Against the shipped bounds: the 2400 s deadline is about four times the longest hold, and twice the
serialized last admission is about 3250 s.

Method: one CPU `llama-server` at the subagent compose file's shape (`-ngl 0`, `--ctx-size 8192`,
`--parallel 2`, `--cpus 4.0`, `--memory 8g`) with the shipped gemma-4-E4B entry, driven through the
real spawn tool, runner, scheduler, placer and backend at `CPU_BUDGET=4.0`, `MEM_BUDGET_GB=8.0` and
asks of 2.0, 3.0 and 3.5; times from the scheduler's admit and release. The serial wait is asserted
in `brain/packages/core/tests/test_scheduler.py`.
