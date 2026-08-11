# Subagent model pick revised to gemma-4-E4B

**Status:** landed 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The revision is recorded as the [ADR-0004 pick-revision addendum](../../adr/ADR-0004-model-lineup.md).
The injection-defense
harness found E4B the standout (0/10 framed-obeyed even thinking-off, re-confirmed at
adoption) vs the old Qwen3.5-2B (1/10, laundering) and gemma-E2B (4/10); the measured CPU
cost (38 s load, ~1.8 s narrow task, ~2.5 GiB RSS) was judged acceptable and the compose
default + admission asks updated. Qwen3.5-2B stays the documented cheap override; **Slice
8.6** still makes the model choice per-task, with E4B as the safe default.
