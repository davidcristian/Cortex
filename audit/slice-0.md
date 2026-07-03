# Audit of Slice 0 (Governance)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Slice 0's deliverables are all present and traceable to a single founding commit (afda641, 2026-06-28) containing exactly the promised set and nothing else: AGENTS.md, CLAUDE.md (@AGENTS.md), the docs skeleton (ARCHITECTURE.md, index.md, adr/, modules/, runbooks/), ADR-0001 with the port/trait list (ARCHITECTURE.md:69-93) and the proto sketch (proto/body.proto with BrainService.Converse/Health + BodyService), the ROADMAP itself, and the Phase 0 assumptions & risks list (ROADMAP.md:601-632), with no feature code. The user-review stop is documented in ADR-0001's status line (approved 2026-06-28). The verdict is 'undocumented-gaps' only on the strict rubric: two low-severity stale-text findings in the Slice 0 artifact ARCHITECTURE.md. Its subagent-tier row still states the pre-ADR-0012 CPU-only design ('GPU budget is the cortex's', contradicting the shipped GPU-first VramBudgetPlacer), and its port tables omit the five ports added since Slice 6 while listing the not-yet-existing EventBus. Neither drift is recorded in the ROADMAP deferral ledger or an ADR. Every substantive Slice 0 claim is verified; the gaps are documentation drift caused by later slices, not missing Slice 0 work, and the current design is correctly stated in ADR-0012, index.md, and the Slice 8.5 text.

## Claims checked (10)

- **✅ verified.** AGENTS.md exists as the authoritative engineering-rules contract (hard rule, invariants, gates, commits, working agreement, repo map)
  - Evidence: /home/david/Files/Git/Cortex/AGENTS.md on disk (10289 bytes, all sections present); delivered in founding commit afda641 (2026-06-28, 105 lines) per `git show --stat afda641`

- **✅ verified.** CLAUDE.md exists and delegates to AGENTS.md
  - Evidence: /home/david/Files/Git/Cortex/CLAUDE.md:1 contains exactly `@AGENTS.md`; present in commit afda641

- **✅ verified.** Docs skeleton exists: ARCHITECTURE.md, index.md, adr/, modules/, runbooks/
  - Evidence: docs/ARCHITECTURE.md:1-124 (components, swap rule, data flow, seams), docs/index.md:1-127 (map/ADR/modules/runbooks index); afda641 added docs/modules/.gitkeep and docs/runbooks/.gitkeep, both dirs now populated (13 ADRs, 14 module docs, 7 runbooks per `ls docs/adr` and index.md:84-127)

- **✅ verified.** ADR-0001 (founding architecture) exists and is accepted
  - Evidence: docs/adr/ADR-0001-architecture.md:1-95. 8 decisions (external state as swap safety, hexagonal, gRPC seam/no FFI, engine behind InferenceBackend, Redis+Postgres/pgvector, gates, generated-code exemption, explicit orchestration) + 6 open questions; status at :3-4 'Accepted'

- **✅ verified**. Port/trait list is defined
  - Evidence: docs/ARCHITECTURE.md:69-93. Brain-side ports table (InferenceBackend, ModelManager, SessionStore, MemoryStore, Embedder, ToolRegistry, EventBus, Clock, BodyGateway) and host-side traits table (ScreenCapture, AudioControl, InputControl, Hotkey, BrainTransport); present in the founding commit (`git show afda641:docs/ARCHITECTURE.md` line 67)

- **✅ verified**. Proto sketch exists (body↔brain seam)
  - Evidence: proto/body.proto delivered as a 101-line sketch in afda641 with `service BrainService` (Converse stream + Health) and `service BodyService` (CaptureScreen/GetVolume/SetVolume/InjectInput); current file proto/body.proto:1-103 is the Slice-2-stabilized v0 of that sketch; referenced from ADR-0001:35

- **✅ verified**. The plan itself (ROADMAP with ordered vertical slices and status markers) exists
  - Evidence: docs/ROADMAP.md:1-19 (slice ordering rationale, status-marker convention); Slice 0 section at docs/ROADMAP.md:14-20 marked 'Status: done'; 632 lines covering Slices 0-11 + Ship

- **✅ verified.** Assumptions & risks list at the bottom of the ROADMAP
  - Evidence: docs/ROADMAP.md:601-632. 'Assumptions & risks to confirm (Phase 0)' with 7 numbered items (VRAM fit, swap latency, brain→body connectivity, Tauri coverage, security model, email safety, default hotkey), each updated with later measurements (e.g. item 1 cites the ADR-0004 addendum and ADR-0012)

- **✅ verified**. No feature code delivered in this slice
  - Evidence: `git show --stat afda641` lists exactly 9 files: AGENTS.md, CLAUDE.md, docs/{ARCHITECTURE,ROADMAP,index}.md, docs/adr/ADR-0001-architecture.md, docs/{modules,runbooks}/.gitkeep, proto/body.proto; no .py/.rs/build files. Prior commit 3d116f9 held only LICENSE

