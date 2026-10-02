# The chaos kill at tier scale

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-02

Blocked on the overlay, for what the user sees and nothing else. Re-scoped 2026-10-02: the kill
itself, and the checks that the cortex comes back, the session survives and the next turn works,
are agent work on the 24 GB card through a client that approves the confirm card, filed as
[R-772](../../refinements/tasks/772-a-headless-client-that-approves-the-handoff-card.md). What stays
here is how the overlay shows a handoff that died.

**What only this proves.** That the user sees an accurate failure. When the deep tier's
`llama-server` dies mid answer or mid load, the panel shows the turn's failure as the stream sends
it, the connection dot follows `Health` (amber while the cortex is down, green once it serves), and
the next turn asked from the overlay works with the chat's history intact.
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) states the procedure and the hard rule it tests;
the CI chaos test over fakes is what `just check` covers.

**Do.** Run it after R-772 has drawn its kill row, so the hard rule is already checked and a failure
here is about the overlay. Approve an escalation in the overlay, then kill the deep child with the
command in [runbooks/model-swap-recovery.md](../../runbooks/model-swap-recovery.md), "The chaos
kill, host-side":

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host sh -c 'kill -9 $(pgrep -f 8081)'
```

Once mid answer and once mid load.

**Pass.** The panel shows the failure without a wedged spinner, the dot returns to green, and the
next turn from the overlay works in the same chat.

**Fail.** A panel that waits forever, a chat that loses its history in the overlay, or a dot that
stays amber once the cortex serves. A lost session or a cortex that does not return is R-772's
finding against the hard rule itself, and the most serious thing either backlog can produce.

**Record it.** In this file's History, and in the same runbook section wherever the overlay shows
the failure differently from what it says.

## History

- 2026-07-19: marked as needing both capabilities, after an audit tried to execute this item and its
  two siblings from the GPU doc alone. The kill itself is a `docker exec` on the card's machine;
  what the other capability supplies is the approved confirm card that puts a handoff in flight.
- 2026-08-04: the deep-model pick closed, which unblocked this item along with the swap, the timings
  and the injection-harness run, leaving the overlay as what still blocks it.
- 2026-10-02: re-scoped to the overlay's view of a killed handoff. The approved card that puts a
  handoff in flight can come from any client holding the `Converse` stream, so the kill and the
  hard-rule checks went to
  [R-772](../../refinements/tasks/772-a-headless-client-that-approves-the-handoff-card.md).
