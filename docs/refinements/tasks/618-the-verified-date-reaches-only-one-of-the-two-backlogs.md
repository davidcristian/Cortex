# The Verified date reaches only one of the two backlogs

**Status:** landed 2026-09-11
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-09-09 by the slice that added the `**Verified:**` field to the refinements grammar. The
field records the day somebody last held a task's claim against the code, so the next reader pays
for that re-derivation once instead of again. `KIND_FIELDS` in `scripts/backlog.py` gave it to
refinements alone, and the gate rejected it on a host task as an unknown field.

The argument for widening it is that a host task's claim goes stale by the same mechanism. A host
task describes code that is written and unrun, and the code keeps moving while the hardware it
needs stays out of reach, so by the time somebody has a Win32 desktop session or a 24 GB card in
front of them the description they are working from can be months behind the tree. That is the
refinements failure exactly, and the two backlogs share one parser, so widening it is one tuple
entry, one rule, and the renderings the refinements half already has.

The argument against is that the two backlogs answer different questions. A refinement's claim is
about a design that has not been built, and re-deriving it is reading the code. A host task's claim
is about built code plus a hardware fact, and reading the code settles only half of it: the half
that decides whether the bring-up will work is the card or the desktop session, which no date in
this repo can record. A `Verified` line on a host task would therefore say less than the same line
on a refinement while looking identical, and the `**Status:**` grammar already carries
`attempted <date>, inconclusive: <what happened>` for the reading a host task can really take.

**What would close it.** Either widening `KIND_FIELDS` to give host tasks the field, with the index
rendering that follows it, or recording here that the host grammar deliberately stops at
`attempted`, and saying which half of a host claim a reader is expected to re-derive before a
bring-up. Both are small. The entry did not choose when it was opened, on the ground that nothing had yet
shown a host task being wrong about its own subject; the reading of 2026-09-11 below found that
one already had, before the field existed.

## Trail

- 2026-09-09: opened by the slice that added the `**Verified:**` field to the refinements task
  grammar, recorded in the [ADR-0039](../../adr/ADR-0039-backlog-per-task.md) addendum on the date
  a re-derivation was taken.
- 2026-09-11: re-filed as actionable, because the premise the deferral rested on was false when
  it was written. A host task already records the failure the trigger waited for:
  [H-005](../../host/tasks/005-session-read-commands.md) quotes a description of the overlay's
  cold start whose parenthetical calls auto-restore deferred, and marks it stale because
  auto-restore landed on 2026-07-12, which is built code moving under a host task's account of
  it. [H-002](../../host/tasks/002-core-audio-volume-action.md) records a second staleness of the
  other kind, a 2026-07-19 correction of a false VRAM clause that had mistagged the item's
  capability, corrected from a measurement this repo holds. The grammar was re-read as well:
  `KIND_FIELDS` in `scripts/backlog.py` still gives `Verified` to refinements alone, the host
  states are still `never attempted`, `attempted <date>, inconclusive: <what happened>` and
  `done`, and no host task file has changed since this entry was opened. The refinements sweep
  is not finished, 92 of 169 open tasks carrying the field today. Recommendation for whoever
  lands it: widen the field, since the code half of a host claim is exactly what the date
  records and the hardware half keeps `attempted`. Recorded in the origin decision's addendum
  of the same day.
- 2026-09-11: landed. `KIND_FIELDS` in `scripts/backlog.py` gives the host kind the `Verified`
  field; a host task's date covers the code half of its claim and `attempted` keeps the hardware
  half; a standing item is refused by name rather than as closed. The renderer needed no change,
  since it never read the kind. Four mutants over `scripts/tests` (1745 tests) failed 4, 1, 3 and
  3. The host index and the gate tree's contract say what the line means on a host item. No host
  task was given a date, since the reading behind one is still to be taken. Recorded in the origin
  decision's addendum of the same day, the later of the two.
