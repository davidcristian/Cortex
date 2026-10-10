# Health reads ready with a subagent server down

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Verified:** 2026-10-10

On the Linux shell on 2026-10-10 the default subagent server was killed in the middle of a
delegated turn ([readings](../../readings/delegation-overlay.md#a-subagent-server-killed-during-a-delegated-run)).
The turn ended at once with a reply naming a server error, which is correct. The panel's dot stayed
green through that turn and the summons after it, because `ServingWatch` asks only the session store
and the cortex (ADR-0054 decision 8), and the server stayed exited: `docker kill` counts as a manual
stop under `restart: unless-stopped`. Every delegated turn after that fails the same way while the
dot says the brain is serving.

Reproduction: the stack with the `subagents` override, a delegated turn, then
`docker kill -s KILL <project>-llama-subagent-1` and a summon. `GET /health` on the server's
published port refuses the connection while `Health` answers `ready=true`.

## What to do

Decide whether a down subagent server is a `degraded` state or a note. A turn still answers without
delegation, so `ready=false` overstates it; a `HealthNote` naming the entry and its endpoint, read
from a `ServingProbe` per roster entry, may be the right form. Check what the overlay shows for a
note before choosing.

## History

- 2026-10-10: filed from the delegation flows on the Linux shell.
