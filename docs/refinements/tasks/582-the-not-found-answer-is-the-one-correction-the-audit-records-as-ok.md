# The not-found answer is the one correction the audit records as ok

**Status:** open, fix when it bites
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Trigger:** a reading over the tool audit that counts how often a turn was corrected, or a
runbook that tells an operator to find corrections by the audit row's `ok` field.

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
