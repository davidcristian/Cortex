# A delete that fails after the chat is gone leaves a dead chat open

**Status:** done 2026-10-30
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

`session_rpc.delete_session` deletes the chat first, then runs the memory cascade, then
`ScheduleStore.detach_session`. A store error in either later step aborts `DeleteSession` as
`UNAVAILABLE` after the chat is already in the deleted set, and nothing retries the step that
failed (ADR-0021 decision 11 says so). The overlay's `deleteSession` (`useSessionCatalog.ts`) reads
any rejection as "the brain still holds it", keeps the chat open and listed, and since a turn sent to
a deleted chat ends as `session_deleted`, every message the user then sends into it fails. The
next `ListSessions` drops the row, so the user loses the only control that would retry the
cascade, and the chat's memories or scheduled items stay.

Reproduced on 2026-10-29 over fakes: a `BrainService` with a schedule store whose
`detach_session` raises answered `DeleteSession` with `UNAVAILABLE`, after which
`InMemorySessionStore.deleted("chat-1")` was `True` and `ListSessions` returned no rows.

Two remedies do not work. Running the cascade and the detach before the chat delete reopens the
two races ADR-0021 and ADR-0066 close: a turn's memory write and a `schedule_task` add each read
the deleted mark after they commit, so the mark has to commit before the cleanup reads its rows,
and `RedisSessionStore.delete` writes the mark and drops the chat from the list in one
transaction. Answering success and only logging the failed step would report a chat's memories as
deleted while they remain. An overlay retry is lost when the overlay restarts.

## What to do

1. Add a pending cleanup record to the session store port, written in the same transaction as
   the deleted mark and cleared once the cascade and the detach both succeed, with its contract
   test, the Redis adapter and the in-memory fake.
2. Make `delete_session` answer success once the chat delete commits, and repeat each pending
   cleanup until it succeeds (at boot and on a timer beside the serving watch, within the 30 day
   `DELETED_CHAT_HORIZON` after which the deleted mark expires). Record the decision in ADR-0021.
3. The overlay's catch then covers only a failed chat delete, where its comment is true; add a
   Vitest case that a resolved delete switches away even when the brain logged a failed cleanup.

## History

- 2026-10-29: filed from the audit of the delete-time detach of a chat's scheduled items.
- 2026-10-29: checked against `session_rpc.py`, `store.py` and `useSessionCatalog.ts`; the claim
  holds. Ruled out reordering, a logged success and an overlay retry, and set out the pending
  cleanup record as the remedy. Left open: the build needs a port change.
- 2026-10-30: done as set out, with no proto change. `SessionStore.delete` adds the chat to
  `cortex:sessions:cleanup` in the transaction that writes its deleted mark, and `pending_cleanups`
  and `clear_cleanup` read and clear it, under the contract suite and a live run on a throwaway
  `redis:8-alpine`. `delete_session` now aborts only on a failed chat delete; `finish_cleanup` runs
  the cascade, the detach and the clear, and `CleanupRepeater`, started before `serve`, repeats a
  failed one at once and every 60 s. The record has no age limit, since a cleanup after the
  horizon is still safe. The filed reproduction now answers success with the chat in
  `pending_cleanups`. Step 3 needed no overlay change: a rejection now means the chat delete
  failed, which is what the catch's comment says, and the existing Vitest case for deleting the
  open chat already checks that a resolved delete switches away. ADR-0021 decision 11 states it.
