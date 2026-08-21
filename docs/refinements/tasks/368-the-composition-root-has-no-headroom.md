# The composition root sits at exactly its line cap

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`brain/packages/orchestrator/src/cortex_orchestrator/wiring.py` is 300 lines, which passes the cap
and leaves nothing. The next capability wired at the root, or the next comment explaining a line
already there, fails the line-cap gate for whatever unrelated change adds it. That is the shape
[38](038-core-barrel-headroom.md) recorded for the core barrel, and it was resolved there by
finding an economy rather than by moving anything.

There is no comparable economy here: the file is a sequence of config reads, builder calls, three
closures and a `finally` that releases in reverse order, and a fifth of it is comments arguing why
one object is built before another (52 comment lines and a 21-line module docstring out of 300).
The builders themselves were split out long ago, one module at a time, as each hit the cap.

What is left to split is the part that is not wiring: `capabilities`, `make_turn_engine` and
`make_engine` are three nested closures spanning 75 lines, which build a `TurnCapabilities` and
pick between a plain and an escalating engine per stream. They close over fourteen names, which is
why they were left in place, but they are a per-stream factory rather than a composition step, and
a factory object taking those names once would leave the root reading as the list of steps it is.
That is a refactor with no behaviour in it, so it wants its own change rather than a ride on the
next feature, which is the whole reason it is filed instead of done.

Until then, anything wired at the root has to arrive at zero net lines, which the ordering check
that filed this managed only by re-wrapping a docstring bullet that fitted on one line.

## Trail

- 2026-08-21: Filed by the close of
  [363](363-the-call-bound-and-the-run-bound-are-unordered.md), whose one added import line took
  the file to the cap exactly. Recorded in the ADR-0009 ordering addendum.
