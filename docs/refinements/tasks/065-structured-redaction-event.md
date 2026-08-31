# Structured redaction event for the overlay

**Status:** declined 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It is recorded as an [ADR-0015](../../adr/ADR-0015-output-guardrail.md) addendum.
Read against the shipped path,
the inline marker the guardrail already emits meets the user need a structured event would, and
meets it more durably. **The marker is self-explanatory and in context:** a live run of the real
`UrlRedactingGuardrail` turned `Full report at https://evil.example/report for details.` into
`Full report at [link removed: untrusted source] for details.` (`guardrail.py`, `REDACTED_LINK`),
so the user sees that a link was removed, where it stood, and why (untrusted source), with no
second channel. **It reaches the overlay as ordinary reply text and renders verbatim:** the engine
folds the scrubbed delta into `TextDelta` (`engine.py`), the orchestrator maps it onto the wire
`TextDelta` (`converse.py`), and the overlay reducer appends delta text into the assistant bubble
unconditionally (`overlayState.ts`, the `delta` case), confirmed live by feeding the exact marker
string through the real reducer. **The marker is durable where the event would not be:** it is part
of the persisted `full_text` (the reply on record equals the reply shown, the ADR-0015 invariant),
so a reloaded chat still shows it (`hydrate`, `sessionState.ts`), whereas a `StatusUpdate`-shaped
event is ephemeral by contract (never persisted, and the status chip drops when the turn settles),
so a redaction badge driven by it would flash once and vanish, the same dead-on-reload shape
reasoning persistence was declined for. **A safe event could carry only a count, never the URL:** a
redaction event that included the redacted link would reopen the very channel the guardrail exists
to close, and a bare count adds nothing the visible inline markers do not already show. Its real
cost is the `OutputFilter.feed` port widening (the `OutputFilter` protocol, both filter policies,
the `ThinkingChannel`, the engine feed loop, and `open_output_channels`), all to drive a signal
nothing in the overlay reads. Moved to the index's dead-until-a-consumer list; reopens only if the
overlay grows a redaction surface the inline marker genuinely cannot serve (a persisted count
badge, distinct styling), which needs a durable channel designed with its record rather than the
ephemeral status one this deferral imagined.

## Trail

- 2026-07-16: Read against the shipped path and declined, taking the area's count from 16 to 15.
  Both halves were observed live, the marker in the real guardrail's output and the real overlay
  reducer rendering it verbatim.
