# A scratch path in the docs names the user

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-11-23

A slot's scratch folder sits under `/tmp/claude-1000/`, and its name holds the home directory, so a
doc that cites it by its full path names the user. The docs cite each one as the slot's name and
its run date, as in "the `slot14` scratch directory of the 2026-11-15 run", and the test cases
write `/home/user`. The repo names no person.

No check finds such a path: the cross-tree scans read no path for a home directory.

What would close it: a scan beside the cross-tree scans that fails on a home directory path in a
tracked text file, in both forms: `/home/<name>/` and the `-home-<name>-` form a scratch folder
name takes, with a test that plants each form and watches it fail. It is the fourteenth scan, so
the AGENTS.md list and the recipes it is compared with change with it.

## History

- 2026-11-23: filed by the audit of the night's commits, when the run folders under the home
  directory that the docs cite were written as `~/.cache/`.
- 2026-11-23: the scratch citations in 87 docs and two test cases rewritten so they name no home
  directory; the scan is left.
