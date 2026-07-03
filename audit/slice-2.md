# Audit of Slice 2 (The seam: proto compiled on both sides)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Every functional claim in the Slice 2 section is implemented and verifiable in code: proto/body.proto v0 carries BrainService.Health + Converse with frozen field numbers; committed codegen exists on both sides (tonic stubs in body/crates/rpc/src/_generated behind an env-gated build.rs, grpcio stubs + .pyi in brain/packages/seam/src/cortex_seam/_generated behind a typed facade); contract tests with fakes exist on both sides (FakeBrain over loopback in Rust, a loopback grpc.aio server over fake engine parts in Python); the _generated exemption is wired into linecap, ruff, pyright, Python coverage, and cargo llvm-cov; the seam-health justfile recipe runs the #[ignore]d live Health check against the Compose brain, whose end-to-end run is documented in the delivery commit (5197b0f) and the local-dev-wsl runbook; ADR-0003's six decisions all match the code, and the one consciously deferred refinement (transport retry/reconnect) is recorded in the ROADMAP ledger. The verdict is downgraded from fully-implemented solely for low-severity documentation staleness: the Slice 2 runbook still claims 'No GPU wiring exists yet' and speaks of Slice 4 in the future tense although Slice 4 shipped docker-compose.gpu.yml, and the retry deferral is absent from its origin ADR despite the ledger intro promising ADR-side records. No promised code or test is missing.

## Claims checked (14)

- **✅ verified**. proto/body.proto v0 defines BrainService with Health and the Converse shape (stream ClientEvent -> stream ServerEvent), field numbers frozen
  - Evidence: proto/body.proto:14-22 (service BrainService; rpc Converse :18, rpc Health :21); v0 freeze note :2; ClientEvent/UserTurn/Cancel :24-37; ServerEvent oneof (TextDelta/ToolActivity/StatusUpdate/TurnComplete/SeamError) :39-53; HealthRequest/HealthReply :55-56

- **✅ verified**. tonic build in body/crates/rpc: env-gated build.rs regeneration plus committed stubs in a _generated directory
  - Evidence: body/crates/rpc/build.rs:22-28 (no-op unless CORTEX_REGEN_PROTO=1, then tonic_prost_build into src/_generated); committed stub body/crates/rpc/src/_generated/cortex.seam.v1.rs exists; wrapper module with clippy allows body/crates/rpc/src/lib.rs:18-28

- **✅ verified.** Generated Python stubs live in brain/packages/seam (cortex_seam) with a typed facade the rest of the brain imports from
  - Evidence: brain/packages/seam/src/cortex_seam/_generated/{body_pb2.py, body_pb2.pyi, body_pb2_grpc.py} committed; typed facade brain/packages/seam/src/cortex_seam/__init__.py:13-58 (re-exports + re-annotated add_*Servicer helpers), __all__ :60-88; consumed via cortex_seam by the orchestrator (brain/packages/orchestrator/src/cortex_orchestrator/server.py:18-25)

- **✅ verified**. The typed BodyService client wrapper (body_client) is deferred to Slice 9, not part of this slice
  - Evidence: No body_client package under brain/packages/ (listing: core, email, embedding, inference, memory, orchestrator, seam, session, tools); Slice 9 still planned (docs/ROADMAP.md:403-409); ADR-0003 decision 5 (docs/adr/ADR-0003-seam-codegen.md:34-37) and AGENTS.md repo map mark body_client as planned

