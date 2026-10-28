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

1. The rows F1 to F5 and their pass rule are in
   [forget-chosen-memories.md](../../readings/forget-chosen-memories.md), written before any change.
2. The delete is built: `MemoryStore.delete_ids` on the fake and the pgvector adapter, with the
   shared contract and a live lock test ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)).
3. The search is built: `MemoryStore.find_text` returns the rows whose text contains a fact, case
   ignored, oldest first, checked by the same contract (ADR-0075 says why a literal match).
4. Build the tool: the confirmation card lists the matched rows' texts, written by the tool, and the
   delete removes exactly the ids the card showed. The ids must pass from the card to the invoke
   without a second search, since a row committed in between was never shown. After the delete,
   search again and report the rows that still match, never "removed" while a row holds the fact.
5. Register it beside `forget_untrusted_memories`, update the module doc and the runbook, rebuild
   the brain from HEAD and run F1 to F5 on the stack.
6. Decide whether a recall reply that repeats a stored fact should be recorded again.

## History

- 2026-10-28: filed from the privacy flows on the `cortexn9` stack.
- 2026-10-28: rows and pass rule written; the delete by id built behind the port and checked live
  on the stack's Postgres, then the text search the same way. The tool and the stack rows remain;
  `cortex_memory/store.py` is at 298 of 300 lines, so the next verb splits it first.
