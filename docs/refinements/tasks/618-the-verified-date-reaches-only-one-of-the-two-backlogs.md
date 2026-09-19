# The Verified date reaches only one of the two backlogs

**Status:** done 2026-09-11
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

The `**Verified:**` field records the day somebody last checked a task's claim against the code, so
the next reader pays for that once instead of again. `KIND_FIELDS` in `scripts/backlog.py` gave it
to refinements alone, and the check rejected it on a host task as an unknown field.

A host task's claim goes stale the same way: it describes code that is written and unrun, and the
code keeps moving while the hardware it needs stays out of reach, so by the time somebody has a
Win32 desktop session or a 24 GB card the description can be months behind the tree. Both backlogs
share one parser, so widening the field is one tuple entry and one rule. The argument against was
that reading the code settles only half of a host claim, the other half being the card or the
desktop session, which no date in this repo can record, and that the `**Status:**` grammar already
has `attempted <date>, inconclusive: <what happened>` for what a host task can really report.

**What closed it.** `KIND_FIELDS` gives the host kind the `Verified` field: a host task's date
covers the code half of its claim and `attempted` keeps the hardware half.

## History

- 2026-09-09: opened by the slice that added the `**Verified:**` field to the refinements task
  grammar, now [ADR-0039](../../adr/ADR-0039-backlog-per-task.md) decision 12.
- 2026-09-11: re-filed as actionable, because the reason for deferring was false when it was
  written. Two host tasks were already wrong about their own subject:
  [H-005](../../host/tasks/005-session-read-commands.md) quoted a description of the overlay's cold
  start calling auto-restore deferred, which was wrong once auto-restore was added on 2026-07-12,
  and [H-002](../../host/tasks/002-core-audio-volume-action.md) records a 2026-07-19 correction of
  a false VRAM clause that had mistagged the item's capability. The grammar was re-read too:
  `KIND_FIELDS` still gave `Verified` to refinements alone, the host states were still
  `never attempted`, `attempted <date>, inconclusive: <what happened>` and `done`, and no host task
  file had changed since this entry was opened. The refinements review was unfinished, 92 of 169
  open tasks having the field that day.
- 2026-09-11: done. `KIND_FIELDS` in `scripts/backlog.py` gives the host kind the `Verified` field,
  and a current item is refused by name rather than as closed. The renderer needed no change, since
  it never read the kind. Four mutants over `scripts/tests` (1745 tests) failed 4, 1, 3 and 3. The
  host index and the check tree's contract say what the line means on a host item. No host task was
  given a date, since the reading behind one is still to be taken. Recorded as
  [ADR-0039](../../adr/ADR-0039-backlog-per-task.md) decision 12.
