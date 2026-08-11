# The delete cascade's seam mapping

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** The first data defect met on the cascade, or the next seam mapping to be widened.

The close
drew its line at the two core catches a turn goes through and left the third call site alone:
`SessionServicer.DeleteSession` catches `(SessionStoreError, MemoryStoreError)` and aborts
`UNAVAILABLE`, which the new subclass inherits. So a cascade whose `delete_scope` met a `DELETE`
command tag it could not parse would tell the body to try again later about the one condition no
retry improves, and the overlay would offer a retry for it. The fix is the same move one layer
out, a narrower `except MemoryDataError` ahead of that one aborting `INTERNAL`, plus the body's
reading of the code if it distinguishes them. It is small and it is deliberately not in the
close, whose evidence was all on the read path: the delete path already fails loudly, so what is
wrong here is the label on a failure the user does see rather than a failure they do not.
**Trigger:** the first data defect met on the cascade, or the next seam mapping to be widened
for a narrowed error, since one pass over both is cheaper than two.

## Trail

- 2026-08-11: Opened by the data-defect close as the third call site that close deliberately left
  alone, and the area's count held at 8 by exchange rather than by standing still. The index reads
  it as a cascade that meets an undecodable reply and offers the user a retry for the one condition
  no retry improves.
