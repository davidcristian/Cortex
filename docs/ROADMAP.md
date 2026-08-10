# Roadmap of vertical slices

Each slice is a thin end-to-end path: small, green under `just check`, documented before
it is done. **Gate proven** marks the first slice that exercises each hard gate for real.
The order follows the founding spec's arc (chat → memory → tools → subagents → body →
handoff last); the two insertions are the seam skeleton at Slice 2 (pulled early because
every later slice talks over `Converse` and the seam gate should be proven before code
piles up on both sides) and real inference at Slice 4, so memory/tools/subagents build
against a real model while CI keeps using fakes. A decimal number is a later insertion
that avoided renumbering the heavily-referenced Slices 9 to 11.

Each slice carries a **Status** marker (*done* or *in progress*); slices without one are
planned and not yet started. **Done** means the code landed and is green under
`just check`; anything still owed on this repo's own side is named in that slice's status
and tracked in [refinements/](refinements/index.md).

**What a slice entry deliberately does not carry**, so that it stays a few lines:

| Kind of detail | Where it lives |
| --- | --- |
| Why a slice is shaped this way, and how it was validated | its ADR in [adr/](adr/) |
| How to run or re-run any of it | [runbooks/](runbooks/) |
| A consciously deferred refinement and what blocks it | [refinements/](refinements/index.md) |
| Work needing hardware this repo is not developed on | [host/](host/index.md) |
| A module's purpose, contract, and invariants | [modules/](modules/) |

None of those is repeated per slice. In particular **no slice status tracks host-side
work**: a done slice can still have a Windows-native or tier-scale half that has never been
run, and [host/](host/index.md) is the single register of all of it, one doc per sitting,
with its own index, prerequisites, order, and blockers. [index.md](index.md) maps the rest
of the docs.

## Slice 0 (Governance, this phase)

**Status:** done.

AGENTS.md, CLAUDE.md, docs skeleton, ADR-0001, port/trait list, proto sketch, this plan,
and the assumptions & risks list at the bottom of this file. No feature code.
**Stops for maintainer review.**

## Slice 1 (Walking skeleton): both toolchains, all gates

**Status:** done.

One trivial pure module per side (e.g. a typed routing decision in `brain/packages/core`,
a hotkey-config type in `body/crates/core`), plus: `uv` workspace, Cargo workspace,
justfile (`just check` spanning both), the line-cap script, pre-commit, and GPU-less CI
building and gating both trees.
**Gates proven:** Python 100% line+branch · Rust 100% via cargo-llvm-cov · 300-line scan
· dual-toolchain `just check` · GPU-less CI.

## Slice 2 (The seam): proto compiled on both sides

**Status:** done.

`proto/body.proto` v0 (`BrainService.Health` + `Converse` shape), tonic build in
`body/crates/rpc`, generated Python stubs in `brain/packages/seam`; that is the shared wire
code, and the typed `BodyService` client wrapper (`body_client`) arrived with Slice 9. A
body-side dev command calls brain `Health` end-to-end (brain in Compose, caller on host).
Contract tests with fakes on both sides; the generated-code exemption wired into the
scan/coverage config. Runbook: [runbooks/local-dev-wsl.md](runbooks/local-dev-wsl.md).
**Gate proven:** gRPC seam as single source of truth (codegen in both builds).

## Slice 3 (Cortex-only chat with fake inference)

**Status:** done.

`SessionStore` port (in-memory fake + Redis adapter behind the same contract test),
`InferenceBackend` port + scripted fake, orchestrator use-case "handle a user turn" in
the pure core; a turn arrives over `Converse`, is answered by the fake, and the session
state survives an orchestrator process restart (proving state is external).
**Gate proven:** ports-before-adapters with contract tests; repository pattern.

## Slice 4 (Real inference): llama.cpp adapter + Model Manager v1

**Status:** done 2026-06-29 ([ADR-0007](adr/ADR-0007-model-manager-inference.md)).

