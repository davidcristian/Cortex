# Paging / cursor on the read RPCs

**Status:** open, fix when it bites
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)
**Trigger:** A list or a single history growing large enough that unary snapshots stop sufficing.

Paging / cursor on `ListSessions` / `GetSessionMessages` if a list or a single history ever
grows large (a cursor field on the same RPCs); unary snapshots suffice at personal scale.
