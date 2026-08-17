# A per-attempt deadline on the body-to-brain seam

**Status:** open, actionable
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)

Nothing on the body's side of this seam sets a gRPC deadline: no `Endpoint::timeout`, no
per-request timeout, and no wall-clock around the call. Every resilience the retry work built
bounds the *waiting between* attempts and never an attempt itself, so the whole design assumes a
brain that answers or fails, and has nothing to say about one that accepts the connection and
then goes quiet. A hung `health` future is the case that matters, because the connection
indicator renders that probe's answer: `RetryPlan::probe_budget` was built precisely so raising
the reads' knobs could not make the dot claim a state the seam stopped proving, and it sums
`RetryPolicy::delay` values, so a probe that never returns is a lie the budget cannot bound. The
origin decision's own consequence, that `Down` arrives within `probe_budget` of the probe
starting, holds only for a brain that answers.

What it needs is a deadline expressed as a property of the call rather than a timer bolted onto
the shell: a duration on `RetryPlan` beside `probe_budget` (the probe's and the reads' honest
answers differ again here, the same way their patience does), applied by the adapter as a request
timeout, with the resulting status classified. That last part is the interesting half and the
reason this was not folded into the code-table decline: a deadline is the one thing that *creates*
a `DEADLINE_EXCEEDED` producer on this seam, and a deadline that is then retried is the classic
load amplifier, so the two decisions have to be made together rather than one inheriting the
other's default.

## Trail

- 2026-08-17: opened as the residue of the retryable-code table
  ([022](022-retryable-code-table.md)), which declined `DEADLINE_EXCEEDED` on the ground that
  nothing sets a deadline and found, in checking it, that the absence is itself the gap. Verified
  by reading `body/crates/rpc/src/` and the shell's `link.rs` and `seam.rs`: the only durations
  either spends are the retry knobs.
