# Docs index

Start here. Rules for working in this repo: [AGENTS.md](../AGENTS.md).

## Map & plan

- [ARCHITECTURE.md](ARCHITECTURE.md) covers components, boundaries, data flow, the swap rule,
  the body/brain split, ports & traits, the two portability seams.
- [ROADMAP.md](ROADMAP.md) lists ordered vertical slices; which slice proves which gate; the
  Phase 0 assumptions & risks list.
- [refinements/](refinements/index.md) is the consolidated deferred-refinements backlog (every
  follow-up, one self-contained doc per area, by origin ADR), with an index carrying a blurb
  per doc, the recommended pickup order, and what blocks each open item. Moved out of the
  ROADMAP on 2026-07-15.
- [host/](host/index.md) is the work only the maintainer can perform, one self-contained doc
  per sitting, each item tagged with the capability it needs: a real Win32 desktop session, or a
  24 GB GPU. Deferred *design* lives in refinements; this holds code that is written and needs
  hardware the dev machine does not have. Moved out of the ROADMAP on 2026-07-19.

## Decisions (ADRs)

- [ADR-0001: Founding architecture](adr/ADR-0001-architecture.md): hexagonal on both
  sides, polyglot split with a gRPC seam (no FFI), external state as swap safety, the
  engine behind `InferenceBackend` (originally vLLM, now superseded by ADR-0005),
  Redis + Postgres/pgvector, toolchain gates; open questions.
- [ADR-0002: Toolchain and gate mechanics](adr/ADR-0002-toolchain-gates.md): nightly
  for Rust branch coverage, the JSON branch gate, `scripts/` as a standalone project,
  the `_generated` marker, tests-outside-source, ruff ALL, pre-commit = `just check`;
  a live contract run gets a Redis logical database of its own, so it reports on the
  adapter rather than on whatever the brain happens to have stored.
- [ADR-0003: Seam codegen and packaging](adr/ADR-0003-seam-codegen.md): committed
  stubs in `_generated` dirs (hermetic builds, `just proto` to regen), tonic + grpcio,
  `#[ignore]` tests as the Rust integration suite, stubs shared via `cortex_seam`,
  the CORTEX_SEAM_* env contract.
- [ADR-0004: Model lineup](adr/ADR-0004-model-lineup.md): locked candidate sets per
  tier + embedder (all GGUF via LM Studio), logical model ids, local data locations
  (models in `D:\Software\AI\Models`, knowledge base in `D:\Software\AI\Database`);
  picks: cortex gemma-4-12B, embedder nomic-v1.5, subagent **gemma-4-E4B** (revised
  2026-07-03 for injection-robustness, scoring 0/10 vs the old Qwen3.5-2B's 1/10; measured
  CPU cost in the pick-revision addendum), brain **gemma-4-31B q4_0 QAT** (measured
  2026-08-04 on a card that holds the tier, with Qwen3.6-27B as the documented lighter
  alternate; VRAM separated none of the four candidates and answering under an unbounded
  reply separated all of them, in the brain-pick addendum).
- [ADR-0005: llama.cpp as the inference engine](adr/ADR-0005-llamacpp-engine.md):
  supersedes vLLM (ADR-0001 d4); one `llama-server` per model behind the
  OpenAI-compatible API; swap = process lifecycle; embeddings on the same engine.
  Its 2026-08-09 addendum bounds the read phase of both generation clients with a per-tier
  stall ceiling (`CORTEX_INFERENCE_STALL_TIMEOUT_S`, `CORTEX_SUBAGENTS_STALL_TIMEOUT_S`), a gap
  between chunks rather than a cap on a generation, derived from measured time to first token.
- [ADR-0006: Gate performance](adr/ADR-0006-gate-performance.md): path-filtered CI via
  the fail-closed in-repo classifier (`scripts/ci_paths.py`), PR-only run cancellation,
  SHA-pinned actions + dependabot, parallel `just check`.
- [ADR-0007: Model Manager v1 + llama.cpp adapter](adr/ADR-0007-model-manager-inference.md):
  `ModelManager` core port; the `LlamaCppBackend` httpx adapter behind the unchanged
  `InferenceBackend`; a pure single-resident Model Manager (no swap yet); Echo stays the
  GPU-less default, llama.cpp opt-in; the `docker/docker-compose.gpu.yml` override.
- [ADR-0008: Memory v1](adr/ADR-0008-memory-v1.md): custom-and-thin over pgvector, not
  Letta (no framework that hides control flow); `Embedder` + `MemoryStore` ports and the
  `MemoryRecaller` use-case; the pgvector adapter stays 100%-covered without a DB in CI via
  the accepted MockTransport pattern (behavior proven against the fake in CI, against real
  Postgres on the host); durable data as a named volume + export to `D:\Software\AI\Database`.
