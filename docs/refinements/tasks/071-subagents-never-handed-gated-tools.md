# Subagents are never handed a gated tool

**Status:** landed 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Subagents are never *handed* a gated/outbound tool, ahead of the Slice 9-10 need, recorded as the
[ADR-0013 subagent-exclusion addendum](../../adr/ADR-0013-untrusted-content.md). Structural, no
longer wiring discipline: `UngatedToolRegistry` (core) strips gated specs from advertisement and
rejects a call to one (live walk, fail closed); `build_subagent_tools` wraps the shared registry in
it before the subagent dispatcher. A jailbroken small subagent (framing is unreliable on the small
tier) has nothing dangerous to call, not merely a gate denial.
