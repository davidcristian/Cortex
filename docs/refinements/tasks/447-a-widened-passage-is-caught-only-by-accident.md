# A list's passage widened past the names it bounds is caught only by accident

**Status:** open, waiting for its trigger
**Trigger:** an existing list's `opens` or `closes` value changes in `scripts/rosters.py`, or a
passage's prose before its first name or after its last grows past the figures in this entry's
2026-09-17 history entry. The event this entry is about, a widened passage containing no extra
name, reports nothing, so those two readings are what a review can take.
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)
**Verified:** 2026-09-17

`scripts/rosters.py` bounds each passage with two phrases the document contains. A phrase that
stops appearing, or starts appearing twice, is a reported fault. A phrase that moved is not a fault
at all: it still appears once, so the check reads a different region and compares whatever it finds
there.

Measured rather than reasoned about, on the day this was filed. Moving the live RPC list's closing
phrase to the invariants heading below it made the passage cover a section whose bullets open with
prose, and the run failed on those, which is the accident working. Moving the module list's closing
phrase back one sentence covered a run of text containing no code span the module pattern matches,
and `rostercheck.py` exited 0 with the same summary line it prints when nothing moved.

The exposure is small and one-sided: a widened passage can only make the check see more names,
which fails on any name that is not a member, and can never hide a member the list lost. What it
can do is make the passage's own claim untrue while the check still passes, so a later reader
trusts a boundary that no longer bounds the list.

Every fix costs something. Requiring a passage to contain at least one name catches nothing here,
since a widened passage still contains all of them. Fixing the passage's length or its line span
would make an ordinary prose edit fail the check. Reading the extent from the document's own
structure is the heading-and-paragraph approach the close argued its way out of, since two lists
share one paragraph's page and one opens with a fenced command. Probably the answer is a
registry-health test rather than a check rule: assert that each passage is the smallest run
containing all of its names, which a widened boundary breaks by definition. Measured on 2026-09-17
over all ten, that is true of none, since every one deliberately opens or closes some distance from
its nearest name.

## History

- 2026-08-26: opened by the close of
  [R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), which made a list's boundaries
  data and required the phrases to appear exactly once, and nothing else about them.
- 2026-09-11: not fired. No `opens` or `closes` phrase registered in `scripts/rosters.py` has been
  edited since this was filed: the registry's history since then adds five lists and moves no
  phrase, and `rostercheck` passes over 8 lists in 5 documents naming 196 members. The
  registry-health test proposed above was measured against every registered passage, and none of
  the eight is the smallest run containing its names. Each has prose before its first name, from 29
  characters on the registry's parts to 1132 on the live RPC checks, and after its last, from 3 to
  409, so the test would fail every list as it stands.
- 2026-09-17: not fired. The registry gained two lists on 2026-09-15, the repo map's rows for the
  brain's packages and the body's crates, and the diff adds their phrases and changes none already
  registered; the only other commit to touch those modules since moved the markdown fence reader.
  `just check-rostercheck` passes over 10 lists in 5 documents naming 223 members. The slack was
  measured again over all ten by a scratch script that reads each passage with
  `rosternames.passage` and its names with `rosternames.names`, and none is the smallest run
  containing its names: prose before the first name runs from 18 characters (both repo map rows) to
  1132 (the live RPC checks), and after the last from 3 (the registry's parts) to 409 (the live RPC
  checks). The trigger used to name the unreported event itself, which no reading can observe, so
  it now names the registry diff and these figures.
