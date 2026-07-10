# AGENTS.md (Cortex Engineering Rules)

Authoritative rules for every agent and human working in this repo. A change that
violates anything here is **not done**, regardless of whether it works. This file is the
contract; details live in `docs/` (map: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
index: [docs/index.md](docs/index.md), decisions: `docs/adr/`).

## What this is

A personal, local-first assistant: inference, memory, and state live on-machine; only
tools reach out to external services (e.g. read-only email over IMAP). A host-native
Rust/Tauri app (the **body**: global hotkey, overlay UI, screen capture, audio, input
injection) talks over gRPC to a dockerized Python **brain** (inference via llama.cpp,
orchestration, memory, MCP tool servers).
Three model tiers share one 24 GB GPU: a resident ~9-12B multimodal **cortex**, small
2-4B **subagents**, and an on-demand ~31B **brain** model that requires evicting the
others. See `docs/adr/ADR-0001-architecture.md` for why everything below is the way it is.

## The one hard rule

**State must survive a model swap.** Models are loaded and unloaded from the GPU at any
time; every model instance is stateless and disposable. No conversation state, task
state, working memory, or in-flight context may live inside a model-server process or any
model's KV cache. All such state lives in the external stores (Redis for hot state,
Postgres for durable data) behind the `SessionStore`/`MemoryStore` ports. A handoff is:
serialize context to the store → swap models → rehydrate the target from the store → run
→ persist results → swap back. Every agent is a stateless function over the store.
Interfaces are designed around this rule from day one. Retrofitting it is a rewrite.

## Architecture invariants

- **Hexagonal on both sides of the language boundary.** Pure core (no I/O) → ports
  (Python `Protocol`s / Rust traits) → thin adapters. The core never imports a concrete
  backend, SDK, network client, or OS API. Adapters translate; they hold no business logic.
- **Ports before adapters.** A new capability starts as a port + contract test + fake.
  The real adapter must pass the same contract test as the fake.
- **Polyglot split, one seam.** Brain: Python 3.12+ (`uv`, async-first), dockerized.
  Body + overlay UI: one host-native Rust (stable) / Tauri process, never dockerized.
  Rust never crosses into inference/orchestration; Python never runs on the host body.
- **The seam is gRPC, defined once in [proto/body.proto](proto/body.proto).** No
  in-process FFI (no PyO3). Everything crossing body↔brain is declared in that proto, and
  it is the single source of truth; tonic and the Python stub are both generated from it.
- **Two portability seams**, each a port with per-platform adapters:
  1. OS backends (Rust traits, `cfg(target_os)`-gated crates), with Windows implemented,
     macOS/Linux as `unimplemented!()` stubs that satisfy the traits.
  2. `InferenceBackend` is llama.cpp now (ADR-0005); any future engine is an adapter.
  Everything else stays portable: no hard-coded paths, no OS assumptions in the core,
  all config via env (`pydantic-settings` / typed env parsing in Rust).
- **Orchestration is explicit typed code in the core**, with no heavy agent framework that
  hides control flow. New capabilities and patterns are always welcome (breadth is a
  goal, not creep), provided each lands extensibly: behind a port, contract-tested,
  documented.

## Hard gates (CI and pre-commit run the same `just check`)

1. **≤ 300 lines per non-test source file**, `.py` and `.rs`, comments and blank lines
   included. Hard failure above 300. Split by responsibility, as you go, never as a
   cleanup pass. Generated code (protobuf stubs) is exempt and lives only in clearly
   marked generated-code directories excluded by the scan (ADR-0001 decision 7).
2. **100% line + branch coverage in both toolchains.** Python: `pytest --cov` with
   branch coverage and `--cov-fail-under=100`. Rust: `cargo llvm-cov` with a failing
   100% threshold. Tests assert behavior (fakes over mocks, error/edge paths included), and
   vacuous coverage-chasing tests are a violation. Generated-code directories are
   excluded from coverage measurement too (ADR-0001 decision 7); hand-written wrappers
   around them are normal code, fully gated. Escape hatches (`# pragma: no cover`,
   `#[cfg_attr(coverage, coverage(off))]`) only for genuinely unreachable code, each with
   an inline reason (e.g. non-target-OS `unimplemented!()` stubs, `__main__` guards).