The llama.cpp adapter for `InferenceBackend` (ADR-0005: one `llama-server` process per
model, OpenAI-compatible HTTP as the adapter surface, engine flags and quirks inside the
adapter); the `ModelManager` port and the pure `SingleResidentModelManager` owning the GPU
behind an `acquire()` lease and queue, with no swap yet; config-driven backend selection
(`CORTEX_INFERENCE_BACKEND`, Echo by default and llama.cpp opt-in); and
`docker/docker-compose.gpu.yml` with the read-only model-dir bind mount (ADR-0004). The
per-tier picks are locked against measured VRAM, the cortex to gemma-4-12B
([ADR-0004 addendum](adr/ADR-0004-model-lineup.md),
[runbooks/llamacpp-gpu.md](runbooks/llamacpp-gpu.md)). Model Manager v1 is pure and lives
in `cortex_core`; the process-lifecycle package deferred here landed with Slice 11 as the
`model-host` supervisor sidecar plus its `ModelHost` adapter.
**Gate proven:** integration suite excluded from coverage/CI; adapter as blast radius.

## Slice 5 (Memory v1): retrieval that grows

**Status:** done 2026-06-29 ([ADR-0008](adr/ADR-0008-memory-v1.md)).

`MemoryStore` + `Embedder` ports with a pgvector adapter and a CPU llama.cpp embedder
behind them (fakes in CI: the cosine `InMemoryMemoryStore`, the deterministic
`HashEmbedder`); recall of top-k into an ephemeral system message that is never persisted,
and a record at turn end, opt-in via `CORTEX_MEMORY_BACKEND` with
`docker/docker-compose.memory.yml` adding Postgres+pgvector and the embedder. Both
adapters are validated against a real database and a live embedder, and the embedding pick
is nomic-embed-text-v1.5 Q8_0, 768-dim
([runbooks/memory-pgvector.md](runbooks/memory-pgvector.md)). Durable data satisfies the
plug-and-play requirement as a named volume plus an export job rather than a raw PGDATA
bind mount, per ADR-0008 decision 7.

## Slice 6 (Tools via MCP): files, then email

**Status:** done 2026-06-29 ([ADR-0009](adr/ADR-0009-tools-mcp.md)).

The `ToolRegistry` + `ToolAuditSink` ports and a stateless `ToolDispatcher` in the pure
core, writing exactly one audit record per dispatch and turning a registry failure into a
recoverable `is_error`; native function-calling in the turn (`InferenceBackend` yields
`TextChunk | ToolCall` and takes `tools`, `Message` gained `tool_calls`/`Role.TOOL`, and a
bounded infer↔tool loop runs behind an optional capability bundle); the `cortex_tools` MCP
client over the official SDK behind an injected session port, opt-in via
`CORTEX_TOOLS_BACKEND`; and the standalone `cortex_email` FastMCP server, read-only
enforced three ways over imap-tools. Both sidecars are live-validated, including the
read-only mount blocking a write and the resident cortex natively emitting
`read_text_file` through the audited loop ([runbooks/tools-mcp.md](runbooks/tools-mcp.md),
[runbooks/email-imap.md](runbooks/email-imap.md)). All later tools, including body-backed
OS actions, go through this port.

## Slice 6.5 (Untrusted-content boundary): prompt-injection defense

**Status:** done 2026-07-01 ([ADR-0013](adr/ADR-0013-untrusted-content.md)). The real
overlay confirmation adapter it deferred to the first outbound tool landed with Slice 8.8.

Any content the brain reads through a tool (file contents, email bodies, later screen
captures and web pages) is **untrusted data, not instructions**, yet before this slice it
flowed into the cortex's context verbatim. A malicious file or email can carry text aimed
at the model, and the cortex holds increasingly powerful tools. The boundary is drawn
entirely behind the existing `ToolRegistry`/`ToolDispatcher`/tool-loop seams plus one new
`Confirmer` port, in three prongs:

- **Provenance framing.** A fail-closed `Trust` on every `ToolResult`, an untrusted result
  fenced behind a per-turn nonce under a standing `SECURITY_PREAMBLE`, and provenance
  written to the audit trail.
- **Capability gating.** `ToolSpec.gated` plus a dispatcher gate: a gated tool on a turn
  that read untrusted content is confirmed through the `Confirmer` before it runs, and a
  denial (including the fail-closed no-confirmer default) returns a message without
  invoking the tool. Ships inert but complete, since every tool here is a read.
- **Taint propagation + memory hygiene.** A subagent's taint rides home and aggregates, so
  a subagent that reads a malicious file taints the cortex, and a tainted turn records
  nothing to memory, keeping recall trustworthy.

Framing was measured on the real cortex: the framed model **cites the shipped preamble in
its own reasoning** to defeat seven injection variants, so framing works causally, and the
gate remains the deterministic backstop.
**Gate proven:** the untrusted-input boundary the founding safety posture requires.

## Slice 7 (Subagents)

**Status:** done 2026-07-01 ([ADR-0010](adr/ADR-0010-subagents.md)).

Delegate narrow tasks to small (2-4B) subagents: a task record in the store, each subagent
a stateless function over it, the result persisted and consumed by the cortex. Delegation
is a native `spawn_subagents` tool dispatched through Slice 6's audited loop, so the cortex
decides mid-turn and picks count and size, merged with the MCP tools by a
`CompositeToolRegistry` (the first internal-tool seam, ADR-0001 Q2); the tool spawns a
concurrent batch so the budget is meaningful. Subagents are tools-enabled but
delegation-free, bounding fan-out to **depth-1**. Admission is a dedicated
`SubagentScheduler` port rather than the GPU `ModelManager`, since a counting CPU budget
and an exclusive GPU lease are different resources. The Redis `TaskStore`, the shared tool
loop extracted from `TurnEngine`, and `docker/docker-compose.subagents.yml` land with it.
Validated on a real CPU `llama-server` running the pick, Qwen3.5-2B Q4_K_M, and end to end
from a resident cortex; Qwen3.5 is a reasoning model, so the subagent server disables
thinking ([runbooks/subagents-cpu.md](runbooks/subagents-cpu.md)). Placement was revised to
GPU-first in Slice 8.5, behind these same seams.

## Slice 8 (Body v1): hotkey → overlay → chat

**Status:** done 2026-07-01 ([ADR-0011](adr/ADR-0011-body-v1.md)).

Tauri app skeleton: tray plus hidden window, the `Hotkey` trait with a Windows backend over
the `global-hotkey` crate (macOS/Linux `unimplemented!()` stubs behind the coverage escape
hatch, which is where that policy is proven), overlay on hotkey, prompt over `Converse`,
streamed reply rendered, configurable hotkey. One turn per `Converse` call, since session
continuity is external and cancel is dropping the stream; a typed `TurnEvent` core mirror
of `ServerEvent`; a React + Vite overlay gated at 100% in its own path-filtered CI job; and
the Tauri shell (`body/app/src-tauri`, `cortex-body`) host-native and outside the gated
workspace. Validated on Windows against the GPU brain: the hotkey summons the overlay, the
tray works, and a typed prompt streams a real reply token by token
([runbooks/body-overlay.md](runbooks/body-overlay.md)).
**Gate proven:** cfg-gated OS backends; stub coverage escape hatch policy.

## Slice 8.5 (Resource governance): revise the GPU/CPU managers

**Status:** done 2026-07-01 ([ADR-0012](adr/ADR-0012-resource-governance.md)).

Revise the `ModelManager` (ADR-0007) and `SubagentScheduler` (ADR-0010) **ports** while they
are still small and pure and before the Slice 11 swap builds on them; retrofitting the
swap's foundation is a rewrite, the same "design the interface around the rule from day one"
logic as the hard rule. Two user-directed motivations: subagents are **GPU-first,
CPU-overflow** rather than CPU-only (correcting ADR-0010 and ADR-0004), and
**container-scoped resource caps** keep the machine usable, under the constraint of no
`.wslconfig`, no shared parent cgroup, and no hard limits on WSL. There is no per-process
GPU-utilization cap available on this stack, so that dimension is modeled as scheduler
policy instead.

