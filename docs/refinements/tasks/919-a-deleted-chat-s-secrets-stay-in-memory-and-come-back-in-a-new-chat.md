# A deleted chat's secrets stay in memory and come back in a new chat

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack with the default `global` memory scope, three chats held a
router password, an API key, a wifi password and a card number, typed by the person. Each
exchange was recorded as a `global` row in `memories`, whether or not the person asked to remember
it. `DeleteSession` on all three removed their Redis keys and left every row: two rows for each
secret. A new chat asked "What is my wifi password?" and the reply was "Your wifi password is
Plum-Lantern-9052."

This is what ADR-0021 decides: under the `global` scope a session's memories are the shared space,
so the cascade removes nothing. The overlay's confirm reads "Delete this chat?", and nothing tells
the person that what the chat taught the assistant stays, so a delete made to remove a secret
leaves it recallable from every later chat.

Reproduction: section "Remember, forget, and delete the chat" of
[overlay-privacy-flows.md](../../readings/overlay-privacy-flows.md).

## What to do

1. Decide between recording the session id beside each `global` memory so the delete can remove the
   rows a chat wrote (a store change behind `MemoryStore`, with its contract test), and saying on
   the confirm that the chat's memories stay. The first is what a person deleting a chat to remove
   a secret expects.
2. Either way, write the decision into ADR-0021 in place of its current global scope paragraph.

## History

- 2026-10-28: filed from the privacy flows on the `cortexn9` stack.