- [ADR-0009: Tools via MCP](adr/ADR-0009-tools-mcp.md): `ToolRegistry` + audited
  `ToolDispatcher` in the pure core; native function-calling (evolve `InferenceBackend`,
  not prompt-and-parse); the brain as an MCP client (`mcp` SDK v1.x behind the port); tool
  servers as sidecar containers over streamable-http (filesystem read-only-mounted, patched
  for the EscapeRoute CVEs); a thin read-only IMAP server for email over ProtonMail Bridge.
- [ADR-0010: Subagents](adr/ADR-0010-subagents.md): delegation as a native `spawn_subagents`
  tool (a concurrent batch, per the increment-2 addendum) through the audited tool loop; a
  `CompositeToolRegistry` merging built-in + MCP tools;
  the shared infer↔tool loop extracted from `TurnEngine`; tools-enabled depth-1 subagents over a
  Redis `TaskStore`; a dedicated `SubagentScheduler` (bounded CPU concurrency, not the GPU
  `ModelManager`); subagent inference on a CPU `llama-server`.
- [ADR-0011: Body v1](adr/ADR-0011-body-v1.md): the first host-native slice with one-turn-per-
  `Converse` streaming (`TurnEvent`), the `Hotkey` OS-backend seam (first `cfg`-gated backend +
  the stub coverage escape hatch), the Tauri app outside the gated workspace, and a React+Vite
  overlay gated at 100% + browser-validated (addendum).
- [ADR-0012: Resource governance](adr/ADR-0012-resource-governance.md): GPU-first/CPU-overflow
  subagents (revising ADR-0007/0010) with the new pure `SubagentPlacer` VRAM-budget accountant
  (`VramBudgetPlacer`, `acquire` untouched), a soft two-dimensional CPU/RAM `SubagentScheduler`
  (`ResourceBudgetScheduler`), composed at `SubagentRunner`; ledgers as live-resource (not durable)
  state; `drain()`/CUDA-OOM re-place deferred to Slice 11. Its 2026-08-09 addendum bounds how long
  a spawn may queue for room (`CORTEX_SUBAGENTS_ADMISSION_WAIT_S`, 3600 s, derived from the wait a
  full spawn batch legitimately produces) and declines the queue-depth half, the scheduler holding
  charges and no durations.
- [ADR-0013: Untrusted-content boundary](adr/ADR-0013-untrusted-content.md): prompt-injection
  defense behind the tool seams (Slice 6.5) via fail-closed `Trust` on `ToolResult`, a static
  security preamble + nonce-delimited per-result wrap, a turn-local `TaintLedger` in the shared
  loop (propagating subagent → cortex), `ToolSpec.gated` + a dispatcher gate + the one new
  `Confirmer` port (inert until the first outbound tool), memory-suppress on taint; the screening
  subagent and the real overlay confirmation adapter deferred.
- [ADR-0014: Session-history windowing](adr/ADR-0014-history-windowing.md): the Slice-3
  deferral landed as a pure `HistoryWindow` seam in `TurnCapabilities` with a turn-aligned
  char-budget tail (`CharBudgetHistoryWindow`, `CORTEX_HISTORY_CHAR_BUDGET`, on by default,
  0 disables); persistence untouched. Summarization landed behind the same seam on 2026-08-06
  (ADR-0038 decision 9 and its summarizing-window addendum): `SummarizingHistoryWindow` recaps
  the turns the budget drops, cached in the session store and folded forward as the boundary
  moves, `CORTEX_HISTORY_SUMMARY`. Fenced at both ends since the same day
  (ADR-0038 untrusted-recap addendum): a stored transcript can quote untrusted content, so the
  recap pass runs under the security preamble over wrapped material and the recap re-enters the
  turn wrapped in turn, under a nonce minted after the model has spoken. Re-measured behind that
  fence the same day (ADR-0038 re-measured-behind-the-fence addendum): the fence costs characters
  rather than the answer, and the default stayed off then, on a fold that reached 224.5 s and an
  opening fact surviving five compounding folds 2 times in 3. **It defaults on since the
  cheap-fold addendum, later the same day**, which built the four things that move waited on: the
  fold asks for no thinking and at most 512 tokens per request (a new `GenerationBounds` on
  `InferenceBackend.stream`), `CORTEX_HISTORY_RECAP_MIN_CHARS` puts a floor under a fold, and
  `HistoryWindow.select` takes a `ProgressSink` so a folding turn says so. A fold now decodes 61 to
  163 tokens for 2.9 s to 6.2 s and the opening fact survives 3 times of 3. Its claim to let go of
  the GPU before the reply asks for it stopped being a sequencing argument on 2026-08-08 (ADR-0038
  fold-under-load addendum): measured against three overlapping `Converse` streams it held on every
  point, and what load costs is queueing, one reply waiting 5.41 s behind two folds that were not
  its own.
