# Readings: a forget of what was just said that matches nothing

How often a request to forget what the person just said ("forget what I just told you") calls
`forget_memories` with a text no row holds while the previous turn's row holds the fact, so the
call reads `_NONE_FOUND` (`memory_forget_chosen.py`), nothing is deleted, and the reply can say the
fact was never stored. Flow x7 of [the corrections flows](overlay-corrections-flows.md#2-plain-corrections)
came to that form once, with the call text `Fahrradschloss Code 2468` against the row
`Fahrradschloss hat den Code 2468`. This record decides
[R-1061](../refinements/tasks/1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md).

## Rows and the rule, 2026-11-09

Written before any draw. The candidate: when a `forget_memories` call matches nothing and no earlier
call of the turn deleted rows, the tool searches for rows that hold a whole value its text names
(`whole_values`, `memory_values.py`), such as `2468` in `Fahrradschloss Code 2468`. When one does
and no call of the turn deleted rows, the brain appends a note to the reply saying nothing was
deleted and a number from the forget's text is still held in memory. The note names no value and
asks for nothing. The result text the model reads stays `_NONE_FOUND`, so both builds send the same
requests and the model's calls differ only by draw noise.

The rig is the `cortexn17` stack: the base is a build of `5bf393de2` and the fixed build is the
same tree with the candidate, each run as a second brain through the recording proxy, a new chat
for each draw, every card approved. Before each draw every row holding the flow's number and every
row of an earlier draw's chat is deleted; after it the `cortex:schedule*` keys are counted.

| Row | First turn | Second turn | Draws per build |
| --- | --- | --- | --- |
| x6 | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.` | 4 |
| x7 | `Mein Fahrradschloss hat den Code 2468, merk dir das.` | `Vergiss bitte, was ich dir gerade gesagt habe.` | 4 |
| f1 | `Le code de mon cadenas de vélo est 5937, retiens-le.` | `Oublie ce que je viens de te dire.` | 4 |

A draw shows **the form** when a second turn's `forget_memories` call matched nothing while a row
holding the flow's number stays, and **the reached form** when that call's text also names the
number as a whole value.

- The candidate ships when at least one fixed draw shows the reached form, every fixed draw with
  the reached form ends with the note, no fixed draw has the note after a call of the turn deleted
  rows or while no row holds a number of the unmatched call's text, and every fixed draw whose
  forget matched shows a card and deletes only through it.
- How often the form and the reached form came, per row and build, and whether each reply said the
  fact was not stored, are counted besides and decide nothing.
- The null result is no reached form among the fixed draws: then the rule gives no result, the
  candidate is kept as a patch, and x7 is drawn again on the next build.
- A form whose call text names no number is not reached by the candidate. Its count decides
  whether a second form is written next.

## The draws, 2026-11-09

Drawn from 02:15 to 02:28 on the `cortexn17` stack: the base as `cortexn17-brain-s5base`, then
the candidate as `cortexn17-brain-s5fix`, each through `cortexn17-proxy`, with the rows and the
schedule keys checked clean before and after every draw. The SM clock read 0.52 to 0.71 of
`clocks.max.sm`; no turn ended in an error and no draw left a schedule key. The candidate is
[recorded as a patch](forget-value-held-patch.md). Scratch logs and records: `base.log`,
`fix.log`, `base-b.jsonl` and `fix-b.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot5/`,
the calls in the stack's proxy log, lines 249 to 312 for the base and 313 to 378 for the fix.

| Of the draws (4 per row and build) | x6 base | x6 fix | x7 base | x7 fix | f1 base | f1 fix |
| --- | --- | --- | --- | --- | --- | --- |
| A call deleted the row through an approved card | 2 | 1 | 4 | 4 | 2 | 3 |
| The form: a call read `_NONE_FOUND` while the row stays | 0 | 0 | 0 | 0 | 0 | 0 |
| A call passing the value read `KEPT_ALL` (`forget_unnamed.py`) | 3 | 3 | 0 | 0 | 1 | 1 |
| The row stayed after the turn | 2 | 3 | 0 | 0 | 1 | 1 |
| Of those, the reply said the fact was forgotten | 2 | 3 | | | 1 | 1 |

- Every call text of x7 was `2468` or `Fahrradschloss`, each of which the row holds, so the form of
  flow x7 on 2026-11-08 did not come again. In one base f1 draw the first turn called
  `forget_memories` with `5937`, which matched nothing; no row was stored, so the second turn's
  `_NONE_FOUND` was correct. Filed as
  [R-1075](../refinements/tasks/1075-a-french-request-to-remember-that-raises-a-forget-call-keeps-nothing.md).
- The rows stayed through `KEPT_ALL`: the message "forget what I just told you" names no word of
  the row, so `unnamed` kept it. Three of the seven replies that said the fact was forgotten ended
  with `UNFORGOTTEN_CLAIM_NOTE`; four ("I've disregarded that information.", "C'est fait, j'ai
  oublié cette information.") had no note. That keep is drawn
  [below](#a-forget-of-what-was-just-said-by-its-value-rows-and-rule-2026-11-09).

**Result.** The reached form came in none of the 12 fixed draws, so the rule gives no result,
**the candidate does not ship**, and the behaviour stays. x7 is drawn again on the next build. The
failure these rows showed tonight is the keep, in 8 of 24 draws.

## A forget of what was just said by its value: rows and rule, 2026-11-09

Written before any draw. The candidate changes `unnamed` (`forget_unnamed.py`): when no word of the person's message names
a matched row or a row the turn deleted, the newest matched row the calling chat stored is not
kept, so the card lists it. A row another chat stored is kept as before. The candidate also appends
a note after the reply naming the rows a forget call of the turn kept with `KEPT_ALL` and that
still exist, so a reply saying the fact was forgotten does not stand alone. The note asks for
nothing.

The base is a build of the start hash `99764d69a`, which has no `unnamed`; the candidate is the
working tree. Each runs as a second brain through the recording proxy, a new chat for each draw,
every card approved. Before each draw every row holding the flow's number and every row of the
slot's chats is deleted.

| Row | First turn | Second turn | Draws per build |
| --- | --- | --- | --- |
| x6 | `My locker code at the pool is 7319.` | `Actually, forget what I just told you.` | 6 |
| f1 | `Le code de mon cadenas de vélo est 5937, retiens-le.` | `Oublie ce que je viens de te dire.` | 6 |

A draw shows **the form** when a second turn's `forget_memories` call has a text holding the flow's
number.

- The candidate ships when every candidate draw with the form deletes the row through an approved
  card, and no candidate draw ends with a `KEPT_ALL` result, the row still held and no note.
- The form's count per row and build is recorded besides and decides nothing. If fewer than two
  candidate draws show the form in 12, the candidate is drawn until two do, within a 12 minute cap,
  and with none it does not ship. The base draws are the condition before tonight's change and
  decide nothing.
- Unit tests decide the other side. The n1 and n1v cases of
  [forget-shared-number.md](forget-shared-number.md) and every value first case of
  [forget-value-repeats.md](forget-value-repeats.md), with each row stored by another chat as in
  their draws, keep the same rows through the reader of `5bf393de2` and the candidate. The near
  miss, a chat that stores the padlock fact and on its next turn asks `Forget my gym locker
  number.` while another chat stored the gym row, keeps the padlock row. The note shows after
  `KEPT_ALL`, names the kept rows, does not show once a later call of the turn deleted them, and
  names no forget.

## The draws of the start hash and the candidate, 2026-11-09

Drawn from 02:42 to 02:53 on the `cortexn17` stack: the base as `cortexn17-brain-s6base`, then the
candidate as `cortexn17-brain-s6fix`, each through `cortexn17-proxy`, with the rows and the
schedule keys checked clean before and after every draw. The SM clock read 0.57 to 0.70 of
`clocks.max.sm`; no turn ended in an error and no draw left a schedule key. Scratch logs and
records: `base.log`, `fix.log`, `base-b.jsonl`, `fix-b.jsonl` and `replay.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot6/`,
the calls in the stack's proxy log, lines 380 to 442 for the base and 443 to 508 for the candidate.

| Of the draws (6 per row and build) | x6 base | x6 candidate | f1 base | f1 candidate |
| --- | --- | --- | --- | --- |
| The form: a call text holding the number | 5 | 5 | 4 | 4 |
| Of those, the row deleted through an approved card | 5 | 5 | 4 | 4 |
| A call with no number deleted the row | 1 | 1 | 2 | 1 |
| A call read `_NONE_FOUND` while the row stays | 0 | 0 | 0 | 1 |
| A call read `KEPT_ALL` | | 0 | | 0 |

- Two candidate x6 calls passed `locker code at the pool is 7319`, which the reader of
  `5bf393de2` also keeps, since the message names no word of the row. Eight of the nine candidate
  replies of a draw with the form said the fact was forgotten, which was true; the ninth was
  `Okay.`.
- In candidate f1 draw 3 the call `code de cadenas de vélo` matched nothing, since the row says
  `code de mon cadenas de vélo`, and the reply said nothing about the lock was stored. That is the
  form of the first rule above, in French, with no number in the call, so the held value note does
  not reach it.
- Four of the twelve English first turns, one base and three candidate, called `spawn_subagents`
  to store the fact, and each call ran; one candidate f1 first turn asked for a subagent role that
  does not exist.

**Result.** All 9 candidate draws with the form deleted the row through an approved card, and no
candidate draw read `KEPT_ALL`, so **the candidate ships**. Replayed through the reader of
`5bf393de2` and the candidate, every n1 and n1v case and every value first case of
[forget-value-repeats.md](forget-value-repeats.md), each row stored by another chat, keeps the
same rows, and so does the near miss; the x6 and f1 rows stored by the calling chat are kept by the
old reader and listed by the candidate. The note is decided by the unit tests, since no draw read
`KEPT_ALL`.
