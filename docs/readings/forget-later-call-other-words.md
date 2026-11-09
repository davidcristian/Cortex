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

## The replay draws: condition, 2026-11-08

Written before any replay draw. The form came in 2 of 10 live draws, so the four draws the rule
needs are reached by replaying the two recorded requests that held it, straight to the model
host, so the calls and their results are fixed and only the reply is drawn. The requests are the
last model requests of lk3 (`req.log` line 581: `5819` deleted, then `locker combination`: none
found) and bk3 (line 554: `4512` deleted, `bike code`: none found, then `bike lock code`: deleted
earlier), sent with `stream` off and the recorded sampling, alternating lk3 and bk3, until 20
draws or 10 minutes of model time. Every replay draw shows the form. The note is a check of the
reply after the model has answered, so both builds send the same requests and the draws serve the
start hash and the build alike; the build's note is computed for each reply from the same runs and
the count of calls that matched nothing. A draw whose answer is a tool call has no reply and is
counted apart. The pass rule above applies to the replay draws as written; its second item is
measured by replaying every recorded reply of a forget turn through the build.

## The replay draws, 2026-11-08

Twenty draws from 04:58:33 to 04:59:06, 33 seconds of model time, every one a reply (`finish`
`stop`), on the stack's model host. The SM clock read 0.57 of its maximum before, 0.61 at 38% use
during and 0.62 after. All twenty show the form. Each reply is read by hand for the rule, and the
build's note is computed by `unfound_claim` with the request's runs and one call that matched
nothing (`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot8/replay_readers.py`, output `readers.log` beside it). No bk3 reply says anything was
not found; each names the removal, so none fails and none gets the note. The lk3 replies:

| Draw | Turn d reply, after the removal it names | Says not found | Note on the build |
| --- | --- | --- | --- |
| 1 | `I couldn't find any entries specifically for "locker combination," but since it's gone now, it won't be stored.` | yes | yes |
| 3 | `Regarding the locker combination, I didn't have any record of it stored.` | yes | yes |
| 5 | `I didn't find any stored records for that specific phrase.` | yes | yes |
| 7 | `It appears that nothing else related to those terms was stored.` | no | no |
| 9 | `I couldn't find any other entries regarding a "locker combination," so nothing else was deleted.` | other entries | yes |
| 11 | `I couldn't find any specific entry for that, so it doesn't appear to have been stored.` | yes | yes |
| 13 | only the removal: `I've removed the gym locker code and the locker combination from my memory.` | no | no |
| 15 | `I couldn't find any entries for "locker combination," so it appears that information was not stored.` | yes | yes |
| 17 | `I also checked ... and confirmed that nothing else was stored.` | no | no |
| 19 | `I couldn't find any existing memory for "locker combination," so there was nothing to delete for that part of your request.` | yes | yes |

On the start hash, which appends no note, 6 of the 20 draws fail: draws 1, 3, 5, 11, 15 and 19. On
the build all 20 pass: the six and draw 9 end with the note, and no reply that names only the
removal or `nothing else` gets it. The rule's second item: of the 119 distinct recorded forget
turns with a successful call (`replay_turns.py`, output `turns.log`, a call with no approved card
counted as one that matched nothing, which counts the most notes), the 22 with no delete get no
note, and 3 of the 97 with a delete get it: pph1, whose passport was never stored, pph2, which
says the deleted phone was not found, and live lk3. The note says the text may be among the
deleted exchanges, which is true of all three. Over the 143 distinct recorded forget replies, slot
7's candidate reader reads 22 and the build's reads 18; the 4 it releases say a new phone number
the forget message gave was not saved, which `FORGET_NOT_KEPT_NOTE` requires. The rule passes, so
the note ships.

## Live draws on the build, 2026-11-08

Eight lk draws on the stack brain rebuilt from the build, from 05:17:55 to 05:21:29, cards
approved, through no proxy, so the calls are not recorded. Every row was deleted. Four replies
say the locker combination was not found and end with the note (lk2, lk3, lk6, lk8). lk7 says
"there were no other records of that found to remove", which says no other record was found,
which is true. The build that drew it did not read the plural; the reader now does (below). The
other three name only the removal and get no note. The run record is
`/tmp/claude-1000/-home-david-Files-Git-Cortex/5e7bbbe2-0692-4951-9718-a5c1c4b48de9/scratchpad/slot8/live.jsonl`.

## The plural and `other` forms, 2026-11-09

`says_not_stored` now reads `no records of` and `no other record of` as well as `no record of`,
unless the rest of the clause says the records remain, are left, exist, are kept, or are gone
`any more`, `any longer` or `no longer`. A clause that also names finding or storing (`found`,
`stored`, `saved`, `had`) is read either way, since the note shows when the reading is unsure.
Near misses written first: "no other records of it remain", "no records of it are kept now", "no
record of it is left in my memory". The last was read before the change.

Replay over the 28,039 distinct strings of `docs/readings/` (every line, table cell, quoted and
backticked text): 4 change, all from not read to read. One is lk7's reply above; the other three
are prose lines of this file quoting it or the form. No recorded reply moves from read to not
read. The script is `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot7/replay.py`.
