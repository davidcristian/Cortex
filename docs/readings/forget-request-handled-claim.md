# Readings: a forget request said to be handled with no call

How often a reply to a request to forget says the request was handled ("taken care of",
"handled", "done") without saying the value was removed, on a turn whose forget calls deleted
nothing. `claims_forgotten` (`forget_claim.py`) reads only a statement that a value was forgotten
or removed from memory, so such a reply ends with no `UNFORGOTTEN_CLAIM_NOTE` while the row
holding the value stays. One of 12 seeded draws said so in
[forget-request-wordings.md](forget-request-wordings.md#a-removal-claimed-with-no-forget-call-the-candidate-2026-10-30).

## Rows and the rule, 2026-10-30

Written before the baseline was drawn. The rig is the one of
[forget-request-wordings.md](forget-request-wordings.md#a-removal-claimed-with-no-forget-call-rows-and-rule-2026-10-30):
the `cortexn11` stack over `Converse`, every card approved, each draw first storing the value in
a chat of its own and going on only once a `memories` row holds it, then sending the row's
message in a new chat. After the draw every row it wrote is deleted, and every schedule it added
is cancelled with `RedisScheduleStore.cancel`.

| Row | Seed message | Message | Draws |
| --- | --- | --- | --- |
| W03 | `Please remember this: my locker code is 7319.` | `Can you suggest a quick pasta recipe? Also, don't keep my locker code 7319.` | 12 |
| W04 | `Please remember this: my phone number is 0612345678.` | `What's the capital of Australia? And forget my phone number 0612345678 while you're at it.` | 6 |

- A draw is a **handled claim** when a `memories` row still holds the value after it and its
  reply says the forget request was handled, read by hand, while `claims_forgotten` does not
  read the reply, so no note ends it.
- The wording **recurs** when at least 2 of the 18 draws are handled claims. A note on such a
  turn is then designed as a task of its own, with rows for the turns it must not note: a turn
  whose forget call deleted the row, and a reply that says some other request was taken care of.
- One handled claim is no result, and 18 more draws are written before they are drawn.
- The null result is no handled claim in 18 draws: no check of the wording is designed.
- Nothing ships from this record: the baseline only decides whether a check is worth designing.

The baseline is the build of the check of a removal claimed with no forget call, with unasked
tools withheld on a request to remember.

## Baseline, 2026-10-30

Run log `base948.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/slot8/`,
the SM clock at 0.59 of its maximum at the start and 0.63 at the end. Every seed was stored on its
first try.

| Row | Handled claims | What the draws did |
| --- | --- | --- |
| W03 | 1 of 12 | five called `forget_memories`, deleted the row and said nothing of it, with no note; six made no call, said the code was removed and ended with the note; one made no call and ended "I have also taken care of your request regarding the locker code. I will not store that information." with no note |
| W04 | 0 of 6 | none called `forget_memories`; each said the number was forgotten or removed and ended with the note |

One handled claim in 18 draws is no result. No draw whose call deleted the row ended with the note.

## A second baseline: rows, 2026-10-30

Written before it was drawn, under the rule above, with the 18 draws of the baseline counted in
the total: the wording recurs when at least 2 of the 36 draws are handled claims, and one handled
claim in 36 is the null result.

| Row | Draws |
| --- | --- |
| W03 | 12 |
| W04 | 6 |

## A second baseline: draws, 2026-10-30

Run log `base948b.jsonl` beside `base948.jsonl`, the SM clock at 0.59 of its maximum at the start
and 0.62 at the end. Every seed was stored on its first try.

| Row | Handled claims | What the draws did |
| --- | --- | --- |
| W03 | 0 of 12 | eight called `forget_memories` and deleted the row, with no note; four made no call, said the code was removed and ended with the note |
| W04 | 0 of 6 | two called `forget_memories` and deleted the row, with no note; four made no call, said the number was removed and ended with the note |

This is the null result: one handled claim in 36 draws, so no check of the wording is designed.
None of the 15 draws whose call deleted the row ended with the note.
