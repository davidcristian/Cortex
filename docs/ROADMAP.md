# Roadmap of vertical slices

Each slice is a thin end-to-end path: small, green under `just check`, documented before it is done. The order
follows the founding plan (chat, memory, tools, subagents, body, handoff last), with two insertions: the proto
skeleton at Slice 2, because every later slice talks over `Converse`, and real inference at Slice 4, so memory,
tools and subagents are built against a real model. A decimal number is a later insertion that avoided
renumbering Slices 9 to 11.

A slice with no **Status** line is planned and not yet started. **Done** means the code is committed and green
under `just check`; anything still owed on this repo's own side is named in that slice's status and tracked in
[refinements/](refinements/index.md). Each entry stays short because the detail lives elsewhere: the reasoning
in its ADR, how to run it in [runbooks/](runbooks/), deferred work in [refinements/](refinements/index.md) and
[host/](host/index.md), and a module's contract in [modules/](modules/). In particular **no slice status tracks
host-side work**: a done slice can still have a Windows-native or tier-scale half that has never run.

## Slice 0 (Governance)

**Status:** done. AGENTS.md, CLAUDE.md, the docs skeleton, ADR-0001, the port and trait list, the proto sketch,
this plan, and the assumptions at the bottom of this file. No feature code.

## Slice 1 (Walking skeleton): both toolchains, all checks

**Status:** done. One trivial pure module per side, plus the `uv` workspace, the Cargo workspace, the justfile
with a `just check` spanning both, the line-cap script, pre-commit, and GPU-less CI.

## Slice 2 (The proto): compiled on both sides

**Status:** done. `proto/body.proto` v0 (`BrainService.Health` and the `Converse` shape), the tonic build in
`body/crates/rpc`, generated Python stubs in `brain/packages/seam`, a body-side dev command that calls brain
`Health` end to end, contract tests with fakes on both sides, and the generated-code exemption wired into the
scan and the coverage configuration.

## Slice 3 (Cortex-only chat with fake inference)

**Status:** done. The `SessionStore` port (an in-memory fake and a Redis adapter behind one contract test), the
`InferenceBackend` port with a scripted fake, and the "handle a user turn" use case in the pure core. A turn
arrives over `Converse`, is answered by the fake, and the session state survives an orchestrator restart, which
is what proves the state is external.

## Slice 4 (Real inference): llama.cpp adapter and Model Manager v1

**Status:** done 2026-06-29 ([ADR-0007](adr/ADR-0007-model-manager-inference.md)).

The llama.cpp adapter for `InferenceBackend`, the `ModelManager` port and the pure `SingleResidentModelManager`
owning the GPU behind an `acquire()` lease with no swap yet, backend selection through
`CORTEX_INFERENCE_BACKEND` (Echo by default), and the GPU compose override with its read-only model mount. The
per-tier picks are fixed against measured VRAM, the cortex to gemma-4-12B ([ADR-0004](adr/ADR-0004-model-lineup.md)).

## Slice 5 (Memory v1): retrieval that grows

**Status:** done 2026-06-29 ([ADR-0008](adr/ADR-0008-memory-v1.md)).

The `MemoryStore` and `Embedder` ports with a pgvector adapter and a CPU llama.cpp embedder behind them, and
cosine and hash fakes in CI. Recall of the top k goes into an ephemeral system message that is never stored, a
record is written at turn end, and the path is opt-in through `CORTEX_MEMORY_BACKEND`. The embedding pick is
nomic-embed-text-v1.5 Q8_0, 768 dimensions, and durable data is a named volume plus an export job.

## Slice 6 (Tools over MCP): files, then email

**Status:** done 2026-06-29 ([ADR-0009](adr/ADR-0009-tools-mcp.md)).

The `ToolRegistry` and `ToolAuditSink` ports with a stateless `ToolDispatcher` in the pure core, writing one
audit record per dispatch; native function calling, with `InferenceBackend` yielding `TextChunk | ToolCall` and
a bounded loop between inference and tools; the `cortex_tools` MCP client; and the standalone `cortex_email`
server, read-only three ways. Every later tool goes through this port.

## Slice 6.5 (Untrusted-content boundary)

