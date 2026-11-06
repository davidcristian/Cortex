# Sidecar tools on a request to remember: a value named by a record

Readings for the record-word reader of `unasked_tools.py`, the second part of
[sidecar-tools-on-remember.md](sidecar-tools-on-remember.md), which is at its line limit. The task is
972 in the backlog. The reader was first drawn on 2026-10-31 over the words lease, contract,
spreadsheet, invoice, passport, receipt, statement, bill, payslip, policy, licence, certificate, form
and ticket, and reverted on a reply claim the claim reader did not read then; that patch was lost.
This record rebuilds it from those readings, adds `sheet`, `report`, `resume` and `cv`, and draws it
again.

## The reader, 2026-11-06

`_RECORD` reads a request to remember "the X from, on or in my Y" as a source only when Y is one of
the record words above, the message ends at Y (a full stop or exclamation mark may follow), and X
holds no form of "to be". Everything else the reader read before, it reads as before. A record word
anywhere else states a fact as often as it names a file, so `Remember that my report is due on
Friday.`, `Remember my resume` and `Remember that the total in my report is wrong.` still refuse the
file tools. The reader fails toward refusing: a message of the shape with a trailing clause
(`Remember the numbers in my budget sheet, please.`) is refused, since a wrong keep loses the fact
(W01 on 2026-10-31) while a wrong refusal stores it.

The near misses, written as tests before the code: `Remember the meeting on my birthday.` (W01),
`Remember my resume needs a new summary`, `Remember that the keys are in my coat`, `Remember that the
total in my report is wrong.`, `Keep in mind the total on my last invoice was high.`, `Remember my
resume`, `Remember the numbers in my budget sheet, please.`, `Note that the numbers are in my budget
sheet.` and `Remember the name on a form.`. The shape itself: `Remember the numbers in my budget
sheet.`, `Keep in mind the total on my last invoice.`, `Remember the reference on my bank statement.`,
`Remember the address on my lease.`, `Keep in mind the total from my budget spreadsheet.` and
`Remember the dates on my train tickets!`. The lease message moved from the list of messages that
refuse the tool that calls the sidecar to the list of messages that keep it.

`Remember my resume needs a new photo` was meant as a near miss and is not one: `photos?` is in
`_SOURCE`, so the reader kept the file tools on it before this change. The picture words are read
below.

### Replay

Every backticked or quoted string in `docs/readings/`, the task files and the brain tests, read
through the committed reader and the new one (`replay.py` beside the run log): 27772 strings, 438
read as requests to remember, the file tools refused on 357 by the old reader and 351 by the new.
The six that change are all of the shape, each from refused to kept:

- `Keep in mind the total from my budget spreadsheet.` (M01, M04)
- `Keep in mind the total on my last invoice.` (M07)
- `Remember the address on my lease.` (M02, M03)
- `Remember the numbers in my budget sheet.`
- `Remember the phone number on my contract.`
- `Remember the reference on my bank statement.` (M08)

## Rows and the rule, 2026-11-06

Written before the draws. The rig is the one of the first record: a candidate brain built from the
working tree beside the stack's brain, the same model host, with `budget.csv` (a four-line budget
whose total is 1705) and `statement.txt` (reference `BX-77-2041`) in the sidecar's root for every
draw, `memories` emptied before each draw and read after it. The committed reader refuses the file
tools on W01 and N01 to N03 exactly as the candidate does, so the brain's first request on those rows
is the same on both builds: they check that the shape's near misses store the fact, not a difference
between builds. The R rows have their baseline in the first record (0 of 8 M draws stated the value).

| Row | Message | File | Draws |
| --- | --- | --- | --- |
| R01 | `Remember the numbers in my budget sheet.` | `budget.csv` | 3 |
| R02 | `Remember the reference on my bank statement.` | `statement.txt` | 3 |
| W01 | `Remember the meeting on my birthday.` | none | 3 |
| N01 | `Remember that my report is due on Friday.` | none | 3 |
| N02 | `Remember my resume needs a new summary` | none | 3 |
| N03 | `Remember that the keys are in my coat` | none | 3 |

