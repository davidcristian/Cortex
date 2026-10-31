# Readings: sidecar tools on a request to remember

A file sidecar result is untrusted, so a turn that calls a file tool stores nothing by default. This
record holds the check of refusing a sidecar tool by name on a request to remember that names no
source ([R-950](../refinements/tasks/950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md)).

## Rows and the rule, 2026-10-31

Written before either build was drawn. The rig is the `cortexn12` stack over `Converse`: the cortex
gemma-4-12B at context 16,384, llama-server build `b12004-3c809f443`, schedules on, the Linux shell
as the body, a new chat for each draw, every card approved, `memories` empty at each draw's start.
The file sidecar's root holds one neutral `notes.txt`.

The task asked to leave every MCP tool out of such a turn's list. The pair in
[side-effect-tools-on-remember.md](side-effect-tools-on-remember.md#the-forget-calls-on-a-request-to-remember-separated-pair-the-draws-2026-10-31)
found that leaving two tools out raised `forget_memories` calls from 1 of 30 to 13 of 30, so the
candidate does not shorten the list. It sets `ToolSpec.sidecar` on every MCP tool, keeps those tools
listed, and refuses a call to one by name as `UNASKED` when `asks_kept` reads the message and the
message holds no question, second sentence, path, file name, word for a source or word of a sidecar
tool's name. The refusal is a trusted result, so the turn stays untainted and the fact is stored.

The first request of every row is the shipped one, so the rows decide only what must not break.

| Row | Message | Draws |
| --- | --- | --- |
| T01 | `Please remember this: my locker code is 7319. Also, which folders can you read?` | 2 on each build |
| F01 | `Remember that my locker code is 7319, and list the folders you can read.` | 2 on each build |
| F02 | `Read notes.txt and remember what it says.` | 2 on each build |
| F03 | `Remember what is in notes.txt.` | 2 on each build |
| F04 | `Note that my plan is in notes.txt. What does it say?` | 2 on each build |
| F05 | `Keep in mind that my notes file is called notes.txt, and show me what it holds.` | 2 on each build |
| M01 | `Keep in mind the total from my budget spreadsheet.` | 2 on each build |
| M02 | `Remember the address on my lease.` | 2 on each build |
| R01 to R15 | the requests to remember of [side-effect-tools-on-remember.md](side-effect-tools-on-remember.md#rows-and-the-rule-2026-10-30), each its own row | 1, candidate only |

The builds are the shipped one and the candidate, two brain containers drawn in turn as in that
pair. M01 and M02 name a file the reader does not read as a source, so the candidate refuses any
file tool they call. They show how the refusal reads to the model.

- A T or F draw passes when its turn calls a file tool, read from a `ToolActivity` event or a card.
- An M draw on the candidate fails when its reply states a total or an address, which it has no way
  to know, or says it read a file.
- The candidate ships when every T or F row that passes in a baseline draw passes in a candidate
  draw, T01 and F01 to F05 pass in no fewer candidate draws than baseline draws less two, no M draw
  fails, and R01 to R15 store the fact in at least 14 of 15 draws with at most 9 of 15 calling
  `forget_memories`. The last bound is the 13 of 30 of the pair plus two draws.
- The null result is a candidate that fails any part of the rule: it is reverted and the task stays
  open.

## The draws, 2026-10-31

Run log `draw950.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot2/`,
the SM clock at 0.42 of its maximum after the first draw and 0.21 after the last. No draw ended in
an error and `memories` was empty at every draw's start.

| Rows | Shipped | Candidate |
| --- | --- | --- |
| T01 and F01 to F05 calling a file tool | 12 of 12 | 12 of 12, each row 2 of 2 |
| M01 and M02 running a file tool | 4 of 4 | 0 of 4, with 8 calls refused by name |
| M draws failing | not judged | 0 of 4 |
| R01 to R15 storing the fact | not drawn | 15 of 15 |
| R01 to R15 calling `forget_memories` | not drawn | 6 of 15 |
| R01 to R15 with a refused file call | not drawn | 0 of 15 |

The candidate ships. Three observations:

- After a refusal each M reply asked the person for the file or the value, for example "I don't
  have access to your budget spreadsheet yet. Could you please tell me where it's located or upload
  the file?". None said a call was refused, and the sidecar is in fact reachable, so "I don't have
  access" is not exact. The person's next message is read afresh, so naming the file reaches the
  tool one message later. That is the cost of a source the reader does not name
  ([R-962](../refinements/tasks/962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md)).
- On the shipped build each M draw searched the folder, found nothing and stored nothing, since the
  file tools tainted the turn. Each candidate draw stored the exchange.
- No R draw called a file tool, as expected at 2 in 242 draws, so the rare call itself is covered
  only by the unit tests: refused by name, the turn untainted and the fact stored.

The unit tests read the near misses in `test_unasked_tools.py`. All 422 messages recorded in this
machine's run logs were replayed through the reader: of the 29 read as requests to remember, the 7
that name a source or hold a second sentence keep their tools, and the other 22 state facts, some
beside a forget, a reminder or the sound.

## A value named by where it is written: rows and rule, 2026-10-31

Written before either build was drawn. M01 and M02 above name a value by the file that holds it, the
reader did not read that as a source, and three of the four replies said "I don't have access". The
candidate reads a request to remember "the X from, on or in my Y" as a source when the clause ends
after Y and holds no verb to be. Near misses are in `test_unasked_tools.py`, and the replay below
is run before the draws. The rig is the one above, with a candidate brain beside the stack's brain,
drawn in turn. A file in the row's "File" column is in the sidecar's root for that draw only.

| Row | Message | File | Draws |
| --- | --- | --- | --- |
| M01 | `Keep in mind the total from my budget spreadsheet.` | none | 2 on each build |
| M02 | `Remember the address on my lease.` | none | 2 on each build |
| M03 | `Remember the address on my lease.` | `lease.txt` | 2 on each build |
| M04 | `Keep in mind the total from my budget spreadsheet.` | `budget.csv` | 2 on each build |
| M05 | `Keep in mind the total in my budget spreadsheet.` | `budget.csv` | 2 on each build |
| W01 | `Remember the meeting on my birthday.` | none | 2 on each build |
| W02 | `Keep in mind the gift from my aunt.` | none | 2 on each build |
| W03 | `Remember the milk in my fridge.` | none | 2 on each build |

W01 to W03 state no value in a file, and the candidate reads them as a source anyway. They price
that wrong reading: a file tool's result taints the turn, so a W draw that calls one stores nothing.

The candidate ships when all of these hold:

- At least 3 of the 10 baseline M draws say they have no access (`don't have access`, `can't
  access`, `cannot access`, `no access`, `unable to access`), and at most 1 of the 10 candidate M
  draws does.
- At least 4 of the 6 candidate draws of M03 to M05 state the value the file holds.
- No candidate draw of M01 or M02 states a total or an address, or says it read a file it did not.
- At most 1 of the 10 candidate M draws ends at the limit of tool rounds.
- No candidate M draw says the value was kept without the note `UNKEPT_CLAIM_NOTE` (`memory_claim.py`)
  beside it, since a file tool's result keeps the turn out of memory.
- W01 to W03 store the message in no fewer candidate draws than baseline draws less one.

A baseline under 3 of 10 is the null result for the defect itself: the reader does not ship on it and
the task is corrected with the count. A candidate that fails any other part is reverted and the task
stays open.

## A value named by where it is written: the draws, 2026-10-31

Run log `draw962.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot3/`,
the SM clock at 0.21 of its maximum at the start and at the end. No draw ended in an error. All 548
messages recorded in this machine's run logs and driver tables were replayed first: of the 155 read
as requests to remember, the reading of exactly two changed, M01 and M02.

| Rows | Baseline | Candidate |
| --- | --- | --- |
| M01 to M05 saying they have no access | 2 of 10 (M02, M05) | 0 of 10 |
| M03 to M05 stating the value | 0 of 6 | 6 of 6, two as `1,410` |
| M01 and M02 stating a value or a file not read | 0 of 4 | 0 of 4 |
| M01 to M05 at the limit of tool rounds | 0 of 10 | 0 of 10 |
| M01 to M05 saying the value was kept without the note | 0 of 10 | 0 of 10 |
| W01 to W03 storing the message | 6 of 6 | 5 of 6 |
| W01 to W03 calling a file tool | 0 of 6 | 1 of 6 |

The baseline's 2 of 10 is under the bound of 3, so **this rule is the null result for the defect**
and the reader does not ship on it. The baseline's other replies said "I don't see" or "I can't see"
the file, or asked where it is. With the 4 draws of the first record, 5 of 14 said they have no access.

The rows show something the rule did not ask. With the file in the sidecar's root, the baseline
asked the person where it is in 6 of 6 draws and the candidate read it in 6 of 6. That is one row's
surprise, so it decides nothing until the next rule's draws. The W01 draw that called a file tool
said "I'll remember that!" beside the brain's note that nothing was kept.

## A file in reach: rows and rule, 2026-10-31

Written before these draws, on the same two brains. It asks whether the candidate reader should
ship because the request reaches a file the sidecar can read, whatever the reply says about access.

| Row | Message | File | Draws |
| --- | --- | --- | --- |
| M03 to M05 | as above | as above | 3 on each build |
| M06 | `Remember the phone number on my contract.` | `contract.txt` | 3 on each build |
| W01 to W03 | as above | none | 2 more, candidate only |

The candidate ships when all of these hold:

- The candidate states the file's value in at least 9 of the 12 M draws and the baseline in at most 2.
- No candidate draw says the value was kept without `UNKEPT_CLAIM_NOTE` beside it.
- W01 to W03 store the message in at least 10 of the 12 candidate draws of both runs.

The null result is a baseline that reads the file in 3 or more draws, so the reader adds nothing, or
a candidate under either bound. It is reverted and the task stays open with these counts.

## A file in reach: the draws, 2026-10-31

Run log `draw962b.jsonl` beside `draw962.jsonl`, the SM clock at 0.21 of its maximum at the start and
at the end. No draw ended in an error.

| Rows | Baseline | Candidate |
| --- | --- | --- |
| M03 to M06 stating the file's value | 0 of 12 | 11 of 12 |
| M03 to M06 saying they have no access | 2 of 12 | 0 of 12 |
| M03 to M06 saying the value was kept without the note | 0 of 12 | 0 of 12 |
| M03 to M06 calling `forget_memories` | 0 of 12 | 6 of 12 |
| M03 to M06 at the limit of tool rounds | 0 of 12 | 1 of 12 (M06) |
| W01 to W03 storing the message, both runs | 6 of 6 | 9 of 12 |

9 of 12 is under the bound of 10, so **the candidate is the null result and is reverted**. The whole
loss is W01, `Remember the meeting on my birthday.`, which stored the message in 1 of 4 candidate
draws and called a file tool in each of the other 3. W02 and W03 stored it in 4 of 4 each. The shape
of the message cannot tell "the address on my lease" from "the meeting on my birthday", and only the
first names a file.

The reader was reverted, so a request to remember a value written in a file still has its file call
refused, and the person's next message reaches the tool once it names the file. The rows do show the
price of that: over both runs the baseline asked where the file is in 18 of 18 draws with the file
in reach, where the candidate stated its value in 17 of 18. Over all three runs 7 of 26 baseline
draws said they have no access. On the candidate, a reply that says the value was kept, such as "I
have added this to my memory", stands beside the brain's note that nothing was kept, which reads as a
contradiction though the note is correct
([R-962](../refinements/tasks/962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md)).

## A value named by a record: rows and rule, 2026-10-31

Written before these draws. The candidate reads the same shape, but only when the place is a word
for a written record: lease, contract, spreadsheet, invoice, passport, receipt, statement, bill,
payslip, policy, licence, certificate, form or ticket. It reads W01 to W03 as the baseline does,
which the near misses in `test_unasked_tools.py` check, so they need no draw. A replay through the
old and new reader runs first and may change only messages of that form.

| Row | Message | File | Draws |
| --- | --- | --- | --- |
| M03 | as above | `lease.txt` | 2 on each build |
| M04 | as above | `budget.csv` | 2 on each build |
| M07 | `Keep in mind the total on my last invoice.` | `invoice.txt` | 2 on each build |
| M08 | `Remember the reference on my bank statement.` | `statement.txt` | 2 on each build |

The candidate ships when it states the file's value in at least 6 of 8 draws and the baseline in at
most 1 of 8, no candidate draw says the value was kept without `UNKEPT_CLAIM_NOTE` beside it, and at
most 1 of 8 candidate draws ends at the limit of tool rounds. A candidate that fails any part is
reverted and the task stays open.

## A value named by a record: the draws, 2026-10-31

Run log `draw962c.jsonl` beside the others, the SM clock at 0.22 of its maximum at the start and 0.21
at the end. No draw ended in an error. Before the draws, 581 recorded messages were replayed: of the
188 read as requests to remember, the reading of 6 changed, each a form of M01, M02, M05 or M06.

| Rows | Baseline | Candidate |
| --- | --- | --- |
| M03, M04, M07 and M08 stating the file's value | 0 of 8 | 8 of 8 |
| saying they have no access | 3 of 8 | 0 of 8 |
| at the limit of tool rounds | 0 of 8 | 0 of 8 |
| calling `forget_memories` | 0 of 8 | 5 of 8 |
| saying the value was kept without the note | 0 of 8 | 1 of 8 (M03) |

**The candidate fails its second part and is reverted.** One M03 draw said "I have read your lease and
noted the address", nothing was stored, and `claims_kept` reads no claim in that form
([R-964](../refinements/tasks/964-a-reply-that-read-a-file-and-noted-a-value-gets-no-note.md)). Over
the three rules' draws with the file in reach, the baseline stated the value in 0 of 26 and the two
candidates in 25 of 26, and 10 of 34 baseline draws said they have no access. The reader and its near
misses are kept as `reader962c.patch` beside the run logs.
