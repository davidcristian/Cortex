# ADR-0003: Generated gRPC stubs and packaging

**Status:** Accepted (2026-08-25)

## Context

`proto/body.proto` is the single source of truth for everything that crosses between body and brain
([ADR-0001](ADR-0001-architecture.md) decision 3). Making it real on both sides forces decisions
about stub generation, where generated code lives, how it stays exempt from the repo checks
(ADR-0001 decision 7, [ADR-0002](ADR-0002-toolchain-checks.md) decision 4), which gRPC stacks to
use, and what keeps the committed stubs in step with the proto once nobody regenerates them on
every build.

## Decision

1. **Generated stubs are committed, only inside `_generated` directories:**
   `body/crates/rpc/src/_generated/` and `brain/packages/seam/src/cortex_seam/_generated/`. Builds
   are hermetic, so CI and fresh clones never need `protoc`. Regeneration is a developer action,
   `just proto`, which needs a local `protoc` and regenerates both stacks together. A regeneration
   diff is reviewed like any other change. The proto's field numbers are frozen: extend, never
   renumber.

2. **Rust stack: tonic.** Regeneration happens only when `CORTEX_REGEN_PROTO=1` is set for
   `build.rs`, so a normal build does nothing. The generated file is `include!`d inside a wrapper
   module that holds the needed `allow` attributes, since `cargo fmt` does not format an
   `include!`d file. The coverage exemption is `--ignore-filename-regex '/_generated/'` on the
   `check-body` llvm-cov run.

3. **The Rust live suite is `#[ignore]`-marked tests** (`body/crates/rpc/tests/live.rs`), the Rust
   equivalent of the Python `integration` marker: compiled, never run in CI or under coverage, and
   run against a live brain by `just rpc-health`. Its list in
   [body-rpc](../modules/body-rpc.md) is compared with the file
   ([ADR-0044](ADR-0044-document-rosters.md) decision 7).

4. **Python stack: grpcio and grpcio-tools** (mature `grpc.aio`), not betterproto. The committed
   `body_pb2.py` and `body_pb2_grpc.py` come with a `.pyi` so pyright strict works for consumers,
   while `_generated` itself is excluded from ruff, pyright, coverage and the line limit.
   Package-absolute imports come from staging the proto under `cortex_seam/_generated/` before
   `protoc` runs.

5. **Python generated code lives in `brain/packages/seam` (`cortex_seam`).** It is shared wire code
   used by the orchestrator (the `BrainService` server) and by `body_client` (the typed
   `BodyService` client, [ADR-0023](ADR-0023-body-gateway-volume.md)).

6. **Connection settings.** The brain server reads `CORTEX_SEAM_HOST` (default `127.0.0.1`, and
   `0.0.0.0` inside the container) and `CORTEX_SEAM_PORT` (default `50051`); the body's live checks
   read `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`). Compose publishes the port on
   loopback only, for the single-user security posture.

7. **The committed Rust stub is compared with the proto's comments, and with nothing else.**
   `scripts/stubcheck.py` checks that every comment in the proto's body appears in
   `body/crates/rpc/src/_generated/cortex.seam.v1.rs`. It is a text comparison that runs no
   codegen, needs no `protoc`, docker or GPU, and so runs everywhere `just check` does. `prost`
   copies proto comments verbatim into the Rust stub, which is the file a Rust reader opens, and a
   comment there can state a value (the body's default capture edge) that `crosscheck.py` checks
   only on the proto side; skipping a regeneration once left the stub stating the old number with
   nothing reporting it. The comparison skips the file header above `syntax = `, which `prost` does
   not copy, and normalizes the three transformations `prost` applies: it escapes `[` and `]` for
   rustdoc, turns a service-level block into markdown headings, and collapses a rule line of any
   length. The comparison code is `scripts/protocomments.py`. This is the cheaper question the tree
   can already answer ([ADR-0067](ADR-0067-image-volume-record.md) decision 1): regenerating and
   diffing would catch structural differences that the Rust compiler and pyright already report,
   and it misses a changed comment entirely.

8. **A service comment needs two copies.** tonic writes every service into a client module and a
   server module and documents both from one declaration, so a comment inside a `service` block, or
   in the unbroken run directly above the `service` line, must appear in the stub twice, and every
   other comment once. The rule is a tally comparison, and a mismatch names both numbers. A rule
   line contains no words and `prost` folds a banner's closing rule into the heading above it, so
   the number of rule lines that survive does not follow from the number written; rule lines are
   required to be at least one instead of an exact count.

## Consequences

- A proto change produces generated-code diffs in the same commit: noisy, reviewable, and every
  build stays reproducible without `protoc`.
- A version bump of `protoc`, `tonic-build` or `grpcio-tools` can produce spurious regeneration
  diffs, so regeneration is deliberate, never a side effect; the `CORTEX_REGEN_PROTO` switch exists
  for this.
- Regenerating raises the runtime minimums the generated code enforces (it refuses to import under
  older grpcio or protobuf), so the declared minimums in the `seam` and orchestrator
  `pyproject.toml` files are raised with every regeneration.
- `tonic-build` compiles as a build dependency on a fresh build even though a normal build skips
  codegen.
- `stubcheck.py` is not a regeneration check. It does not see a field added to the proto and
  missing from a stub, it reads only one direction, and it does not read the Python stubs; each
  limit is explained under the alternatives below.
- The body's transport retry and reconnect policy, deferred when this interface was built, is
  [ADR-0024](ADR-0024-transport-retry.md). What stays open from it is reconnecting a `converse`
  turn before its first event, which needs a replayable request and so a different signature.

## Alternatives rejected

- **betterproto** for Python, for the maturity of `grpc.aio`.
- **Stubs in `body_client`**, the original layout sketch: the wire code is shared by two packages.
- **Regenerating and diffing inside `just check`.** The Python half is free (`grpcio-tools` ships
  its own `protoc` and reproduces the committed files byte for byte in well under a second), but
  the `.pyi` contains no comments and `body_pb2.py` embeds a descriptor with its source info
  stripped, so it catches only structural differences the compiler and pyright already report, plus
  a field added and used nowhere, which no code depends on yet. The Rust half needs a system
  `protoc`, which decision 1 exists to avoid. If a structural check is ever needed, the Python
  regenerate-and-diff is the one to build; it is known to work.
- **Checking the reverse direction**, a comment deleted from the proto but still in the stub: the
  stub contains comments `prost` synthesizes (`Nested message and enum types in ...`), so it would
  need an exception list, and a stale comment worded like a synthesized one would be excused. A
  reworded comment is already reported in the direction that is checked.

## Related

- Code: `scripts/stubcheck.py`, `scripts/protocomments.py`, `body/crates/rpc/build.rs`, the `proto`
  recipe in the justfile.
- Modules: [body-rpc](../modules/body-rpc.md), [`cortex_seam`](../modules/brain-seam.md),
  [repo checks](../modules/repo-checks.md).
- [ADR-0044](ADR-0044-document-rosters.md): the list scan, first built for this record's live
  suite, and the list of scans.