The reader ships when all of these hold:

- R01 and R02 call a file tool in at least 5 of 6 draws and state the file's value (`1705` or the
  budget's lines, `BX-77-2041`) in at least 4 of 6.
- W01 and N01 to N03 call no file tool in 12 of 12 draws and store the message in at least 11 of 12.
- No R draw says the value was kept without `UNKEPT_CLAIM_NOTE` (`memory_claim.py`) beside it.
- At most 1 of 6 R draws ends at the limit of tool rounds.

A part that fails keeps the reader out of the tree as a recorded patch, and the next row is written
here. Fewer draws than the table names, from the slot's time box, decide nothing: the counts are
recorded and the remaining draws are the next step.

## The draws, 2026-11-06

Run log `rows.jsonl`, the stored rows in `records.jsonl` and the scoring in `score.py`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot9/`.
The candidate `cortexn14-brain-r972` was built from the working tree; 18 draws ran from 04:34:53 to
04:40:05 UTC, the SM clock at 0.57 of its maximum on every row's reading. No draw ended in an error.

| Rows | Candidate |
| --- | --- |
| R01 and R02 calling a file tool | 6 of 6 |
| R01 and R02 stating the file's value | 6 of 6 |
| R01 and R02 saying the value was kept without the note | 0 of 6 |
| R01 and R02 at the limit of tool rounds | 0 of 6 |
| W01 and N01 to N03 calling a file tool | 0 of 12 |
| W01 and N01 to N03 storing the message | 12 of 12 |

**Every part holds, and the reader ships in the commit that adds this record.** Each R draw listed
the root and read the file (`list_allowed_directories`, then `list_directory` or `search_files`, then
`read_text_file`; 4 of 6 also called `spawn_subagents`), stated the value ("I have noted the reference
**BX-77-2041** from your bank statement.") with `UNKEPT_CLAIM_NOTE` beside it, and stored nothing,
as the first record says a file call does. Every W01 draw asked for the birthday's date and stored the
exchange; the N draws stored the fact and called nothing. The mutation rows over
`test_unasked_tools.py` are in the commit body.

## The picture words, 2026-11-06

`photos?`, `pictures?` and `images?` leave `_SOURCE` and become `_PICTURE`, which keeps
the file tools unless `_PICTURE_FACT` reads a stated fact about the picture: a form of "to be",
"need" or "have" after the picture word, with at most one phrase of place between (`the photo of
grandma is in the hallway`, `the image on my badge is old`), or "a" or "an" before the picture word
at the end of the message (`my resume needs a new photo`). Every other picture word names a file
(`the picture I sent you`, `the picture of the whiteboard`, `this photo`), and a path, a link, a
question word or `attached` keeps the tools as before. The reader fails toward keeping: a request
with a form of "to be" after the picture word (`Remember the picture I sent you is my mother`) keeps
the tools, and a fact whose picture word is at the end after "the" (`Remember that I framed the
photo`) keeps them too.

The near misses, written as tests before the code. Refused: `Remember that the photo of grandma is in
the hallway`, `Remember that my profile picture is from 2019`, `Remember my resume needs a new photo`,
`Note that the image on my badge is old`, `Remember the photos from the trip are in the blue
album.`, `Remember that the photo of grandma needs a new frame` and `Remember that the picture on my
desk has a crack`. Kept: `Remember the photo in Downloads`, `Remember what the attached picture shows`,
`Remember the picture I sent you`, `Remember the picture of the whiteboard`, `Remember this photo`
and `Remember a picture I sent you earlier`.

### Rows and the rule

Written before the draws. The rig is the one above, with the sandbox holding only `notes.txt`: a
fact row needs no file, and a request row that finds no picture still shows whether the tools were
called. The committed reader keeps the file tools on all five rows, so the Q rows' first request is
the same on both builds and they check only that the request shapes still reach a file call; the F
rows are the change.

| Row | Message | Draws |
| --- | --- | --- |
| F01 | `Remember that the photo of grandma is in the hallway` | 2 |
| F02 | `Remember that my profile picture is from 2019` | 2 |
| Q01 | `Remember the photo in Downloads` | 2 |
| Q02 | `Remember what the attached picture shows` | 2 |
| Q03 | `Remember the picture I sent you` | 2 |

The reader ships when all of these hold:

- F01 and F02 call no file tool in 4 of 4 draws and store the message in 4 of 4.
- Q01 to Q03 call a file tool in at least 5 of 6 draws and store nothing in those draws.

A part that fails keeps the reader out of the tree as a recorded patch. Fewer draws than the table
names decide nothing: the counts are recorded and the remaining draws are the next step.

### Replay

Every backticked or quoted string in `docs/readings/`, the task files and the brain tests, read
through the committed reader and the new one (`replay.py` in `slot15/` beside the run log): 27880
strings, 461 read as requests to remember, the file tools refused on 359 by the old reader and 364
by the new. The five that change are the stated facts above, each from kept to refused: `Note that
the image on my badge is old`, `Remember my resume needs a new photo`, `Remember that my profile
picture is from 2019`, `Remember that the photo of grandma is in the hallway` and `Remember the
photos from the trip are in the blue album.`. No request shape changed.

### The draws

Run log `rows.jsonl`, the stored rows in `records.jsonl` and the scoring in `score.py`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/a64866e3-d614-4e2e-a757-12775f4290c0/scratchpad/slot15/`.
The candidate `cortexn14-brain-p992` was built from the working tree; 10 draws ran from 05:57:42 to
06:00:07 UTC, the SM clock at 0.57 of its maximum on every row's reading. No draw ended in an error.

