# Readings: a requested repeat of a line the model writes

Before this rule, `RepeatWatch`, the repeated block check of
[reply loop](reply-loop.md#the-fifth-rule), ended every reply at the third back to back copy of a
block of one to four lines holding a line of at least 20 characters, with a letter, that the
person's message does not hold. A request to make up a line and write it several times has that
shape, so the check cut it as a loop: on 2026-10-14 two of three such turns on the Linux shell
ended at the third copy with `REPEATED_LINE_NOTE` ([overlay
flows](overlay-repeat-and-forget-flows.md#a-requested-repeat-of-a-line-the-model-writes)).
This record holds the sixth rule, written before any of its rows was drawn, and its results.
The shape that passed, E, is the check in the brain now.

## The sixth rule

Read off the fourth rule's baseline before this rule was written: the same block check needing K
back to back copies in place of 3 stops all 22 looping rig draws before their 1536 token limit for
every K up to 13, 21 of them at K = 16 and 18 at K = 21. Two shapes are compared with the current
one, C.

- **E, a count from the message**: the watch needs 3 copies, or one more than the largest count
  the person's message asks for when that is more. A count is a number in digits or one number
  word (two to twenty, the tens to ninety, hundred) followed by `times` or `copies`. "Write it ten
  times" then needs 11 copies, and a message with no count needs 3, as now.
- **F, a fixed count**: the watch needs 16 back to back copies, the most that still stops all but
  one looping rig draw above. It lets a request of up to 15 copies through, and it cuts each of the
  21 loops it stops 39 to 156 words later than C does.
- **Request rows**, drawn after this rule at the server's defaults with `max_tokens` 2048, five
  draws each, on the format control's state with its message replaced by "Without using any tool,
  make up one sentence of advice of about ten words for a choir singer, then write that exact
  sentence N times, one per line, and nothing else.", N written `5`, `ten` and `20`. A row judges
  when C stops at least 3 of its 5 draws; otherwise no shape is judged. SM clock read after each
  row.
- **A shape passes** when, read off the fourth rule's baseline as the fifth rule reads it, it stops
  every looping rig draw but at most one before its token limit, no other rig draw and no control
  draw; it stops none of the fifth rule's 20 request draws; and it stops no draw of the request rows
  above that writes its sentence no more times than the message asks.
- **E ships when it passes**, in `RepeatWatch`, since it leaves the cut where it is for every
  message that names no count. **F ships** when only F passes. No pass changes nothing, and the
  rows are recorded here.

## Results

**2026-10-14, the sixth rule's rows**, 15 request draws on the same test stack and server build as
the fourth rule's rows, read with that rule's 60 baseline draws and the fifth rule's 20 request
draws. Words are after the prefill.

| Shape | Looping rig draws stopped | Other rig and control draws stopped | Fifth rule request draws stopped | Request draws stopped: 5, ten, 20 copies |
| --- | --- | --- | --- | --- |
| C, three copies | 22 of 22, at 221 to 516 words | 0 | 0 | 5, 5, 4 |
| E, a count from the message | 22 of 22, at 221 to 516 words | 0 | 0 | 0, 0, 0 |
| F, sixteen copies | 21 of 22, at 294 to 620 words | 0 | 0 | 0, 0, 4 |

Every row judges. Each draw of the first two rows made up a sentence of 51 to 58 characters and
wrote it exactly as many times as asked; four draws of the third wrote theirs 20 times, and the
other spent all 2048 tokens in `reasoning_content` and wrote no reply. **E passes** and ships in
`RepeatWatch`. **F fails**, since it stops all four 20 copy draws at the sixteenth copy. Fed each
of the 95 draws in pieces of 7 characters, the built watch stops exactly where E stops. SM clock
0.61 to 0.62 of `clocks.max.sm` after each row.

Live turns on the same stack with E in the brain: the ten copy request ran to ten copies with no
note over `Converse` and on the Linux shell, the 20 copy request to 20 copies with no note, and the
choir rota read answered as before.

The shipped reading of E also skips a count whose `times` or `copies` is followed by another number,
so the product "What is 365 times 24?" needs 3 copies, as under C. Each of the three request
messages above still reads the count it names, which `test_repeat_watch.py` asserts on the exact
message, so none of the rows above changes.

Method: `mkreq.py`, `draw.sh` and `score6.py` in the run's scratch directory, with the replay
driver of the fifth rule's rows, against the test stack's cortex server on `127.0.0.1:8080`.
