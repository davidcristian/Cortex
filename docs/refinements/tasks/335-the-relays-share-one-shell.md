# The two coverage arguments are safe only because they share one shell

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Trigger:** `grep -rnE 'python[^#]*rustcoverage' justfile .github .pre-commit-config.yaml` stops
returning exactly one line, the `check-body` recipe's run of the check; or that line stops filling
`--rustc` and `--llvm-cov` from two command substitutions of its own, whether by splitting them
across recipe lines, which just runs in separate shells, or by reading either from an environment
variable, a file or a CI step's output. The arrangement also depends on the `justfile` setting no
`shell`, so each recipe line is one `sh -cu`, and on both substitutions naming the toolchain as
`+nightly`, which no directory override can change.
**Verified:** 2026-09-22

The decline of [R-313](313-a-relay-can-be-required-and-empty.md) rests entirely on the shape of one
line in the `justfile`: both arguments are filled by two command substitutions in the same shell,
so the toolchain that empties one empties the other, and an empty `--llvm-cov` fails loudly as a
producer mismatch while an empty `--rustc` would print `measured by` and pass. Measured against a
toolchain name that does not resolve, both come back empty together and the run exits 1.

What is unchecked is the arrangement, not the check itself. Nothing fails if somebody fills either
argument from somewhere else: a second recipe line, an environment variable, a file passed between
shells, a CI step's output. Each is a reasonable edit for an unrelated reason, and any of them
restores the quiet half the decline was measured against. Nothing in the `justfile` names the
assumption: the comment above `check-body` covers its toolchains only, so an editor splitting the
line meets no warning, and only a reader running this entry's trigger finds the split.

If the arrangement goes, add the validator the declined entry described: one shared non-blank check
on both arguments, so a blank or whitespace string is refused with argparse's own usage error
before any result prints, the way `_require_version` already states that rule for the export's own
fields. It is three lines.

## History

- 2026-08-20: Opened by the decline of [R-313](313-a-relay-can-be-required-and-empty.md), to hold
  the trigger a closed task may not, and narrowed to the arrangement that decline depends on.
- 2026-09-07: Not fired, and the arrangement holds in both places it can be read. The `justfile`
  still fills both arguments from two command substitutions on the one line that runs
  `rustcoverage.py`, and `.github/workflows/ci.yml` reaches that line by running `just check-body`
  rather than the script, so CI inherits the same shell. A second support turned up while checking
  the first: the two probes above the line are their own recipe lines, so a toolchain name that
  does not resolve fails the recipe there and the script is never reached. The trigger gains the CI
  half as a second place to look.
- 2026-09-11: Not fired. The `check-body` recipe still fills both arguments from two command
  substitutions on the one line that runs `rustcoverage.py`, the two probes are still their own
  lines above it, and `.github/workflows/ci.yml` still reaches that line through `just check-body`,
  naming `rustcoverage.py` only in the comment saying why `uv` is installed. `_require_version`
  still states the non-blank rule the remedy would copy.
- 2026-09-17: Not fired. The grep in the trigger returns one line, the run at `justfile` line 235,
  which still fills both arguments from two substitutions on that line. `.github/workflows/ci.yml`
  names the script only in the comment at line 161 and reaches the run through `just check-body`,
  and `.pre-commit-config.yaml` does not name it. The two probes are still their own lines (231 and
  232), and the comment naming the assumption still sits above the recipe (lines 208 to 216).
  `just --dry-run check-body` prints the run as one line. The `justfile` has no `set shell`, so the
  line runs in one `sh -cu`, and both substitutions name `+nightly` explicitly, so the probes
  running from `body/` and the run from `scripts/` resolve the same toolchain. Three commits
  touched the `justfile` since the last reading and none of their diffs names this recipe or the
  script.
- 2026-09-22: Not fired. The trigger's grep returns one line, `justfile:172`, which still fills
  `--rustc` and `--llvm-cov` from two substitutions of its own, both naming `+nightly`. The two
  probes are their own lines (168 and 169), the `justfile` has no `set shell`, and
  `.github/workflows/ci.yml` names the script only in the comment at line 130. The body's claim
  that the `check-body` comment states the assumption was wrong: the comment above the recipe
  (lines 159 to 161) names the nightly toolchain and the Windows target and nothing about the
  shared shell, so the text now says so. `_require_version` still states the non-blank rule at
  `scripts/rustcoverage.py:54`. Six commits touched the `justfile` since the last reading. Two
  changed this recipe, one adding the comment above it and one renaming the script the line runs,
  and neither moved either substitution.
