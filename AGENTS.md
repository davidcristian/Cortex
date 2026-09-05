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

1. **≤ 300 lines per non-test source file**, `.py`, `.rs`, `.ts` and `.tsx`, comments and
   blank lines included. Hard failure above 300. Split by responsibility, as you go, never
   as a cleanup pass. Generated code (protobuf stubs) is exempt and lives only in clearly
   marked generated-code directories excluded by the scan (ADR-0001 decision 7), as is
   build output (`dist/`, `coverage/`). The overlay's stylesheet and markup and
   [proto/body.proto](proto/body.proto) are deliberately outside the cap, argued in the
   ADR-0011 line-cap addendum; nothing else is.
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
   (Python, Rust, the `body/app/` overlay's node tree, and the Tauri shell beside it, whose job is
   the one that installs system libraries). Each toolchain's job runs when a change
   can affect it (path-filtered, ADR-0006); shared gate files (justfile, proto, scripts, workflows)
   and unrecognized paths trigger all of them (fail closed), with one deliberate carve-out:
   `.md` files outside a toolchain tree are toolchain-inert (the classifier's trailing markdown
   rule, ADR-0006, so only the unconditional line-cap job sees them).
4. **Doc-first Definition of Done.** Per slice: design doc/ADR → define or adjust the
   port → tests → implementation → module doc + runbook updates → **record every consciously
   deferred refinement in `docs/refinements/` (one file per task under `tasks/`, plus its dated
   addendum at the origin ADR)**, per [ADR-0039](docs/adr/ADR-0039-backlog-per-task.md). A change
   that touches code but not docs is incomplete; a refinement knowingly punted but not written
   down is a lost decision. That directory is the one place none is lost, so updating it is part
   of finishing a slice, not an afterthought. **A task's status lives on its own `**Status:**`
   line and nowhere else**, and [docs/refinements/index.md](docs/refinements/index.md) is
   generated from those files by `just backlog`, so never edit the index by hand. Its companion is
   [docs/host/](docs/host/index.md), recorded the same way and holding the other kind of not-done:
   work that is built but needs hardware this repo is not developed on, meaning a real Win32
   desktop session or a 24 GB GPU. Anything the agent can reach, including GPU and model behavior
   via Docker, belongs in neither and is done now. Every module has a short contract
   doc in `docs/modules/` (purpose, public contract, invariants, dependencies) that lets a
   future agent work on it without reading the tree.
5. **Types & quality.** Python: `ruff` (lint + format) clean; `pyright` in strict mode
   clean; no unjustified `Any`; public functions fully typed; explicit typed exceptions, never
   bare `except`. Rust: `cargo fmt --check` clean; `cargo clippy -- -D warnings` clean;
   no `unwrap()`/`expect()` on fallible paths (`Result` + `thiserror`); `unsafe` requires
   an ADR. Both: structured logging, no secrets in logs, **no secrets in the repo**,
   config via env only.
