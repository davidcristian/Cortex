# A delete that fails after the chat is gone leaves a dead chat open

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-29

`session_rpc.delete_session` deletes the chat first, then runs the memory cascade, then
`ScheduleStore.detach_session`. A store error in either later step aborts `DeleteSession` as
`UNAVAILABLE` after the chat is already in the deleted set. ADR-0021 decision 11 says "a retry
completes", but nothing retries: the overlay's `deleteSession` (`useSessionCatalog.ts`) reads any
rejection as "the brain still holds it", keeps the chat open and listed, and since a turn sent to
a deleted chat ends as `session_deleted`, every message the user then sends into it fails. The
next `ListSessions` drops the row, so the user loses the only control that would retry the
cascade, and the chat's memories or scheduled items stay.

Reproduced on 2026-10-29 over fakes: a `BrainService` with a schedule store whose
`detach_session` raises answered `DeleteSession` with `UNAVAILABLE`, after which
`InMemorySessionStore.deleted("chat-1")` was `True` and `ListSessions` returned no rows.

## What to do

1. Decide in ADR-0021 who finishes a delete whose later step failed. Candidates: the brain keeps
   the cleanup pending in the store beside the deleted set and repeats it until it succeeds, so
   `DeleteSession` answers once the chat is gone; or the reply names the failed step and the
   overlay drops the chat and retries the delete by id.
2. Make the overlay's failure path match that decision, with a Vitest case for a rejection that
   follows a completed chat delete.

## History

- 2026-10-29: filed from the audit of the delete-time detach of a chat's scheduled items.