**Status:** done 2026-07-01 ([ADR-0013](adr/ADR-0013-untrusted-content.md)). The real overlay confirmation
adapter it deferred arrived with Slice 8.8.

Anything the brain reads through a tool is **untrusted data, not instructions**. Behind the existing tool
interfaces plus one new `Confirmer` port: a fail-closed `Trust` on every `ToolResult`, an untrusted result
fenced behind a per-turn nonce under a security preamble, `ToolSpec.confirm_required` with a dispatcher check, and taint
propagation, so a subagent that reads a malicious file taints the cortex and a tainted turn records nothing to
memory. Measured on the real cortex: the framed model cites the preamble in its own reasoning to defeat seven
injection variants.

## Slice 7 (Subagents)

**Status:** done 2026-07-01 ([ADR-0010](adr/ADR-0010-subagents.md)).

Narrow tasks are delegated to small 2-4B subagents, each a stateless function over a task record in the store.
Delegation is a native `spawn_subagents` tool dispatched through Slice 6's audited loop, so the cortex decides
mid-turn and picks the count and size. Subagents have tools but cannot delegate, which bounds fan-out to **depth
1**, and admission is a dedicated `SubagentScheduler` rather than the GPU `ModelManager`, since a counting CPU
budget and an exclusive GPU lease are different resources.

## Slice 8 (Body v1): hotkey, overlay, chat

**Status:** done 2026-07-01 ([ADR-0011](adr/ADR-0011-body-v1.md)).

The Tauri app skeleton, the `Hotkey` trait with a Windows backend and `unimplemented!()` stubs elsewhere behind
the coverage escape hatch, the overlay on hotkey, a prompt over `Converse` and the streamed reply. One turn per
`Converse` call, since session continuity is external and cancelling is dropping the stream; a React and Vite
overlay tested to 100% in its own CI job; and the Tauri shell host-native and outside the checked workspace.
Validated on Windows against the GPU brain.

## Slice 8.5 (Resource governance)

**Status:** done 2026-07-01 ([ADR-0012](adr/ADR-0012-resource-governance.md)).

The `ModelManager` and `SubagentScheduler` ports were revised while they were still small and pure, before Slice
11's swap built on them. Subagents became **GPU-first with CPU overflow**, and container-scoped caps keep the
machine usable, since WSL allows no `.wslconfig`, no shared parent cgroup and no per-process GPU cap. Placement
became a new pure port, **`SubagentPlacer`**, so the swap uses the same untouched `acquire` signature: it
fit-tests each spawn against `soft cap − cortex reservation − placed` and puts the whole model on the GPU or the
CPU, never split. `SubagentScheduler.admit` gained a two-dimensional CPU and RAM budget whose over-budget spawns
queue.

## Slice 8.6 (Heterogeneous subagent models)

**Status:** done 2026-07-03 ([ADR-0018](adr/ADR-0018-heterogeneous-subagents.md)).

The cortex chooses the subagent model per spawn and mixes them across the roster: the spawn schema takes a
per-item `{instruction, model?, context?}`, the wiring builds one `SubagentResources` per candidate model, and
the roster states each option's trade-offs. The safety constraint is
[ADR-0017](adr/ADR-0017-subagent-model-safety.md): the per-spawn choice is a hint, and the wiring **forces** the
injection-resistant default whenever the path can include untrusted content.

## Slice 8.7 (Chat history and cycling over the proto)

**Status:** done 2026-07-07 ([ADR-0021](adr/ADR-0021-session-read-rpcs.md)).

Two **read-only** RPCs, `ListSessions` and `GetSessionMessages`, are views of the durable store as the hard rule
requires, threaded through one new `SessionStore.list_sessions` method with a shared pure `summarize_session`
and a Redis recency index, unary `BrainTransport` calls with core mirrors on the body side, and an overlay that
owns the `session_id` and ships the switcher, `Ctrl+↑/↓` cycling and `Ctrl+K`.

## Slice 8.8 (Email send): the first outbound tool and the real confirmer

**Status:** done 2026-07-08 ([ADR-0022](adr/ADR-0022-email-write-confirmer.md)).

