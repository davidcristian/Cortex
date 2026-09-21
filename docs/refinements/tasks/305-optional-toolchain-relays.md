# Deleting a toolchain argument deletes its check, silently

**Status:** done 2026-08-18
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

`rustcoverage.py` took `--rustc` and `--llvm-cov` as optional arguments defaulting to `None`, and
`attribute` skipped the check for an argument that was missing. Removing `--llvm-cov` from the
`check-body` recipe therefore removed the producer cross-check with no error and no missing output
line: the run printed the export's own writer, passed all three metric checks, and said nothing
about the tool comparison no longer running.

The fix is to make both arguments required, remove the two `is not None` conditions, and add a test
that a missing argument is a usage failure rather than a pass.

## History

- 2026-08-18: Opened while checking [290](290-the-export-names-its-tool-not-its-compiler.md), which
  read the same module for an unrelated reason.
- 2026-08-18: Fixed as proposed. Both arguments are `required=True`, both `is not None` conditions
  are gone, and `Toolchain` holds two plain strings. Reproduced end to end before and after: with
  `--llvm-cov` deleted from the `check-body` line, the old version printed a passing result and
  exited 0, while the new one exits 2 on `the following arguments are required: --llvm-cov` and
  fails the recipe. Required is not the same as non-empty, and that remainder is filed as
  [313](313-a-relay-can-be-required-and-empty.md). The reasoning is recorded at the origin
  decision.
