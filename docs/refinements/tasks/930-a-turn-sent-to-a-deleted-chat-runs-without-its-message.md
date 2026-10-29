# A turn sent to a deleted chat runs without its message

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-29

A deleted chat's id stays in `cortex:sessions:deleted`, and `SessionStore.append` stores nothing for
it. `TurnEngine.handle_turn` appends the user's message and then builds the prompt from
`history`, so a turn a client sends to a chat it already deleted reads an empty history and the
model is asked with no user message at all. The overlay does not do this: deleting the open chat
moves it to a new chat id. A client that keeps an old id, such as a `Converse` driver or a second
body, does.

## What to do

1. Decide in ADR-0021 decision 11 what a turn sent to a deleted chat gets: a typed refusal before
   any inference (a `SessionDeletedError` the stream reports with its own error code), or an answer
   built from the message alone that stores nothing.
2. Build it in the engine and the deep phase, with a test on the fake store, and one `Converse` row
   on the stack: a turn to a deleted id gets the decided result and the chat stays deleted.

## History

- 2026-10-29: filed from the deleted-set build in
  [925](925-a-chat-deleted-while-its-turn-runs-comes-back.md), which made an append to a deleted
  chat store nothing.
