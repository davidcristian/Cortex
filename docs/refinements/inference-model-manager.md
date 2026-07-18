# Inference & Model Manager

Deferrals from the Slice 4 inference work, whose origin decision is
[ADR-0007](../adr/ADR-0007-model-manager-inference.md); the reasoning-status entry carries its own
decision record in [ADR-0020](../adr/ADR-0020-reasoning-status.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the
historical record of what each deferral became, and the index at [index.md](index.md) carries the
recommended pickup order.

**Open items:** model-manager co-residency; resume a crashed handoff from its record; fence the
single-handoff claim across processes; reconverge the brain's residency when the sidecar restarts
under it; MTP model variants, disable-thinking / token-budget capping

**Inference / Model Manager in Slice 4 ([ADR-0007](../adr/ADR-0007-model-manager-inference.md)):**
- **`cortex_model_manager` process lifecycle and the real swap landed 2026-07-17 and 2026-07-18
  across the brain-handoff sub-slices ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decisions 3 to
  5); co-residency stays deferred.** The entry read: "**`cortex_model_manager` process lifecycle,
  co-residency, real swap.** The pure single-resident manager exists now; process I/O and swap land
  in **Slice 11** behind the unchanged `ModelManager` port (consequences)." It landed behind that
  port exactly as written, `acquire(model) -> ModelLease` untouched: the process half went behind a
  **new, segregated** `ModelHost` port rather than into `ModelManager`, and the swap behind a
  `ResidencyController` that only `SwappingModelManager` implements, which is what kept the
  original port unchanged rather than merely compatible. The real half is the `model-host`
  supervisor sidecar: one `llama-server` child per logical tier, an HTTP control API whose requests
  carry a logical id and nothing else, and the `HttpModelHost` adapter, all passing the same
  contract suite as the in-core scriptable twin. The mechanism is agent-validated in Docker on the
  8 GB dev GPU with two small artifacts standing in for the tiers (real processes started,
  health-gated, evicted, swapped, killed, restarted; see
  [runbooks/model-swap.md](../runbooks/model-swap.md)); **tier scale stays host-side**, the dev
  card being unable to hold the real cortex beside a deep model. **Co-residency remains open**, and
  its shape is now recorded rather than sketched: ADR-0030 decision 8's v1 rule is that while the
  deep model is resident it is **alone** on the GPU, since no candidate fits beside the ~11.3 GB
  cortex in 24 GB, so keeping CPU subagents serving through a swap, or a tiny GPU subagent beside
  the deep model on a larger card, is the thing still deferred. What this landing changes about it:
  the tiers it would need to keep alive are now real hosted models rather than hypothetical ones,
  so the deferral is exercisable for the first time on hardware that fits them.
- **Resume a crashed handoff from its record, instead of failing it.** Opened 2026-07-17 with the
  brain-handoff conductor sub-slice ([ADR-0030](../adr/ADR-0030-brain-handoff.md) decision 4),
  which names it as the recorded refinement. Boot recovery marks any handoff a crash interrupted
  `FAILED` and converges the GPU back onto the cortex; it deliberately does **not** re-run the
  deep model's phase, even though the record holds everything needed to (that is the point of the
  record). Replaying it would risk double-running side-effectful work, because nothing carries
  request identity: the tail may contain tool calls whose results were fed back but whose effects
  are not idempotent, and the deep phase's own dispatches would run again. Unlocked by the same
  dedup design the seam-transport reconnect entry needs (a request id plus an
  idempotency/resume registry keyed by it), after which resuming is a small addition to
  `recover_handoffs`: read the record, re-enter the residency scope, and run `BrainPhase` against
  it, which is exactly what the conductor already does. Until then the honest failure is the
  cheaper one, and the user simply asks again.
