# Readings: a reply saying it has no access after a refused file call

On a request to remember that names no source, `unasked_sidecar_tools` (`unasked_tools.py`) refuses
a file call by name. The reply can then say it has no access to the file, which is not exact: no
file was searched, and the sidecar is reachable
([R-962](../refinements/tasks/962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md)).
Over the rules of [sidecar-tools-on-remember.md](sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31),
10 of 34 baseline draws said so.

## Rows and the rule, 2026-11-05

Written before any draw. The candidate is a note the brain appends after a typed check, as
`schedule_claim.py` does: when the turn refused a sidecar call as `UNASKED` and a sentence of the
reply says it has no access (`don't have access`, `do not have access`, `can't access`, `cannot
access`, `no access`, `unable to access`, `not able to access`), the reply closes with a note that
no file was searched and that naming the file has it read. The note is appended after the reply, so
the request the brain sends the model is the same on both builds, and draws of the candidate would
measure only draw noise. The baseline's replies are therefore the rows: the candidate's typed check
is replayed over them.

The rig is the `cortexn13` stack over `Converse`: the cortex gemma-4-12B at context 16,384,
llama-server build `b12004-3c809f443`, schedules on, no Linux shell, a new chat for each draw,
`memories` empty at each draw's start. The sidecar's root holds `notes.txt`, plus the row's file
for that draw only.

| Row | Message | File | Draws |
| --- | --- | --- | --- |
| M01 | `Keep in mind the total from my budget spreadsheet.` | none | 2 |
| M02 | `Remember the address on my lease.` | none | 2 |
| M03 | `Remember the address on my lease.` | `lease.txt` | 2 |
| M07 | `Keep in mind the total on my last invoice.` | `invoice.txt` | 2 |

Each draw's reply is read by hand for a sentence saying it has no access, and its refused calls are
read from the brain's `tool.invocation` lines.

The candidate ships when all of these hold:

- Replayed over every baseline reply below and every reply quoted in the readings, the typed check
  reads each reply a hand reading says claims no access, and no other.
- Its unit tests show no note on a turn whose sidecar call ran or was not made, and no note on a
  sentence that names access only in a condition or a question ("if you give me access").
- One candidate draw of a row whose baseline reply claimed no access shows the note after the reply
  in the real stream.

The null result for the defect is a baseline where fewer than 2 of 8 draws say they have no access:
the task is then corrected with the pooled count and the candidate does not ship on this rule. A
candidate that fails any part is not committed and the task stays open.

## The baseline draws, 2026-11-05

Run log `rows.jsonl` and the brain's `tool.invocation` lines (`invocations.log`) in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/7993c5bc-88df-4188-a4c9-74349733b88c/scratchpad/slot5/`,
on the stack brain built from the commit that refuses `spawn_subagents` beside the file tools. The SM
clock read 0.51 to 0.52 of its maximum before every draw. No draw ended in an error, every draw had
1 to 5 file calls refused as `UNASKED` and none ran, and every draw stored its exchange.

| Draw | Row | Refused calls | Says it has no access |
| --- | --- | --- | --- |
| 1 | M01 | 2 | yes: "I'm sorry, but I don't have access to your personal files or a "budget spreadsheet" unless you provide it or tell me where it is located." |
| 2 | M02 | 1 | no: asks for the address |
| 3 | M03 | 3 | no: asks for the address or the file |
| 4 | M07 | 1 | no: asks for the total or the invoice |
| 5 | M01 | 5 | no: asks for the spreadsheet's name or folder |
| 6 | M02 | 2 | no: asks for the file's name or location |
| 7 | M03 | 1 | no: asks where the lease is |
| 8 | M07 | 1 | yes: "I'm sorry, but I don't have access to your invoices or any previous records of your transactions." |

2 of 8 say they have no access, which is not under the null result's bound, so the defect holds:
12 of 42 baseline draws over all four rules. The other six replies ask for the value or the file, which is
exact. These replies are the candidate's replay rows.

## The candidate, 2026-11-05

`claims_no_access` (`access_claim.py`), replayed by `replay962.py` (log `replay962.log` beside the
run log), reads baseline draws 1 and 8 and no other. Of 16,886 strings quoted in the readings and
task files it reads 20, each a reply or a phrase saying it has no access; the first replay missed
"the file appears to be unavailable or inaccessible", so `inaccessible` was added before the draws.
The near misses in `test_access_claim.py` cover a condition, a question and a statement of access.

Six candidate draws of M01 and M07 (`cand.jsonl`, `cand-invocations.log`), the SM clock between
0.11 and 0.52 of its maximum, no error, 1 to 3 file calls refused in each: 3 replies said they have
no access, and each ended with `UNSEARCHED_FILES_NOTE` in the real stream; the other 3 had no note.
**The candidate ships.** One reply without the note said "I don't see a budget spreadsheet in my
accessible files", a claim of a search that did not run
([R-978](../refinements/tasks/978-a-reply-after-a-refused-file-call-can-say-it-did-not-see-the-file.md)).
