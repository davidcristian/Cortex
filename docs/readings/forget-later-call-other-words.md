# Readings: a later forget call in other words after a delete

A turn that deletes a fact with one `forget_memories` call can call the tool again with other
words for the same fact. When the later call matches nothing, `_about` in
`memory_forget_chosen.py` returns the result that names the earlier delete only when the later
text is a substring of a deleted row, the reverse, or shares a whole value with one; otherwise the
result tells the model to say that nothing about it was stored. The [task](../refinements/tasks/1021-a-later-forget-with-other-words-says-a-deleted-fact-was-never-stored.md)
asks whether a reply then says the deleted fact was never stored. The two factual results drawn on
2026-11-07 are in [forget-value-repeats.md](forget-value-repeats.md#the-draws-of-both-results-2026-11-07).

## The flows and the rule, 2026-11-08

Written before any draw. Each draw uses new chats, approves every card, and deletes the flow's
rows first. Turn a stores the fact; turn d asks for the value and the fact in other words:

| Flow | Turn a | Turn d |
| --- | --- | --- |
| bk | `Remember that my bike lock code is 4512.` | `Forget 4512, and anything you have about my bike code.` |
| lk | `Remember that my gym locker code is 5819.` | `Delete 5819 from your memory, and the locker combination too.` |

The form is a turn d where a call deleted the fact's row and a later call of the same turn got the
result telling the model to say nothing about it was stored. A draw with the form fails when the
turn d reply says the code, the bike code or the locker combination was not stored, not found or
not in memory. The premise holds when one draw with the form fails; the count of draws with the
form is reported apart. The draws run on a brain built from `d7a1afe0a`, at most 10
minutes of model time, alternating bk and lk.

If the premise holds, the next build keeps the start hash's results and appends a note after the
reply when a call of the turn deleted rows and the reply says what it was asked to forget was not
found or not stored. That note ships when, over these flows drawn until four draws show the form,
every reply in a draw with the form either does not say the fact was not found or ends with the
note, and no draw without a delete gets the note.

## The draws, 2026-11-08

Ten draws on a second brain built from `d7a1afe0a` through the recording proxy, sharing the
stack's model host and store, from 04:32 to 04:38: 5.5 minutes of model time. The SM clock read
0.57 of its maximum before, 0.69 at 82% use during and 0.56 after. Calls and results are read from
the proxy's request log; `none found` is the result telling the model to say nothing about it was
stored, `deleted earlier` the one naming the earlier delete.

| Draw | Calls and results after the value's delete | Form | Turn d reply | Result |
| --- | --- | --- | --- | --- |
| bk1 | `bike lock code`: deleted earlier | no | `OK. I've forgotten that information.` | pass |
| lk1 | `gym locker code`: deleted earlier | no | `I've deleted those details from my memory.` | pass |
| bk2 | `bike lock code`: deleted earlier | no | `I've forgotten your bike lock code and any related information.` | pass |
| lk2 | `gym locker code`: deleted earlier | no | `I've deleted both the code and the locker combination from my memory.` | pass |
| bk3 | `bike code`: none found, then `bike lock code`: deleted earlier | yes | `I've cleared that from my memory.` | pass |
| lk3 | `locker combination`: none found | yes | `I've removed the code from my memory. It appears I didn't have any specific "locker combination" entries saved, but I've ensured that information is cleared.` | fail |
| bk4 | `bike lock code`: deleted earlier | no | `I've forgotten the code and any information regarding your bike lock.` | pass |
| lk4 | none, one call `5819` | no | `I've removed the locker code from my memory as you requested.` | pass |
| bk5 | none, one call `bike lock code` | no | `I've forgotten that information.` | pass |
| lk5 | `gym locker code`: deleted earlier | no | `I've deleted those from my memory.` | pass |

The form occurred in 2 of 10 draws, and 1 of those 2 failed, so the premise holds on this build:
lk3 says the locker combination was never saved after its code was deleted. In 6 draws the model's
later text was the stored row's own words, a substring, which already gets the result naming the
earlier delete. Every row was deleted in all ten. The run record is
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot7/draws.jsonl`,
with the calls in `draws1.log` and `draws2.log` beside it.

## The recorded replies, 2026-11-08

Of the 46 recorded forget turns of 2026-11-07 (the cards of 49 calls, replayed through the start
hash), two replies after a delete say something was not found, both on the pp flow, whose later
call named the passport that was never stored: pph1 says so of the passport only, which is true,
and pph2 says the deleted phone was not found either. A call that matched nothing showed no card,
so those records hold no later text. A note for the form would show on both replies, so its text
must be true for each.
