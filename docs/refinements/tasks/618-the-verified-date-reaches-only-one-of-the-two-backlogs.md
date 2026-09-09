# The Verified date reaches only one of the two backlogs

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** a host task found to be wrong about the built code it describes, which is the same
failure the refinements field was added for, or the refinements sweep finishing, at which point
there is real use of the field to compare the two backlogs against.

Opened 2026-09-09 by the slice that added the `**Verified:**` field to the refinements grammar. The
field records the day somebody last held a task's claim against the code, so the next reader pays
for that re-derivation once instead of again. `KIND_FIELDS` in `scripts/backlog.py` gives it to
refinements alone, and the gate rejects it on a host task as an unknown field.

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
bring-up. Both are small; the entry does not choose, because nothing has yet shown a host task
being wrong about its own subject.

## Trail

- 2026-09-09: opened by the slice that added the `**Verified:**` field to the refinements task
  grammar, recorded in the [ADR-0039](../../adr/ADR-0039-backlog-per-task.md) addendum on the date
  a re-derivation was taken.
