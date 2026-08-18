# A required toolchain relay can still arrive empty

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a coverage verdict prints `measured by` with nothing after it, or the recipe stops
probing the compiler on its own standing line before it measures.

Opened 2026-08-18 by the close of [305](305-optional-toolchain-relays.md), which made `--rustc` and
`--llvm-cov` required arguments of `coverage_gate.py` so that deleting one from `check-body` is a
usage error rather than a quieter gate. Required is not the same as non-empty, and the two halves
degrade differently when the substitution that fills them yields an empty string.

`--llvm-cov ""` is already loud: the probed string has to contain the version the export records
for itself, and an empty one cannot, so the gate fails with a producer mismatch naming `''`. That
path is covered by a test. `--rustc ""` is the quiet half: the relay is printed rather than checked,
the compiler being absent from the export, so the verdict prints `measured by ` with nothing after
it and passes.

**Why it is not fixed in the same sitting.** The recipe probes rustc twice on purpose, and the
first probe is a standing `rustc +nightly --version` line that fails the run before the measurement
starts. Reaching an empty relay therefore needs that line to succeed and the identical command
substitution two lines later to produce nothing, which is not a failure mode anybody has seen. A
gate that cannot fail for a reason that happens is the shape this ADR has now declined twice, and
adding one here would be a third.

**What would close it if the trigger fires.** A shared validator on both relay arguments, rejecting
a blank or whitespace string with argparse's own usage error, so the two relays are refused on the
same grounds and in the same place; `_require_version` in the module already spells that rule for
the export's fields and would say what "present" means for a probed one too.

## Trail

- 2026-08-18: Opened by the close of [305](305-optional-toolchain-relays.md), which made both
  relays mandatory and recorded, at the origin decision, that mandatory is not non-empty.
