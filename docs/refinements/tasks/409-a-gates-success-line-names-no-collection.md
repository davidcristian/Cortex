# Every other gate reports a verdict without saying what it covered

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-23 by the close of
[R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which made `crosscheck.py` state the
collection its verdict is over and left the other gates as they were.

The six cross-tree scans all print a success line. Only two of them say anything about what they
read. `crosscheck.py` now prints entries, sites, mentions and pinned counts;
`backlogcheck.py` prints one count line per backlog. The other four print a claim with no
collection behind it:

- `linecap.py`: "no non-test source file under {root} exceeds {cap} lines"
- `dashcheck.py`: "no text file under {root} uses a banned dash"
- `bindcheck.py`: "every compose bind default under {given} is outside, tracked, or ignored"
- `defaultcheck.py`: "every variable spelled twice or more under {given} carries one value"

Each is true of an empty tree. A run that walked nothing, because an exclusion widened or a root
resolved wrong, prints the same sentence as a run that walked the repo, and the reader has no way
to tell. These gates fail closed on what they find and say nothing about how much that was.

**Why it was left.** The close that built the reading was scoped to one scan, and adding a count to
four more would have buried it.

**What would close it.** Print what each walked beside its verdict: files scanned for the line cap
and the dash ban, compose files and mounts for the bind check, files and variables for the defaults
check. Re-derive the walk in each before writing a number, since the count that matters is the one
after exclusions rather than the one before. Decide the same thing the shape reading decided:
whether anything may assert these, and the answer is expected to be no for the same reason, with
one thing to check that did not apply there. A floor ("at least one file was read") is not prose
quoting the gate's own data and might be a legitimate gate rather than a reading, since a scan that
read nothing is the fail-open case every one of these was written to avoid.

## Trail

- 2026-08-23: filed by the close of
  [R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which stated one scan's collection
  and left the other gates as they were.
- 2026-08-24: landed. All four now print what the walk read after its exclusions: files and lines
  for the line cap and the dash ban, compose files and binds and the landings git was asked about
  for the bind check, and compose files and variables beside the count of variables actually
  compared for the defaults check, that last being the collection its verdict is over. **This
  file was half right about the empty tree.** The four quoted success lines were exact, but
  `bindcheck.py` and `defaultcheck.py` have refused an empty walk since they landed, `composefiles.py`
  raising on no compose file for the reason this file gives, so the fail-open case was open in two
  gates and the other two were the precedent for closing it. **The open question is answered
  both ways.** Nothing asserts the counts, per the reading the registry shape decided: the suites
  pin that each gate's numbers count different things, over fixtures where no two of them
  coincide, and pin no number the live tree holds. The floor is a gate and is written as one:
  `linecap.py` and `dashcheck.py` exit 2 on a walk that measured no file, with the message
  `composefiles.py` already gives, because "at least one file was read" is a fact about the walk
  rather than about the tree and is the condition under which everything else they say is vacuous.
  The deeper counts get no floor, a compose file declaring no bind being an ordinary thing to
  find. Ten proofs, six planted mutations over the scripts suite and four runs against the live
  tree, tabled in the ADR-0029 addendum on the other four gates. Two residues filed: the floor is
  one file, so a collapsed walk still clears it
  ([R-410](410-the-floor-under-a-walk-is-one-file.md)), and the dash ban's count is a fact about a
  working tree rather than about a commit, reading ten files git does not track and skipping 26 it
  does ([R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md)).
