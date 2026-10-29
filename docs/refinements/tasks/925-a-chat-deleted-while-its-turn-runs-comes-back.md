# A chat deleted while its turn runs comes back

**Status:** done 2026-10-29
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

`DeleteSession` (`session_rpc.py`) deletes the chat and then the memories it wrote, and does not
wait for a turn in flight in that chat. On the `cortexn9` stack a chat deleted while the cortex was
writing came back in the chat list holding only the reply, and its exchange was stored as a
`memories` row the cascade had missed. Two `psql` sessions show the same window in the store: the
delete holds only against a turn that recalled a row it removes
([readings](../../readings/deleted-chat-on-disk.md#a-delete-while-the-chats-turn-runs)). A secret
typed into a chat that is deleted at once can so stay in memory and be recalled in any chat.

`RedisSessionStore.append` (`append_once`) writes the reply and adds the chat to the index whether
or not the chat still exists, and `record_exchange` stores with no check either.

## What to do

1. Decide in the ADR how a delete meets a turn in flight in its chat: stop the turn and wait for it
   to end before deleting, or leave a marker of the deleted chat that an append and a record check,
   with the window between that check and the write named.
2. Build it behind the `SessionStore` and `MemoryStore` contracts, with a contract test for an
   append to a deleted chat and the `psql` rows of the readings as the live check.

## History

- 2026-10-28: filed from the second audit, with a stack row and four `psql` rows.
- 2026-10-29: reproduced on the `cortexn10` stack (2 of 2 draws brought the chat back with a memory
  row) and with `psql` R1 and R4, then done: a delete adds the chat's id to
  `cortex:sessions:deleted`, an `append`, `set_title` or `set_recap` to a deleted chat stores
  nothing, and `record_exchange` reads the set before recording and after the row commits, removing
  a row stored for a chat deleted meanwhile (ADR-0021 decision 11). 0 of 4 draws kept the chat or
  a row ([readings](../../readings/deleted-chat-on-disk.md#the-deleted-set-2026-10-29)).