The first outbound, irreversible capability, and the overlay confirmation adapter every later
approval-requiring action reuses: an SMTP write path in `cortex_email`, off by default, dispatched through the
audited `ToolDispatcher` with `From` always the authenticated user, and a `Confirm` pair on the existing
`Converse` stream shown as an overlay card with the draft verbatim. An untainted call proceeds only on approval,
while a **tainted** turn stays fail-closed, since a send demanded by injected content must never become
reachable by approving a card; subagents never see the tool. An adversarial review then moved the authoritative
set of approval-requiring names to the dispatcher.

## Slice 9 (One OS action end to end: volume)

**Status:** done 2026-07-08 ([ADR-0023](adr/ADR-0023-body-gateway-volume.md)).

The first **brain-to-body** direction and the first OS action: an `AudioControl` Windows backend over Core
Audio, `BodyService.SetVolume` and `GetVolume` served by the body, a brain-side `BodyGateway` port with its gRPC
adapter and fake, and a volume tool in Slice 6's `ToolRegistry`, so "set volume to 30%" spoken to the overlay
changes the host volume. No proto change was needed. Volume needs no approval because it is reversible, and a
user can require it by adding the tool to `CORTEX_TOOLS_GATED`.

**OS actions are an open-ended, growing set, never a fixed catalog:** each later one (brightness, media keys,
window and app control, input injection, clipboard) is another `BodyService` RPC plus an OS-backend method plus
an audited tool, behind the *same* port and traits, and any side-effectful one inherits the Slice 6.5 check and
the Slice 8.8 `Confirmer`.

## Slice 9.5 (Scheduling and proactive reminders)

**Status:** done 2026-07-08 ([ADR-0025](adr/ADR-0025-scheduling-reminders.md)). The three surfaces it deferred
(the body-side reminder reads, the reminders-on-open stack, the toast) arrived by 2026-07-16.

A schedule lives in the external store, as the one hard rule requires. A `ScheduleStore` port claims due and
lease-expired items oldest first under fresh fencing tokens (at least once, with corrupt records quarantined to
a dead-letter hash), applies transitions only under the live token, and deletes on `cancel`. Three cortex-only
built-ins schedule, list and cancel, with the current time in the spec because the model cannot otherwise
compute an absolute `at`, an active-item cap, a refusal on a tainted task, and a listing trusted only when every
item is clean. `ListDueReminders`, `AckReminder`, `BodyService.Notify` and a stateless poll loop beside `serve`
deliver a reminder by pull when the overlay opens and by a native WinRT toast.

## Slice 10 (Vision): "see my screen"

**Status:** done 2026-07-18 ([ADR-0029](adr/ADR-0029-vision-screen-capture.md)), repaired 2026-07-19 after
three adversarial audits, and validated against the real cortex and its projector.

A model-initiated `capture_screen` built-in over the unchanged `BodyGateway`, so it inherits the audit trail,
the dispatch budget, taint marking and cortex-only reach. A `ScreenCapture` OS trait returns **raw pixels**,
with all downscale, encode and byte-bounding policy in pure `body_core` and a GDI `BitBlt` Windows backend under
its own `unsafe` authorization. **Pixels are turn-local** as an invariant: images are allowed on the `Role.TOOL`
and `Role.USER` messages (ADR-0070), both session stores raise on an image-bearing append, and a turn holding a
picture cannot hand over to the deep model. Since no nonce can bracket an image, the boundary is taint plus a turn-local
`opaque` bit that forces strict URL redaction and blocks durable memory, a receipt the brain cannot suppress, a
kill switch that fails closed, and the overlay excluding itself from capture.

Small text on a 4K desktop was measured 2026-08-06 and mitigated the same day, and what the mitigation could not
reach was fixed 2026-08-10 as a **targeted capture**: `capture_screen` requires a `CaptureTarget`, so the model
chooses between the focused window and the whole display. A window crop reads 15 px text 9 or 10 times in 12
where the shrunk screen reads 5. The image variant of the injection harness ran 2026-08-04 and found the
hardened preamble's content-manipulation clause holding over text and not over pixels.

## Slice 11 (Brain handoff): the swap rule, for real

**Status:** done 2026-07-18 ([ADR-0030](adr/ADR-0030-brain-handoff.md)).

