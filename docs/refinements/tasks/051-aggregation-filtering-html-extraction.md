# Multi-server aggregation, advertised-tool filtering, and HTML extraction

**Status:** landed 2026-07-03
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Multi-server aggregation, advertised-tool filtering, and readable-text-from-HTML extraction,
recorded in the ADR-0009 refinements addendum, with `AggregateToolRegistry`/`FilteredToolRegistry`
in the core, `CORTEX_TOOLS_ENDPOINTS__<name>` config, `html_to_text` in the email sidecar.

These three have no bullet of their own in the area doc. They were recorded together in its lead
paragraph on the tools of Slice 6, beside the partial-degradation policy for the aggregate.
