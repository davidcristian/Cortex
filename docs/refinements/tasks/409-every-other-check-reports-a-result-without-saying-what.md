# Every other check reports a result without saying what it covered

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The six cross-tree scans all print a success line. Only two of them say anything about what they
read. `crosscheck.py` prints entries, declarations, matches and set counts; `backlogcheck.py`
prints one count line per backlog. The other four print a claim with no collection behind it:

- `linecap.py`: `no non-test source file under {root} exceeds {cap} lines`
- `dashcheck.py`: `no text file under {root} uses a banned dash`
- `bindcheck.py`: `every compose bind default under {given} is outside, tracked, or ignored`
- `defaultcheck.py`: `every variable spelled twice or more under {given} carries one value`

Each is true of an empty tree. A run that walked nothing, because an exclusion widened or a root
resolved wrong, prints the same sentence as a run that walked the repo, and the reader cannot tell
the difference.

The remedy is to print what each walked beside its result: files scanned for the line cap and the
dash ban, compose files and mounts for the bind check, files and variables for the defaults check,
counted after exclusions rather than before. The same question the shape reading answered applies
here: whether anything may assert these numbers. A minimum of one file read is not prose quoting
the check's own data and might be a legitimate check, since a scan that read nothing is the
fail-open case every one of these was written to avoid.

## History

- 2026-08-23: filed by the close of
  [R-404](404-the-registrys-own-shape-is-counted-by-hand.md), which stated one scan's collection
  and left the other checks as they were.
- 2026-08-24: closed. All four now print what the walk read after its exclusions: files and lines
  for the line cap and the dash ban, compose files and binds and the paths git was asked about for
  the bind check, and compose files and variables beside the count of variables actually compared
  for the defaults check. This file was half right about the empty tree. The four quoted success
  lines were exact, but `bindcheck.py` and `defaultcheck.py` have failed on an empty walk since
  they were added, `composefiles.py` raising on no compose file for the reason this file gives, so
  the fail-open case was open in two checks and the other two were the precedent for closing it.
  The open question is answered both ways. Nothing asserts the counts, per the reading the registry
  shape decided: the suites check that each scan's numbers count different things, over fixtures
  where no two of them coincide, and check no number the live tree holds. The minimum is a check
  and is written as one: `linecap.py` and `dashcheck.py` exit 2 on a walk that measured no file,
  with the message `composefiles.py` already gives, because "at least one file was read" is a fact
  about the walk rather than about the tree and is the condition under which everything else they
  say is vacuous. The deeper counts get no minimum, a compose file declaring no bind being an
  ordinary thing to find. Ten proofs, six planted mutations over the scripts suite and four runs
  against the live tree (ADR-0042 decision 19). Two residues filed: the minimum is one file, so a
  collapsed walk still clears it ([R-410](410-the-floor-under-a-walk-is-one-file.md)), and the dash
  ban's count is a fact about a working tree rather than about a commit, reading ten files git does
  not track and skipping 26 it does
  ([R-411](411-the-dash-ban-reads-a-working-tree-not-a-commit.md)).