- **Fence the single-handoff claim across processes.** Opened 2026-07-18 by a verification pass
  over the brain-handoff conductor ([ADR-0030 addendum](../adr/ADR-0030-brain-handoff.md)), which
  found the residual undocumented rather than unknown. The one-GPU-one-handoff rule is
  `SwappingModelManager.handoff_claim`, and it holds `self._handoff_claimed` as instance state, so
  it binds **one process**; the store-side guard ADR-0030 names as the cross-process backstop is
  `active()` read in `SwapConductor._prepare` and the record written two awaits later, a check
  followed by an act rather than a claim, so two brain processes on one Redis could both read "no
  handoff" and both evict the cortex. Not a live defect: the deployment runs exactly one brain
  process (one `brain` service in `docker/docker-compose.yml`, no replicas), so the in-process
  claim is the whole population of claimants, and the loser of either guard is refused before
  anything is drained or evicted and told a handoff is already running rather than that the swap
  broke. **Costs a port change, not a tweak:** `put` cannot express "only if no handoff is active",
  so `HandoffStore` gains a fenced claim verb, implemented in Redis as an atomic `SET
  cortex:handoff:active <id> NX` issued before the record write or as a Lua script (a MULTI/EXEC
  transaction cannot branch on an intermediate reply). It also needs an expiry story, because a
  fenced claim whose holder dies wedges every other process until the key is cleared by hand,
  where a stranded record today is deliberately TTL-free and settled by the next boot recovery: a
  lease (TTL plus a heartbeat) or a user id recovery can recognize. Then the fake carries the
  same semantics, the contract suite gains a two-concurrent-claimants case, and `_prepare` calls
  the claim instead of `active()`. **Trigger:** a second process that can swap (a second brain
  replica, a CLI or worker sharing the Redis, or a supervisor sidecar that swaps itself).
  **Still not met as of 2026-07-18**, now that the supervisor sidecar exists: it performs no swap of
  its own. The brain drives it through the port, its control API can only start, stop and report the
  tiers its own env declares, and it holds no handoff state at all, so it is not a second claimant.
