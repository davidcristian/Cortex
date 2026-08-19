# A message that is raised and logged keeps its values in prose

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a seventh site of this shape arriving, or one where the prose value and the field
beside it disagree
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Six sites build one string, log it, and raise it as a typed error's text:
`residency_moves._refuse_a_load_the_card_cannot_hold` (twice, for a card that reports nothing and
for one that is short), `residency_watch` (the daemon that could not be converged, and the fresh
sidecar whose worst stop the deadline no longer clears), `supervisor._kill` (a child that survived
SIGKILL) and `swap_builders` (the deadline pairing the composition root refuses to serve on). Each
of them raises, so the string has to read on its own where no formatter runs, and each also
attaches the same numbers as fields. The line an operator sees therefore carries a value in the
prose and again on the right: `CORTEX_MODELHOST_TIMEOUT_S is 60.0 s and the model host's worst stop
is 45.0 s ... deadline_s=60.0 worst_s=45.0`.

This is what the twice-printed-field sweep deliberately did not touch, because the two demands are
genuinely opposed: a log message wants to be constant so a `grep` matches it and the varying parts
sit in fields, and an exception message wants to be self-contained so the reply, the traceback and
the runbook all say which numbers refused. Nothing here is wrong; it is one value read twice in one
line, on lines that fire rarely and are read closely.

The shape a fix would take is two strings per site, a constant one for the log call and the full
one for the `raise`, which costs a second string that can drift from the first. The alternative
worth weighing first is to leave the raise alone and drop the *log* call at these six, since the
exception is already logged wherever it is finally caught; that would be a real reduction rather
than a second spelling, and the question it turns on is whether every one of the six is in fact
caught and logged upstream.

## Trail

- 2026-08-19: Opened by the close of
  [R-323](323-a-field-spelled-into-its-own-message.md), which took every field out of the message
  that carried it and left exactly these six standing, each for the reason above.