6. **`just check` is the single gate.** It runs ruff, pyright, pytest with coverage,
   `cargo fmt --check`, clippy, `cargo test`, `cargo llvm-cov`, the overlay's typecheck and
   Vitest coverage, and **the cross-tree scans**, eleven of them:

   - `linecap.py`: the 300-line cap, across all three toolchains.
   - `dashcheck.py`: no dash used as punctuation in any text file (ADR-0026).
   - `crosscheck.py`: every value this repo spells in more than one place still agrees, whether
     the far side declares it, orders itself against it, accepts it among several, or spends it
     inside a string, a stylesheet or a bare literal (ADR-0029 cross-language-constant addendum).
   - `bindcheck.py`: every compose bind mount resolves outside the repo, onto a path git tracks,
     or onto one git ignores, so `docker compose up` cannot create a directory the index would
     take (ADR-0026 bind addendum).
   - `defaultcheck.py`: one variable spelled in several compose files has one default in all of
     them, compared as a value so docker's own syntax may re-spell it (ADR-0026 defaults
     addendum).
   - `volumecheck.py`: every volume an image declares is covered by a mount or a tmpfs in each
     service that runs it, so no container leaves an anonymous volume on the host. It reads a
     recorded answer, because the gate cannot run docker, and holds that record to every `VOLUME`
     and `ONBUILD VOLUME` the Dockerfiles here declare (ADR-0011 out-of-reach-evidence addendum
     and the addendum on what a base declares for its children; `just image-volumes` re-derives
     the record).
   - `stubcheck.py`: the committed Rust seam stub still carries every comment
     [proto/body.proto](proto/body.proto) does, which catches a skipped regeneration no compiler
     would (ADR-0003 stub-fidelity addendum).
   - `samplecheck.py`: every log line a runbook shows an operator matches the call site that
     writes it, on level, logger, message, and field names in render order. Field names only,
     because a captured value is a dated reading. A call whose field set the source cannot list,
     the tool audit's, is held instead to a line the sink's own suite asserts whole (ADR-0009
     proven-line addendum). A module may not spell one logger name or one message twice (ADR-0009
     sample-membership, one-name and one-message addenda).
   - `rostercheck.py`: every roster a document keeps names the set it really describes. It
     compares membership and naming only, since the sentence beside each name is what the roster
     is for (ADR-0003 live-roster addendum, ADR-0029 roster addenda).
   - `flagcheck.py`: every subagent server the stack starts carries the flags its tier requires,
     the reasoning-off pair and the tool-capable chat template. The set is derived from the
     stack's own wiring and argv rather than read from a list, so a server added anywhere is
     covered the day it is written, and every model artifact is named under a
     `CORTEX_MODEL_FILE_` variable found structurally rather than by prefix (ADR-0029 addenda on
     deriving the set a rule runs over, on covering both placements of one tier, and on holding
     the convention it is read out of).
   - `backlogcheck.py`: each backlog index matches the task files it describes and every link in
     them resolves, so a status is written in exactly one place; and every `#fragment` in the repo
     names a heading its target really offers (ADR-0039).

   Each of them runs unconditionally, in CI too, and this list is itself held to the recipes that
   run them (ADR-0003 scan-roster addendum). Pre-commit mirrors it. Run it before declaring
   anything done.

   **One recipe is deliberately outside it**: `check-shell` (clippy on the Tauri shell), which CI
   schedules and `just check` does not run. It is the only check needing system libraries, the
   Linux GTK/webkit/dbus dev packages a clean dev box need not have, and requiring them would make
   the single gate unrunnable rather than strict (ADR-0011 shell-clippy addendum). Nothing else
   may join it. A check whose *evidence* is out of reach, rather than its toolchain, is not a
   second exception: it records the far answer in the tree, gates the record, and re-derives it
   with a hand-run recipe (ADR-0011 out-of-reach-evidence addendum).

## Prose

Code, comments, documentation, and commit messages are written to be understood on one
reading. Clarity is the target, not brevity: a sentence cut until it needs a second
reading has failed this rule twice.

- **Comment only what the code cannot say.** A comment earns its place by explaining a
  non-obvious why: a workaround, a spec citation, an ordering constraint, a measured
  number, a rejected alternative. Comments that restate the code are deleted, and a clear
  name or a smaller function is always preferred to a comment explaining an unclear one.
- **Docstrings are short.** One line saying what the module or function does, plus
  arguments and return values where those are not obvious. Design reasoning belongs in
  `docs/modules/` or in the ADR that decided it, not in a docstring the reader scrolls
  past to reach the code. Ten lines is the practical ceiling; beyond that it is a document
  living in the wrong file.
- **Name the subject and say what it does.** Every sentence states plainly what it is
  about. Do not withhold the subject for effect, and do not open a module with a riddle.
- **Code has no intentions.** A gate does not know, notice, want, refuse, or believe. It
  passes, fails, reads, writes, returns, or raises. Write "the check fails when the tail
  carries no marker", not "the check refuses a tail it has no word for".
- **No metaphor outside a designed name.** Metaphor is allowed in exactly one place: a
  naming family built under the naming rule below, whose entries are labels and whose
  structure carries real meaning. Most such families are user-facing (the mark's styles,
  the window's edges), and an internal one qualifies on the same terms when it is defined
  where it is introduced, as `RankBasis` is. A metaphor may be a label. It may never be
  the explanation of a mechanism. Write "an unrecognized chat-template format", not "a
  third family's spelling".
- **No aphorisms.** State the consequence instead of coining a maxim about it. Not "a
  reducer that guesses is a gate that agrees with itself", but "unknown forms are refused,
  because a guessed reduction would report two values as equal that were never compared".
- **Define jargon once, then use it.** A precise term introduced where it is first used is
  welcome (`site` and `mention` in `scripts/couplings.py`). A figurative term standing in
  for a technical one is not.
- **No AI-isms.** Machine-written prose has recognizable tics and every one of them costs
  clarity: runs of short parallel fragments, the "not X, but Y" reversal, throat-clearing
  openers ("it is worth noting that"), inflated stakes ("critically", "fundamentally",
  "load-bearing"), stock intensifiers ("seamlessly", "robust", "comprehensive"), and
  closing sentences that restate the paragraph above them. Write the specific fact instead.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), enforced by two
