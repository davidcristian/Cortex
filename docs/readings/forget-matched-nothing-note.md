# Readings: the note after a forget that matched nothing

A `forget_memories` call whose text no row contains reads `_NONE_FOUND` (`forget_results.py`),
which tells the model to say nothing about it was stored. That is false when a row holds the same
fact in other words: the call text `Fahrradschloss Code 2468` against the row `Fahrradschloss hat
den Code 2468`
([R-1061](../refinements/tasks/1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md)),
or the new number `0699000000` while a row holds the old one
([R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md)).
Over five nights that form came in 0 to 2 of every 24 draws, so no rule written about a fix for one
of its call texts gave a result ([forget-value-held-patch](forget-value-held-patch.md),
[forget-new-value-patch](forget-new-value-patch.md)). This record decides a fix for every call text
at once.

## Rows and the rule, 2026-11-10

Written before any draw. The candidate is `UNMATCHED_FORGET_NOTE` and `unmatched_note_due`
(`forget_unfound_claim.py`): `limit_notes` appends the note when a `forget_memories` call of the
turn matched nothing (`TaintLedger.forget_unmatched`), no call removed a row
(`TaintLedger.forget_deleted`) and no forget run of the turn deleted a memory (`deleted_memory`).
The note says nothing was deleted, that a forget call searched for an exact text no remembered
exchange contains, and that any remembered exchange stating the same fact in other words is still
stored. That is true whether or not such a row exists, so the note needs no guess of what the
person meant, and it reads no reply, so a reply in any language gets it. It names no value and
asks for nothing. The text the model reads in the turn is unchanged, so a base build would send the
same requests and is not drawn.

The rig is the `cortexn18` stack: the candidate is the working tree over `075f41c92`, run as a
second brain through the recording proxy, a new chat for each draw, every card approved. Before
each draw every row of the slot's chats and every row holding the row's number is deleted.

| Row | First turn | Second turn | Draws |
| --- | --- | --- | --- |
| m1 | `Forget my passport number.` | | 4 |
| v1 | `Forget that my phone number is now 0699000000.` | | 3 |
| x7 | `Mein Fahrradschloss hat den Code 2468, merk dir das.` | `Vergiss bitte, was ich dir gerade gesagt habe.` | 3 |
| d1 | `My locker code at the pool is 7319.` | `Forget 7319.` | 2 |

m1 and v1 reach the note's condition on purpose: no row holds what they name. x7 and d1 are the
neighbouring flows, where a forget is expected to delete the row through a card.

A turn **reaches the condition** when a `forget_memories` result in the proxy log is `_NONE_FOUND`
and the turn removed no row (the stores before and after).

- The note ships when at least four turns reach the condition, every turn that reaches it ends with
  the note, no turn in which a forget removed a row has it, and no turn without a `_NONE_FOUND`
  result has it.
- How often the form of R-969 and R-1061 came (a `_NONE_FOUND` call while a row holds the fact),
  and how often a reply said the fact was never stored, are counted besides and decide nothing.
  When the form comes, the turn reaches the condition, so the first item covers it.
- The null result is fewer than four turns reaching the condition: then the rule gives no result
  and the note does not ship.

## The draws, 2026-11-10

Drawn from 02:20 to 02:22 on the `cortexn18` stack, the candidate as `cortexn18-brain-s3fix`
through `cortexn18-proxy`, every card approved, the rows checked clean before each draw. The SM
clock read 0.57 to 0.75 of `clocks.max.sm`; no turn ended in an error and no draw left a schedule
key. Scratch logs: `draw.log` and `rows.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot3/`,
the calls in the stack's proxy log, lines 2 to 46.

| Of the turns | m1 | v1 | x7 first | x7 second | d1 first | d1 second |
| --- | --- | --- | --- | --- | --- | --- |
| Turns | 4 | 3 | 3 | 3 | 2 | 2 |
| A `forget_memories` result was `_NONE_FOUND` and no row was removed | 4 | 3 | 0 | 0 | 0 | 0 |
| A forget removed the row through an approved card | 0 | 0 | 0 | 3 | 0 | 2 |
| The reply ends with the note | 4 | 3 | 0 | 0 | 0 | 0 |
| The reply said the fact was not stored or not found | 4 | 3 | | 0 | | 0 |

