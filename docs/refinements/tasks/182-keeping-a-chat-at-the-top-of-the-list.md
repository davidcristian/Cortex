# Keeping a chat at the top of the list

**Status:** done 2026-07-16
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

A `SessionStore.set_hoisted` write and a `hoisted` field on `SessionSummary` across the wire and all
four trees, but the real cost was a read-path decision: whether a hoisted chat escapes the recency
`ZREVRANGE` window and so has to be merged into the listing.

It does. `list_sessions` merges the hoisted set into every listing. Round trip one reads both
indexes in one transaction (`ZREVRANGE` for the recency window and `SMEMBERS` for the new
`cortex:sessions:hoisted` set), their union is the listed set (recency window first, then the
hoisted ids outside it, deduplicated), and round trip two is the same batched ends-read, so it stays
two round trips and two decoded records per chat. A new pure-core `merge_hoisted` is the one
ordering rule (stable-sort by recency, then by not being hoisted, so hoisted chats sort above the
recency group, newest first within each), and both the fake and the Redis adapter build the same
deduplicated candidate set and hand it there.

Three costs the "one write plus one field" framing hid: the union is additive, so a catalog with
many hoisted chats lists more than `limit`; `delete` must also `SREM` the member, or a deleted id
lingers; and `set_hoisted` takes `*, hoisted` keyword-only, per the repo's boolean-argument
convention.

`SetSessionHoisted` is protected by the same structural user-only reachability as rename and delete:
no tool, never through the turn engine. Its `SeamMethod` is classified not repeatable despite being
idempotent by value, because the convention is uniform and a lost reply must not re-assert a value
the user's next toggle reversed.

The overlay adds a per-row toggle, re-lists after the write so the group re-forms at the top, and
reads the one order everywhere (switcher, cycling, and cold-start adoption, which now adopts the
top hoisted chat when there is one).

Checked live against Docker and real Redis: four chats seeded with an old one hoisted and a
`limit=3` listing returned that old chat first, above the three newer chats, exactly once.

## History

- 2026-07-16: Closed end to end, the last of the three catalog-write entries and the one whose
  central question the entry named exactly. It opened nothing behind it.