- **✅ verified.** A body-side dev command exists that calls brain Health (justfile seam-health running the #[ignore]d live suite against CORTEX_BRAIN_ADDR)
  - Evidence: justfile:109-110 (seam-health: cargo test -p body-rpc --test live -- --ignored --nocapture); body/crates/rpc/tests/live.rs:39-56 (brain_reports_ready_over_the_live_seam calls Health via BrainSeamClient), :23-25 (CORTEX_BRAIN_ADDR default http://127.0.0.1:50051); brain served in Compose with loopback publish docker/docker-compose.yml:26 and a healthcheck calling the real Health RPC :33-41

- **📄 verified-as-documented (host-only run; paper trail checked)**. The Health call was run end-to-end on the host (brain in Compose, caller on host)
  - Evidence: Delivery commit 5197b0f ('feat: gRPC seam end-to-end, Health over Compose', 2026-06-28): 'Verified end-to-end: brain healthy in Compose, body live seam test passes from the host'; runbook docs/runbooks/local-dev-wsl.md:123-138 describes the run; live test is #[ignore]-marked per ADR-0003 d3 (body/crates/rpc/tests/live.rs:40)

- **✅ verified.** Contract tests with fakes on both sides of the seam
  - Evidence: Body: body/crates/rpc/tests/client.rs:33-61 (scripted FakeBrain serving the generated BrainService on 127.0.0.1:0; 7 tests covering ready, Rpc vs Connection taxonomy, brain-death-after-connect :165-187, Converse-unimplemented :215-233) and body/crates/core/tests/transport.rs:9-14 (FakeTransport contract for the BrainTransport port). Brain: brain/packages/orchestrator/tests/test_server.py:42-52 (loopback grpc.aio server over fake engine parts EchoInferenceBackend + InMemorySessionStore; Health tests :55-95) and brain/packages/seam/tests/test_facade.py:6-41 (wire round-trips, export surface)

- **✅ verified.** Generated-code exemption is wired into the line-cap scan and coverage/lint/type configs
  - Evidence: scripts/linecap.py:27 (_generated in SKIPPED_DIRS, doc :5); brain/pyproject.toml:57 (pyright exclude **/_generated) and :74 (coverage omit */_generated/*); ruff.toml:20 (extend-exclude **/_generated); justfile:67 (cargo llvm-cov --ignore-filename-regex '/_generated/'); matches ADR-0002 decision 4 (docs/adr/ADR-0002-toolchain-gates.md:26-28)

- **✅ verified**. Runbook docs/runbooks/local-dev-wsl.md exists and covers brain-in-Compose plus the host-side dev loop from WSL
  - Evidence: docs/runbooks/local-dev-wsl.md: env config table :31-41, run-the-brain (native + Compose) :69-86, host-side Converse probe :88-121, live seam check :123-138, stub regeneration :149-155

- **✅ verified.** Gate proven: gRPC seam as single source of truth (codegen in both builds from the one proto)
  - Evidence: justfile:80-84 (just proto regenerates the Python stubs via grpc_tools.protoc and the Rust stub via CORTEX_REGEN_PROTO=1 cargo build -p body-rpc, both from proto/body.proto); committed stubs on both sides (body/crates/rpc/src/_generated/, brain/packages/seam/src/cortex_seam/_generated/); normal builds/CI never invoke protoc (body/crates/rpc/build.rs:22-24, ADR-0003 d1)

- **✅ verified.** ADR-0003 records the seam codegen/packaging decisions and the code matches every decision
  - Evidence: docs/adr/ADR-0003-seam-codegen.md: d1 committed stubs (both _generated dirs exist); d2 env-gated tonic regen (build.rs:22) + coverage regex (justfile:67); d3 #[ignore] live suite (live.rs:40,59); d4 grpcio + committed .pyi (body_pb2.pyi exists, ruff.toml:20/pyproject excludes); d5 stubs in cortex_seam not body_client (packages listing); d6 env contract (config.py:23-26, live.rs:24, compose loopback :26)

- **✅ verified**. Seam env config contract: CORTEX_SEAM_HOST/CORTEX_SEAM_PORT read by the brain via pydantic-settings, CORTEX_BRAIN_ADDR by the body live check, Compose publishing loopback-only
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/config.py:20-31 (SeamServerConfig, env_prefix CORTEX_SEAM_, defaults 127.0.0.1:50051); body/crates/rpc/tests/live.rs:23-25; docker/docker-compose.yml:26 ('127.0.0.1:50051:50051') and :59 (redis loopback)

- **✅ verified**. Module contract docs exist for both seam sides and match the code
  - Evidence: docs/modules/brain-seam.md (facade API list matches cortex_seam.__all__, regen recipe matches justfile:80-83, invariants match _generated contents); docs/modules/body-rpc.md (BrainSeamClient contract matches tests/client.rs behavior incl. status-origin split; no-retries note :6; live-check section matches live.rs)

- **✅ verified**. The Slice 2 deferred refinement (transport retry/reconnect policy) is recorded in the ROADMAP deferral ledger
  - Evidence: docs/ROADMAP.md:457-461 ('Seam / transport, Slice 2 (ADR-0003)': no-retries deferral behind the unchanged BrainTransport port); echoed in docs/modules/body-rpc.md:6

## Gaps (2)

### G1 · severity low · **not documented as a deferral**

Stale text in the Slice 2 runbook docs/runbooks/local-dev-wsl.md: line 23-24 states 'No GPU wiring exists yet. The docker/docker-compose.gpu.yml override arrives with Slice 4', and line 90-91 says the echo backend answers 'until Slice 4 delivers real inference'. Slice 4 is done: docker/docker-compose.gpu.yml exists, justfile has up-gpu/down-gpu (justfile:101-105), and docs/runbooks/llamacpp-gpu.md covers the GPU stack. (The echo statement is still functionally true for the default path (echo remains the default backend, config.py:68), but the future tense is superseded.) Doc staleness only; no code is missing.

**Adversarial re-check: confirmed.** I could not refute the auditor. The stale future-tense Slice 4 references exist exactly where claimed in docs/runbooks/local-dev-wsl.md, the runbook was never revised after Slice 4 landed, and no written deferral or known-staleness record exists in the ROADMAP deferred-refinements ledger, ADR-0003 (the runbook's origin ADR), ADR-0007 (Slice 4), or any other doc. A side observation strengthening the auditor: docs/modules/brain-core.md:239 carries similar 'until Slice 4' phrasing ('the runtime wiring until Slice 4'), though that one is arguably still accurate as a historical description of the shipped fakes. The gap stands as reported: doc staleness only, undocumented.

### G2 · severity low · documented (docs/ROADMAP.md:457-461 ('Seam / transport (Slice 2)') and docs/modules/body-rpc.md:6)

Minor ledger inconsistency: the ROADMAP deferral ledger intro (docs/ROADMAP.md:453-454) says each deferral is 'recorded at its origin ADR', but the Slice 2 transport-retry deferral appears only in the ledger (ROADMAP:457-461) and docs/modules/body-rpc.md:6. ADR-0003 itself never mentions a retry/reconnect policy. The deferral itself IS written down; only the promised ADR-side record is absent.
