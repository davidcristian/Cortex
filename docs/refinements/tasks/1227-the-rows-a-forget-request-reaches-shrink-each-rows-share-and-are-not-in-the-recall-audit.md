# The rows a forget request reaches shrink each row's share and are not in the recall audit

**Status:** done 2026-11-26
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

On a request to forget, `with_forget_reach` (`forget_reach.py`) adds up to 5 stored rows to the 5
that recall ranked. On 2026-11-15 unit runs of `assemble_inference_messages` showed four things it
does not do:

- The ten rows share the one `RECALL_CHAR_BUDGET`. Over 300 rows of 900 characters holding `4242`,
  `Forget 4242.` showed each row cut to 600 characters, the ranked rows too, where a turn asking a
  question showed its 5 rows whole. A value past the cut is not in the request.
- The request holds the 5 oldest rows holding the value and no line saying 290 more hold it.
- `MemoryRecaller.recall` writes the `RecallAudit` record before the reach runs, so the record
  does not hold a reached row the model was shown.
- `FORGET_REACH_LIMIT` is its own number, not `DEFAULT_RECALL_K`, which its comment says it equals.

`Can you forget things like 4242?` is read as a request and reaches rows. That costs context only:
the rows are framed as ranked rows are and the tools offered do not change.

## What to do

1. Decide in the origin ADR whether reached rows get their own budget or a share of recall's, and
   test a value past the cut.
2. Add a line to the memory context when more rows hold the value than the request shows.
3. Record the reached rows in the recall audit, behind `RecallAuditSink`.

## History

- 2026-11-15: filed from the audit of the reach beside the defences already there
  ([readings](../../readings/forget-everything-but-call.md#the-reach-beside-the-defences-already-there-2026-11-15)).
- 2026-11-26: the first three findings held in the code. Reached rows keep a share of
  `RECALL_CHAR_BUDGET`, written into the origin ADR with the reason (a second budget would take
  about half the room left for tool steps and the reply), and a test shows a value past a reached
  row's cut is not in the request. The memory context ends with `more_held_note` for each value a
  row the turn does not show also holds, and `RecallAudit.reached` lists the reached rows, which
  the fake, both file sinks and the log line keep. `FORGET_REACH_LIMIT` equals `DEFAULT_RECALL_K`
  today, as its comment says.
