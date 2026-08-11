# Screening subagent for external content

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Trigger:** unrecorded

A small subagent that pre-screens external content for injection
markers before the cortex sees it. Mostly moot: the GPU validation showed a screener would be
another small, equally-injectable model. Kept only as a last-resort option behind the delegation seam.
