# A shared check list for the brain transport

**Status:** done 2026-10-04
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)

`BrainTransport` in `body/crates/core/src/transport.rs` is the body's client port to the brain,
eleven methods from `health` to `set_preference`. Its shared list, `body_contract::transport`,
covers all eleven through `Calls`, a dyn-compatible twin of the port (ADR-0068 decision 14), with
`converse` taking a boxed `Decisions` stream and returning a boxed `Events` stream. It runs over
`FakeTransport` in `body/crates/contract`, over `RetryingTransport` wrapping that fake, and over
`BrainRpcClient` on the one scripted `BrainService` in `rpc/tests/brain/mod.rs`, a confirm round
trip included.

## History

- 2026-10-03: Filed from [R-018](018-ports-without-contract-suite.md) when the `AudioControl`
  list fixed the shape of a Rust list, because this port cannot take that shape as it is.
- 2026-10-04: Listed `converse` with six checks (the reply in order, the user's words in the
  chat's history, the first terminal event ends the turn, a reply with no completion fails as
  `Protocol`, a refusing and an unreachable brain), and removed the four `rpc/tests/converse.rs`
  tests and the one core turn test that the list now covers. `ScriptedTransport`, `FlakyTransport` and
  `StallingTransport` stay off the list: each is one suite's stub that stands for no brain, as
  ADR-0068 decision 14 now says.
- 2026-10-04: Moved `FakeTransport` into `body/crates/contract`, where it is measured. Its failure
  is now a clone of the error it was built with, since `TransportError` derives `Clone` as the
  other port errors do.
- 2026-10-04: Closed. Two confirm checks list the round trip: after a confirm request both fakes
  answer a decision naming it with the tool's `ToolOutcome`, and anything else with
  `ConfirmResolved` `timeout`. The restated timeout test left `rpc/tests/converse.rs`; a decision
  sent in reaction to the request stays there, since the list feeds its decisions in advance.
