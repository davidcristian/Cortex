# A delete whose reply is lost after it commits leaves a dead chat open

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-30

`DeleteSession` aborts only when `SessionStore.delete` raises, and the overlay's
`deleteSession` (`useSessionCatalog.ts`) reads that rejection as "the brain still holds it". One
case breaks that reading: Redis commits the delete's transaction and the reply is lost, and every
retry inside the store's budget fails too. The chat is then deleted, with its cleanup pending, while
the overlay keeps it open and listed. Every turn the user sends into it ends as `session_deleted`
(`converse_stream.py`), and the next `ListSessions` drops the row. Nothing is lost: the
`CleanupRepeater` finishes the cleanup. The open chat is the only defect.

This follows from the code and was not reproduced. It needs Redis to go away between `EXEC` and
its reply and stay away for the whole retry budget.

## What to do

1. Decide what the overlay does with a turn that ends as `session_deleted`: most likely drop the
   chat from the list and switch to a new one, as a resolved delete does, so any path that leaves
   a dead chat open recovers on the user's next message.
2. Add a Vitest case for that switch, and record the rule in ADR-0021 decision 11.

## History

- 2026-10-30: filed while closing
  [937](937-a-delete-that-fails-after-the-chat-is-gone-leaves-a-dead-chat-open.md), whose remedy
  covers every failure after the chat delete but not a lost reply from the delete itself.