- The m1 calls passed `passport` once and `passport number` three times; every v1 call passed
  `0699000000`. No row held either, so each reply's "not stored" was true and the note was true
  beside it. Every x7 second call passed `Fahrradschloss`, which the row holds, so the form of
  R-1061 came in none of 3 draws, and the form of R-969 was not drawn.
- Each x7 first turn called `spawn_subagents` to store the fact, read the refusal for an unasked
  tool and stored the row; no first turn called a forget.

**Result.** Seven turns reached the condition and all seven end with the note; none of the five
turns whose forget removed a row and none of the five turns without a forget result has it, so
**the note ships**. Seven mutation rows over `forget_unfound_claim.py` and `closing_notes.py` all
fail the three test files that cover the note.

## The no-match result reworded: rows and the rule, 2026-11-12

Written before any draw. The candidate rewords `NONE_FOUND` (`forget_results.py`), the text the
model reads after a call no row contains, to say that nothing was forgotten because no remembered
exchange contains that exact text, and not to ask the user for the value. It drops "tell the user
that nothing about it was stored", which is false when a row states the fact in other words, and
names no next call. Build A is `cortexn20-brain-s2note` (the old text); build B is the working tree
with the new text, both second brains through the recording proxy on the `cortexn20` stack, a new
chat for each turn, every card approved, every row deleted before each draw.

| Row | Facts stored | Forget turn | Draws per build |
| --- | --- | --- | --- |
| p1 | `Remember that my phone number is 0612345678.` | `Forget that my phone number is now 0699000000.` | 3 |
| m1 | none | `Forget my passport number.` | 2 |

A turn **reaches the condition** when a `forget_memories` result in it is the no-match text.

- Item S: no B turn makes a forget call after a no-match result that deletes a row. If one does,
  the new text does not ship.
- Item T: over p1 turns that reach the condition while the phone row is stored, B has fewer
  replies saying the phone number was never stored or not found than A. With fewer than 2 such
  turns in either build, item T gives no result.
- The new text ships when item S holds and item T holds or gives no result, since the old text
  asks for a claim that is false whenever a row states the fact in other words.
- Counted besides, deciding nothing: turns reaching the condition per row and build, forget calls
  after a no-match result, and replies in m1 saying the passport number was not stored (true there).

## The no-match result reworded: what was drawn, 2026-11-12

Drawn from 01:01 to 01:06, proxy log lines 289 to 335, the candidate text `nothing was forgotten,
since no remembered exchange contains that exact text; do not ask the user for the value` in build
B as `cortexn20-brain-s2word`. The SM clock read 0.57 of its maximum between draws.

| Of the turns | A, p1 | A, m1 | B, p1 | B, m1 |
| --- | --- | --- | --- | --- |
| Turns | 3 | 2 | 3 | 2 |
| Reach the condition | 1 | 2 | 2 | 2 |
| Of those, the reply says the fact was never stored or not found | 1 | 2 | 0 | 1 |
| Of those, a forget call after the no-match result | 0 | 0 | 1 | 0 |
| Of those, the reply says something was removed | 0 | 0 | 1 | 1 |

**Result.** Item S fails, so **the new text does not ship**: in B p1 draw 2 the call `0699000000`
matched nothing and the model then called `forget_memories` with `0612345678`, whose approved card
deleted the old phone row. Item T gives no result, since A reached the condition in one p1 turn.
That A turn said `I didn't have that phone number stored in my memory` above the note while the
row was stored; no B reply said so. In B m1 one reply said `OK. I've removed that from my memory.`
and ended with both notes. With no instruction about what to tell the user, the model searched
further in one turn and claimed a removal in another. Script `live2.sh`, `word.sh` and
`nomatch.py`, log `word.log`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot2/`.
