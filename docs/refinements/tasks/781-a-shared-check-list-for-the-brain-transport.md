# A shared check list for the brain transport

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Verified:** 2026-10-03

`BrainTransport` in `body/crates/core/src/transport.rs` is the body's client port to the brain,
eleven methods from `health` to `set_preference`. It has no shared check list. Its four test
implementations each live in one suite and promise only what that suite needs: `FakeTransport`
in `core/tests/transport.rs`, `ScriptedTransport` in `core/tests/link.rs`, `FlakyTransport` in
`core/tests/retry.rs` and `StallingTransport` in `core/tests/retry_gap.rs`. The adapters are
`BrainRpcClient`, tested over a loopback fake `BrainService` that is itself written twice, as
`FakeBrain` in both `rpc/tests/client.rs` and `rpc/tests/converse.rs`, and `RetryingTransport`,
which wraps any transport.

The OS ports' lists are tables of plain functions over trait objects, which is what keeps each
check one coverage record (ADR-0068 decision 11). That shape does not fit here: ten methods
return `impl Future` and `converse` takes and returns `impl Stream`, so `dyn BrainTransport` does
not compile.
The list needs a subject that hands each check a boxed, object-safe view of the transport, or an
object-safe twin trait the checks call, and the choice decides how much of each method's error
mapping the list can state. The first slice is the read methods (`health`, `list_sessions`,
`session_messages`) over `FakeTransport` and over `BrainRpcClient` on the loopback server, with the
two `FakeBrain` copies reduced to one.

## History

- 2026-10-03: Filed from [R-018](018-ports-without-contract-suite.md) when the `AudioControl`
  list fixed the shape of a Rust list, because this port cannot take that shape as it is.
