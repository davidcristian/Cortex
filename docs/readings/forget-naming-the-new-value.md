# Readings: a forget call that names the new value

How often a request to replace a fact and forget the old one calls `forget_memories` with the new
value as its text, which no row holds, so the call matches nothing, the old row stays, the turn is
stored, and the reply says no old value was found. Row M02 came to that form in 6 of 60 draws
([readings](forget-no-match-on-remember.md#a-forget-after-a-delete-the-second-15-draws-2026-11-06)).
This record decides step 2 of
[R-969](../refinements/tasks/969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md).

## Rows and the rule, 2026-11-07

Written before any draw. The candidate: a `forget_memories` result that matched nothing, in a turn
with no earlier delete, whose text follows `now` or `new` in the person's message with at most
three words between them (`is now 0699000000`, `new phone number is 0699000000`), reads "nothing
was forgotten: that text is the new value the user just gave, which no remembered exchange holds,
so call `forget_memories` again with one word from the request that names the fact, such as
"phone", and do not say that the old value was not stored" in place of `_NONE_FOUND`. The tool
holds no message, so the result is replaced where the round reads the query, as `_told`
(`dispatch_round.py`) replaces a wrong-date schedule refusal. Every other no-match result stays
`_NONE_FOUND`. Before the code, the reader gets near-miss tests (a value after `now` in a
question, `new` naming another fact, a value before `now`), and every recorded draw message is
replayed through it.

The rig is that of [the after-delete record](forget-after-delete-provoked.md#rows-and-the-rule-2026-11-07):
the `cortexn15` stack, a candidate beside the stack brain through the recording proxy, a new chat
for each draw, every card approved, every `memories` row holding `0612345678`, `0699000000`
or `phone number` deleted before each draw.

| Row | Message | Pool at the draw's start | Draws | A draw counts when |
| --- | --- | --- | --- | --- |
| N01 | `Note that my phone number is now 0699000000, and delete the old one.` | the seed row holding `0612345678` | 15 | a call whose text is `0699000000` matched nothing before any delete in the turn |
| N02 | `My new phone number is 0699000000, so forget the old one.` | the seed row | 15 | as N01 |
| V01 | `Forget that my phone number is now 0699000000.` | no row holding either number | 5 | always |

- The candidate ships when at least 2 N01 and N02 draws count, a later call in the turn deletes the
  old row through an approved card in at least half of the counted draws, no counted reply says the
  old value was not stored or could not be found while a row holds it, and every V01 draw shows
  no card, deletes nothing, does not ask the user for the value, and says nothing about it was
  stored. Fewer than 2 counted draws is no result, and N01 and N02 are drawn 15 more times each.
- How often the form came, per row, is counted besides and decides nothing.
- The shipped build is not drawn: the change reaches only the result of a call that matched nothing,
  so the first request of both builds is identical. For the same reason no row names a value that
  follows neither word, such as a passport number never stored: its result is `_NONE_FOUND` on both
  builds, which the reader's unit tests check.
- The null result is counted draws whose turn makes no later call; then the result text does not
  move the model, and a search the brain runs itself for a word of the message is the next form to
  write a rule for.
