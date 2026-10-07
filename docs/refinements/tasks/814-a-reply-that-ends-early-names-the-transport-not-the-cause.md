# A reply that ends early names the transport, not the cause

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 2
**Trigger:** a History line in this file recording the maintainer's pick of the wording and of the
stopped reply's look.
**Verified:** 2026-10-07

Three replies that end before the brain finishes show text that does not tell a person what
happened ([readings](../../readings/overlay-turn-flows.md)):

- A brain that dies during a reply ends it with the tonic status verbatim,
  `Unknown: h2 protocol error: error reading a body from connection`, which `WireError::from` in
  `body/app/src-tauri/src/converse.rs` passes through as `{code}: {message}`.
- A turn sent while the brain is down ends with `no reply within 5s` when the dial times out, as it
  does on this machine, though no question reached the brain. A dial that is refused, which this
  machine does not produce, would show the connection error's own text instead.
- A Stop before any text leaves an empty reply bubble under `Thoughts`.

## Proposal

- **The words** (recommended): one sentence per `TransportError` kind, chosen in the overlay from
  the `kind` field the wire already has, with the detail kept for the dot's tooltip. For example
  "The brain stopped answering partway through." for an `rpc` or `protocol` error after text,
  "The brain could not be reached." for a `connection` error or a timeout before any event, and
  the timeout's own sentence otherwise.
- **The empty stopped reply**: drop the bubble, or show a dimmed "Stopped" in it.

## History

- 2026-10-07: filed from the outage and Stop flows on the Linux shell.
