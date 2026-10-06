# A list's passage widened past the names it bounds is caught only by accident

**Status:** open, waiting for its trigger
**Trigger:** an existing list's `opens` or `closes` value changes in `scripts/rosters.py`, which
`git log -p -- scripts/rosters.py` shows as a changed phrase line on a list registered before that
commit. The event this entry is about, a widened passage containing no extra name, reports nothing,
so the registry diff is the reading a review can take.
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)
**Verified:** 2026-10-07

`scripts/rosters.py` bounds each passage with two phrases the document contains. A phrase that
stops appearing, or starts appearing twice, is a reported fault. A phrase that moved is not a fault
at all: it still appears once, so the check reads a different region and compares whatever it finds
there.

Measured rather than reasoned about, on the day this was filed. Moving the live RPC list's closing
phrase to the invariants heading below it made the passage cover a section whose bullets open with
prose, and the run failed on those, which is the accident working. Moving the module list's closing
phrase back one sentence covered a run of text containing no code span the module pattern matches,
and `rostercheck.py` exited 0 with the same summary line it prints when nothing moved.

The exposure is small and mostly one-sided: a widened passage makes the check see more names,
which fails on any name that is not a member. It hides a member the list lost only when the wider
run writes that member's name a second time, since the check compares the set of names. What it
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
- 2026-09-24: fired on its first clause and reviewed. On 2026-09-19 the two lists in the repo checks
  module doc moved phrases, `opens` to `## Public contract` and `closes` to `## How the checks run`,
  and the repo map's list of check modules was removed. Both lists still fall inside the range the
  entry above records, which kept only its extremes. `just check-rostercheck` passes over 9 lists in
  7 documents naming 163 members. Prose before the first name, then after the last, per list: live
  gRPC checks 837 and 305, modules run from a shell 80 and 137, modules only read 186 and 89, the
  three cross-tree scan lists 51 and 117 (AGENTS.md), 70 and 2 (`ci.yml`), 71 and 83
  (`docs/index.md`), the brain's packages 18 and 67, the body's crates 18 and 8, the registry's
  parts 27 and 18. The trigger now compares against these per-list figures.
- 2026-10-03: fired on its second clause and reviewed; no boundary widened. The one registry commit
  since, on 2026-10-02, adds a tenth list, the scan headings in `docs/modules/repo-checks-scans.md`,
  and changes no phrase of an existing list. Measured as before (characters from a passage's start
  to the first occurrence of any of its names, and from the last occurrence to its end), two lists
  grew, each from members added at its end with both phrases unmoved: the modules run from a shell
  82 and 175, after `memwatch.py` and `replaysince.py` were added last with their descriptions and
  the count before the first name became twenty-three, and the body's crates 18 and 81, after
  `contract`. The live gRPC checks fell to 770 before; the new list reads 495 and 1109; the rest
  are unchanged. `just check-rostercheck` passes over 10 lists in 7 documents naming 180 members.
  Every rise here came from an ordinary member edit and none from a moved phrase, so the trigger now
  names the registry diff alone. Correction to the body: the modules-only-read list already writes
  six names twice inside its passage (`backlogindex.py`, `bannedwords.py`, `envelopesamples.py`,
  `prosereaders.py`, `proseliterals.py`, `slashcomments.py`), so a widened passage is not the only
  way the check can count a member whose own entry is gone.
