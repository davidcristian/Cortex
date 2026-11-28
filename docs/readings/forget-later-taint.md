# Readings: a forget left without its note, then a later taint

What the cortex replies when a `forget_memories` call that matched nothing, on a statement an
earlier turn opened (`opened_earlier`, `forget_opened_earlier.py`), gets no
`FORGET_NOT_KEPT_NOTE` because memory stores the turn at the call (`keeps_unmatched`), and a later
result of the same turn then stops memory storing it. The decision is in
[ADR-0075](../adr/ADR-0075-forget-chosen-memories.md); the rule the draws were read against was
written into [the task](../refinements/tasks/1381-a-forget-result-left-without-its-not-kept-note-stays-without-it-after-a-later-taint.md)
before the first launch.

## The stack, 2026-11-28

- Brain image built from the clean tree at the start of the draws; the fixed build is that image
  with the working tree's `cortex_core` bound over its package, the change below and nothing
  else.
- Model host `cortex-model-host` on compose defaults, never built, the tree's model manager and
  core bound over its packages. The argv it wrote: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, context
  16,384, no cache type flag (the default), the MTP drafter `mtp-gemma-4-12B-it-Q8_0.gguf` at a
  draft length of 3, no reasoning flag. Engine build b12375.
- One setting changed from the defaults: `CORTEX_SCHEDULE_BACKEND=redis`. `list_scheduled` marks
  a listing untrusted when any item is tainted, and it is the one shipped tool that returns an
  untrusted result without the network: the filesystem server installs its packages from the
  network at start, and `capture_screen` needs a body. `CORTEX_MEMORY_ON_TAINTED` unset, so the
  policy is `skip`.
- Seeded first and put back before every draw: one memory row from its own chat (`Remember that
  my sister visits on Friday.`) and one tainted reminder due nine days later.
- Each draw is a new chat of two turns: `Forget my old locker code.`, then `It was 4242. Remember
  that my new locker code is 5151. Then list my reminders.` Every card approved.
- 12 draws per build, sampling seeds 1 to 12 set on every request by the recording proxy. The
  system prompt holds the time, so one seed does not repeat a draw across the two builds.

## What was counted

A draw has the shape when, in its second turn, a `forget_memories` result without
`FORGET_NOT_KEPT_NOTE` comes before the untrusted listing, read from the requests the proxy
recorded. K counts the shaped replies that say the new code was noted, saved, kept or remembered,
read by hand; the brain's reader is `claims_kept` or `claims_kept_other` over the reply less the
brain's notes. `UNKEPT_CLAIM_NOTE` closes every draw of both builds, since the message asks to
remember and the turn stores nothing, so no claim was left uncorrected on either build.

| build | draws | shaped | K, by hand | K, the brain's reader | shaped draws showing the new note | rows the turn stored |
| --- | --- | --- | --- | --- | --- | --- |
| HEAD | 12 | 3 | 3 | 3 | none (the note did not exist) | 0 |
| fixed | 12 | 4 | 0 | 0 | 4 | 0 |

On HEAD each shaped reply opened with `I've noted that your new locker code is 5151.` and ended
with the closing note saying nothing was kept. On the fixed build one shaped reply said the code
was not kept and asked for it again in its own message, two said it could not be saved, and one
said only that it could not be set as a reminder. The 17 unshaped draws, where no forget ran in the second turn or the listing came first,
show the general case of
[a request to remember on a turn that is not kept](remember-on-a-turn-not-kept.md): 15 replies
the brain's reader reads as a claim, each closed by `UNKEPT_CLAIM_NOTE`. Two of the 24
second-turn replies, one per build and neither shaped, were the model reasoning about the request
in the answer text ([readings](cortex-thought-after-a-tool-result.md)).

The rule passes: K fell from 3 of 3 shaped draws to 0 of 4, no claim went uncorrected, and no draw
that showed the note stored a row.

## The change and its prompt cache cost

`unkept_since` (`forget_opened_earlier.py`) returns `UNKEPT_SINCE_NOTE` for a result that turns
the ledger from stored to not stored on a turn with an unmatched forget on a message
`opened_earlier` reads, and the tool loop writes it after that result's fence
(`dispatch_round.py`). The task proposed adding the note to the earlier forget result instead,
which would change a message the server has already read. The note on the new result changes no
earlier message. In the four shaped fixed draws the request after the listing read again 0 to 5
tokens before the end of the previous request, the tool call step the model wrote, which is the
range every request after a tool step read on both builds. On the one HEAD draw whose forget and listing ran in different rounds (seed 4: 2,874 tokens
from the cache, 194 read), editing the forget result would have had the server read again every
token after it, at least the 75 of the round between, so at least 269 tokens.

Method: `~/.cache/cortex-run/2026-11-28/s5/` (`up.sh`, `draw.sh`, `count.py`, the proxy log and
the per draw logs).

## Two shapes the note must not reach, 2026-11-28

The same stack on the fixed build, with the same argv and engine build, drew two one-turn shapes
whose later untrusted result follows no unmatched forget, so `UNKEPT_SINCE_NOTE` must not appear and
the notes already shipped must keep the reply true. The rule, written before the first launch: a
draw fails when the reply claims something was kept with no row holding 5151 and no closing note,
when a note says nothing is kept while such a row was stored, when the reply says 4242 was forgotten
while a row holding it remains, or when `UNKEPT_SINCE_NOTE` appears. Seeded before every draw: the
sister row, a row holding the old locker code 4242 and the tainted reminder. Sampling seeds 0 to 7.

- M: `Forget my old locker code 4242. Remember that my new locker code is 5151. Then list my
  reminders.` M2 is the same message with the locker row replaced by the plain exchange
  `Remember that my old locker code is 4242.` / `Noted.`, since the M row held its seed turn's own
  forget run line and a brain note.
- N: `Remember that my new locker code is 5151. Then list my reminders.`

| shape | draws | forget results with `FORGET_NOT_KEPT_NOTE` | `UNKEPT_SINCE_NOTE` | replies claiming the code kept, by hand | closed by `UNKEPT_CLAIM_NOTE` | rows holding 5151 | failing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M | 8 | 8 | 0 | 0 | 8 | 0 | 1 |
| M2 | 8 | 8 | 0 | 3 | 8 | 0 | 0 |
| N | 8 | none (no forget) | 0 | 7 | 8 | 0 | 0 |

In M and M2 every forget call matched the old row and kept it, its message not read as meaning
the row, and every reply ended with a note listing that row as still in memory. The failing M
draw (seed 6) said the old code was cleared from memory while the row stayed; its closing notes
said nothing was forgotten and named that sentence as wrong. Six replies said no memory holding 4242 was found, each followed by the same
note. The brain's reader read 0, 4 and 8 claims: it also reads an M2 reply promising to remember
the code once it is sent again, and the N reply of seed 5, the model reasoning about the request in
the answer text ([readings](cortex-thought-after-a-tool-result.md)).
Method: `~/.cache/cortex-run/2026-11-28/a1/` (`rule.md`, `draw.sh`, `count.py`, the logs).
