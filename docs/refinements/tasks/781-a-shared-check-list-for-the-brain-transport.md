# A shared check list for the brain transport

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Verified:** 2026-10-04

`BrainTransport` in `body/crates/core/src/transport.rs` is the body's client port to the brain,
eleven methods from `health` to `set_preference`. Its shared list, `body_contract::transport`,
covers all eleven through `Calls`, a dyn-compatible twin of the port (ADR-0068 decision 14), with
`converse` taking a boxed `Decisions` stream and returning a boxed `Events` stream. It runs over
`FakeTransport` in `body/crates/contract`, over `RetryingTransport` wrapping that fake, and over
`BrainRpcClient` on the one scripted `BrainService` in `rpc/tests/brain/mod.rs`. What remains is
the confirm round trip. The fake drops the caller's decisions, and the list checks no decision, so
only `rpc/tests/converse.rs` shows one reaching the brain. Listing it needs a brain behavior both
fakes share after a `ConfirmRequest` in the held reply (wait for the decision naming it, then show
which it was), and a decision stream the check feeds in reaction to the request.

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
