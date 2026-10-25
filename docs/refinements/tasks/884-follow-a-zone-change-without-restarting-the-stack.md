# Follow a zone change without restarting the stack

**Status:** open, waiting for its trigger
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 5
**Trigger:** a reminder fires at the wrong local time after the person's machine changed zone
while the stack ran, or the stack runs on a machine other than the body's.
**Verified:** 2026-10-25

The stack recipes read the host's zone once, when the stack starts, and pass it to the brain as
`CORTEX_SCHEDULE_TZ`. A laptop that moves to another zone keeps rendering and reading bare times
in the old one until the brain is recreated, and a brain on another machine reads that machine's
zone, not the person's.

## What to do

The body reports the host's IANA zone over `proto/body.proto`, and the brain uses it when
`CORTEX_SCHEDULE_TZ` is unset. The zone is then state the brain receives per connection, so:

1. Add the zone to a body to brain message, and have the body send it on connect and when the OS
   reports a change (an IANA name lookup on Windows, a new crate, so the Tauri shell's lock file
   and `just check-shell` change too).
2. Store it behind the `SessionStore` port, and have the schedule built-ins and the ticker read it
   on each use instead of the startup `DisplayZone`, keeping one zone for creation and the next
   occurrence.
3. Fall back to the startup zone before the body has connected.
4. File the Windows validation under `docs/host/tasks/`.

## History

- 2026-10-16: filed when the stack recipes started passing the host's zone (ADR-0065 decision 5).
- 2026-10-25: checked again and not fired: nothing records a reminder at the wrong local time after
  a zone change, and the proto still has no zone field.
