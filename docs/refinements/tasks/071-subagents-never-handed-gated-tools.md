# Subagents are never given a tool that needs approval

**Status:** done 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

A subagent is never given a tool that reaches outside and needs the user's approval, which is
structural rather than a matter of wiring discipline. `UngatedToolRegistry` in the core removes
those specs from what is advertised and rejects a call to one, walking the live listing and
failing closed, and `build_subagent_tools` wraps the shared registry in it before the subagent
dispatcher. A jailbroken small subagent, where framing is unreliable, therefore has nothing
dangerous to call, rather than being denied after asking. Recorded as
[ADR-0013 decision 9](../../adr/ADR-0013-untrusted-content.md).
