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
`_SOURCE`, so the reader kept the file tools on it before this change. That wrong keep is task 992.

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
