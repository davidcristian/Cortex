# The chaos kill at tier scale

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Blocked on the tier-scale swap. Tag **W+G**, corrected 2026-07-19, for that item's reason and one of
its own: there is no handoff to kill in the middle of until a confirm card has been approved, and
the ADR's own procedure says to verify from the overlay. The kill itself is a `docker exec` on the
card's machine; what the overlay supplies is the turn that is in flight when it happens and the
failure the user sees.

**What only this proves.** That the one hard rule holds when a real 31B process dies, not a 2B
stand-in. [ADR-0030](../../adr/ADR-0030-brain-handoff.md) states the procedure: on the 24 GB
machine, `docker exec` into `model-host` and `kill -9` the brain's `llama-server` child mid-handoff
and once mid-load, then verify from the overlay that the turn fails clearly, the cortex comes back,
and the next turn works, with the procedure and expected timings recorded in
[runbooks/model-swap.md](../../runbooks/model-swap.md). CI has no GPU and the older 8 GB dev card
could not hold the 12B cortex and a 31B brain, so the tier-scale swap can only be validated on the
host; the CI chaos test over fakes is what `just check` covers.

**Do.** [runbooks/model-swap.md](../../runbooks/model-swap.md), "The chaos kill, host-side", which
has the exact command:

```
docker compose --project-directory . -f docker/docker-compose.yml \
  -f docker/docker-compose.gpu.yml exec model-host sh -c 'kill -9 $(pgrep -f 8081)'
```

Once mid answer and once mid load.

**Pass.** The turn fails clearly on the stream, the cortex comes back (the swap back is a
`finally`), and the next turn works.

**Fail.** A wedged stream, a lost session, or a cortex that does not return. Any of those is a
finding against the hard rule itself and is the most serious thing this directory can produce.

**Record it.** The same runbook section and readings record, and ADR-0030 edited in place where the
run changes what it states.

## History

- 2026-07-19: marked as needing both capabilities, after an audit tried to execute this item and its
  two siblings from the GPU doc alone. The kill itself is a `docker exec` on the card's machine;
  what the other capability supplies is the approved confirm card that puts a handoff in flight.
- 2026-08-04: the deep-model pick closed, which unblocked this item along with the swap, the timings
  and the injection-harness run, leaving the overlay as what still blocks it.