- [ADR-0015: Output guardrail](adr/ADR-0015-output-guardrail.md): the model-independent
  laundering defense (ADR-0013 hardening deferral landed). The `TaintLedger` collects the
  URLs untrusted content carries in, an `OutputGuardrail` seam in `TurnCapabilities` redacts
  any that reappear in the reply (minus the user's own) before the user sees it,
  streaming-safe, persisted-equals-shown (`CORTEX_OUTPUT_GUARDRAIL`, on by default).
- [ADR-0016: Seam token](adr/ADR-0016-seam-token.md): assumption 5's shared secret made
  real, via `CORTEX_SEAM_TOKEN` on both sides of the seam; a brain-side gRPC interceptor
  rejects untokened calls UNAUTHENTICATED (structural, covers future RPCs), the body's
  tonic client attaches it, the healthcheck carries it; empty disables (dev/CI unchanged).
- [ADR-0017: Subagent model safety](adr/ADR-0017-subagent-model-safety.md): a constraint
  on the planned Slice 8.6 (heterogeneous subagent models). Untrusted content never reaches
  an injection-weak model. The cortex's per-spawn model choice is a hint, not authority: the
  wiring forces the injection-robust default (gemma-4-E4B) whenever the spawn is tainted or
  tools-enabled, so a weak roster model is reachable only for a tool-less subagent on an
  untainted turn. Deterministic; binds the ADR-0013 taint signal to the ADR-0004 pick.
- [ADR-0018: Heterogeneous subagents](adr/ADR-0018-heterogeneous-subagents.md): Slice 8.6
  mechanics. The spawn schema grows per-item `{instruction, model?, context?}`; a pure
  `SubagentRoster` (per-entry backends + `PlacementRequest`, one shared scheduler/placer)
  whose `resolve` enforces ADR-0017 at the runner; the turn's taint reaches built-ins as a
  dispatcher stamp on `ToolCall`; the task record carries `model`/`tainted` (and the
  `SubagentResult.tainted` round-trip gap is fixed); flat env = the default entry,
  `CORTEX_SUBAGENTS_ROSTER__<name>` adds alternates.
- [ADR-0019: Tainted-memory recording](adr/ADR-0019-tainted-memory-recording.md): the ADR-0013
  poisoning deferral landed. A tainted turn can be recorded with an untrusted-provenance marker
  (`MemoryRecord.tainted`, a pgvector column) under `CORTEX_MEMORY_ON_TAINTED=record` (default
  `skip`); recall always fences a stored tainted memory and re-taints the turn, so untrusted-derived
  content is fenced-and-tainting across turns, not just within one, behind the unchanged
  `MemoryStore`/`MemoryRecaller`/`TaintLedger` seams.
- [ADR-0020: Reasoning status](adr/ADR-0020-reasoning-status.md): the Slice-4 reasoning-model
  deferral landed. The cortex's `reasoning_content` (it thinks before it replies) is surfaced as a
  live `StatusUpdate` (`state="thinking"`) instead of silently dropped. `ReasoningChunk` joins the
  `InferenceEvent` union, the shared tool loop yields `str | ReasoningDelta`, and the engine maps
  reasoning to an ephemeral (unpersisted, non-reply) `StatusUpdate`; the proto/body/overlay status
  path was already built and is now lit end to end. Behind the unchanged `InferenceBackend`.
- [ADR-0021: Session-read seam](adr/ADR-0021-session-read-seam.md): Slice 8.7. Two read-only
  unary RPCs (`ListSessions`/`GetSessionMessages`) expose views of the durable store over the seam,
  so the overlay's chat list, switcher, and `Ctrl+↑/↓` cycling load store-backed history instead of
  in-memory. One new port method (`SessionStore.list_sessions`, a `cortex:sessions` ZSET index; a
  pure `summarize_session` derives title/preview both adapters share); `GetSessionMessages` reuses
  `history`. The body `BrainTransport` / overlay `BrainBridge` grow typed reads, and the overlay
  owns the `session_id` for real multi-chat.

- [ADR-0022: Email-write + the real Confirmer](adr/ADR-0022-email-write-confirmer.md):
  Slice 8.8 adds the first outbound/irreversible tool (`send_email`, SMTP over ProtonMail Bridge,
  off by default) and the machinery every later gated action reuses: the confirm exchange rides
  the Converse stream (`ConfirmRequest`/`ConfirmResponse`), each stream builds its engine via an
  `EngineFactory` so its `SeamConfirmer` reaches the dispatcher, the gate table is revised
  (untainted gated → user confirms via the overlay card; tainted gated → denied outright and
  never merely a confirm-away), and `GatedToolRegistry` + `CORTEX_TOOLS_GATED` declare remote
  tools gated at the composition root (subagents never see them).
- [ADR-0023: Body gateway + volume](adr/ADR-0023-body-gateway-volume.md): Slice 9 brings the first
  **brain→body** seam direction and the first OS action. Resolves ADR-0001 Q2 (body capabilities
  are internal tools over a `BodyGateway` port, not MCP) and Q3 (the brain dials the host body via
  `host.docker.internal`; the abstract port keeps the tunnel fallback an adapter swap). Adds the
  `BodyGateway` port + `GrpcBodyGateway` adapter (`cortex_body_client`) on the brain, the
  `AudioControl` OS trait + real Core Audio `WindowsAudioControl` on the body, and the
  `BodyService` server (`OsService`, named `VolumeService` until the reminder toast joined it)
  + the reversed seam-token validator in `body_rpc`. Volume is ungated (reversible); `set_volume`
  is opt-in-gatable via `CORTEX_TOOLS_GATED`. `unsafe` for Core Audio is authorized narrowly to
  `os_windows`; `SEAM_TOKEN_HEADER` is lifted to `cortex_seam`.
- [ADR-0024: Transport retry / reconnect](adr/ADR-0024-transport-retry.md): the Slice-2
  deferral, landed as a `RetryingTransport` decorator over the unchanged `BrainTransport` port, with
  bounded exponential backoff on the idempotent calls, a `Sleeper` port keeping time injectable
  (real `TokioSleeper` in the shell, a recording fake in tests), and a lazy
  `connect_lazy_with_token` channel so a briefly-down brain reconnects transparently. `converse`
  is forwarded unchanged (non-idempotent → a failed turn stays terminal).
- [ADR-0025: Scheduling & reminders](adr/ADR-0025-scheduling-reminders.md): Slice 9.5 adds durable
  schedules behind a new `ScheduleStore` port (Redis adapter, no TTL, versioned records), a pure
  coalescing `next_due`, five cortex-only built-ins (`schedule_task`/`list_scheduled`/
  `cancel_scheduled`/`snooze_scheduled`/`edit_scheduled`, taint riding the record), the stateless `ScheduleTicker` (at-least-once via
  a claim lease; autonomous tasks fire through the existing subagent seams with `confirmer=None` +
  `UngatedToolRegistry` as the structural safety posture), and delivery over both seam directions:
  pull (`ListDueReminders`/`AckReminder` on `BrainService`) and push (`BodyService.Notify` → a
  native toast, the body's second OS capability).
- [ADR-0026: Prose style gates](adr/ADR-0026-prose-style-gates.md): the no-dash-as-punctuation and
  no-volatile-reference rules get gates instead of goodwill, after a sweep found 3452 em-dash lines
  and 144 of 148 non-conforming commit messages. `dashcheck.py` scans every text file (em dash and
  en dash alike, spaced or not, since a range takes a plain hyphen, while the minus sign stays
  legal; ASCII `--` stays the
  inline-reason idiom in files but is banned in messages, which are pure prose). `commitlint.py`
  grows from the header to the whole message and resolves hex tokens with `git cat-file`, so only a
  hash that really is a commit is flagged. Escape hatch: `dashcheck: allow` plus a reason. A
  message declares a paste with a code fence or a `$` prompt, and a paste is exempt from the wrap
  and from the dash ban, never from the volatile-reference ban or the hash check.
- [ADR-0027: Structured turn provenance](adr/ADR-0027-turn-provenance.md): the convergence seam
  for four provenance deferrals (ADR-0013/0019/0022/0025). One frozen `TurnStamp`
  (`session_id` + `tainted` + `sources`) replaces the loose taint keyword:
  the dispatcher stamps every call, discarding a model-forged stamp; the engine threads the
  turn's session through `ToolLoopContext`; the ticker stamps a fired item's stored provenance.
  First consumer: `schedule_task` fills `ScheduledItem.session_id`, closing session attribution.
  The source fields landed with the addendum: kind-tagged `Provenance` values, sanitized and
  bounded in the pure core so attacker-chosen text is inert, captured from the advertised tool an
  untrusted result came through and from a recalled tainted memory's id.
- [ADR-0028: Grammar-constrained subagent output](adr/ADR-0028-grammar-constrained-subagents.md):
  the ADR-0017 option (c) hardening pass. An additive `schema` keyword on the unchanged
  `InferenceBackend` (mapped to a llama.cpp `response_format` `json_schema`) lets the
  `SubagentRunner` decode a tool-less subagent's reply into a fixed `{"reply": …}` envelope,
  killing format-laundering on the weak-model niche with no grammatical position for an appended
  footer or link. Gated to the tool-less path so the JSON grammar never fights tool-calling.
- [ADR-0029: Vision (screen capture)](adr/ADR-0029-vision-screen-capture.md): **landed** and
  audit-repaired (its 2026-07-19 addendum), except
  the host-only Windows validation of the GDI blit (authored and cross-compiled, never run
  against a real screen). Slice 10 gives the
  cortex eyes through a model-initiated `capture_screen` built-in over the unchanged
  `BodyGateway`, a `ScreenCapture` OS trait returning raw pixels with all downscale/encode/byte
  policy in pure `body_core`, a GDI backend under its own `unsafe` line, and the image riding
  `ToolResult.images` onto the `Role.TOOL` message (measured accepted by the real cortex plus
  projector) with `InferenceBackend.stream` unchanged. Pixels are turn-local, enforced by a
  `Message` invariant plus a loud store rejection. Since no nonce can bracket an image, the
  boundary is deterministic: always UNTRUSTED, a new turn-local `opaque` bit escalating the
  guardrail to strict redaction and blocking durable memory, a body-authored capture receipt, a
  fail-closed host kill switch, and the overlay excluding itself to break the self-injection loop.
  The 2026-07-18 closeout addendum records five corrections the implementation made to the design
  (a fifth proto field, because a fixed byte ceiling made the shrink ladder's give-up arm
  unreachable and putting the budget on the request makes "one ceiling, two enforcers" a
  mechanism) and its validation, including the control arm that shows a projector-less turn
  **fabricates** a desktop rather than failing. Its 2026-08-03 addendum turns the last piece of
  that mechanism from prose into a gate: `scripts/crosscheck.py`, a cross-tree scan that ties
  the constants declared once per language (the byte ceiling, and the seam token's metadata key)
  by comparing declaration sites with each other rather than against a master. Its 2026-08-08
  addendum widens it to the couplings a declared equality could not reach: an ordering comparator
  for a bound that must sit under another, and a mention form for a far side that spends a value
  without declaring it, in a compose string, a stylesheet, or a bare literal. Its 2026-08-09
  counted-mentions addendum lets a mention pin an exact number of occurrences, opt in, for the far
  sides whose several spellings are one set that must move together. Its 2026-08-10 addendum lands
  the **body half of a targeted capture**: `CaptureScreenRequest.target` is a two-value
  `CaptureTarget` (the whole display, which is the proto3 zero and today's behaviour, or the
  window the user is looking at), and it landed in the same commit as the body that honours it,
  because under proto3 a field an older body ignores is a silent lie about a constraint the brain
  believes it set. A model-named rectangle is declined on this ADR's own measurement (the cortex
  will not decline to name one it cannot see) and reopens on an overlay-drawn region picker. The
  window is resolved by walking the desktop's Z-order rather than by `GetForegroundWindow`, which
  is the overlay itself whenever a capture runs; the crop is pure core, so `source_width`/
  `source_height` keep meaning the display; and the receipt gains a second fixed sentence for a
  window. The brain does not ask for one yet.
- [ADR-0030: Brain handoff (the real model swap)](adr/ADR-0030-brain-handoff.md): the Slice 11
  capstone design, **accepted**; every engineering sub-slice has landed, the deep-model pick was
  measured 2026-08-04 (gemma-4-31B QAT q4_0, ADR-0004), and the tier-scale swap remains because a
  handoff begins at a confirm card only the overlay answers. An explicit gated `escalate_to_brain`
  built-in triggers a within-turn handoff: the turn's not-yet-stored remainder (brief, taint
  ledger with sources and URLs, nonce, tool-loop tail, dispatch budget) serializes into a
  `HandoffRecord` behind a new `HandoffStore` port; a core `SwapConductor` drains subagents,
  swaps `llama-server` processes through a new `ModelHost` port (a supervisor sidecar starting
  and stopping one process per model, ADR-0005 made literal), health-gates, rehydrates the
  brain from the stores, persists, and converges back to a serving cortex on every exit path.
  `ModelManager.acquire` stays unchanged (ADR-0012); residency moves under an additive swap
  scope so eviction never preempts a mid-stream round, and `Health` answers an honest
  `ready=false` from it while the deep model holds the GPU, or while a boot recovery that could
  not settle the cortex stands. The CI gate is a parameterized chaos
  test over the fake host (kill at every step boundary, converge with no state loss); tier-scale
  swap validation is host-side. Co-residency landed 2026-08-07 with a fit check that reads the
  card between the swap's last eviction and its load, and its blind half closed 2026-08-08: the
  backend now surfaces llama.cpp's own decode rate as a `DecodeCadence`, a pure `CadenceWatch`
  judges a whole handoff on its fastest judgeable completion, and the deep phase warns once when
  the tier never reached `CORTEX_SWAP_BRAIN_DECODE_TPS`. Measured on the card: 20.38 to 22.77
  tok/s spilled against 31.08 to 33.78 alone, **both tiers reporting `ready` and the card reading
  like a fit in each**.

- [ADR-0031: The bubble mark, and the mark as a picked style](adr/ADR-0031-bubble-mark.md): the
  overlay's activity mark, **landed**. The living rings retired (concentric turning rings read as
  another product's identity) for a soap bubble carrying the same eight-hue palette: an outline
  built from sine harmonics of order two or higher, which fixes the centroid and the mean radius,
  so the standing "the anchor never moves" rule holds by construction. Four styles ship in a
  registry that mirrors the theme registry, named as movements of thought (Mull the default,
  Muse, Hunch, Tangent), picked from the empty state's
  own mark rather than a fifth header button; the motion left CSS and SMIL for a frame clock, so
  reduced motion schedules no frames at all.

- [ADR-0032: The user's preference record](adr/ADR-0032-preference-record.md): appearance
  choices made durable, **landed**. Opaque key/value pairs the brain stores and never parses
  (`GetPreferences`/`SetPreference`, a `PreferenceStore` port adapted to the same Redis the
  conversation state uses), so a new setting costs no seam change and a choice outlives a body
  reinstall. An empty value clears a key, which is how the overlay expresses "follow the system"
  without a magic value. Reads retry, writes do not; the write is optimistic and its failure costs
  only durability. Its surface is the console's appearance tab, holding the theme and the mark,
  which also gave the mark picker a route in from a chat that already has messages.
- [ADR-0033: The panel grows upward](adr/ADR-0033-panel-growth.md): the overlay panel anchored by
  its bottom edge so the composer never moves, with size changes eased through the Web Animations
  API, **landed**. The CSS-only version is documented there as measured-and-rejected: a
  `transition: height` cannot fire between two content-driven `auto` heights, and
  `interpolate-size` does not change that.
- [ADR-0034: The panel's other faces are views](adr/ADR-0034-panel-views.md): settings and the
  shortcut list stop being sheets laid over the panel and become views it morphs into, so the panel
  resizes to what each needs and slides back to true centre, **landed**. Amends the entry above:
  the bottom edge is pinned only *within* a view, the ceiling is derived from the max height so a
  full-height panel lands exactly centred, and sections now animate their own height instead of
  being deleted while the panel eases after them.
- [ADR-0035: One console, and the motion a user's eye corrected](adr/ADR-0035-console-and-motion.md):
  the two views above fold into **one console with a tab strip** (appearance and the shortcut list
  are tabs of a single destination, so the panel has one thing to leave and Esc leaves it in one
  press), and the day's maintainer review of the running overlay is the rest, **landed**. Amends the
  entry above: coming back to the chat restores the edge it was left at instead of re-centring, the
  pinned edge is remembered unclamped, a move is paced by its distance and resumed rather than
  restarted, a roll announces its start so the panel can ride it, and the chat carries a floor so
  the first message cannot shrink the window. Scrollbars became reserved chrome and the connection
  dot moved into the button cluster in the same pass.

- [ADR-0036: The window's dreaming edge, as a picked style](adr/ADR-0036-window-edge.md): the
  panel's silhouette can go liquid, warped by the mark's own maths (integer wave orders on the
  closed perimeter, corner-weighted, one path per frame), **landed**. A third appearance registry
  beside the theme and the mark, named as a ladder of dream depth (Still, Lucid, Reverie, Trance)
  with **Lucid the default** by the user's call; the animated clip rides a background-only slab
  so the words never sit on the warping layer, the glow cross-fades neutral to accent with the
  turn (Trance's resting ember is the one written exception to color-as-activity), and a liquid
  panel trades its backdrop blur for a near-solid ground because Chromium does not clip
  backdrop-filter output by a path clip, invisible in the v1 opaque window and refiled with the
  transparent-window pass.

- [ADR-0037: The reply whispers in, and the bubble grows at its pace](adr/ADR-0037-whisper-streaming.md):
  the streaming redesign the maintainer picked over three rounds of live pitch, **landed**. The reply
  condenses like breath on glass: letters clear through a nine-letter blur band on one continuous
  front (paced not timed, per letter), a single accent mist is the whole lifecycle (it breathes
  before the first token, glides along the front, evaporates on settle) and is the streaming
  bubble's only colour, and the bubble's box is posed by the same clock (a pill around the mist
  while thinking, then growth eased at the front's pace, its bottom edge doubling as the reveal).
  The block caret, the three dots, the per-word rise and the streaming glow are deleted; the
  reducer is untouched.

- [ADR-0038: A ranked `select`, its audit trail, and where a history summary lives](adr/ADR-0038-ranked-recall.md):
  the design the deferred-refinements backlog had been holding two entries against, **landed** in
  both halves. `RecallPolicy.select` is widened once for all three of its waiting consumers,
  to `async def select(hits, *, query, now, k) -> Ranking`, and the key a policy ranked by travels
  with the hits it kept under a named `RankBasis` (`ECHO`, `EMBER`, `SPREAD`, `SWEEP`, `VERDICT`,
  and `DEMUR` since the abstention addendum taught the judge to decline a pool that helps with
  nothing) whose `comparable` property carries the fact that an MMR key is measured against the
  kept set. The
  declined blended-relevance field is reversed onto that return rather than onto `ScoredMemory`;
  recall gets its first audit trail (`RecallAuditSink` plus a logging sink that writes rank keys and
  no text); and the model rank ships as `JudgeRecallPolicy`, measured against the shipping cosine at
  0.917 to 1.000 mean reciprocal rank. **The rank's request is bounded since the bounded-side-calls
  addendum**, which took it from 448 to 613 decoded tokens at 18.4 s per recall to 12 to 22 at
  0.9 s at exactly the same ranking, so `CORTEX_MEMORY_RECALL=judge` was recommended as a default and
  left for the user to call, the session title having taken the same lever on the same day (ADR-0021
  addendum). **The user called it on 2026-08-08, and the turn-cost addendum is what the call rested
  on:** over 48 real turns an arm through the seam, with a raw block either side of the judged one,
  a recalling turn's time to first token rises 0.515 s under the judge (95% CI 0.116 to 0.915) while
  the two raw blocks differ by an amount whose interval spans zero, which is less than the rank's own
  0.877 s because a rank that keeps 1.17 notes leaves the reply less to read than the cosine's 5. So
  `judge` is the default and `raw` the opt-out. A session summary is cached in Redis rather than
  recomputed per turn, safe because `SessionStore` has no verb that edits a message, so a prefix
  summary can only go incomplete and never wrong; the summarizing-window addendum records that
  half being built, from the `set_recap`/`recap` verbs through `SummarizingHistoryWindow` to a
  measured run where the shipped window could not answer a question the recap could. **The
  abstention addendum** closes the defect the widened corpus found: a judge that answered
  `{"order": []}` on a question memory cannot answer was read as a failed rank and replaced with the
  cosine's nearest misses, and it now returns nothing on the `DEMUR` basis, which the trail reports
  as a refusal rather than as a fallback (measured: the four unanswerable questions return nothing
  4 of 4, the run falls back 0 of 26 against 4, and the ranking on the answerable 22 is unchanged).
  **The relevance-floor addendum** declines the geometric analogue of that refusal, and its
  calibration is why: a similarity floor cannot separate the questions memory can answer from the
  ones it cannot, because the two populations overlap on cosine behind both embedding models the
  repo ships a path for, so the tightest floor that silences all four unanswerable questions
  silences 6 of 22 answerable ones and guts the vocabulary-trap category. Declining is a property
  of reading, not of ranking. **The fold-under-load addendum** replaces the last argument this
  ADR shipped a default on with a measurement: the summarizing window's claim to release the GPU
  before the reply asks for it was a reading of the call graph, and three overlapping `Converse`
  streams over the real cortex say it holds (no nested or shared lease, every fold released before
  its own reply acquired, no session's facts in another's answer), at a price the argument never
  claimed to know, one reply waiting 5.41 s behind two folds that were not its own. The run refuses
  to report unless the streams provably contended, and it opened one deferral, a stalled consumer
  holding the lease across its whole reply. **The dropped-candidate addendum** gives the trail the
  half a pool size cannot carry: every candidate the rank passed over, by id and by the store's
  cosine, bounded at the width a default deployment fetches and counting anything past it, so a
  memory that never came back stops reading like a memory the store never offered. It carries no
  rank key for a drop, since the judge leaves an unhelpful note out of its order rather than scoring
  it low, which makes the line an account of what was available and not of why the rank declined.
  **The harness addendum** puts the turn-cost run itself in the repo, which it never was, and its
  answer to the two questions that had kept it out is a division of labour: an arm is a container
  configuration, so the restarts live in `just turn-cost`, which puts the arms in separate
  processes, so each block writes a sample and `scripts/contrast.py` reports the blocked paired
  bootstrap while the block driver asserts only invariants. Rerun at the original's own size it
  reproduces the time to first token independently (0.539 s against 0.515 s, null arm spanning
  zero) and revises the whole-turn figure upward to 0.979 s, almost all of the excess sitting in
  the one question memory cannot answer, where a rank that declines leaves the model saying at
  length that it does not know.

New non-obvious decision → add `adr/ADR-XXXX-<slug>.md`, link it here.

## Design

- [design/overlay-ux.md](design/overlay-ux.md) covers the overlay's UX & visual language (Slice 8):
  the bubbly/alive/colorful identity, design tokens, the panel anatomy, the interaction state
  machine (incl. dismiss-while-processing → corner orb → response preview), chats-as-sessions,
  keyboard shortcuts, and how it maps to the `BrainBridge` port + the store. Agents building
  overlay components follow it.

## Contracts

- [proto/body.proto](../proto/body.proto) is the body↔brain seam (single source of truth).
- [modules/](modules/) holds one short contract doc per module (purpose, public contract,
  invariants, dependencies). Every module lands with its doc:
  - [brain-core.md](modules/brain-core.md) covers `cortex_core`: pure brain logic (routing,
    conversation + memory domains, ports, the turn engine, the memory recaller, fakes).
  - [brain-session.md](modules/brain-session.md) covers `cortex_session`: Redis adapters for the
    `SessionStore` and `TaskStore` (subagent tasks, ADR-0010) hot-state ports.
  - [brain-inference.md](modules/brain-inference.md) covers `cortex_inference`: llama.cpp
    adapter for the `InferenceBackend` port (OpenAI-compatible HTTP streaming).
  - [brain-embedding.md](modules/brain-embedding.md) covers `cortex_embedding`: llama.cpp CPU
    adapter for the `Embedder` port (OpenAI `/v1/embeddings`).
  - [brain-memory.md](modules/brain-memory.md) covers `cortex_memory`: pgvector adapter for the
    `MemoryStore` port (Postgres, cosine ranking).
  - [brain-tools.md](modules/brain-tools.md) covers `cortex_tools`: MCP-client adapter for the
    `ToolRegistry` port + the logging audit sink (ADR-0009).
  - [brain-email.md](modules/brain-email.md) covers `cortex_email`: standalone read-only IMAP MCP
    server over ProtonMail Bridge (ADR-0009).
  - [brain-model-manager.md](modules/brain-model-manager.md) covers `cortex_model_manager`: the
    model-host supervisor sidecar (one `llama-server` child per logical model) plus the
    `ModelHost` HTTP adapter the brain swaps with (ADR-0030).
  - [brain-seam.md](modules/brain-seam.md) covers `cortex_seam`: committed wire stubs + facade.
  - [brain-body-client.md](modules/brain-body-client.md) covers `cortex_body_client`: gRPC client
    adapter for the `BodyGateway` port (the brain calls the body's `BodyService`, ADR-0023).
  - [brain-orchestrator.md](modules/brain-orchestrator.md) covers `cortex_orchestrator`:
    the gRPC service hosting `BrainService`.
  - [body-core.md](modules/body-core.md) covers `body_core`: pure host types + ports
    (hotkey chord, `BrainTransport`, the `link` connection classification).
  - [body-rpc.md](modules/body-rpc.md) covers `body_rpc`: tonic adapter for `BrainTransport`.
  - [body-os.md](modules/body-os.md) covers `os_windows`/`os_linux`/`os_macos`: per-platform OS
    backends (the `Hotkey` seam; real Windows, cfg-gated stubs elsewhere).
  - [body-app.md](modules/body-app.md) covers `body/app`: the React overlay (gated 100%) + its
    host-native Tauri shell (`cortex-body`).
  - [repo-gates.md](modules/repo-gates.md) covers `scripts/`: linecap, dashcheck, crosscheck
    (with its `couplings` registry), bindcheck (with its `composemounts` reader), the
    coverage gate, the CI path classifier, and the commit-message CLI.

## Runbooks

- [runbooks/local-dev-wsl.md](runbooks/local-dev-wsl.md) covers the daily dev loop: brain
  natively or in Compose, env vars, the live seam check, Docker Desktop notes.
- [runbooks/llamacpp-gpu.md](runbooks/llamacpp-gpu.md) covers Slice 4 host half: bring up the
  GPU compose override, run the integration test, measure VRAM, lock the final picks.
- [runbooks/memory-pgvector.md](runbooks/memory-pgvector.md) covers Slice 5 host half: bring up
  Postgres+pgvector and the CPU embedder, run the memory/embedder integration tests.
- [runbooks/tools-mcp.md](runbooks/tools-mcp.md) covers Slice 6 host half: bring up the filesystem
  MCP sidecar (streamable-http, read-only mount), run the tools integration test.
- [runbooks/email-imap.md](runbooks/email-imap.md) covers Slice 6 host half (+ the Slice 8.8 send
  path): bring up the email MCP server against a live ProtonMail Bridge, run the email
  integration tests (read-only IMAP; the opt-in SMTP send round-trip).
- [runbooks/subagents-cpu.md](runbooks/subagents-cpu.md) covers Slice 7 host half: bring up the CPU
  subagent `llama-server`, validate delegation (integration test + cortex-driven full stack).
- [runbooks/scheduling.md](runbooks/scheduling.md) covers Slice 9.5: bring up durable schedules +
  the reminder ticker (`CORTEX_SCHEDULE_BACKEND=redis`), the agent-Docker validation runs
  (live contract + the end-to-end fire over the seam), the host-only half (native toast + the
  overlay reminder surface), and tuning/troubleshooting (lease vs long tasks, the
  dead-letter hash).
- [runbooks/body-volume.md](runbooks/body-volume.md) covers Slice 9 host half: the brain→body volume
  seam (`docker-compose.body.yml`) with the agent brain→body dial across the container boundary and
  the host-only Windows Core Audio validation ("set volume to 30%").
- [runbooks/vision.md](runbooks/vision.md) covers Slice 10: the three switches that must all be
  true before a capture can happen (`CORTEX_HOST_CAPTURE`, the overlay's own capture exclusion,
  and `CORTEX_VISION`), the agent-Docker half with the projector and the `/props` probe, the
  host-only Windows half including the one check nothing can stand in for (capture while the
  overlay is visible and confirm the assistant cannot see it), what the body can be pointed at
  now that a capture carries a target, what a capture does to the turn,
  and how to gate or disable it.
- [runbooks/body-overlay.md](runbooks/body-overlay.md) covers Slice 8: run the overlay in a browser
  (fake bridge) or as the real Tauri app on Windows (hotkey → overlay → live brain).
- [runbooks/model-swap.md](runbooks/model-swap.md) covers the brain handoff's manual-recovery
  half: what `ResidencyRestoreError` means with today's scripted model host, and the compose
  steps that put residency back. The live-swap procedure and its timings arrive with the real
  model host.
