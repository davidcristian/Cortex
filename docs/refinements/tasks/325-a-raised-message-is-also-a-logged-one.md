# A message that is raised and logged keeps its values in prose

**Status:** done 2026-08-20
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

Six sites build one string, log it, and raise it as a typed error's text:
`residency_moves._refuse_a_load_the_card_cannot_hold` (twice, for a card that reports nothing and
for one that is short), `residency_watch` (the daemon that could not be converged, and the fresh
sidecar whose worst stop the deadline no longer covers), `supervisor._kill` (a child that survived
SIGKILL) and `swap_builders` (the deadline pairing the composition root refuses to serve on). Each
raises, so the string has to read on its own where no formatter runs, and each also attaches the
same numbers as fields. The line an operator sees therefore has a value in the prose and again on
the right: `CORTEX_MODELHOST_TIMEOUT_S is 60.0 s and the model host's worst stop is 45.0 s ...
deadline_s=60.0 worst_s=45.0`.

The two demands are genuinely opposed: a log message needs to be constant so a `grep` matches it
and the varying parts sit in fields, while an exception message needs to be self-contained so the
reply, the traceback and the runbook all say which numbers were refused. Nothing here is wrong; it
is one value read twice on a line that is rare and read closely.

A fix is two strings per site, a constant one for the log call and the full one for the `raise`,
which costs a second string that can diverge from the first. The alternative is to leave the raise
alone and drop the log call at these six, since the exception is logged wherever it is finally
caught, which turns on whether all six really are caught and logged upstream.

## History

- 2026-08-19: Opened by the close of [R-323](323-a-field-spelled-into-its-own-message.md), which
  took every field out of the message that contained it and left these six.
- 2026-08-20: Fixed as ADR-0051 decision 8, and the answer to the question this entry turned on is
  one of six, not six. The four `SwapFailedError` sites share a single catch in the swap conductor,
  which settles the record and replies with `note_for(err)`, a mapping from error type to one of
  three fixed sentences that never reads `str(err)`, so dropping those logs would delete the
  numbers rather than move them; `swap_builders` raises `ControlDeadlineError` into a composition
  root nothing guards, the brain's entry running the wiring straight under `asyncio.run`, so
  dropping that one turns a designed boot refusal into an interpreter traceback. Only
  `supervisor._end` is a real double, both callers of `stop` logging what they catch, and it is the
  one that changed: the survived-SIGKILL sentence is raised and no longer printed. What the drop
  owed in exchange is the level, so the API's refusal line now follows its status code, 5xx at
  `ERROR` and 4xx at `WARNING`. That matters: a swap's eviction meets the same 503 through the
  brain's port and the brain turns it into a user-facing note without logging its text, so the
  sidecar's line is the only record of it anywhere. Five mutations measured over the whole brain
  workspace. The five sites that keep both forms move to
  [331](331-five-raised-messages-keep-their-numbers-in-prose.md), with the cheap option now ruled
  out rather than merely unweighed.
