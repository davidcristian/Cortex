# A session read has no recalled context, so there is no partial answer to give

**Status:** open, dead until a consumer
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** A read RPC on `BrainService` that recalls anything at all, meaning a handler that
reads a memory port and composes what it finds into its reply. Today none does, so there is
nothing for a reply to be partial about.

The shape asked for was a session read whose memory cascade will not fit returning the transcript
without it, and a wire that says so, because a transcript missing its recalled context with nothing
declaring the omission cannot be told from a session that recalled nothing.

Re-derived on 2026-08-21, and the mechanism it describes is not in the tree. `GetSessionMessages`
calls `SessionStore.history` and maps the result; it touches no memory port. `SessionMemoryCascade`
reaches exactly one handler, `DeleteSession`, where it is a **write** and not a read, and where the
ordering is already a deliberate decision in the other direction: the session is hard-deleted
first, so a memory failure leaves the chat gone with a self-healing retry cleaning up, rather than
leaving a visible chat whose memories vanished. Dropping that step under time pressure is not a
partial answer, it is the failure mode that ordering exists to produce on purpose.

The recall this shape is really about happens inside a turn, where `MemoryRecaller` composes what
it finds into the prompt. That is behind the `Converse` fence: the stream announces no deadline, so
there is no reading there to decide anything from, and putting one there would be the first half of
enforcing a bound that seam deliberately does not have.

So the shape is not declined on its merits; it has no site. Should a read RPC ever gain a recall
step, the wire question it raises is real and is the interesting half: an omission a reader cannot
see is worse than a refusal, and the seam carries one free-text `detail` per reply, which
[320](320-one-detail-string-two-facts.md) already records as one sentence doing the work of two
facts. Whoever builds the recall builds that at the same time.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which found on re-derivation that this one
  of its three shapes describes a cascade no read path has. Recorded in the ADR-0024 addendum on
  what the announced deadline is worth downstream.
