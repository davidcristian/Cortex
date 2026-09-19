# Structured redaction event for the overlay

**Status:** declined 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Read against the shipped path and declined: the inline marker the guardrail already emits meets
the user's need better than a structured event would.

The marker explains itself and stays in context. A live run of the real `UrlRedactingGuardrail`
turned `Full report at https://evil.example/report for details.` into
`Full report at [link removed: untrusted source] for details.` (`guardrail.py`, `REDACTED_LINK`),
so the user sees that a link was removed, where it stood, and why, with no second channel.

It reaches the overlay as ordinary reply text and renders as written: the engine folds the
scrubbed delta into `TextDelta` (`engine.py`), the orchestrator maps it onto the wire `TextDelta`
(`converse.py`), and the overlay reducer appends delta text into the assistant bubble
unconditionally (`overlayState.ts`, the `delta` case), confirmed live by feeding the exact marker
string through the real reducer.

The marker is also durable where the event would not be. It is part of the stored `full_text`, the
reply on record being equal to the reply shown, so a reloaded chat still shows it (`hydrate`,
`sessionState.ts`). A `StatusUpdate`-shaped event is ephemeral by contract, never stored and
dropped from the status chip when the turn settles, so a redaction badge driven by it would appear
once and vanish.

A safe event could hold only a count, never the URL, since including the removed link would
reopen the channel the guardrail exists to close, and a bare count adds nothing the visible inline
markers do not already show. Its real cost is widening `OutputFilter.feed`: the `OutputFilter`
protocol, both filter policies, the `ThinkingChannel`, the engine feed loop and
`open_output_channels`, all to drive a signal nothing in the overlay reads.

It reopens only if the overlay grows a redaction surface the inline marker cannot serve, such as a
stored count badge or distinct styling, which needs a durable channel designed with its record
rather than the ephemeral status one this entry imagined.

## History

- 2026-07-16: Read against the shipped path and declined. Both halves were observed live, the
  marker in the real guardrail's output and the real overlay reducer rendering it as written.
