# Session pinning

**Status:** landed 2026-07-16
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

A new `SessionStore.set_pinned` verb plus a `pinned` field on `SessionSummary`
across the wire and all four trees, but the real cost is a **read-path** decision the bounded
two-round-trip listing does not answer: whether a pinned chat escapes the recency `ZREVRANGE`
window (the expected UX) and so must be unioned into the listing, reshaping the tuned
`list_sessions`. A genuine design change, not a drop-in behind the write verb, which is why it did
not ride the rename that landed 2026-07-16.
**Landed 2026-07-16 ([ADR-0021 pinning addendum](../../adr/ADR-0021-session-read-seam.md)), and the
entry named its own crux exactly: the read-path union was the whole item.** A pinned chat DOES
escape the recency window, so `list_sessions` unions the pinned set into every listing. The tuned
two-round-trip shape held: round trip one now reads BOTH indexes in one transaction (`ZREVRANGE`
the recency window AND `SMEMBERS` a new pinned set `cortex:sessions:pinned`), their union
(recency window first, then pinned ids outside it, deduplicated) is the listed set, and round trip
two is the same batched ends-read, so it stays two round trips and two decoded records per chat.
A new pure-core `merge_pinned` is the one shared ordering rule (stable-sort recency then
`not pinned`, so pinned chats sort above the recency group, newest-active first within each), and
both the fake and the Redis adapter build the same deduplicated candidate set and hand it there,
so they cannot drift. Three costs the "verb + field" framing hid: the union is additive, so a
heavily-pinned catalog lists more than `limit` (bounded by the small pinned set); `delete` must
also `SREM` the pinned member, or a deleted-then-pinned id lingers as a dangling pin; and
`set_pinned` takes `*, pinned` keyword-only (the repo's boolean-arg convention). The write RPC
`SetSessionPinned` has the SAME structural user-only reachability rename/delete got (no tool,
never through the turn engine); its `SeamMethod` is classified **not repeatable** despite being
idempotent by value, because the catalog-write convention is uniform (a lost reply must not
re-assert a pinned value the user's next toggle reversed). The overlay adds a per-row pin toggle
(a filled-pin indicator doubling as the state), re-lists after the write so the pinned group
re-forms at the top, and reads the one pinned-first `sessions` order everywhere (switcher, cycling,
cold-start adoption, which now adopts the top pinned chat when any is pinned). Gated at 100% across
all four trees, with the union mutation-proven: the flagship contract check pins a chat older than
a `limit=3` window and asserts it still lists above the recency group (dropping the union reddens
it), a pinned-and-recent chat is asserted to appear once (dropping the dedup reddens it), and the
user-only path is pinned by a no-tool structural test. Live-validated (agent, Docker + real Redis):
four chats seeded with an old one pinned and a `limit=3` listing returned the pinned old chat
first, above the three newer chats, exactly once.

## Trail

- 2026-07-16: Pinning landed end to end, the last of the three management-verb entries and the
  one whose crux the entry named exactly, and it opened nothing behind it. The area count
  went from 4 to 3.
