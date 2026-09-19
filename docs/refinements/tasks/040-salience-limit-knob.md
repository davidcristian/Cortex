# A configurable limit for the salience policy

**Status:** done 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Recorded inside [R-039](039-salience-on-the-tool-loop.md) as one of the things left behind it: a
way to configure the limit if two proves wrong. The limit is the one `RepeatSalience` ships, which
admits a call unless an identical one already ran in this round or already ran twice in this loop.

Closed 2026-08-18 as `CORTEX_TOOLS_SALIENCE_LIMIT`, a `ToolsConfig.salience_limit` field
defaulting to the core's `MAX_IDENTICAL_DISPATCHES`, which `salience_policy` uses to build
`RepeatSalience(limit=...)`. It closed without waiting for the trigger, because the trigger was
never what the work needed: the origin decision already named the environment variable and called
it configuration rather than design, the policy's `limit` parameter and its rejection of a
non-positive value already existed, and the only choice a deployment had was binary (`repeat` or
`off`, where `off` removes the bound), so nothing between two and unbounded could be expressed. A
value below 1 now fails at boot. There is deliberately no upper limit, since a large one never
binds and still keeps the once-per-round rule that `off` drops. The compose default is tied to the
core constant in `scripts/couplings.py`. It opened
[R-306](306-subagent-memory-budget-spelled-twice.md).

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired. This is one of
  the entries whose trigger is a deployment doing something rather than a file saying something,
  so no reading of the code settles it.
- 2026-08-18: Closed as `CORTEX_TOOLS_SALIENCE_LIMIT`, without waiting for the trigger, because
  the work needed configuration rather than evidence.
