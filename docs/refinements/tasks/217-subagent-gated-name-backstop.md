# The subagent-side gated-name backstop

**Status:** landed 2026-07-12
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The subagent-side authoritative gated-name backstop is recorded at the
[ADR-0022 addendum](../../adr/ADR-0022-email-write-confirmer.md). `build_subagents` now receives
its dispatcher pre-assembled: the composition root calls
`build_subagent_tools(tool_registry, clock, gated_names=CORTEX_TOOLS_GATED)` and passes the
result (the builtins-bundling precedent, so no 7th arg trips the PLR0913 cap). The user's
gated set covers subagents exactly as it covers the cortex and the ticker, closing the
skip-mode double-walk window; `UngatedToolRegistry` (strip + live-walk refusal) and
`confirmer=None` stay as the structural layers beneath it.
