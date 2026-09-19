# Taint and provenance across a mid-turn swap

**Status:** done 2026-07-17
**Area:** untrusted-content
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Taint used to be turn-local and rebuilt from scratch, so a model swap in the middle of a turn
lost it. The brain-handoff record ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 2)
now stores the whole ledger rather than just the bit.

The frozen `HandoffRecord` in `cortex_core/handoff.py` serializes `tainted`, the ordered
ADR-0027 `sources` (attested and claimed kinds alike, already sanitized when `Provenance` was
built) and the ADR-0015 `untrusted_urls` evidence, beside the escalation brief, the turn's fence
nonce, the dispatch-budget position and the tool-loop tail. It sits behind the `HandoffStore`
port (`put`, `get`, `transition`, `delete`, `active`), with an in-memory fake and the Redis
adapter in `cortex_session/handoffs.py` passing one contract suite. A live record has no TTL so
boot recovery can find it; a terminal one expires after an hour.

A ledger built through the real `TaintLedger` API comes back from the store with the same bits,
the same order and the same set through `HandoffRecord.taint_ledger()`, and claimed sources stay
claimed. Dropping `sources` or `untrusted_urls` from the codec, or dropping the ledger copy from
the slot snapshot, each makes that test fail. It was also observed live against the compose
Redis.

The entry had expected provenance to travel on the stored `Role.TOOL` messages. It travels
beside them as the serialized ledger instead, because the brain phase needs the ledger whole
rather than rebuilt message by message.

## History

- 2026-07-17: Closed with the brain-handoff record's schema. The conductor sub-slice used that
  schema across a swap the same day: the deep model's phase rebuilds the ledger from the record,
  so a tainted turn stays tainted and the output guardrail runs over the URL evidence the cortex
  collected.
