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
the AGENTS.md gate-4 record. **Landed 2026-07-08 as [ADR-0024](ADR-0024-transport-retry.md)**
with a `RetryingTransport` decorator + `Sleeper` port + lazy `connect_lazy_with_token` channel,
all behind the unchanged `BrainTransport` port. Jitter and a patient eager dial followed on
2026-07-13, and the per-method policy on 2026-07-16 (a `RetryPlan` gate that answers which
calls may be repeated at all, plus a bounded `Health` probe), each behind the same unchanged
port; see that ADR's addenda. What remains open from this deferral is `converse` resilience,
which is the one part no decorator over this port can deliver: reconnecting a turn before its
first event needs a replayable request and so a different signature.

## Addendum (2026-08-25): the committed stubs are held to the proto's comments, and to nothing else

Nothing compared the committed stubs with the proto they came from, so this measured what each
candidate check would actually catch before choosing one. The result reverses the obvious answer:
the expensive check is the one worth declining, and the cheap one catches the only defect that is
silent.

**Regenerating the Python stubs is free and reproduces exactly.** `grpcio-tools` is already a
brain dev dependency and ships its own `protoc`, so no new toolchain is involved. Regenerated
into a temporary directory and compared against the committed copies, all three files came out
byte identical (`body_pb2.py`, `body_pb2.pyi`, `body_pb2_grpc.py`). A regenerate-and-diff step
inside `check-brain` would therefore have worked, and it was still declined, for the next reason.

**It does not see a comment.** Editing the proto comment that states the body's default capture
edge by a single digit and regenerating left all three Python files byte identical again. The
generated `.pyi` carries no comments at all, and `body_pb2.py` embeds a descriptor whose source
info is stripped. So the check would have covered structural drift only, and structural drift is
already loud: a renamed or removed field fails pyright and fails the Rust compile, and a field
added to the proto that nobody regenerated for is a field nobody uses yet. The genuinely silent
case is the one the check would have missed.

**The silent case is real and it is in the Rust stub.** `prost` copies proto comments verbatim
into `body/crates/rpc/src/_generated/cortex.seam.v1.rs`, 338 doc-comment lines of them, and that
file is what a Rust reader actually opens. The comment stating the body's default edge is a
registered far side of a cross-language constant in `crosscheck.py`'s registry; its generated
copy is not, generated code being outside every scan here. Retune the edge and the gate names the
proto, regenerate and the stub follows, forget to regenerate and the stub goes on stating the old
number in the file being read. Meanwhile the Rust half of a regenerate-and-diff cannot join
`just check` at all, because `tonic-prost-build` needs a system `protoc` binary that a clean dev
box need not have, which is the toolchain the committed-stub decision above exists to avoid
requiring.

**Decision: `scripts/stubcheck.py` holds every comment the proto's body carries to the committed
Rust stub, as a text comparison running no codegen, and the regenerate-and-diff is declined.**
The comparison skips the file header above `syntax = `, which attaches to no declaration and which
`prost` does not copy, and normalizes three mechanical things `prost` does on the way out: it
escapes `[` and `]` so rustdoc does not read them as intra-doc links, it markdown-ifies a
service-level block so a line following a rule comes out with heading markers, and it collapses a
rule of any length. Measured against the tree as it stands, the proto's body carries 208 comment
lines, 177 leading and 31 trailing, and all 208 are present in the stub under exactly those three
normalizations and no others. The gate runs in every environment including CI, needs no `protoc`,
no docker and no GPU, and it is the second of the three answers in the ADR-0011 addendum on
evidence out of the gate's reach: a cheaper question the tree can already answer, chosen because
measuring showed it catches strictly more of what matters than the expensive one does.

What it deliberately does not hold is stated plainly so nobody reads it as more than it is. It is
not a regeneration check. It cannot see a field added to the proto and missing from either stub,
and it cannot see the Python stubs at all. The argument for accepting that line is above, and if
it ever stops holding, the thing to build is the Python regenerate-and-diff, which is known to
work and known to be free.

### Proven able to fail, at both levels

**Suite: `scripts/stubcheck.py --root ..` run against the real `proto/body.proto` and the real
`body/crates/rpc/src/_generated/cortex.seam.v1.rs`**, one temporary edit at a time, each reverted
with `git checkout --` and the revert asserted before the next. Fourteen rows, all as designed.

| # | mutation | expected | got |
|---|---|---|---|
| 00 | none, the tree as committed | 0 | 0 |
| 01 | the proto comment's stated default edge retuned, stub not regenerated | 1 | 1 |
| 02 | the bracketed range doc line deleted from the stub | 1 | 1 |
| 03 | a comment added to the proto only | 1 | 1 |
| 04 | a service banner reworded in the proto only | 1 | 1 |
| 05 | the bracketed comment reworded in the proto only | 1 | 1 |
| 06 | a service banner reworded in the stub, both copies | 1 | 1 |
| 07 | a service banner reworded in the stub, one of its two copies | 0 | 0 |
| 08 | the file header above `syntax` reworded (must stay green) | 0 | 0 |
| 09 | a proto rule line shortened (must stay green) | 0 | 0 |
| 10 | a doc comment the proto never wrote added to the stub (must stay green) | 0 | 0 |
| 11 | the proto emptied | 2 | 2 |
| 12 | the proto removed | 2 | 2 |
| 13 | the stub emptied | 2 | 2 |

Row 01 is the whole reason this exists and row 07 is a limitation the measurement found rather
than one anybody designed: tonic emits each service banner twice, once for the client module and
once for the server, so rewording one copy leaves the other answering for it. It is recorded in
[R-434](../refinements/tasks/434-the-stub-check-reads-one-direction-and-one-stub.md) with the
other two gaps rather than papered over here.

**Suite: `scripts/tests/test_stubcheck.py` and `scripts/tests/test_protocomments.py`, 54 tests**,
run against a mutated gate and restored after each. Baseline 54 passed. Fourteen mutants planted
and fourteen killed: bracket unescape dropped (11 failed), heading strip dropped (5), rule
collapse dropped (6), header read as body (5), string awareness dropped so a `//` inside a literal
opens a comment (3), a block comment walked past instead of refused (1), trailing comments not
collected (6), every comment recorded as leading (4), a plain `//` line counted as a doc comment
(4), the empty-proto floor dropped (1), the empty-stub floor dropped (1), no miss ever reported
(6), the CLI exiting 0 with misses on the page (1), and an unreadable input swallowed (4).

The gate lands green, over 208 proto comments (177 leading, 31 trailing) sought among 338 doc
comment lines, so it earns its place by what it catches next rather than by what it caught today.
