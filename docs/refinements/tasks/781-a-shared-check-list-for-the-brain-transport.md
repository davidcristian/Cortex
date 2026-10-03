# A shared check list for the brain transport

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Verified:** 2026-10-03

`BrainTransport` in `body/crates/core/src/transport.rs` is the body's client port to the brain,
eleven methods from `health` to `set_preference`. Its shared list, `body_contract::transport`,
covers every method but `converse` through `Calls`, a dyn-compatible twin of the port (ADR-0068
decision 14). It runs over `FakeTransport` in `core/tests/transport.rs`, over `RetryingTransport`
wrapping that fake, and over `BrainRpcClient` on the one scripted `BrainService` in
`rpc/tests/brain/mod.rs`. What remains:

- **`converse`**: a twin method that boxes the decision stream it takes and the event stream it
  returns, and a subject condition per turn script the checks need. The turn's mapping is checked
  today by `rpc/tests/converse.rs` over the shared `BrainService`, and by one core test of
  `FakeTransport`'s scripted turn.
- **The other test transports**, `ScriptedTransport`, `FlakyTransport` and `StallingTransport`,
  each misbehave in one way for one suite, and whether they run the list is open.
- When `converse` is listed, `FakeTransport` moves into `body/crates/contract`, as ADR-0068
  decision 11 says of a port's fake.

## History

- 2026-10-03: Filed from [R-018](018-ports-without-contract-suite.md) when the `AudioControl`
  list fixed the shape of a Rust list, because this port cannot take that shape as it is.
