# Readings: a forget whose message asks to keep a fact

How `unnamed` (`forget_unnamed.py`) reads a forget message that names a fact to keep, such as
`Forget my bike lock code 7319, keep the shed padlock one.`, when two stored rows share the call's
value. The rows and the reader before this change are in
[forget-shared-number.md](forget-shared-number.md#audit-probes-of-the-keep-reader-2026-11-09).
The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## The reader before, 2026-11-09

Unit calls over a bike lock row and a shed padlock row, both holding 7319, with the call text
7319. The reader read every word of the message as naming a fact to forget, so a word of a clause
asking to keep named that row too, and the card listed it. Each of these kept no row:
`Forget my bike lock code 7319, keep the shed padlock one.`,
`Forget my bike lock code 7319 but not the shed one.` and
`Forget my bike lock code, not the shed one.`. `Forget 7319, keep the shed one.` kept the bike
row and listed the shed row, the reverse of the request.

## The reader now

A clause asks to keep from a keep verb that no negation precedes within two words (`keep`,
`garde`, `behalte`, `guarda`, `păstrează` and their forms), or from a negation such as `not`,
`n't`, `pas`, `nicht`, `no` or `nu` that opens the clause or follows `but`, `and`, `is`, `mais`, `aber`,
`pero` or `dar`, unless a keep verb follows it. The clause ends at its mark or at a forget verb
that no negation precedes, so `don't forget the shed one` keeps the shed row. A word of such a
clause, other than the keep verb, names a fact to keep unless the message also names it outside
one. A matched row naming a fact to keep is listed under `KEPT_LINE` and kept, even beside a word
to forget or a word for all, and even when it holds the value only in its reply. The other words
decide the rest as before.

Near misses, each still reading its words as facts to forget: `the not so new shed padlock code`
(a negation inside a label), `Don't keep my bike lock code 7319.`, `Do not keep ...`,
`Ne garde pas ...`, `I keep forgetting it, forget my bike lock code 7319.` and `keep everything
else` (a keep clause naming no fact). The tests are `test_forget_keep_clause.py`.

## Replay, 2026-11-09

Every distinct string of `docs/readings/` holding a forget verb (1,710) went through the old and
new reader over seven rows holding the string's value (six other chats' rows and one of the
calling chat), with and without the calling chat's row: 16 cases changed, all prose that holds
`keep`, `kept`, `keeps` or `don't`, and no recorded draw message. Each changed case keeps at
least one more row. In two of them, with the calling chat's row, that row is now listed: the words
naming the shed row are in a keep clause, so no word names a fact to forget and the newest row the
chat stored is read as just said, as `Forget it, but keep the shed padlock code.` asks. Script
`replay.py` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot9/`,
log `replay.log` in the `slot12/` directory beside it. No turn was drawn.
