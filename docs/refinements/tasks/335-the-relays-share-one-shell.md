# The coverage relays are safe because they share one shell, and nothing checks that

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** the `check-body` line stops filling both toolchain relays from two command substitutions in one shell, whether by splitting them across shells or by sourcing either from an environment variable, a file, or a CI step's output.

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
