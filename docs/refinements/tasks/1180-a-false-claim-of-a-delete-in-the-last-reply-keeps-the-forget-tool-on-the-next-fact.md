# A false claim of a delete in the last reply keeps the forget tool on the next fact

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool when the model's own text in
the chat's last reply names forgetting, the brain's notes left out (`model_text`,
`reply_notes.py`). When that text claims a delete no call made, the brain appends
`UNFORGOTTEN_CLAIM_NOTE`, so the reply says both that the row was removed and that nothing was
forgotten. The next message then keeps the tool even when it states a fact to keep. On `s9note`,
after `Recuerda que remuevas mi código.` had its call refused and the reply said `He eliminado el
código de mi memoria.` with the claim note, the next message `Recuerda que mi color favorito es el
verde.` had its forget call run; it matched no row, so nothing was lost
([readings](../../readings/forget-unrequested-notes.md#the-draws-2026-11-13)).

## What to do

1. Write tests first: a stated fact after a reply whose claim the brain closed with
   `UNFORGOTTEN_CLAIM_NOTE` refuses the tool, while a reply that claims a delete a call made, or
   asks whether to forget, keeps it.
2. Read the last reply as naming no forget when its claim was the one the claim note corrects,
   by the turn's own record (the note's presence at the end) rather than by a word list.
3. Replay every recorded message and test string with its last reply, and name every change.

## History

- 2026-11-13: filed when a draw of the note for
  [task 1171](1171-a-request-to-remember-an-action-stated-after-que-dass-or-ca-refuses-the-forget-tool.md)
  had its next message's forget call run after a false claim of a delete.
- 2026-11-14: done. `claim_corrected` (`reply_notes.py`) reads the claim note among a reply's
  notes, and `forget_open` then reads that reply's words as naming no forget; a forget run or a
  message asking to forget still opens it. Replay changed only the recorded chain above, now
  refused. Nine live forget turns produced no claim note, so the tests decide
  ([readings](../../readings/forget-open-from-earlier-turns.md#a-reply-the-brain-closed-as-a-false-claim-2026-11-14)).
