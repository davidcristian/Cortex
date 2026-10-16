# The default display zone is UTC on a host that is not

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-10-16

`CORTEX_SCHEDULE_TZ` defaults to `UTC` in `docker/docker-compose.yml`, and no recipe or check sets
it from the host. On a host in `Europe/Berlin` the model is told the time in UTC and writes UTC
times, so "today at 23:00" fires at 01:00 CEST the next day, and "tomorrow at 9" asked at 00:30
CEST fires at 11:00 on the day the person calls today. The overlay shows no times, so nothing the
person sees reveals the offset until the reminder arrives two hours late
([readings](../../readings/schedule-time-edges.md#t3-the-zone-chain-on-the-default-deployment)).

## Reproduction

On a stack started without `CORTEX_SCHEDULE_TZ` on a host whose zone is not UTC, ask the overlay
"Remind me today at 23:00 to check the oven." and read `due_at` from `cortex:schedule:<id>` in
Redis: it is 23:00 UTC. Row C of the readings shows the "tomorrow" case with a fixed clock.

## What to do

Make the host's zone reach the brain without a manual step. Two shapes, to be decided in ADR-0065:

1. The `just` recipes that start the stack export `CORTEX_SCHEDULE_TZ` from the host when it is
   unset (`timedatectl show -p Timezone --value`, else `/etc/timezone`), and the brain logs the zone
   it renders in at startup. Small, but a stack started with plain `docker compose` keeps UTC.
2. The body reports the host's IANA zone over `proto/body.proto` when it connects, and the brain
   uses it when `CORTEX_SCHEDULE_TZ` is unset. This follows the person's machine, also on Windows,
   where the body runs, but the ticker and a turn made before the body connects need a fallback.

Either way, keep UTC rendering for an unset zone only where the host's zone is unknown.

## History

- 2026-10-16: filed from the time edge flows on the shared stack.
