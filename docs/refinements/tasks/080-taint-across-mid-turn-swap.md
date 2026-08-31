# Taint and provenance across a mid-turn swap

**Status:** landed 2026-07-17
**Area:** untrusted-content
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The vehicle is the brain-handoff record's schema
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 2, the record sub-slice).
The schema this entry flagged for now exists and carries the WHOLE ledger, not just the bit: the
frozen `HandoffRecord` (`cortex_core/handoff.py`) serializes `tainted`, the ordered ADR-0027
`sources` (attested and claimed kinds alike, values already sanitized at `Provenance`
construction), and the ADR-0015 `untrusted_urls` laundering evidence, beside the escalation
brief, the turn's fence nonce, the dispatch-budget position, and the never-persisted tool-loop
tail (the stored `Role.TOOL` messages this entry predicted provenance would ride). It lives
behind the new `HandoffStore` port (`put`/`get`/`transition`/`delete`/`active`, with an
in-memory fake and the Redis adapter in `cortex_session/handoffs.py` passing one contract
suite; a live record carries no TTL so boot recovery can find it, terminal ones expire after a
diagnosis hour). The central check is the pinned round trip the ADR named: a ledger built
through the real `TaintLedger` API comes back from the store bit-, order-, and set-exact via
`HandoffRecord.taint_ledger()` (claimed sources still claimed, kinds intact), mutation-proven
(dropping `sources` or `untrusted_urls` from the codec, or the ledger copy from the slot
snapshot, each makes it fail) and observed live against the compose Redis. One correction to the
entry's guess: provenance rides the record *beside* the tail as the serialized ledger, not "on
the stored `Role.TOOL` messages" themselves, since the brain phase needs the ledger whole
rather than re-derived per message. Honest residue, held by the entries that already own it:
nothing writes a record mid-turn yet (the escalate tool and the conductor are the ADR's later
sub-slices, where the live cross-swap exercise arrives), and the harness-run entry below stays
open. *Original deferred entry, kept verbatim as the historical record:* "**Persisting taint /
provenance across a mid-turn swap.** Taint is turn-local and reconstructed; once **Slice 11**
serializes the tool-step context, provenance rides on the stored `Role.TOOL` messages. Flagged
for that schema. Structured provenance beyond the binary (source URI, sender) joins here if
the confirmation UI needs to display a source."

## Trail

- 2026-07-17: Landed as the brain-handoff record's schema and took the area's count from 14 to
  13. The conductor sub-slice exercised that schema across a swap the same day: the deep
  model's phase rebuilds the ledger from the record, so a tainted turn stays tainted and the
  output guardrail opens over the URL evidence the cortex collected, mutation-proven.