- **📄 verified-as-documented (host-only run; paper trail checked)**. Slice stops for maintainer review
  - Evidence: docs/adr/ADR-0001-architecture.md:3 records 'Accepted (Phase 0 reviewed and approved by the user, 2026-06-28)'. The paper trail of the review stop; cannot be re-executed

## Gaps (2)

### G1 · severity low · **not documented as a deferral**

Stale text: the model-tier table in docs/ARCHITECTURE.md:41 still describes subagents as a 'dynamic pool on CPU' with 'CPU RAM + concurrency; GPU budget is the cortex's'. This was superseded by Slice 8.5/ADR-0012 (done 2026-07-01): subagents are GPU-first with CPU overflow under a shared VRAM budget (ADR-0012 decision 1; brain/packages/core/src/cortex_core/placer.py:19 'GPU-first fit-test against the VRAM soft cap, CPU overflow'). git log shows ARCHITECTURE.md was last touched 2026-06-29 (c882510), before ADR-0012 landed. Partially softened by the fact that the runtime GPU sidecar is itself deferred to Slice 11, so subagents do still execute on CPU today. Yet 'GPU budget is the cortex's' contradicts the shipped VramBudgetPlacer policy.

**Adversarial re-check: confirmed.** The auditor is correct on every point and I found no written record that refutes them. (1) The stale text exists exactly as quoted: docs/ARCHITECTURE.md:41 still describes subagents as a 'dynamic pool on **CPU**' with 'CPU RAM + concurrency; GPU budget is the cortex's'. (2) It is genuinely superseded: ADR-0012 decision 1 and the ADR-0010 2026-07-01 addendum make subagents GPU-first with CPU overflow under the shared VRAM soft cap, and the shipped VramBudgetPlacer (placer.py) implements exactly that. Subagent VRAM headroom is carved out of the cap, directly contradicting 'GPU budget is the cortex's'. (3) The timeline holds: ARCHITECTURE.md was last touched 2026-06-29 (c882510); the ADR-0012 commits (ea82801, 42fb330, both 2026-07-01) updated ROADMAP, index.md, and two module docs but not ARCHITECTURE.md. (4) No deferral is recorded anywhere that counts: the ROADMAP 'Deferred refinements & later work' ADR-0012 block lists five deferrals, none an ARCHITECTURE.md/tier-table update; ADR-0012 itself never mentions ARCHITECTURE.md (its Consequences increment 4 says 'Docs + ROADMAP' as slice work (which was done for index.md and modules docs but missed ARCHITECTURE.md), and its explicit 'Deferred to Slice 11' and 'Deferred to the host half' lists contain nothing about the architecture doc). The auditor's own softening also checks out (the real GPU sidecar runtime is deferred to Slice 11 per ROADMAP:552-555, so subagents execute on CPU today), but the shipped placement policy still contradicts the table's VRAM column, and that staleness is undocumented. Gap stands: documented=false.

### G2 · severity low · **not documented as a deferral**

Stale text: the 'Ports and traits' tables in docs/ARCHITECTURE.md:69-93 have drifted from the code. They omit five ports added by Slices 6-8.5 and present in brain/packages/core/src/cortex_core/ports.py:21-171 (ToolAuditSink, Confirmer, TaskStore, SubagentPlacer, SubagentScheduler), while still listing EventBus, which has no Protocol anywhere in cortex_core yet (BodyGateway is also code-absent but its Slice 9 is still planned, so that entry is forward-looking rather than stale). The current port inventory is instead findable via docs/index.md and docs/modules/, so the impact is limited.

**Adversarial re-check: confirmed.** The auditor holds on every point. (1) The drift is real: ports.py defines twelve Protocols including SubagentPlacer, ToolAuditSink, Confirmer, TaskStore, and SubagentScheduler (added by Slices 6-8.5 per their docstrings citing ADR-0009/0010/0012/0013), and none of the five appears in the ARCHITECTURE.md brain-side port table. (2) EventBus is listed in the table at ARCHITECTURE.md:81 but a repo-wide grep finds no EventBus Protocol (or any 'EventBus' identifier) anywhere in the brain Python tree. Its only occurrences are in ARCHITECTURE.md itself (lines 17, 30, 81). It is not even mentioned in ADR-0001, so unlike BodyGateway (planned Slice 9) there is no written forward-looking anchor for it. (3) The deferral is undocumented: the ROADMAP's 'Deferred refinements & later work' ledger (docs/ROADMAP.md:451-565) covers seam retries, session windowing, tool aggregation, ADR-0013 items, memory scoping, model-manager lifecycle, and resource-governance items, none about refreshing the ARCHITECTURE.md port tables; the origin ADRs of the five missing ports (0009, 0010, 0012, 0013) never reference ARCHITECTURE.md at all, and no ADR or addendum records the table as intentionally frozen. Git history confirms ARCHITECTURE.md was last edited before those slices landed. The mitigating note also checks out: docs/index.md:7 points to ARCHITECTURE.md but the current port inventory is discoverable via docs/modules/, so impact is limited, yet the gap itself is real and unrecorded.
