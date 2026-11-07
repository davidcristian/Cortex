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
three words between them (`is now 0699000000`, `new phone number is 0699000000`), right after
`now`, `is`, `are` or `to`, in a message that asks to forget an old value (`delete`, `forget`,
`remove`, `erase`, `drop`, `clear` or `wipe` opening a clause, then `old`, `previous`, `former`,
`earlier` or `prior` within three words), reads "nothing
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

## The draws, 2026-11-07

Drawn on a build of `97d26b572` with the [recorded patch](forget-new-value-patch.md) as a second
brain (`cortexn15-brain-r969n`) through the proxy, beside the `cortexn15` stack brain, with the
seed row (`User: Remember that my phone number is 0612345678.`) copied in before each N01 and N02
draw and no phone row before each V01 draw. Every card was approved. The SM clock read 0.57 to
0.69 of its maximum; no draw ended in an error. Scratch logs:
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot4/`.

| Of the draws | N01 | N02 | V01 |
| --- | --- | --- | --- |
| Draws | 30 | 30 | 5 |
| First call's text the old value `0612345678`, card shown and approved, old row deleted | 30 | 30 | |
| Counted: a call naming `0699000000` matching nothing before any delete | 0 | 0 | |
| A row holding the old number after the draw | 0 | 0 | |
| No card, nothing deleted, value not asked for, reply says nothing was stored | | | 5 |

Before the draws every recorded first-call text was replayed with its message through the shipped
result, where every unmatched call reads `_NONE_FOUND`, and through the reader: `0699000000` in
M02, M05 and N02 and `8426` in the locker code form M01 read the new result, while `0612345678`,
`phone number`, `old phone number`, `phone`, `7319`, `locker code` and V01's `0699000000` keep
`_NONE_FOUND`.

Every N01 and N02 draw's first request held the seed row among the recalled notes, and every first
call named the old number. In V01 the call named `0699000000` and read
`_NONE_FOUND`, because the message names no old value, and each reply said the number was not
stored, for example "I didn't have that phone number stored in my memory, so there's nothing to
forget."

The rule counted 0 of the first 30 draws, under its 2, and 0 of the 15 more of each row it then
calls for, so **the candidate does not ship** and the behaviour stays. The form came in 6 of
60 draws of M02 over three earlier nights and in none of tonight's; those requests are not recorded,
so whether they held the seed row is not known. The next row is one whose first request does not
hold the old value, for example a pool in which recall leaves the seed row out, with its rule
written before it is drawn.
