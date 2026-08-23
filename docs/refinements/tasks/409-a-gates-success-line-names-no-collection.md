# Every other gate reports a verdict without saying what it covered

**Status:** open, actionable
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
