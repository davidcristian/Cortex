# The not-found answer is the one correction the audit records as ok

**Status:** done 2026-09-06
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`read_email` answers a uid that is not there with `_one_text(NOT_FOUND.format(...))` and no
`failed=True`, where both refusals are answered `_one_text(str(correction), failed=True)`
(`brain/packages/email/src/cortex_email/server.py`). `McpToolRegistry` copies `result.isError` into
the `ToolResult` (`cortex_tools/registry.py`), and the audit trail's `ToolInvocation.ok` is the
negation of it (`cortex_core/loop_events.py`). So the three answers a model may have to act on say
the same kind of thing and two of them are recorded failed while the third is recorded `ok`.

Which value is right is a real question. A refused search and a guessed folder are calls the server
declined. A read of a uid that is not there is a call the server ran: the folder opened, the FETCH
was sent, and the answer is that no message has that uid, which is a fact about the mailbox rather
than a fault in the call.

## History

- 2026-09-06: opened by the close of
  [572](572-the-not-found-answer-states-no-correction-where-the-folders-does.md), which made the
  three answers alike in what they say and left them unlike in how they are recorded.
- 2026-09-06: done, by writing the rule down rather than changing the flag. `isError` says whether
  the server ran the call, so the two answers it declined before touching the mailbox are marked and
  the two the mailbox itself answered, a uid it does not hold and a search with no hits, are not.
  The empty search decided it: marking the not-found answer alone would leave that one as the only
  ran-and-empty answer recorded `ok`, and marking both would record an empty mailbox as a tool
  failure. `docs/modules/brain-email.md` has the decision and what a reading over `ok` therefore
  counts, `server.py` a comment at the return, and `test_email_server.py` a test asserting the rule
  across all three answers. The rule is [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
  decision 14. One claim here was wrong: two things downstream read the flag, not one, the audit
  trail's `ToolInvocation.ok` and the `StepOutcome` that `dispatch_round.py` reads off the same
  result, which crosses to the overlay and is applied to the screen-capture tool alone. Neither
  renders anything for an email answer today, so the decision changes nothing that runs, and the
  flipped flag would have written a failed audit line and a false outcome for every read of an
  absent uid. What it left is [591](591-an-ok-audit-line-carries-a-size-where-the-correction-is.md).