Placement became a new pure-core port **`SubagentPlacer`** rather than a fattening of
`ModelManager`, so Slice 11's swap rides the same untouched `acquire` signature. Its
reference `VramBudgetPlacer` fit-tests each spawn against
`soft_cap − cortex_reservation − placed` and places the whole model on GPU (`-ngl 99`) or
spills it to CPU (`-ngl 0`), never a straddle, with the ledger bounding concurrency instead
of a separate knob. `SubagentScheduler.admit` gained a two-dimensional CPU/RAM budget whose
over-budget spawns queue and whose impossible charge is a typed refusal the runner degrades
to a failed result and the config refuses at boot. `SubagentRunner` composes admit → place →
route → release, and `InferenceBackend` and the proto are untouched. The ledgers are
live-resource state rebuilt from zero, never the durable state the hard rule governs. The
runtime mechanism landed with the Slice 11 lifecycle behind these corrected ports, and in a
shape this slice predicted wrongly: not two live sidecars but one `model-host` supervisor
container running a `llama-server` child per tier, with the cgroup caps applied to that
container (ADR-0030 decision 3).

## Slice 8.6 (Heterogeneous subagent models): the cortex picks which, and how many

**Status:** done 2026-07-03 ([ADR-0018](adr/ADR-0018-heterogeneous-subagents.md)).

The cortex chooses the subagent model per spawn and mixes them across the ADR-0004 roster: a
small-fast model for a trivial lookup, a larger one for a harder or untrusted subtask.
Additive behind the existing task-store, spawn, and placement seams. The spawn schema takes
a per-item `{instruction, model?, context?}` (delivering the deferred ADR-0010 context
field); the wiring builds a roster of `SubagentResources`, one per candidate model, each
placed independently and admitted against the shared budget, instead of a single wired tier;
and the roster the spec advertises to the cortex carries each option's trade-offs, size and
latency against injection-robustness.

The hard safety constraint is [ADR-0017](adr/ADR-0017-subagent-model-safety.md): the
per-spawn choice is an optimization *hint, not authority*. The wiring **forces** the
injection-robust default whenever the path can carry untrusted content, meaning a tainted
spawning turn or a tools-enabled subagent, so a cheap model is reachable only for a
tool-less subagent on an untainted turn. Deterministic, not the cortex's judgment, so it
holds even when the cortex picks a weak model for what turns out to be a hostile subtask.
Validated with both sidecars live, a mixed batch routed per pick, and a resident cortex
deciding a per-item model itself.
**Gate proven:** the cortex composing a heterogeneous team of subagents within one budget,
with every untrusted-content path pinned to the robust model.

## Slice 8.7 (Chat history & cycling over the seam)

**Status:** done 2026-07-07 ([ADR-0021](adr/ADR-0021-session-read-seam.md)).

The overlay's deferred multi-chat features ([design/overlay-ux.md](design/overlay-ux.md)):
store-backed history, listing, and cycling. Slice 8 kept the current run's chat in memory,
so this extended [proto/body.proto](../proto/body.proto) with two **read-only** RPCs,
`ListSessions` + `GetSessionMessages`, views of the durable store as the hard rule requires,
and threaded them through every seam: one new `SessionStore.list_sessions` port method with
a shared pure `summarize_session` and a Redis recency index; unary `BrainTransport` calls
plus core mirrors on the body side; and an overlay that owns the `session_id`, reloads the
chat list after each turn, and ships the switcher, `Ctrl+↑/↓` cycling, and `Ctrl+K`.
Auto-restore of the most recent chat landed 2026-07-12.
**Gate proven:** the overlay as a true view of store-backed session state.

## Slice 8.8 (Email-write): the first gated outbound tool + the real Confirmer