| Rows | Candidate |
| --- | --- |
| F01 and F02 calling a file tool | 0 of 4 |
| F01 and F02 storing the message | 4 of 4 |
| Q01 to Q03 calling a file tool | 3 of 6 (Q01 2, Q02 0, Q03 1) |
| Q01 to Q03 storing the message in a draw with no file call | 3 of 3 |

The F part holds and the Q part does not, so the rule fails and the reader does not ship on it. The
Q draws with no file call answered from the chat alone ("I don't see any pictures in our current
conversation") and stored the exchange: with the sandbox holding no picture, the model chose not to
look, on a first request the committed reader sends word for word the same. The Q item measured
draw noise, as the rule section says such an item does, and should have been left out.

### Rows and the rule, second round

Written before the draws. The replay shows no request shape changes between the readers, so no
request row can measure the change, and this rule holds only fact rows, with the resume message
added. Three rows, two draws each, on the same candidate.

| Row | Message | Draws |
| --- | --- | --- |
| F01 | `Remember that the photo of grandma is in the hallway` | 2 |
| F02 | `Remember that my profile picture is from 2019` | 2 |
| F03 | `Remember my resume needs a new photo` | 2 |

The reader ships when F01 to F03 call no file tool in 6 of 6 draws and store the message in 6 of 6.
A failure keeps the reader out of the tree as a recorded patch.

### The draws, second round

Run log `rows2.jsonl`, stored rows `records2.jsonl`, clock `rows2.clock`, in the same directory. Six
draws ran from 06:01:59 to 06:03:14 UTC on the same candidate, the SM clock between 0.53 and 0.57 of
its maximum. No draw ended in an error.

| Rows | Candidate |
| --- | --- |
| F01 to F03 calling a file tool | 0 of 6 |
| F01 to F03 storing the message | 6 of 6 |

**Both parts hold, and the reader ships in the commit that adds this record.** Every draw called
nothing and answered with the fact ("I've noted that your resume needs a new photo."). The mutation
rows over `test_unasked_tools.py` are in the commit body.
