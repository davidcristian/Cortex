# The coverage relays are safe because they share one shell, and nothing checks that

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** the `check-body` line stops filling both toolchain relays from two command substitutions in one shell, whether by splitting them across shells or by sourcing either from an environment variable, a file, or a CI step's output; or `.github/workflows/ci.yml` stops reaching that line through `just check-body` and runs `coverage_gate.py` itself, which is the one place a CI step's output could arrive without the recipe changing at all.
**Verified:** 2026-09-11

Opened 2026-08-20 by the decline of [R-313](313-a-relay-can-be-required-and-empty.md), which asked
for a non-blank validator on `--rustc` and `--llvm-cov` in `scripts/coverage_gate.py` and was
refused because the empty compiler relay cannot arrive on its own. That refusal rests entirely on
the shape of one line in the `justfile`: both relays are filled by two command substitutions in the
same shell, so the toolchain that empties one empties the other, and an empty `--llvm-cov` fails
loudly as a producer mismatch while an empty `--rustc` would print `measured by` and pass. Measured
against a toolchain name that does not resolve, both come back empty together and the gate exits 1.

**What is unchecked is the arrangement, not the gate.** Nothing fails if somebody fills either relay
from somewhere else: a second recipe line, an environment variable, a file carried between shells, a
CI step's output. Each of those is a reasonable edit for an unrelated reason, and any of them
restores the quiet half the decline was measured against. The assumption is written in the
`check-body` comment beside the line, which is where an editor would meet it, and a comment is what
this entry exists to back up rather than to replace.

**What would close it.** If the arrangement goes, add the validator the declined entry described: one
shared non-blank check on both relay arguments, so a blank or whitespace string is refused with
argparse's own usage error before any verdict prints, the way `_require_version` already spells that
rule for the export's own fields. It is three lines and the decline was never about their cost.

## Trail

- 2026-08-20: opened by the decline of [R-313](313-a-relay-can-be-required-and-empty.md), to carry
  the trigger a closed task may not, and narrowed to the arrangement that decline depends on rather
  than the symptom it was originally filed under.
- 2026-09-07: not fired, and the arrangement holds in both places it can be read. The `justfile`
  still fills both relays from two command substitutions on the one line that runs
  `coverage_gate.py`, so one shell, and `.github/workflows/ci.yml` reaches that line by running
  `just check-body` rather than the gate, so CI inherits the same shell instead of supplying a
  second filling site. A second support for the decline turned up while checking the first: the two
  standing probes above the line are their own recipe lines, so a toolchain name that does not
  resolve fails the recipe there and the gate is never reached. An empty `--rustc` therefore needs
  the standing probe to succeed and the substitution of the same command to come back empty, which
  are not independent. The trigger gains the CI half as a second place to look, since a workflow
  that called the gate directly would restore the quiet relay without touching the recipe the
  clause was written about.
- 2026-09-11: not fired. The `check-body` recipe still fills both relays from two command
  substitutions on the one line that runs `coverage_gate.py`, the two standing probes are still
  their own lines above it, and `.github/workflows/ci.yml` still reaches that line through
  `just check-body`, naming `coverage_gate.py` only in the comment saying why `uv` is installed.
  `_require_version` still spells the non-blank rule the remedy would copy.
