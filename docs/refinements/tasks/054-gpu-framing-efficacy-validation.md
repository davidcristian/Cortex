# Agent GPU validation of framing efficacy

**Status:** done 2026-07-01
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Run on the host GPU through Docker against gemma-4-12B: the framed model cites the shipped
`SECURITY_PREAMBLE` in its reasoning and defeats seven injection variants. The deterministic
check is what stops an injection when framing does not. The readings are in
[untrusted-framing](../../readings/untrusted-framing.md), and the run repeats per the
[runbook](../../runbooks/llamacpp-gpu.md).