3. **Real GPU/OS/network calls live only in thin adapters.** Their live tests are
   `integration`-marked, excluded from the coverage gate, run manually on the host, never
   in CI. **"On the host" includes the agent:** GPU and model-behavior validation is run via
   Docker against the real models (Docker-reachable at the mount, GPU via the container toolkit)
   by the agent, not something to punt to the maintainer; only genuinely OS-native validation
   (the Windows Rust/Tauri body) is host-only. **CI runs without a GPU** and builds each toolchain
   (Python, Rust, and the `body/app/` overlay's node tree). Each toolchain's job runs when a change
   can affect it (path-filtered, ADR-0006); shared gate files (justfile, proto, scripts, workflows)
   and unrecognized paths trigger all of them (fail closed), with one deliberate carve-out:
   `.md` files outside a toolchain tree are toolchain-inert (the classifier's trailing markdown
   rule, ADR-0006, so only the unconditional line-cap job sees them).
4. **Doc-first Definition of Done.** Per slice: design doc/ADR → define or adjust the
   port → tests → implementation → module doc + runbook updates → **record every consciously
   deferred refinement in the ROADMAP's "Deferred refinements & later work" section (and at its
   origin ADR)**. A change that touches code but not docs is incomplete; a refinement knowingly
   punted but not written down is a lost decision. That section is the one place none is lost, so
   updating it is part of finishing a slice, not an afterthought. Every module has a short contract
   doc in `docs/modules/` (purpose, public contract, invariants, dependencies) that lets a
   future agent work on it without reading the tree.
5. **Types & quality.** Python: `ruff` (lint + format) clean; `pyright` in strict mode
   clean; no unjustified `Any`; public functions fully typed; explicit typed exceptions, never
   bare `except`. Rust: `cargo fmt --check` clean; `cargo clippy -- -D warnings` clean;
   no `unwrap()`/`expect()` on fallible paths (`Result` + `thiserror`); `unsafe` requires
   an ADR. Both: structured logging, no secrets in logs, **no secrets in the repo**,
   config via env only.
6. **`just check` is the single gate**, running ruff, pyright, pytest + coverage,
   `cargo fmt --check`, clippy, `cargo test`, `cargo llvm-cov`, and the cross-tree
   line-cap scan. Pre-commit mirrors it. Run it before declaring anything done.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), enforced by two
commit-msg hooks (conventional-pre-commit validates the type/format; `scripts/commitlint.py`
the subject style). Imperative mood is the one convention no machine checks:

