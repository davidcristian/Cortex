# Agent GPU validation of framing efficacy

**Status:** landed 2026-07-01
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

The run is recorded as an [ADR-0013](../../adr/ADR-0013-untrusted-content.md) addendum.
The agent ran it on the host GPU via Docker (gemma-4-12B): the framed model cites the shipped
`SECURITY_PREAMBLE` in its reasoning to defeat seven injection variants; the gate is the
deterministic backstop. Re-runnable per the [runbook](../../runbooks/llamacpp-gpu.md).
