# Auto-restore the most-recent chat on cold start

**Status:** landed 2026-07-12
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

A new reducer action
(`adoptSession`, in the line-cap-driven `sessionState.ts` split) hydrates `sessions[0]`'s
history like `openSession` but mode-preserving (no panel pop) and guarded in the reducer on
an explicit `touched` flag (a `seq`/`messages` proxy cannot tell an explicit new chat from a
pristine boot, since `newChat` leaves both pristine): only an untouched overlay adopts, so a
racing summon, submit, cycle, or explicit new-chat wins and StrictMode's double-fire is
idempotent; the hook attempts once per mount and a failed history load leaves the fresh chat.
Gated at 100%; browser-validated in both themes against the demo bridge.
