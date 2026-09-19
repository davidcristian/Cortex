# Auto-restore the most recent chat on cold start

**Status:** done 2026-07-12
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

A new reducer action, `adoptSession` in `sessionState.ts`, loads `sessions[0]`'s history like
`openSession` but keeps the current mode, so the panel does not appear. It is guarded on an explicit
`touched` flag, because a `seq` or `messages` check cannot tell an explicit new chat from a fresh
boot: `newChat` leaves both untouched. Only an untouched overlay adopts, so a racing summon, submit,
cycle or explicit new chat wins, and StrictMode's double render is harmless. The hook tries once per
mount, and a failed history load leaves the fresh chat in place.

Covered at 100%, and checked in the browser in both themes against the demo bridge.

## History

- 2026-07-12: Closed with the cold-start restore.
