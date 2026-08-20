# A message that is raised and logged keeps its values in prose

**Status:** landed 2026-08-20
**Area:** cross-cutting
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
- 2026-08-20: Landed as the ADR-0038 raised-and-logged addendum, and the answer to the question
  this entry turned on is **one of six, not six**. The trace is the substance: the four
  `SwapFailedError` sites share a single catch in the swap conductor, which settles the record and
  answers `note_for(err)`, a mapping from error type to one of three fixed sentences that never
  reads `str(err)`, so dropping those logs would delete the numbers rather than move them;
  `swap_builders` raises `ControlDeadlineError` into a composition root nothing guards, the brain's
  entry running the wiring straight under `asyncio.run`, so dropping that one turns a designed boot
  refusal into an interpreter traceback. Only `supervisor._end` is a real double, both callers of
  `stop` logging what they catch, and it is the one that changed: the survived-SIGKILL sentence is
  raised and no longer printed. What the drop owed in exchange is the level, so the API's refusal
  line now follows its status code, 5xx at `ERROR` and 4xx at `WARNING`. That is load bearing
  rather than tidy: a swap's eviction meets the same 503 through the brain's port and the brain
  turns it into a user-facing note without logging its text, so the sidecar's line is the only
  record of it anywhere. Five mutations measured over the whole brain workspace. The five sites
  that keep both spellings are carried forward as
  [331](331-five-raised-messages-keep-their-numbers-in-prose.md), with the cheap option now ruled
  out rather than merely unweighed.