**Status:** done 2026-07-08 ([ADR-0022](adr/ADR-0022-email-write-confirmer.md)).

Send email as a **gated** tool, and make a gated action actually confirmable end to end: the
first *outbound, irreversible* capability, and the vehicle that lands the real overlay
**confirmation** adapter every later gated action reuses (Slice 9's OS actions, Slice 9.5's
side-effectful reminders). It is orderable any time after Slice 8 and should **precede
Slice 9**, so the OS actions inherit a working Confirmer instead of re-inventing it. Three
parts:

- **The send tool.** An SMTP write path in `cortex_email`, the write twin of the read-only
  reader, advertised `gated=True` and dispatched through the audited `ToolDispatcher`, off
  by default, with `From` always the authenticated user and never a parameter.
- **The real `Confirmer`.** A `Confirm` request/response pair riding the existing `Converse`
  stream rather than a new RPC, surfaced as an overlay approval card carrying the draft
  verbatim.
- **Gate composition.** An *untainted* gated call prompts the user and proceeds only on
  approval; a **tainted** turn stays fail-closed, since a send demanded by injected content
  is never merely a confirm away. Subagents never see the tool at all.

The one hard rule holds throughout: no confirmation state lives in a model process, and a
pending confirm is one awaiting coroutine, reconstructed like taint. Validated as the card
in a real browser, gating over real MCP, and a live IMAP + SMTP round-trip against the real
ProtonMail Bridge. An adversarial review of the landed diff then hardened it (15 findings,
all fixed), the load-bearing one being that the dispatcher, not the advertisement snapshot,
holds the authoritative gated-name set, so a flaky sidecar cannot open a bypass window.
**Gate proven:** the first outbound/irreversible capability under the capability gate, and
the `Confirmer` round-trip over the seam.

## Slice 9 (One OS action end-to-end, volume)

**Status:** done 2026-07-08 ([ADR-0023](adr/ADR-0023-body-gateway-volume.md)).

The first **brain→body** seam direction and the first OS action: an `AudioControl` Windows
backend over Core Audio, `BodyService.SetVolume/GetVolume` served by the body, a brain-side
`BodyGateway` port plus its gRPC adapter and fake, and a volume tool that registers in the
Slice 6 `ToolRegistry` and dispatches through the existing audited path, so "set volume to
30%" spoken to the overlay changes host volume. Resolves ADR-0001 Q2 (body capabilities are
**internal** tools over a port, not MCP) and Q3 (the brain **dials** the host body via
`host.docker.internal`, with the abstract port keeping the tunnel fallback a pure adapter
swap). No proto change, since `BodyService` was frozen at Slice 2 and both stubs were
already committed. Volume is **ungated** because it is reversible, so no approval card
appears, and `TRUSTED` because host state never taints; a user can gate it by adding it to
`CORTEX_TOOLS_GATED`, where the dispatcher backstop applies. The containerized brain's
tokened dial to a host-side `BodyService` round-tripped and the untokened dial was rejected
`UNAUTHENTICATED`.

Volume is the **first, minimal** OS action, chosen to prove the seam with the smallest
surface. **OS actions are an open-ended, growing set, never a fixed catalog:** each later one
(brightness, media/transport keys, window & app control, input injection, clipboard,
launch/focus, …) is another `BodyService` RPC + a `cfg`-gated OS-backend method
(`AudioControl` is the first of many such capability traits) + an audited tool, all behind
the *same* `BodyGateway` port and OS-trait seams. New capability, no seam change (AGENTS.md
scope policy). Any *side-effectful* OS action inherits the Slice 6.5 gate and the Slice 8.8
`Confirmer` for free.
**Gate proven:** bidirectional seam (brain calls body).

## Slice 9.5 (Scheduling & proactive reminders)

