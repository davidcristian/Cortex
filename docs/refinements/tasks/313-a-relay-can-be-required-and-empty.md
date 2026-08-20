# A required toolchain relay can still arrive empty

**Status:** declined 2026-08-20
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

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

**Declined 2026-08-20, on a re-derivation that found the symptom exact and the reachability
argument aimed at the wrong line.** Both halves were reproduced first on a synthetic export:
`--rustc ""` prints `measured by ` and three `PASS` lines and exits 0, and `--llvm-cov ""` prints the
producer mismatch naming `''` and exits 1.

**What shields the quiet half is not the standing probe.** This entry argued that reaching an empty
relay needs the recipe's standing `rustc +nightly --version` line to succeed and the identical
substitution two lines later to yield nothing. That line runs in `body/` in a shell of its own, so it
is the weaker half of the argument. The load-bearing half is that both relays are filled on one
recipe line by two command substitutions in one shell, one working directory and one toolchain
resolution, so the quiet half is shielded by the loud one rather than by the probe above it.
Measured against a toolchain name that does not resolve: both substitutions come back empty together
and the gate exits 1 on the producer mismatch. An empty `--rustc` arriving alone therefore needs
nightly cargo-llvm-cov to answer while nightly rustc prints nothing, in the same shell, seconds
apart.

**So the validator would be a third gate of a shape this origin has twice declined**, the dated pin
on its expiry cost and the compiler-in-export comparison on being unable to disagree, and the gate's
own suite would carry a case its only caller cannot produce. The asymmetry this entry names is real
and stays: one relay is checked and the other printed, because the export records a tool and no
compiler.

**The arrangement the decline rests on is now written where it can be broken**, in the `check-body`
comment beside the line, and the trigger that would reopen the question moves with it to
[R-335](335-the-relays-share-one-shell.md): the relays stop being filled by two substitutions in one
shell. The fix, if it fires, is the three lines this entry already describes.

## Trail

- 2026-08-18: Opened by the close of [305](305-optional-toolchain-relays.md), which made both
  relays mandatory and recorded, at the origin decision, that mandatory is not non-empty.
- 2026-08-20: declined. The symptom is exact and the shield is stronger than this entry knew: the
  two relays are filled in one shell, so the compiler probe cannot come back empty while the
  cargo-llvm-cov probe beside it does not, and the loud half fails the run whenever the toolchain
  that fills both is gone. Reproduced both halves and measured the shared-shell claim against an
  unresolvable toolchain before deciding. The argument is recorded at the origin decision, the
  arrangement in the recipe's own comment, and the trigger in
  [R-335](335-the-relays-share-one-shell.md).
