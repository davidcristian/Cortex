# The delete cascade's seam mapping

**Status:** landed 2026-08-20
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The data-defect close drew its line at the two core catches a turn goes through and left the third
call site alone: `SessionServicer.DeleteSession` caught `(SessionStoreError, MemoryStoreError)` and
aborted `UNAVAILABLE`, which the narrower subclass inherits. So a cascade whose `delete_scope` met
a `DELETE` command tag it could not parse told the body to try again later about the one condition
no retry improves. `MemoryDataError` is now named ahead of that catch and aborts `INTERNAL`, the
same move one layer out, leaving every other failure on the method reading exactly as it did.

The path is real and was traced end to end before the fix: `PgVectorMemoryStore.delete_scope`
raises `MemoryDataError` from its `ValueError` catch, `SessionMemoryCascade.delete_session_memories`
calls it under session scoping, and `session_rpc.delete_session` calls that from the servicer.

**Two things this entry claimed that are not true**, both checked against the code rather than
argued about. It said the work included the body's reading of the code if it distinguishes them: it
does not, and there is nothing to do there. `is_transient` treats only `Rpc { code: "Unavailable" }`
as retryable, and `SeamMethod::DeleteSession` is classified non-repeatable besides, so the
transport never repeated this call under either code and cannot. It said the overlay would offer a
retry for it; `body/app/src` carries no per-code retry affordance at all. So this is an honest label
and symmetry with the two core catches, not a behaviour change, and it is worth having for what an
operator reads: `UNAVAILABLE` sends them after a Postgres that is down, and on this condition
nothing is down to find.

The trigger's second half, the next seam mapping to be widened for a narrowed error, already has a
home of its own in [R-297](297-cut-tool-call-fails-the-cortex-turn.md), which is the same question
asked about `MalformedToolCallError` on the turn path. Nothing new is filed here.

## Trail

- 2026-08-11: Opened by the data-defect close as the third call site that close deliberately left
  alone, and the area's count held at 8 by exchange rather than by standing still. The index reads
  it as a cascade that meets an undecodable reply and offers the user a retry for the one condition
  no retry improves.
- 2026-08-20: Landed, with the entry's own framing corrected: the body and the overlay both turned
  out to be already right, so what changed is the label alone. Recorded in the ADR-0008
  delete-cascade-code addendum.