- **Reconverge the brain's residency when the model-host sidecar restarts under it.** *Fix when it
  bites.* Opened 2026-07-18 by the model-host sub-slice, and observed live rather than reasoned
  about: `kill -9` on the supervisor daemon ended its container (both `llama-server` children died
  with it and VRAM returned to baseline), `restart: unless-stopped` revived it, and its boot default
  started the cortex again from a clean slate. That direction reconverges by construction. The other
  one does not. `SwappingModelManager` holds `_resident`, `_scope_model` and `_handoff_claimed` as
  instance attributes ([residency.py](../../brain/packages/core/src/cortex_core/residency.py)), and
  `recover_handoffs` runs **only** at brain startup
  ([wiring.py](../../brain/packages/orchestrator/src/cortex_orchestrator/wiring.py)), so a sidecar
  that restarts mid handoff leaves the brain believing the deep model is resident and holding a
  claim while the fresh sidecar serves the cortex. The turn then fails at the backend (the deep
  tier's endpoint answers nothing), the swap back's `stop`/`start` are idempotent and harmless
  against a sidecar that already did both, and the claim is released in the conductor's `finally`,
  so the failure is honest and self-limiting; what is lost is that one handoff, plus a window where
  `Health` would misreport residency once the honesty-surfaces sub-slice makes it read residency at
  all. **Nothing is at stake with escalation off** (the default), because the plain
  `SingleResidentModelManager` holds no residency state: a sidecar restart is then invisible to the
  brain, which was confirmed live (a turn answered normally straight after the restart).
  **What would close it:** the daemon exposing a boot id or generation counter on `GET /health`, the
  adapter carrying it, and the manager treating a change in it as "everything I believe about
  residency is stale, converge again" (which is `converge_residency`, already written, called from
  somewhere other than startup). That is a wire addition plus a caller, not a port change. It pairs
  naturally with the residency state the honesty-surfaces sub-slice introduces, since both want a
  place to keep "what is actually resident" that is not an attribute nobody revisits.
  **Trigger:** a sidecar that restarts (an OOM kill, a crash, an operator's `docker compose restart
  model-host`) while a handoff is in flight over the supervisor backend, seen more than once.
- **MTP (multi-token-prediction) model variants.** Deferred until they earn their keep, per
  [ADR-0004](../adr/ADR-0004-model-lineup.md).
- **The cortex reasoning trace is surfaced as a thinking status. This landed 2026-07-06
  ([ADR-0020](../adr/ADR-0020-reasoning-status.md)).** The cortex (gemma-4-12B) emits
  `reasoning_content` before `content` (found during the Slice 6.5 GPU validation), and thinking
  stays on for it; `LlamaCppBackend` used to read only `content`, so a long deliberation streamed
  nothing until it concluded. The chosen option (of disable-thinking / surface / token-budget) is
  **surface**: `ReasoningChunk` joins the `InferenceEvent` union, the shared `stream_tool_loop`
  yields `str | ReasoningDelta` (reasoning ephemeral, never persisted or fed back), and the engine
  maps it to a domain `StatusUpdate(state="thinking", …)` → the wire `ServerEvent.status` the
  proto/body/overlay already carried but the brain never emitted. CI-gated end to end over the
  fakes; **host-validated via Docker (agent, 2026-07-06, [ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):**
  live gemma-4-12B streamed a real reasoning trace surfaced as 326 `StatusUpdate(state="thinking")`
  events, reply clean and persisted==shown (integration test `test_reasoning_model_emits_reasoning_before_reply`).
  **The output guardrail over reasoning status landed 2026-07-12
  ([ADR-0020 addendum](../adr/ADR-0020-reasoning-status.md)):** the inline chips (see [body-overlay.md](body-overlay.md)) gave the
  thinking status a rendered surface, so a laundered URL in the reasoning trace had a display
  channel the reply-side guardrail never inspected. The trace now streams through its own second
  `OutputFilter` under the same policy and user-URL allowlist (`output_channels.py`, an engine
  line-cap split): a `ThinkingChannel` scrubs each delta (a wholly-carried one emits no status),
  its carry surviving tool steps between thinking bursts so a URL split around a dispatch is
  joined before matching (an adversarial multi-agent review caught the per-burst-flush variant
  letting a fragmented URL cross the seam), released once at end of stream. Redact +
  strict modes and the obfuscation-resistant grammar are inherited; no new config, no seam
  change; reasoning stays ephemeral. Remaining behind the same
  `InferenceBackend`/`TurnCapabilities` seams (ADR-0020 deferred):
  the **disable-thinking / token-budget** alternatives (still available if a runaway trace needs
  capping) and **reasoning persistence/summarization**. **`state`-aware overlay treatment landed
  2026-07-13 ([ADR-0020 third addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now
  keeps the status event's `state` (a new `Message.statusState`) and a `"thinking"` chip renders
  distinctly (a `chip-think` modifier: the reasoning bob on its dot, an accent label, an aria
  label) from a generic status or tool chip, entirely in the CI-gated overlay tree with no seam
  change (the `state` field already rode the wire). A richer collapsed "thoughts" section stays
  open behind the same field. **The collapsed "thoughts" section landed and reasoning
  persistence/summarization was declined on 2026-07-16, both without a seam change ([ADR-0020
  fourth addendum](../adr/ADR-0020-reasoning-status.md)):** the reducer now also concatenates every
  scrubbed thinking delta into a new `Message.thoughts`, and the settled reply renders it as a
  collapsed `<details>` disclosure above the bubble, the chip's retrospective counterpart
  (`overlayState.ts` + `Message.tsx`, gated + browser-validated in both themes). Persisting or
  summarizing the trace stays **declined for want of a consumer**: nothing reads a stored trace,
  re-display on reload needs a `GetSessionMessages` reasoning field (the read path the open-chat
  title-consistency entry independently needs widened) and the store to grow by the observed
  ~13,882-char single-turn scale, and summarization reverses this ADR's "never fed back" while
  re-raising the non-reentrant GPU-lease sequencing the title generator navigates. It moves to
  this backlog's dead-until-a-consumer list and reopens the day either consumer appears.
