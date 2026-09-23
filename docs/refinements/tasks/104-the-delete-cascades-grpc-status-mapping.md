# The delete cascade's gRPC status mapping

**Status:** done 2026-08-20
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The data-defect close ([R-103](103-memory-data-error.md)) drew its boundary at the two core
catches a turn goes through and left the third call site alone. `SessionServicer.DeleteSession`
caught `(SessionStoreError, MemoryStoreError)` and aborted `UNAVAILABLE`, which the narrower
subclass inherits, so a cascade whose `delete_scope` met a `DELETE` command tag it could not
parse told the body to try again later about the one condition no retry improves.
`MemoryDataError` is now named ahead of that catch and aborts `INTERNAL`, leaving every other
failure on the method as it was.

The path is real and was traced end to end before the fix: `PgVectorMemoryStore.delete_scope`
raises `MemoryDataError` from its `ValueError` catch, `SessionMemoryCascade.delete_session_memories`
calls it under session scoping, and `session_rpc.delete_session` calls that from the servicer.

Two of the entry's claims were wrong. It said the work included how the body reads the two codes:
it does not distinguish them, and there is nothing to do there, since `is_transient` treats only
`Rpc { code: "Unavailable" }` as retryable and `RpcMethod::DeleteSession` is classified
non-repeatable anyway. It said the overlay would offer a retry for it; `body/app/src` has no
per-code retry control at all. So this is an accurate label and symmetry with the two core
catches rather than a behaviour change, and it is worth having for what an operator reads:
`UNAVAILABLE` sends them looking for a Postgres that is down, and on this condition nothing is
down to find.

The trigger's second half, the next status mapping to be widened for a narrowed error, has a home
of its own in [R-297](297-cut-tool-call-fails-the-cortex-turn.md), which asks the same question
about `MalformedToolCallError` on the turn path.

## History

- 2026-08-11: Opened by the data-defect close as the third call site that close deliberately left
  alone, and the area's count held at 8 by exchange.
- 2026-08-20: Shipped, with the entry's framing corrected: the body and the overlay were both
  already right, so what changed is the label alone. Stated in ADR-0008 decision 13.
