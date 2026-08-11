# Bounded backpressure on the Converse output queue

**Status:** landed 2026-07-03
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

The per-turn
output queue (`converse.py`) is now credit-bounded (`CORTEX_SEAM_CONVERSE_BUFFER`, default
256): a consumer that stops reading suspends generation at the bound, while the terminal
`SeamError` and teardown bypass the credits so failure never blocks behind a full buffer.
The `Converse` stream contract is unchanged; design in
[brain-orchestrator.md](../../modules/brain-orchestrator.md).
