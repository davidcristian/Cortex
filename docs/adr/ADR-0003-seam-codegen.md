# ADR-0003: Seam codegen and packaging (Slice 2)

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

Slice 2 makes `proto/body.proto` real on both sides of the seam. That forces decisions
about stub generation, where generated code lives, how it stays exempt from the gates
(ADR-0001 d7, ADR-0002 d4), and which gRPC stacks to use.

## Decisions

1. **Generated stubs are committed**, only inside `_generated` directories:
   `body/crates/rpc/src/_generated/` and `brain/packages/seam/src/cortex_seam/_generated/`.
   Builds are hermetic, so CI and fresh clones never need protoc. Regeneration is a dev
   action: `just proto` (requires a local protoc; 35.1 at the time of writing). A regen
   diff is reviewed like any other change; the proto file's field numbers are frozen, so
   extend, don't renumber.
2. **Rust stack: tonic.** Regeneration is env-gated inside `build.rs`
   (`CORTEX_REGEN_PROTO=1`); a normal build does nothing. The generated file is
   `include!`d inside a wrapper module carrying the needed `allow` attributes
   (`cargo fmt` does not format `include!`d files). Coverage exemption is enforced by
   `--ignore-filename-regex '/_generated/'` on the `check-body` llvm-cov invocation.
3. **The Rust integration suite is `#[ignore]`-marked tests** (e.g.
   `crates/rpc/tests/live.rs`), the Rust analog of the Python `integration` marker
   (AGENTS gate 3): compiled but never run in CI or under coverage; run explicitly
   against a live brain via `just` recipes with `-- --ignored`.
4. **Python stack: grpcio + grpcio-tools** (mature `grpc.aio`), not betterproto.
   Committed `*_pb2.py` / `*_pb2_grpc.py` plus `.pyi` stubs so pyright strict works for
   consumers while `_generated` itself is excluded from ruff/pyright/coverage/linecap.
   Package-absolute imports are produced by staging the proto under
   `cortex_seam/_generated/` before invoking protoc.
5. **Python generated code lives in `brain/packages/seam` (`cortex_seam`).** It is shared
   wire code consumed by the orchestrator (server side) today and the future
   `body_client` (Slice 9, typed `BodyService` client wrapper). This deviates from the
   original layout sketch that placed stubs in `body_client`; ROADMAP updated.
6. **Seam config contract:** the brain server reads `CORTEX_SEAM_HOST` (default
   `127.0.0.1`; `0.0.0.0` inside the container) and `CORTEX_SEAM_PORT` (default
   `50051`) via pydantic-settings; the body-side live check reads `CORTEX_BRAIN_ADDR`
   (default `http://127.0.0.1:50051`). Compose publishes the port on loopback only
   (single-user security posture, ROADMAP assumption 5).

## Consequences

- Proto changes produce generated-code diffs in the same commit, which is noisy but reviewable,
  and it keeps every build reproducible without a protoc dependency.
- protoc/tonic-build/grpcio-tools version bumps can produce spurious regen diffs;
  regenerate deliberately, not as a side effect (the env gate exists for exactly this).
- Regenerating stubs ratchets the gencode-enforced runtime minimums (the generated code
  refuses to import under older grpcio/protobuf), so the declared floors in the
  seam/orchestrator `pyproject.toml`s must be bumped together with every regen.
- tonic-build compiles as a build-dependency on fresh builds (~tens of seconds, cached
  in CI by rust-cache) even though normal builds skip codegen.

## Addendum (2026-07-03): the Slice-2 retry/reconnect deferral, recorded here

Slice 2's one consciously deferred refinement is a transport retry / backoff / reconnect
policy behind the unchanged `BrainTransport` port (the thin `body_rpc` adapter does **no
retries**; a dropped stream or transient failure surfaces straight to the caller, and the
overlay treats a failed turn as terminal until the refinement lands) was recorded in the
ROADMAP deferred-refinements ledger and [body-rpc.md](../modules/body-rpc.md) but never at
this, its origin ADR. Added when the 2026-07-02 audit flagged the missing ADR-side half of
the AGENTS.md gate-4 record.
