# Deleting a toolchain relay deletes its check, silently

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Found 2026-08-18 while re-deriving [290](290-the-export-names-its-tool-not-its-compiler.md), and
unrelated to that entry's question. `coverage_gate.py` takes `--rustc` and `--llvm-cov` as optional
arguments defaulting to `None`, and `attribute` guards each with `is not None`. The producer
cross-check, the one half of the attribution that can actually fail, therefore exists only while
the recipe happens to pass the flag. Deleting `--llvm-cov` from `check-body` removes the check with
no complaint and no missing line in the output: the gate prints the export's own writer, the three
metric verdicts pass, and nothing says that the report is no longer being held against the tool
this run used.

That is the same shape as the mute coverage threshold the single-verdict work removed, where a gate
degraded quietly instead of failing. The tests cover an empty probed string but not an absent flag.

What would close it: make both arguments required, drop the two `is not None` guards, add a test
that a missing relay is a usage failure rather than a pass, and update the module docstring and the
recipe's comment. It makes the relay mandatory rather than checked, so it does not answer what
[290](290-the-export-names-its-tool-not-its-compiler.md) asked; it only stops the one check that
does exist from being deletable in silence. Re-derive the guards and the tests before starting.

## Trail

- 2026-08-18: Opened by the re-derivation that closed
  [290](290-the-export-names-its-tool-not-its-compiler.md), which read the same module for a
  different reason and found this beside it.