- Format: `type(scope)?: subject`, in imperative mood, lowercase subject, no trailing
  period, subject ≤ 72 chars. The body explains what and why, wrapped at 72.
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`,
  `revert`. Breaking change: `!` after type/scope plus a `BREAKING CHANGE:` footer.
- Scopes (optional, only when the change is contained to one area): `brain`, `body`,
  `scripts`, `proto`, `docs`, `ci`. Never repeat the type as its own scope
  (`docs(docs)`).
- **Self-contained: no volatile references.** A message must still read correctly once
  the planning docs move on, so never cite a slice number, an ADR number, a roadmap
  entry, an audit, a commit hash, or any numbered pointer into a mutable doc (`gate 3`,
  `assumption 1`, `§5`). Describe the substance instead: name the capability, the
  decision, or the behaviour. Concrete code paths, package names, env vars, and
  measurements are stable, so they stay welcome.
- **No dashes as punctuation.** No em dash, en dash, or spaced `--` in a subject or
  body; restructure the sentence rather than swapping in another mark. Hyphenated words
  and CLI flags (`--locked`) are unaffected.
- One logical change per commit (typically one slice, one fix, or one doc change).
  Every commit passes `just check`, which the pre-commit hook enforces.

## Working agreement

- **Vertical slices, not horizontal layers.** Each increment is a thin end-to-end path,
  small, green, and documented. No big-bang scaffolding of empty layers.
- **Scope grows freely; design stays extensible.** More capability is welcome. Feature
  richness is a goal and feature creep is not a concern. But every addition is built
  for extension: behind a port, contract-tested, swappable, documented. Cutting scope
  is never the answer to a design problem; designing the seam is.
- **Interfaces before implementations.** Port → contract test + fake → real adapter.
- **Decisions are written down.** Any non-obvious choice becomes an ADR in `docs/adr/`.
  Underspecified requirement? Record your interpretation as an ADR and proceed. Don't
  block, and flag the riskiest assumptions in your summary.
- **Claims carry evidence.** Never report a gate green without having run it in this
  session; show the command and result. Unverified statements are labeled assumptions.
- **Distrust green.** A gate that cannot fail is a defect: after wiring or changing one,
  prove it fails on a violation before trusting it.
- **Read before you write.** Open the file and its call sites before editing; never edit
  from memory of its contents or invent an API. Check the signature.
- **Report faithfully.** Failing tests are reported with their output; skipped steps are
  named. A wrong "done" costs more than an honest "not yet".
- **Stop when surprised.** When output contradicts your model of the system, re-derive
  from evidence. Don't pattern-match to the nearest familiar failure and push through.
- Keep this file and all docs pointer-heavy and current; context bloat is a defect.

## Repo map

Entries marked *(planned)* are target layout; docs/ROADMAP.md says which slice delivers each.

```
proto/            body↔brain gRPC contract (source of truth for the seam)
docs/             ARCHITECTURE.md, index.md, ROADMAP.md, adr/, modules/, runbooks/, assets/ (logo)
brain/            Python workspace (uv), dockerized (brain/Dockerfile)
  packages/       core (pure logic + ports), seam (committed gRPC stubs + typed facade),
                  orchestrator (hosts BrainService), session (Redis SessionStore +
                  TaskStore adapters), inference (llama.cpp InferenceBackend adapter), embedding
                  (llama.cpp CPU Embedder adapter), memory (pgvector MemoryStore adapter),
                  tools (MCP-client ToolRegistry adapter + audit sink), email (read-only IMAP
                  MCP server over ProtonMail Bridge), body_client (BodyGateway gRPC client of the
                  body's BodyService, which is the brain→body seam, ADR-0023);
                  subagents live in core (runner, scheduler, spawn tool) + session (task store);
                  (planned) model_manager (Slice 11), shared
body/             Rust/Tauri workspace, host-native
  crates/         core (pure logic + OS traits [Hotkey, AudioControl] + BrainTransport port),
                  rpc (tonic adapter, committed stubs; BrainService client + BodyService server),
                  os_windows (real global-hotkey + Core Audio backends, cfg(windows)) +
                  os_linux/os_macos (cfg-gated stubs)
  app/            React+Vite overlay (gated 100%) + its host-native Tauri src-tauri
                  shell (ungated, host-validated) named cortex-body, its own workspace
scripts/          repo gates: linecap.py (300-line cap), coverage_gate.py (Rust branches),
                  ci_paths.py (CI path classifier), commitlint.py (commit-subject style)
.github/          GPU-less CI running the same `just` recipes as local dev
justfile          `just check` + check-*; proto, up/down, brain-serve, seam-health
docker/           Compose stack (run via `just up`/`up-gpu`, or `docker compose --project-directory .
                  -f docker/docker-compose.yml …`): docker-compose.yml (brain + redis, loopback-only)
                  + overrides: gpu (llama.cpp server + read-only model mount, ADR-0005/0007), memory
                  (Postgres+pgvector + CPU embedder, ADR-0008), tools + email (MCP sidecars: filesystem,
                  read-only email, ADR-0009), subagents (CPU llama-server, ADR-0010) + subagents-roster
                  (a second CPU model as an ADR-0018 roster alternate), body (points the brain at the
                  host-native body's BodyService, ADR-0023); + postgres/init.sql
```