**Status:** done 2026-07-08 ([ADR-0025](adr/ADR-0025-scheduling-reminders.md)). The three
surfaces it deferred behind committed seam shapes landed by 2026-07-16: the body-side
reminder reads, the overlay's reminders-on-open stack, and the native toast. Placed after
Slice 9 because proactive delivery rides the **brain→body** direction that slice
establishes.

Give the assistant a sense of time: schedule a task or reminder now, have it fire later. The
one hard rule governs it (**a schedule outlives every model swap**), so it lives in the
external store, never in a model process:

- **The fenced store.** A `ScheduleStore` port whose `claim_due` claims due and lease-expired
  items oldest-first under fresh per-claim fencing tokens (at-least-once, with corrupt
  records quarantined to a dead-letter hash rather than poison-pilling the pass), whose
  transitions apply only under the live token, and whose `cancel` deletes outright and so
  sticks through an in-flight fire. One contract suite runs the in-memory fake and the Redis
  adapter interchangeably, races included.
- **Three cortex-only built-ins.** `schedule_task` (its spec rebuilt per walk and carrying
  the current time, because the model cannot otherwise compute an absolute `at`, under an
  active-item cap and a tainted-task refusal), `list_scheduled` (trusted only when every
  listed item is clean, else fenced, which is the laundering guard), and `cancel_scheduled`.
  Subagents never see any of them, the depth-1 analog.
- **The seam and the ticker.** `ListDueReminders`/`AckReminder` on `BrainService` and
  `Notify` on `BodyService`, plus a stateless poll loop beside `serve` that claims, fires
  concurrently under the lease, and persists. An **autonomous task** dispatches through the
  ticker's own audited, fail-closed dispatcher; a **reminder** is delivered two ways, the
  pull surface when the overlay next opens and a native WinRT toast over the brain→body seam.

Any *side-effectful* scheduled action stays subject to the Slice 6.5 gate: a reminder created
from injected external content must not silently fire an irreversible action. The design was
adversarially reviewed before implementation and the landed diff again after, and real
firing was validated end to end against live Redis
([runbooks/scheduling.md](runbooks/scheduling.md)).
**Gate proven:** durable scheduled state that survives a swap; the brain acting on its own
initiative.

## Slice 10 (Vision): "see my screen"

**Status:** done 2026-07-18 ([ADR-0029](adr/ADR-0029-vision-screen-capture.md)), repaired
2026-07-19 after three adversarial audits, and validated against the real cortex and its
projector. The three measurements this repo could run on its own card have all run: whether
thinking needs disabling on a vision turn and `llama-server`'s `mmproj`-less error body text on
2026-08-03, and the image arm of the injection-defence harness on 2026-08-04, which found the
hardened preamble's content-manipulation clause holding over text and not over pixels. Each is
recorded at that ADR with its entry in [refinements/vision.md](refinements/vision.md). The
headline risk this slice shipped with, small text on a 4K desktop, was measured 2026-08-06 and
mitigated by a default change the same day; the fix for what the mitigation cannot reach landed
2026-08-10 as a **targeted capture**, the body half first (the seam carries a `CaptureTarget` and
a shipping body honours it) and the brain half the same day, so `capture_screen` now takes a
required target and the model chooses between the window the user is looking at and the whole
display. What is left of that thread is one measurement, whether a window-sized crop reaches the
15 px text no token budget did. See [runbooks/vision.md](runbooks/vision.md).

