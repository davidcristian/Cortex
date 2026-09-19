# A required toolchain argument can still be empty

**Status:** declined 2026-08-20
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

[305](305-optional-toolchain-relays.md) made `--rustc` and `--llvm-cov` required arguments of
`coverage_gate.py`, so deleting one from `check-body` is a usage error. Required is not the same as
non-empty, and the two behave differently when the substitution that fills them produces an empty
string.

`--llvm-cov ""` fails loudly: the probed string has to contain the version the export records for
itself, and an empty one cannot, so the check fails with a producer mismatch naming `''`. A test
covers that path. `--rustc ""` is the quiet half: the value is printed rather than compared, the
compiler being absent from the export, so the output reads `measured by ` with nothing after it and
passes. Both were reproduced on a synthetic export before this was decided.

What protects the quiet half is not the recipe's earlier `rustc +nightly --version` probe, which
runs in `body/` in a shell of its own. It is that both arguments are filled on one recipe line by
two command substitutions in one shell, one working directory and one toolchain resolution.
Measured against a toolchain name that does not resolve: both substitutions come back empty
together and the check exits 1 on the producer mismatch. An empty `--rustc` arriving alone would
need nightly cargo-llvm-cov to answer while nightly rustc prints nothing, in the same shell,
seconds apart.

Declined because the validator would be a check that cannot fail for a reason that happens, a shape
this origin has declined at least three times, and the suite would contain a case its only caller
cannot produce. The asymmetry stays: one argument is compared and the other printed, because the
export records a tool and no compiler. The arrangement the decline rests on is written in the
`check-body` comment beside the line, and the trigger that would reopen the question is
[R-335](335-the-relays-share-one-shell.md): the two arguments stop being filled by two substitutions
in one shell. The fix, if that happens, is a shared validator on both arguments rejecting a blank
string with argparse's own usage error; `_require_version` in the module already states that rule
for the export's fields.

## History

- 2026-08-18: Opened by the close of [305](305-optional-toolchain-relays.md), which made both
  arguments mandatory and recorded, at the origin decision, that mandatory is not non-empty.
- 2026-08-20: Declined. The symptom is exact and the protection is stronger than this entry knew:
  the two arguments are filled in one shell, so the compiler probe cannot come back empty while the
  cargo-llvm-cov probe beside it does not. Reproduced both halves and measured the shared-shell
  claim against an unresolvable toolchain before deciding.
- 2026-08-20: Two counts above corrected. The probe and the argument are four recipe lines apart
  rather than two, with the tool probe, the instrumented run and a `uv sync` between them; and the
  shape has been declined at least three times rather than twice. Neither number affects the
  decline.
