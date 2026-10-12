# A recall-tainted turn blocks the person's own send

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-10-12

With `CORTEX_MEMORY_ON_TAINTED=record`, a turn whose only untrusted input is a recalled tainted
memory still blocks every tool that needs confirmation, apart from a record card
([ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 8). For `send_email` the
block returns `DENIED_MSG`, which tells the model that a new message giving the address, subject
and body "lets it run without reading anything first". Under recall that is false: the new message
recalls the same tainted row, so the person's own email is blocked in every chat while a related
tainted row exists, and each blocked exchange is stored tainted too. This is the shape
[R-073](073-fence-without-block-recall.md) fixed for a task, where the fix could rest on the
task's structure; a send acts outward on arguments the model writes, so the block stays.

## What to do

Decide what a recall-only block says and offers. Candidates, each a hypothesis: a typed refusal
text, chosen when the stamp's `recalled_only` is set, that names a remembered conversation as the
cause instead of advising a new message; or a way for the person to answer a turn without recall.
Write rows and a pass rule first over a stack with the email sidecar's send path enabled
(`docs/runbooks/` has the Bridge setup), with one row where the person asks for an email after a
tainted recall and one where the recalled text asks for the send.

## History

- 2026-10-12: filed while closing R-073, whose rows had no send path on the stack.