The shape: a model-initiated built-in `capture_screen` tool over the unchanged `BodyGateway`
(the volume precedent, so it inherits audit, the dispatch budget, taint marking, and
cortex-only reachability), a `ScreenCapture` OS trait returning **raw pixels** with all
downscale, encode, and byte-bounding policy in pure `body_core` (since `cfg(windows)` code
is invisible to the coverage gate), a GDI `BitBlt` Windows backend under its own `unsafe`
authorization, and the image riding `ToolResult.images` onto the `Role.TOOL` message with
`InferenceBackend.stream` unchanged. **Pixels are turn-local**, enforced as an invariant
rather than a convention: a `Message` invariant allows images on the `Role.TOOL` message
alone, both session stores raise on an image-bearing append, and a turn that looked at the
screen cannot hand over to the deep model at all, so the later attachment slice must design
persistence deliberately instead of half inheriting it. Since no nonce can bracket an image,
the boundary is taint (a capture is always untrusted, closing every gated tool for the turn),
a turn-local `opaque` bit escalating the output guardrail to strict URL redaction and
blocking durable memory outright, a body-authored notification receipt a compromised brain
cannot suppress, a host-side kill switch that fails closed, and the overlay excluding itself
from capture to break the self-injection loop. The user-attached `UserTurn.images` path is
deliberately **not** in this slice.
**Gate proven:** a seam that carries a payload stays bounded at both ends, and unfenceable
content gets a deterministic boundary rather than a prompt-shaped one.

## Slice 11 (Brain handoff): the swap rule, for real (capstone)

**Status:** done 2026-07-18 ([ADR-0030](adr/ADR-0030-brain-handoff.md)).

Full handoff: cortex escalates → context serialized → the manager evicts cortex and
subagents and loads the brain (stopping and starting `llama-server` processes, per ADR-0005)
→ the brain rehydrates from the store, works, persists → swap back → the cortex resumes from
the store. The hard rule is **CI-proven over fakes**: a parameterized chaos suite kills a
handoff at every step boundary of the swap sequence and asserts convergence back to a serving
cortex, an intact store, a terminal record, and an honest stream. The real process lifecycle
is the `model-host` supervisor sidecar behind the `ModelHost` port, one `llama-server` child
per tier, whose mechanism is validated against real processes with two small stand-ins
(started, health-gated, evicted, swapped, killed under the daemon, and restarted over their
own corpses). The honesty surfaces are complete: the swap window emits status updates, and
`Health` reads the swapping manager's published residency and answers `ready=false` with a
truthful detail between turns, which lights the overlay's connection dot amber with no
overlay change. Runbook: [runbooks/model-swap.md](runbooks/model-swap.md).
**Gate proven:** THE hard rule, end to end.

## Deferred refinements & later work

Moved to [refinements/](refinements/index.md) on 2026-07-15: one self-contained doc per
area with the entries kept verbatim, plus an index carrying a blurb per doc, the recommended
pickup order, and what blocks each open item. Two of the four blocker classes this sentence once
named are gone (corrected 2026-07-19): **host-side validation** moved to
[host/](host/index.md), and nothing waits on **a pending slice** now that the last one has
landed. What that index actually carries today is a seam or port change, a consumer that does not
yet exist, a trigger that has not bitten yet, and hardware that fits two model tiers.
The contract is unchanged and lives there now: every
consciously deferred refinement is recorded in its area doc and on the index (and at its
origin ADR) as part of finishing a slice. References elsewhere in this repo to "the ROADMAP's
deferred-refinements section" resolve through this pointer.

## Host-side work

Moved to [host/](host/index.md) on 2026-07-19, mirroring the extraction above: one
self-contained doc per **sitting** rather than per area, with the load-bearing wording kept
verbatim, plus an index carrying a blurb per doc, the prerequisites each sitting needs, the
recommended order, a line per item, and what blocks each. Two capabilities, tagged per item
because the layout must not assume they are one machine or two: a **real Win32 desktop
session** for everything OS native, and a **24 GB GPU** for everything at tier scale.
User *decisions* stay at their ADRs and are listed on that index rather than copied, so a
decision keeps one home. References elsewhere in this repo to a slice status's "host-only half",
"Host-Windows", or "host half (user)" resolve through this pointer.

## The finish line (the very last step)

**Status:** open. The terminal marker, crossed only when **every slice above, the entire
deferred-refinements backlog ([refinements/](refinements/index.md)), and the host-side work
([host/](host/index.md)) are all cleared**. The three are different kinds of "not done":
a slice is unbuilt, a refinement is built-around, a host item is built but unrun. Nothing
may call the system finished while any of the three holds an open item.

