# A shared check list for the brain transport

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Verified:** 2026-10-03

`BrainTransport` in `body/crates/core/src/transport.rs` is the body's client port to the brain,
eleven methods from `health` to `set_preference`. Its shared list, `body_contract::transport`,
covers the three read calls (`health`, `list_sessions`, `session_messages`) through `Reads`, a
dyn-compatible twin of the port (ADR-0068 decision 14). It runs over `FakeTransport` in
`core/tests/transport.rs` and over `BrainRpcClient` on the one scripted `BrainService` in
`rpc/tests/brain/mod.rs`. What remains, call by call:

- **The reminder calls**, `list_due_reminders` and `ack_reminder`: `Held` gains the due
  reminders, and an ack answers whether it cleared the fire it names.
- **The chat writes**, `rename_session`, `delete_session` and `set_session_hoisted`, each checked
  by the listing after it. The scripted `BrainService` and `FakeTransport` record a write today
  rather than apply it, so both need to hold their chats where a write can change them.
- **The settings**, `get_preferences` and `set_preference`, the same way: a written key read back,
  and an empty value clearing the key.
- **`converse`**, whose twin method boxes the decision stream it takes and the event stream it
  returns, with the turn's scripts in the shared `BrainService` as the conditions.
- **`RetryingTransport`** as a subject over `FakeTransport`. The other test transports
  (`ScriptedTransport`, `FlakyTransport`, `StallingTransport`) each misbehave in one way for one
  suite, and whether they run the list is open.
- When every call is listed, `FakeTransport` moves into `body/crates/contract`, as ADR-0068
  decision 11 says of a port's fake.

## History

- 2026-10-03: Filed from [R-018](018-ports-without-contract-suite.md) when the `AudioControl`
  list fixed the shape of a Rust list, because this port cannot take that shape as it is.
