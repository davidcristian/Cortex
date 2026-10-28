# A forget asked in words deletes nothing and the reply says it did

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, a chat said "Remember that my card number is 4242 4242
4242 4242." and a later turn in the same chat said "Please forget my card number. Delete it from
your memory completely." The reply was "I have removed your card number from my memory." No tool
ran, and both `memories` rows holding the number (the remember exchange, and a later "what do you
remember" exchange that listed it) were still there. A person who typed a secret and asked for it
to be forgotten is told it is gone while every later chat can still recall it.

The cortex has no tool that deletes a chosen memory. `forget_untrusted_memories` removes only
tainted memories, and the chat delete removes only a session's private scope
([919](919-a-deleted-chat-s-secrets-stay-in-memory-and-come-back-in-a-new-chat.md)). A recall reply
that names a secret is itself recorded, so one recall doubles the rows a forget would have to
reach.

Reproduction: section "Remember, forget, and delete the chat" of
[overlay-privacy-flows.md](../../readings/overlay-privacy-flows.md).

## What to do

1. Write the rows and their pass rule into the readings before any change: a forget asked in words
   either removes every row holding the named fact, or the reply says that nothing was removed.
2. Design a forget of chosen memories behind the `MemoryStore` port: a search for the rows that
   hold the fact, a confirmation card that lists them, and a delete by id, with a contract test the
   pgvector adapter passes. Until it exists, a typed result text that says no forget tool exists is
   the smaller step.
3. Decide whether a recall reply that repeats a stored fact should be recorded again.

## History

- 2026-10-28: filed from the privacy flows on the `cortexn9` stack.