The cortex escalates, the context is written to the store, the manager evicts the cortex and the subagents and
loads the brain model, which reloads from the store, works and persists before the swap reverses. The hard rule
is **proven in CI over fakes**: a parameterized chaos suite kills a handoff at every step boundary and asserts
that the system returns to a serving cortex with an intact store, a terminal record and an accurate stream. The
real process lifecycle is the model-host supervisor sidecar behind the `ModelHost` port. `Health` reports the
swapping manager's residency and answers `ready=false` between turns, which turns the overlay's connection dot
amber.

## Deferred and host-side work

Deferred refinements live in [refinements/](refinements/index.md), one file per task, each with its own status,
and that index's open set is generated from the task files. What the backlog holds today is a port change, a
consumer that does not exist yet, a trigger that has not happened yet, and hardware that fits two model tiers.
Host-side work lives in [host/](host/index.md) in the same layout, with the prerequisites each session needs and
the recommended order. Two capabilities are tagged per item, because the layout must not assume they are one
machine or two: a **real Win32 desktop session** for everything OS native, and a **24 GB GPU** for everything at
tier scale.

## The finish line

**Status:** open. Crossed only when **every slice above, the whole [refinements/](refinements/index.md) backlog
and all the [host/](host/index.md) work are cleared**. The three are different kinds of not-done: a slice is
unbuilt, a refinement is worked around, a host item is built but never run.

The root [README.md](../README.md) is the repo's product face and speaks to a person deciding whether to care,
so it reads in the present tense and has no engineering process in it. A change that alters what a stranger
would see or run updates the README in the same change, and the captures under [assets/](assets/) are retaken
when the overlay's face changes. Crossing the finish line means reading it once more against the running system
and finding nothing to correct.

## Assumptions to confirm (Phase 0)

Deferred *decisions* live in ADR-0001's open questions. These are the *assumptions* the plan bets on.

1. **VRAM fit.** *Measured in Slice 4 ([ADR-0004](adr/ADR-0004-model-lineup.md)).* The soft cap is **14 GB**
   (`CORTEX_VRAM_SOFT_CAP_GB`), a deliberate budget rather than the card's size, so the machine stays usable
   alongside the assistant. The cortex (gemma-4-12B, QAT Q4) is reserved at 8.6 GiB at 16K context including the
   vision tower, re-measured 2026-08-07 where the tier peaks at 8573 MiB above the idle floor (it was 11.3 GB
   until then, a total-used reading with the desktop's own floor inside it), so it sits under the cap with
   5.4 GiB of headroom. The embedder runs on the **CPU**, and subagents take the remaining headroom.
2. **Swap latency.** A cortex to brain swap is a `llama-server` stop and start, so its cost is loading a
   multi-GB GGUF from the bind-mounted Windows drive. Assumed acceptable, in seconds, and reported to the
   overlay; if the Windows mount is the bottleneck, hot models get mirrored into a WSL-side cache. **Still
   unmeasured at the brain tier.**
3. **Brain-to-body connectivity.** The dockerized brain can dial the host body's gRPC server through
   `host.docker.internal` and the Windows firewall. Fallback: tunnel body-directed calls over a body-initiated
   stream. *Half real as of 2026-07-08:* the dial and the token round-trip passed from a container under WSL2
   against the Rust `BodyService`; the **Windows firewall** crossing is still untested.
4. **Coverage on Tauri glue.** 100% line and branch coverage on the body holds because the app wiring stays thin
   and the logic lives in `body/crates/core`. If Tauri macro-generated glue resists instrumentation, that glue
   gets a narrowly scoped exclusion with an ADR.
5. **Security model.** A single-user machine: loopback-only listeners except the body's, which the host firewall
   keeps host-local, a shared-secret token from the environment, no mTLS. Revisit if a second user or machine
   joins. *The token is real as of 2026-07-03* ([ADR-0016](adr/ADR-0016-shared-token.md)), the body's bind as of 2026-07-08.
6. **Email safety.** IMAP read-only first; the send path arrived 2026-07-08 exactly as bet: off by default,
   restricted at the composition root, confirmed per action in the overlay, never on a tainted turn.
7. **Default hotkey.** `Ctrl+Alt+Space`, configurable from day one, because `Win+Space` is taken by Windows.
