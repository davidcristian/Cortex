# The subagent-side confirm-set check

**Status:** done 2026-07-12
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Recorded at [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 8. `build_subagents`
now receives its dispatcher already assembled: the composition root calls
`build_subagent_tools(tool_registry, clock, gated_names=CORTEX_TOOLS_GATED)` and passes the result,
which also avoids a seventh argument tripping the PLR0913 limit. The user's confirm set now covers
subagents exactly as it covers the cortex and the ticker, closing the skip-mode double-walk window.
`UngatedToolRegistry` (strip plus live-walk refusal) and `confirmer=None` stay as the structural
layers beneath it.

## History

- 2026-07-12: Closed with the shared confirm set.
