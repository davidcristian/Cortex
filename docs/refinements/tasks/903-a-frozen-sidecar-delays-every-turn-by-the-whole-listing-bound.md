# A frozen sidecar delays every turn by the whole listing bound

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Every turn lists each sidecar's tools before the first model call, and `BoundedToolRegistry`
gives that listing the same bound as a call, `CORTEX_TOOLS_CALL_TIMEOUT_S` (60 s by default),
though a healthy listing takes 146 ms ([tools-mcp.md](../../runbooks/tools-mcp.md)). A sidecar
that keeps its socket open but does not answer makes every turn wait the whole bound, including a
turn that needs no tool, and nothing is shown while it waits: no wait is held around the listing,
so the overlay shows only the mark.

Reproduction ([readings](../../readings/overlay-tool-failure-flows.md#a-sidecar-that-stops-answering)):
`docker pause` the filesystem sidecar, then ask "What key is the Bach cello suite number six in?"
in a new chat. Over `Converse` the first status came at 63.8 s and the reply ("D major") at
67.7 s. On the Linux shell the mark pulsed with no chip in grabs at 5 s and 30 s, and at 63 s
the chip read "the filesystem tool server is not answering, so this turn is answ...". The brain
logged `tool sidecar unavailable; serving without it` with `error="listing a tool sidecar's tools
took longer than 60s"`. The next turn, still frozen, listed again and paid the same wait.

## What to do

1. Give the listing its own, shorter bound (a setting with a default a few times the measured
   listing), and hold a wait with a detail while it runs, so the chip names the server.
2. Consider remembering a listing that overran for a short time, so the next turns skip that
   sidecar at once; the skip already reports through `SkipUnavailableToolRegistry`.
3. Test over a fake sidecar that never answers, and repeat the reproduction on the shell.

## History

- 2026-10-26: filed from the tool failure flows on the `cortexn8` stack.