commit-msg hooks (conventional-pre-commit validates the type/format; `scripts/commitlint.py`
the subject style). Imperative mood is the one convention no machine checks:

- **The subject says what changed; the body says why it was needed.** A subject leads with
  a verb of change (`add`, `fix`, `remove`, `split`, `rename`, `reject`, `document`), names
  what changed, and reads correctly to someone who has not seen the diff. It does not
  describe a relation between two artifacts as though the relation were the action. The
  body states the problem that prompted the change, then what the change does about it,
  and follows the prose rules above.
- **Most bodies are one or two short paragraphs, under about 120 words.** Say why and what,
  then stop. Only three things earn more room: a measurement recorded nowhere else, an
  alternative that was tried and rejected, and a failure mode a future reader would
  otherwise recreate. Design reasoning belongs in `docs/`, and a message that needs it
  should point there instead of restating it. A commit is not the place to argue a
  decision, and a reader looking for what changed should not have to mine a page of prose
  to find it.
- Format: `type(scope)?: subject`, in imperative mood, lowercase subject, no trailing
  period, subject ≤ 72 chars. The body explains what and why, wrapped at 72, which
  `scripts/commitlint.py` now checks: a line past 72 that could have been wrapped fails, and one
  whose longest word alone is over the wrap (a URL, a path, a long identifier) is exempt, having
  nowhere to break. Two kinds of line are exempt by what they are rather than by their width,
  because reflowing a paste changes what it says: a line inside a code fence, and one whose first
  token is a bare `$` prompt. Those two kinds are how a message declares a paste, and a paste is
  exempt from this rule and from the dash ban below, and from nothing else. A fence left open is
  itself reported. A `BREAKING CHANGE:` footer is neither kind, so it wraps like the prose it is.
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
  measurements are stable, so they stay welcome. A paste is **not** exempt: a pasted hash
  stops resolving on the same rewrite a cited one does, and `git show <sha>` says what the
  paste meant.
- **No dashes as punctuation.** No em dash, en dash, or spaced `--` in a subject or
  body; restructure the sentence rather than swapping in another mark. Hyphenated words
  and CLI flags (`--locked`) are unaffected, as is any line inside a paste, whose text
  punctuates nothing and which the author did not write.
- One logical change per commit (typically one slice, one fix, or one doc change).
  Every commit passes `just check`, which the pre-commit hook enforces.

## Working agreement

- **Vertical slices, not horizontal layers.** Each increment is a thin end-to-end path,
  small, green, and documented. No big-bang scaffolding of empty layers.
- **Scope grows freely; design stays extensible.** More capability is welcome. Feature
  richness is a goal and feature creep is not a concern. But every addition is built
  for extension: behind a port, contract-tested, swappable, documented. When a design is
  hard, design the seam rather than cutting scope to avoid it.
- **Interfaces before implementations.** Port → contract test + fake → real adapter.
- **Decisions are written down.** Any non-obvious choice becomes an ADR in `docs/adr/`.
  Underspecified requirement? Record your interpretation as an ADR and proceed. Don't
  block, and flag the riskiest assumptions in your summary.
- **Names are designed, never defaulted.** Anything pickable or family-shaped (a registry
  of styles, themes, modes) gets a naming scheme built with the same craft as its visuals:
  one word per entry, one metaphor per family, and the family's structure carrying real
  meaning. Sibling families draw on related vocabularies: the mark's labels are movements
  of thought (Mull, Muse, Hunch, Tangent) and the window's are depths of sleep (Still,
  Lucid, Reverie, Trance). No collisions with any existing
  family or token. Propose a recommended set with honest alternates before landing one.
  Storage keys freeze once anything beyond the host machine depends on them; until then a
  rename is cheap (a resolver alias over the old name), so name the key right on day one and
  heal a mismatch while healing is free (`body/app/src/mark/marks.ts` carries both halves of
  that lesson). The worked standard lives in the bubble-mark ADR's naming addendum
  (`docs/adr/`).
- **Claims carry evidence.** Never report a gate green without having run it in this
  session; show the command and result. Unverified statements are labeled assumptions.
- **Prove a gate can fail.** A gate that cannot fail is a defect: after wiring or changing one,
  prove it fails on a violation before trusting it. A mutation table is that proof written
  down, so **it names the suite its counts are over**: a commit's own diff hands the next
  reader the file and the edit, and says nothing about the collection a number counts. No
  machine checks this, for the reason none checks imperative mood, and the replay of the
  record that measured both halves is the ADR-0002 replay addendum.
