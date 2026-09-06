# The not-found answer is the one correction the audit records as ok

**Status:** landed 2026-09-06
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-06 by the close of
[572](572-the-not-found-answer-states-no-correction-where-the-folders-does.md), which gave the
not-found answer a correction and left its `isError` alone.

`read_email` answers a uid that is not there with `_one_text(NOT_FOUND.format(...))` and no
`failed=True`, where both refusals are answered `_one_text(str(correction), failed=True)`
(`brain/packages/email/src/cortex_email/server.py`). `McpToolRegistry` copies `result.isError`
into the `ToolResult` (`cortex_tools/registry.py`), and the audit trail's `ToolInvocation.ok` is
the negation of it (`cortex_core/loop_events.py`). So the three answers a model may have to act
on now say the same kind of thing and two of them are recorded failed while the third is recorded
`ok`.

Which value is right is a real question rather than an oversight. A refused search and a guessed
folder are calls the server declined, and the argument was wrong. A read of a uid that is not
there is a call the server ran: the folder opened, the FETCH was sent, and the answer is that no
message has that uid, which is a fact about the mailbox rather than a fault in the call. Nothing
downstream reads the flag as anything else: the own-text overlay does not read it at all
(`cortex_core/own_text.py`), and the model reads the text.

**What would close it.** Either the flag set to match the other two, with the audit reading
"a correction was sent" and the module contract saying so, or a sentence in the module contract
recording that the not-found answer is deliberately not a failure and what an audit reading over
`ok` therefore counts. Deciding costs less than the reading that discovers it by surprise.

## Trail

- 2026-09-06: opened by the close of
  [572](572-the-not-found-answer-states-no-correction-where-the-folders-does.md), which made the
  three answers alike in what they say and left them unlike in how they are recorded.
- 2026-09-06: landed as the second of the two closes it named. The flag stays off, and what it
  means is now written down: the line `isError` draws is whether the server ran the call, so the
  two answers it declined before touching the mailbox are marked and the two the mailbox itself
  answered, a uid it does not hold and a search with no hits, are not. The empty search is what
  decided it: marking the not-found answer alone would have left that one as the sole
  ran-and-empty answer recorded `ok`, and marking both would record an empty mailbox as a tool
  failure. `docs/modules/brain-email.md` carries the decision and what a reading over `ok`
  therefore counts, `server.py` a comment at the return, and `test_email_server.py` a test pinning
  the line across all three answers. The ADR-0022 addendum of that date carries the mutation
  table.

  One claim here was wrong. Two things downstream read the flag, not one: the audit trail's
  `ToolInvocation.ok`, which the entry names, and the `StepOutcome` that `dispatch_round.py`
  reads off the same result, which crosses the seam as `ToolOutcome` and reaches the overlay,
  where it is applied to the screen-capture tool alone. Neither renders anything for an email
  answer today, so the decision changes nothing that runs, and the flipped flag would have written
  a failed audit line and a false outcome for every read of an absent uid. What it left is
  [591](591-an-ok-audit-line-carries-a-size-where-the-correction-is.md): an `ok` audit line
  carries the result's size and not its text, so a correction recorded `ok` is not readable from
  the trail at all.
