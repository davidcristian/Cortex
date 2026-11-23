# A scratch path in the docs names the user

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-11-23

87 files under `docs/` cite a slot's scratch folder by its full path under `/tmp/claude-1000/`,
and that folder's name holds the home directory, so it names the user. Two cases in
`brain/packages/core/tests/test_file_claim.py` write a home path with the same name, where the
other cases there write `/home/user`. The repo names no person. The scratch folders were emptied
with `/tmp`, so each of those citations points at nothing.

No check finds this: the cross-tree scans read no path for a home directory.

What would close it:

1. A scan beside the cross-tree scans that fails on a home directory path in a tracked text file,
   in both forms: `/home/<name>/` and the `-home-<name>-` form a scratch folder name takes, with
   a test that plants each form and watches it fail. It is the fourteenth scan, so the AGENTS.md
   list and the recipes it is compared with change with it.
2. Each scratch citation rewritten as the slot's name and the date of its run, with no path, since
   the folder is gone, and the two test cases given `/home/user`.

## History

- 2026-11-23: filed by the audit of the night's commits, when the run folders under the home
  directory that the docs cite were written as `~/.cache/`.
