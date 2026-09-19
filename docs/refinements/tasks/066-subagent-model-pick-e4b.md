# Subagent model pick revised to gemma-4-E4B

**Status:** done 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The injection-defence run found E4B clearly best, at 0 of 10 obeyed when framed even with
thinking off, re-confirmed when it was adopted, against the old Qwen3.5-2B at 1 of 10 with
laundering and gemma-E2B at 4 of 10. Its measured CPU cost, 38 s to load, about 1.8 s for a narrow
task and about 2.5 GiB resident, was judged acceptable, and the compose default and the admission
requests were updated. Qwen3.5-2B stays the documented cheap override, and the model choice is
still per task with E4B as the safe default.