The root [README.md](../README.md) is the repo's product face: the logo and pitch, the
feature grid, captures of the overlay in action, the model lineup with the hardware it is
tuned to, and the quickstart. It speaks to a human deciding whether to care, so it reads in
the present tense and carries no engineering process; the deeper truth stays in the
engineer-facing docs it links. It is kept current as behavior lands: a change that alters
what a stranger would see or run updates the README in the same change, re-taking the
captures under [assets/](assets/) when the overlay's face changes. Crossing the finish line
means reading it once more against the running system and finding nothing to correct.

References elsewhere in this repo to shipping "the user-facing README" resolve through this
section: the README ships with the repo, and the emptiness those references gate on is this
finish line.

## Assumptions & risks to confirm (Phase 0)

Deferred *decisions* live in ADR-0001's open questions; these are the *assumptions* the
plan bets on, with what would invalidate each:

1. **VRAM fit.** *Measured in Slice 4 ([ADR-0004 addendum](adr/ADR-0004-model-lineup.md)).*
   The soft cap is **14 GB** (env `CORTEX_VRAM_SOFT_CAP_GB`, one knob; enforced by the
   `SubagentPlacer` from Slice 8.5, ADR-0012). It is a deliberate budget rather than the
   card's size, so that the machine stays usable alongside the assistant (ADR-0004 decision
   3). The chosen cortex (gemma-4-12B, QAT Q4) is reserved at 8.6 GiB at 16K ctx incl. the
   vision tower, re-measured on 2026-08-07 where the tier peaks at 8573 MiB above the idle floor
   (it was 11.3 GB until then, a total-used reading with the desktop's own floor inside it), so it
   sits **comfortably under the cap** with 5.4 GiB of headroom.
   The embedder runs on **CPU**; subagents are placed per spawn against the remaining
   headroom. Context size is itself budget-bounded.
2. **Swap latency.** A cortex↔brain swap is a `llama-server` stop + start (ADR-0005),
   so its cost is loading a multi-GB GGUF from the bind-mounted Windows drive.
   Assumed acceptable (seconds, reported to the overlay via the `Converse` status
   stream); if the Windows mount is the bottleneck, hot models get mirrored into a
   WSL-side/volume cache (measured in Slice 4). **Still unmeasured at the brain tier.**
3. **Brain→body connectivity.** The dockerized brain can dial the host body's gRPC
   server via `host.docker.internal` through the Windows firewall. Fallback: tunnel
   body-directed calls over a body-initiated stream (ADR-0001 Q3). *Half real as of
   2026-07-08:* the dial and the token round-trip passed from a container under WSL2 native
   dockerd against the Rust `BodyService` (ADR-0023 addendum); the **Windows firewall**
   crossing is still untested.
4. **Coverage on Tauri glue.** 100% line+branch on the body holds because app wiring
   stays thin and logic lives in `body/crates/core`. If Tauri macro-generated glue
   resists instrumentation, that glue gets an ADR'd, narrowly-scoped exclusion.
5. **Security model.** Single-user machine: loopback-only listeners, shared-secret token
   on the seam via env, no mTLS. Revisit only if anything ever listens beyond loopback.
   *Both halves are real as of 2026-07-03:* loopback-only publish since Slice 2, and the
   token landed as [ADR-0016](adr/ADR-0016-seam-token.md) (`CORTEX_SEAM_TOKEN` on both
   sides, with a brain-side interceptor rejecting untokened calls UNAUTHENTICATED, the body's
   client attaching it; empty disables, keeping the dev loop and CI unchanged).
6. **Email safety.** IMAP read-only first; the send path landed 2026-07-08 (**Slice 8.8**,
   ADR-0022) exactly as bet: off by default, gated at the composition root, behind explicit
   per-action confirmation in the overlay (the real `Confirmer` adapter), and never
   confirmable on a tainted turn.
7. **Default hotkey.** `Ctrl+Alt+Space`, configurable from day one (`Win+Space` is
   taken by Windows).
