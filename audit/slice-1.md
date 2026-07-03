# Audit of Slice 1 (Walking skeleton: both toolchains, all gates)

**Audited:** 2026-07-02 · **Verdict:** fully implemented

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Every concrete claim in the Slice 1 section (docs/ROADMAP.md:22-31) is present in the tree and matches its origin ADR (ADR-0002). Both trivial pure modules exist with full behavior tests (cortex_core.routing on the brain side, body_core::hotkey on the body side), the uv and Cargo workspaces are configured as described, the justfile's `just check` spans both toolchains (now four trees, a later-slice superset), scripts/linecap.py enforces the 300-line cap with the ADR-0002 exemption rules, pre-commit is the literal `just check` mirror ADR-0002 decision 9 requires, and the CI workflow is GPU-less on plain ubuntu runners with nightly-before-stable Rust setup per decision 1. All five 'Gates proven' claims are wired in config exactly as stated: --cov-branch --cov-fail-under=100 for Python, cargo-llvm-cov plus coverage_gate.py for Rust branches, the unconditional linecap CI job, and the shared just recipes across local/pre-commit/CI. The ROADMAP's 'Deferred refinements & later work' ledger contains no Slice 1 entries and none are needed; later evolutions of the CI (path filtering per ADR-0006, the overlay tree per ADR-0011) extend rather than contradict the slice text, so no stale claims were found. Verdict: fully-implemented.

## Claims checked (12)

- **✅ verified.** A trivial pure module exists on the brain side: a typed routing decision in brain/packages/core
  - Evidence: brain/packages/core/src/cortex_core/routing.py:1-32 (Tier enum, frozen RoutingHints dataclass, pure route_turn with explicit->BRAIN->SUBAGENT->CORTEX precedence, no I/O); behavior tests at brain/packages/core/tests/test_routing.py:1-40 covering every branch and precedence interaction; documented as 'Routing (Slice 1)' in docs/modules/brain-core.md:11-16

- **✅ verified.** A trivial pure module exists on the body side: a hotkey-config type in body/crates/core
  - Evidence: body/crates/core/src/hotkey.rs:1-175 (pure HotkeyChord parse/format with typed HotkeyParseError via thiserror, default ctrl+alt+space, explicitly 'no OS APIs' per module doc comment lines 1-6); tests at body/crates/core/tests/hotkey.rs (external tests/ dir per ADR-0002 decision 5); documented in docs/modules/body-core.md:13-22

- **✅ verified**. uv workspace for the Python brain
  - Evidence: brain/pyproject.toml:48-49 ([tool.uv.workspace] members = ["packages/*"]), lines 1-2 explicitly note 'Virtual workspace root ... Slice 1'; brain/packages/core exists with cortex_core package

- **✅ verified.** Cargo workspace for the Rust body
  - Evidence: body/Cargo.toml:1-6 ([workspace] members = crates/core, rpc, os_linux, os_macos, os_windows; resolver 3, edition 2024 at line 10); workspace lints enforcing unsafe_code=forbid and clippy unwrap_used/expect_used=deny at lines 25-36, matching ADR-0002 decision 7; body/clippy.toml exists

- **✅ verified**. justfile with `just check` spanning both toolchains
  - Evidence: justfile:10-37 (`check` runs check-linecap then check-brain, check-scripts, check-body, check-overlay in parallel); check-brain at lines 45-50 (ruff format/check, pyright, pytest), check-body at lines 63-69 (cargo fmt --check, clippy -D warnings, cargo test, cargo +nightly llvm-cov --branch + scripts/coverage_gate.py). Now spans four trees (overlay added by later slices, ADR-0011), a superset of the Slice 1 claim, not a contradiction

- **✅ verified**. Line-cap script enforcing <=300 lines per non-test .py/.rs source file
  - Evidence: scripts/linecap.py:14-30 (DEFAULT_MAX_LINES=300, .py/.rs suffixes, skips tests/ and _generated dirs plus test-named files per ADR-0002 decisions 4-5), scan/main at lines 58-108 counting ALL lines including comments/blanks; wired as `just check-linecap` (justfile:40-42) and an unconditional CI job (.github/workflows/ci.yml:71-81); tested by scripts/tests/test_linecap.py; contract doc docs/modules/repo-gates.md:11-20

- **✅ verified**. Pre-commit configuration mirroring the gate
  - Evidence: .pre-commit-config.yaml:6-14. A single local hook whose entry is literally `just check` (always_run, pass_filenames false), exactly as ADR-0002 decision 9 specifies ('a literal mirror, so the hook can never drift from the gate'); plus a commit-msg conventional-commits hook at lines 15-20 (added later, commit 790166e)

- **✅ verified.** GPU-less CI building and gating both trees
  - Evidence: .github/workflows/ci.yml:1 ('GPU-less by design ... plain ubuntu runners, no CUDA anywhere'); python job runs just check-brain + check-scripts (lines 83-96), rust job installs nightly-then-stable per ADR-0002 decision 1 and runs just check-body (lines 98-125), overlay job (lines 131-145, added later); path filtering is fail-closed via scripts/ci_paths.py (lines 25-66, ADR-0006 evolution) and the linecap job always runs (lines 68-81)

- **✅ verified.** Gate proven: Python 100% line+branch coverage
  - Evidence: brain/pyproject.toml:66 (addopts "--cov --cov-branch --cov-fail-under=100 ... -m 'not integration'") and :70-74 ([tool.coverage.run] branch=true, _generated omitted per ADR-0002 decision 4); scripts/pyproject.toml:25 gates the scripts tree the same way (ADR-0002 decision 3). Config verified by reading; execution is the orchestrator's separate `just check` run

- **✅ verified.** Gate proven: Rust 100% coverage via cargo-llvm-cov (line/region/branch)
  - Evidence: justfile:67-69 (cargo +nightly llvm-cov --branch --fail-under-lines 100 --fail-under-regions 100 --json + coverage_gate.py for branches, since llvm-cov has no --fail-under-branches); scripts/coverage_gate.py:1-60 implements ADR-0002 decision 2 exactly (requires covered==count per metric, never trusts producer percent, count==0 passes with a printed note); tested by scripts/tests/test_coverage_gate.py

- **✅ verified.** Gate proven: dual-toolchain `just check` as the single gate
  - Evidence: justfile:1-2 ('just check is THE gate ... CI and pre-commit run exactly these recipes') and :10-37; CI jobs invoke the identical just recipes (.github/workflows/ci.yml:81,95-96,125,145); pre-commit runs `just check` verbatim (.pre-commit-config.yaml:10)

- **✅ verified.** ADR for the slice's non-obvious decisions exists (doc-first DoD)
  - Evidence: docs/adr/ADR-0002-toolchain-gates.md:1-57 (Accepted, 2026-06-28, titled 'Toolchain and gate mechanics (Slice 1)', 9 decisions all traceable to code as cited above); module contract docs exist for every Slice 1 piece: docs/modules/brain-core.md, body-core.md, repo-gates.md; commit trail: 27edcd9 'feat: bootstrap dual-toolchain walking skeleton' and 37f7d43 'fix: harden repo gates after adversarial review'

## Gaps

None found.