- **Read before you write.** Open the file and its call sites before editing; never edit
  from memory of its contents or invent an API. Check the signature.
- **Report faithfully.** Failing tests are reported with their output; skipped steps are
  named. Report a task as done only when it is: an inaccurate "done" costs more to undo
  than an accurate "not yet" costs to finish.
- **Stop when surprised.** When output contradicts your model of the system, re-derive
  from evidence. Don't pattern-match to the nearest familiar failure and push through.
- Keep this file and all docs pointer-heavy and current; context bloat is a defect.

## Repo map

Entries marked *(planned)* are target layout; docs/ROADMAP.md says which slice delivers each.

```
proto/            body↔brain gRPC contract (source of truth for the seam)
docs/             ARCHITECTURE.md, index.md, ROADMAP.md, adr/, modules/, runbooks/,
                  refinements/ (deferred-refinements backlog: one file per task under tasks/
                  + a generated index, ADR-0039),
                  host/ (work only the host's hardware can do: a Win32 desktop session or a
                  24 GB GPU, same shape), assets/ (logo)
brain/            Python workspace (uv), dockerized (brain/Dockerfile)
  packages/       core (pure logic + ports), seam (committed gRPC stubs + typed facade),
                  orchestrator (hosts BrainService), session (Redis SessionStore +
                  TaskStore adapters), inference (llama.cpp InferenceBackend adapter), embedding
                  (llama.cpp CPU Embedder adapter), memory (pgvector MemoryStore adapter),
                  tools (MCP-client ToolRegistry adapter + audit sink), email (read-only IMAP
                  MCP server over ProtonMail Bridge), body_client (BodyGateway gRPC client of the
                  body's BodyService, which is the brain→body seam, ADR-0023);
                  subagents live in core (runner, scheduler, spawn tool) + session (task store);
                  model_manager (the model-host supervisor sidecar that runs one llama-server per
                  logical model + the ModelHost HTTP adapter, ADR-0030); (planned) shared
body/             Rust/Tauri workspace, host-native
  crates/         core (pure logic + OS traits [Hotkey, AudioControl] + BrainTransport port),
                  rpc (tonic adapter, committed stubs; BrainService client + BodyService server),
                  os_windows (real global-hotkey + Core Audio backends, cfg(windows)) +
                  os_linux/os_macos (cfg-gated stubs)
  app/            React+Vite overlay (gated 100%) + its host-native Tauri src-tauri
                  shell (fmt- and clippy-checked in CI, running it is host-only) named
                  cortex-body, own workspace
scripts/          repo gates and their readers. Eleven scans run in `just check`; the rest are
                  modules those scans read. Each gate is listed with the helpers it uses.

                  linecap.py        the 300-line cap
                  dashcheck.py      no dash used as punctuation
                  crosscheck.py     one value spelled in several places still agrees
                    couplings.py    the vocabulary the registry is written in
                    registry.py     names the parts the registry is joined from
                    values.py       what a value reduces to, and how a mention spells it
                    readings.py     how a constant's readings must stand
                    needles.py      how a rendered needle is searched for, and what a miss reports
                    seamcouplings.py, endpointcouplings.py, shippedcouplings.py,
                    capturecouplings.py, boundscouplings.py, subagentcouplings.py,
                    modelhostcouplings.py, emailcouplings.py, fixturecouplings.py,
                    overlaycouplings.py, logcouplings.py, trailcouplings.py
                                    the registry itself, in twelve parts (nine split off at the
                                    line cap, three added as subjects): the other tree's code,
                                    the address each side answers on, the brain's shipped
                                    defaults, one capture's numbers, a delegated run's bounds,
                                    the subagent tier's budgets, the model host's tiers, the
                                    email sidecar's answers, a measurement fixture, the overlay
                                    stylesheet, work-identity names, and the per-line trails
                  bindcheck.py      no compose bind default lands unignored in the tree
                    composemounts.py    reads mounts out of a compose file
                  defaultcheck.py   one variable, one default, in every compose file spelling it
                    composedefaults.py  reads shell substitutions
                  volumecheck.py    every declared image volume is covered by a mount or a tmpfs
                    composeservices.py  what a service runs, covers, and is built from
                    composetargets.py   the container path a mount names, in all four spellings
                    imagevolumes.py     the recorded answer, since the gate cannot run docker
                    imagedrift.py       asks a real docker and reports moved rows (just image-volumes)
                    dockerfilevolumes.py  VOLUME and ONBUILD VOLUME as the tree declares them
                    dockerfilebases.py    the base image a built row stands on
                  stubcheck.py      the committed Rust stub still carries every proto comment
                    protocomments.py    a comment in both spellings, made comparable
                  samplecheck.py    a documented log line still matches the call site writing it
                    logsamples.py       what a documented sample claims
                    logcalls.py         what the call attaches, and the message it may not repeat
                    logfields.py        the field list, off the call or off the binding above it
                    assertedlines.py    the lines a sink's own suite asserts whole, where the
                                        source cannot list a call's fields
                    loggernames.py      which module owns a logger name
                  rostercheck.py    a document's roster still names the set it describes
                    rosters.py          which rosters exist and where each real set is read from
                    rosternames.py      what a page names, in three shapes, within two bounds
                    rostermembers.py    what the tree really holds, this block included
                    scanrecipes.py      which scans the gate and CI both run
                  flagcheck.py      every subagent server carries the flags its tier requires
                    subagentservers.py  which servers a composed stack starts, derived from wiring
                    hostedtiers.py      the model host's own subagent tier
                    composestarts.py    a service's command and environment
                    moduleconstants.py  what a module's top level binds, read without importing
                    artifactnames.py    every model artifact and the variable naming it
                  backlogcheck.py   a backlog index matches its task files, and anchors resolve
                    backlog.py          task-file grammar
                    backlogindex.py     what the index renders
                    backloganchors.py   anchors offered, and every pointer aimed at one
                    headingshapes.py    what a heading may look like for a slug to be derivable

                  Shared by several of the above: composefiles.py (which compose files the four
                  compose gates walk), gitenv.py (the environment every git call runs with),
                  skippeddirs.py (the directory names every walk here prunes, deliberately not
                  .gitignore). Standalone: coverage_gate.py (Rust branch coverage), ci_paths.py
                  (the CI path classifier), commitlint.py (commit-message style).

                  Seven modules gate nothing and report a measurement: contrast.py (the interval a
                  live measurement reports) and trailwidth.py (the width the recall trail's widest
                  field renders at, ADR-0038); envelopefloor.py (an envelope measurement's arms
                  and the floors its control arm is published against, ADR-0028) with
                  envelopesamples.py (the sample format it reads) and envelopejudges.py (the judge
                  declared per subtask shape, and the readings a delivered rate is taken under);
                  switchtail.py
                  (what a tier's template rendered for the thinking switch, held to the
                  constrained cell the same run drew, ADR-0005) with switchsamples.py (the sample
                  format it reads).
.github/          GPU-less CI running the same `just` recipes as local dev: ci.yml is the gate
                  mirror, shuffle.yml the weekly test-order sweep that gates nothing (ADR-0002)
justfile          `just check` + check-*; proto, up/down, brain-serve, seam-health, turn-cost,
                  envelope-floor, switch-tail,
                  backlog (regenerate each backlog index from its task files), shuffle (every
                  suite at one chosen seed, the sweep the gate's own fixed seed never draws,
                  ADR-0002)
                  (`just check` runs the eleven cross-tree scans before the per-tree ones;
                  `turn-cost` is the A/B/A live measurement, where the container restarts
                  between arms live, ADR-0038; `envelope-floor` publishes an envelope
                  measurement's arms and refuses when its control arm fell through the floor,
                  ADR-0028; `switch-tail` publishes what a tier's template rendered for the
                  thinking switch and refuses when that rendering and the cell it predicts
                  disagree, ADR-0005; `image-volumes` is the hand-run docker
                  re-derivation of the record `check-volumecheck` reads, ADR-0011)
docker/           Compose stack (run via `just up`/`up-gpu`, or `docker compose --project-directory .
                  -f docker/docker-compose.yml …`): docker-compose.yml (brain + redis, loopback-only)
                  + overrides: gpu (the model-host supervisor sidecar, one llama-server child per
                  model tier, + read-only model mount, ADR-0005/0007/0030) + modelhost-loopback
                  (opt-in host access to that sidecar's control API), memory
                  (Postgres+pgvector + CPU embedder, ADR-0008), tools + email (MCP sidecars: filesystem,
                  read-only email, ADR-0009), subagents (CPU llama-server, ADR-0010) + subagents-roster
                  (a second CPU model as an ADR-0018 roster alternate), body (points the brain at the
                  host-native body's BodyService, ADR-0023); + postgres/init.sql
```
