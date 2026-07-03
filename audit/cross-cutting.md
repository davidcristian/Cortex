# Audit of cross-cutting checks

**Audited:** 2026-07-02 · Three repo-wide dimensions beyond any single slice.

## Deferral-ledger consistency (AGENTS.md gate 4, both directions)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps
### Summary

The deferral ledger is in strong shape in the forward direction: 25 of the 27 ledger entries checked are recorded verbatim at their cited origin ADRs (ADR-0004, 0007, 0008, 0009, 0012, 0013 all carry explicit deferral text, several in dedicated 'Deferred' sections or addenda), and the one 'done' entry (agent GPU framing validation) has a complete paper trail (dated ADR-0013 addendum, runbook, integration-marked harness). Two forward-direction failures exist: the transport retry/reconnect entry cites ADR-0003 which never mentions it (the record lives only in the body-rpc module doc), and the Slice-3 history-windowing entry has no ADR-side record because Slice 3 has no ADR. In the reverse direction, four consciously-deferred ADR items never reached the ledger: ADR-0011's long-lived-bidi/Cancel-event refinement, ADR-0010's subagent progress-reporting and richer spawn-schema refinements, and ADR-0012's hard-budget-wall refinement, plus the not-yet-run brain-tier injection probe noted in ADR-0013/0004. On design docs, overlay-ux.md §5's deferred multi-chat features are properly delivered by planned Slice 8.7, and §4's deferred overlay polish is pointed at from the ROADMAP's Slice 8 progress text and the body-overlay runbook. Yet the polish items appear in neither the canonical ledger section nor ADR-0011, and the ledger contains no body/overlay section at all, which is the systemic root of most reverse-direction misses. One resolved deferral (ADR-0010's hard RAM-ceiling rejection, delivered by ADR-0012) is correctly absent, and a minor staleness exists where ADR-0010's addendum still calls the cortex-driven GPU path pending although ROADMAP Slice 7 records it closed 2026-07-01.

### Claims checked (33)

- **❌ not found** (Ledger 'Transport retry / reconnect policy' (Slice 2) deferral is recorded at its cited origin ADR-0003)
  - Evidence: docs/adr/ADR-0003-seam-codegen.md read in full (55 lines). No mention of retries, reconnect, or backoff; the deferral is recorded only in docs/modules/body-rpc.md:6 ('no retries (retry policy is a later slice)') and the ledger itself (docs/ROADMAP.md:458-461)
  - Adversarial re-check: confirmed. The auditor is correct and cannot be refuted. The ROADMAP deferral ledger explicitly names ADR-0003 as the origin ADR for the 'Transport retry / reconnect policy' deferral (docs/ROADMAP.md:457-461), and the ledger's own contract (lines 453-454) requires each deferral to be recorded at its origin ADR. ADR-0003 contains no mention of retries, reconnection, or backoff in its decisions, conseque

- **❌ not found** (Ledger 'Session-history windowing / truncation / summarization' (Slice 3) deferral is recorded at an origin ADR)
  - Evidence: No Slice-3 ADR exists (ADRs 0001-0003 cover governance/gates/seam; grep of docs/adr/*.md for window/truncat/summariz finds only ADR-0008 memory summarization); documented only in the ledger (docs/ROADMAP.md:464-469) and factually in docs/modules/brain-core.md:166 ('runs the inference↔tool loop over the FULL history')
  - Adversarial re-check: confirmed. The auditor is correct and cannot be refuted. There is no Slice-3 origin ADR (ADRs 0001-0003 cover architecture/gates/seam; the ROADMAP Slice 3 section cites none), and an exhaustive grep of all ADRs including addenda, plus docs/design, docs/modules, and docs/runbooks, finds no record of the session-history windowing/truncation/summarization deferral anywhere except the ROADMAP ledger itself. The 

- **✅ verified.** Ledger 'Multi-server tool aggregation' is recorded at ADR-0009's multi-server aggregation addendum
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:181-191 (dedicated addendum, explicitly 'Tracked in the ROADMAP deferred-refinements list')

- **✅ verified.** Ledger 'Advertised-tool filtering' is recorded at ADR-0009's increment-3 addendum
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:137-142 ('a noted refinement, behind the unchanged port; the mount makes it a UX nicety')

- **✅ verified.** Ledger 'Readable-text-from-HTML extraction' is recorded at ADR-0009's increment-4 addendum
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:163-166 ('A readable-text-from-HTML extraction is a noted refinement')

- **✅ verified.** Ledger 'Salience / rate policy on the tool loop' is recorded at ADR-0009 decision 3 / risks
  - Evidence: docs/adr/ADR-0009-tools-mcp.md:121-122 ('Salience/rate policy is a later refinement behind the port')

- **✅ verified**. Ledger 'The real overlay confirmation adapter' is recorded at ADR-0013
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:140-143 and 229-232 (Deferred section: ships with the first gated tool, Slice 9/10)

- **📄 verified-as-documented (host-only run; paper trail checked)**. Ledger 'Agent GPU validation of framing efficacy (done 2026-07-01)' has its recorded addendum, runbook, and integration-marked harness
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:244-271 (dated addendum with results); docs/runbooks/llamacpp-gpu.md documents the re-run; brain/packages/inference/tests/test_injection_defense_live.py exists with @pytest.mark.integration at line 294 (the GPU run itself is host-only, so verified via paper trail)

- **✅ verified**. Ledger 'The screening subagent' deferral is recorded at ADR-0013
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:156-166 (decision 6 'deferred, not built'), 233-234, and 307-308 (addendum: mostly moot, another equally-injectable model)

- **✅ verified.** Ledger 'Model-independent output guardrail for the small tier' is recorded at ADR-0013's hardening addendum
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:337-340 ('a possible future guardrail, deferred; the deterministic layers cover the concrete risk today')

- **✅ verified.** Ledger 'Reconsider the subagent model pick' is recorded at both ADR-0013 and ADR-0004
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:334-336 and 380-382; docs/adr/ADR-0004-model-lineup.md:176-202 (injection-robustness addendum: gemma-4-E4B standout, Qwen-2B pick stands, Slice 8.6 makes it per-task)

- **✅ verified**. Ledger 'Slice 9-10 requirement: subagents never handed a gated/outbound tool' is recorded at ADR-0013
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:383-386 ('Requirement for Slices 9-10: ... the wiring MUST keep it out of the subagent tool set')

- **✅ verified.** Ledger 'Context-preserving tainted-memory recording' is recorded at ADR-0013
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:153-154 (decision 5: 'a deferred refinement') and 235-236 (Deferred section)

- **✅ verified.** Ledger 'Per-remote-tool trust / gating overrides' is recorded at ADR-0013
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:57-58 and 237-238

- **✅ verified.** Ledger 'Persisting taint / provenance across a mid-turn swap' (incl. structured provenance) is recorded at ADR-0013, with the Slice-11 tool-step schema hook in ADR-0009
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:239-242; docs/adr/ADR-0009-tools-mcp.md:52-53 ('Persisting the tool steps for mid-swap rehydration lands with the swap slice (Slice 11)')

- **✅ verified.** Ledger 'Per-session / namespaced memory scoping' is recorded at ADR-0008 decision 3
  - Evidence: docs/adr/ADR-0008-memory-v1.md:41-42 ('Per-session or namespaced scoping is a later refinement behind the same port')

- **✅ verified**. Ledger 'Tiered / self-editing memory + summarization' is recorded at ADR-0008 decision 1
  - Evidence: docs/adr/ADR-0008-memory-v1.md:24-26 ('Its good ideas (tiered/self-editing memory, summarization) can be adopted later behind the unchanged port')

- **✅ verified.** Ledger 'ANN index' deferral is recorded at ADR-0004
  - Evidence: docs/adr/ADR-0004-model-lineup.md:140-141 ('an ANN index would [need a migration]; deferred'); also docs/adr/ADR-0008-memory-v1.md:95-96 (index tuning risk)

- **✅ verified**. Ledger 'cortex_model_manager process lifecycle, co-residency, real swap' is recorded at ADR-0007 consequences
  - Evidence: docs/adr/ADR-0007-model-manager-inference.md:52-54 and 83-84 ('deferred to Slice 11, when process lifecycle gives it real I/O to adapt'); reiterated docs/adr/ADR-0012-resource-governance.md:176

- **✅ verified.** Ledger 'MTP model variants' deferral is recorded at ADR-0004
  - Evidence: docs/adr/ADR-0004-model-lineup.md:25-26 ('MTP ... are deferred. They use more memory; revisit only if latency demands it')

- **✅ verified**. Ledger 'cortex gemma-4-12B is a reasoning model' finding is recorded at the ADR-0013 addendum
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:267-271 ('Recorded as a deferred inference-path refinement (ROADMAP), owned by ADR-0007/ADR-0004')

- **✅ verified**. Ledger 'SubagentScheduler.drain() for a swap' is recorded at ADR-0012
  - Evidence: docs/adr/ADR-0012-resource-governance.md:168-171 ('Deferred to Slice 11 ... drain() quiesces the pool for a swap')

- **✅ verified.** Ledger 'CUDA-OOM → re-place on CPU' is recorded at ADR-0012
  - Evidence: docs/adr/ADR-0012-resource-governance.md:172-175 ('a Slice-11/host refinement')

- **✅ verified**. Ledger 'The real GPU-placed runtime mechanism' is recorded at ADR-0012
  - Evidence: docs/adr/ADR-0012-resource-governance.md:180-183 ('Deferred to the host half'); reconciled with the ledger's 'lands with Slice 11' by docs/ROADMAP.md:290-295 and 352-356

- **✅ verified.** Ledger 'Placement-aware CPU charging' is recorded at ADR-0012
  - Evidence: docs/adr/ADR-0012-resource-governance.md:117-119 ('Placement-aware charging is a later refinement behind the unchanged admit(request)') and 177

- **✅ verified**. Ledger 'The Intel NPU as a third placement target' is recorded at ADR-0012 and detailed in the ROADMAP Slice 8.5 section
  - Evidence: docs/adr/ADR-0012-resource-governance.md:177-178; docs/ROADMAP.md:343-350 (feasibility-pass unknowns)

- **✅ verified**. Ledger cross-cutting 'email-write tool' rides the ADR-0013 capability gate as stated
  - Evidence: docs/adr/ADR-0013-untrusted-content.md:229-232 ('Subsumes ADR-0009's deferred email-write-confirmation and Phase-0 assumption 6'); docs/adr/ADR-0009-tools-mcp.md:172-179

- **✅ verified.** ADR-0010's deferred 'hard RAM-ceiling rejection' was subsequently delivered, so its absence from the ledger is correct
  - Evidence: docs/adr/ADR-0010-subagents.md:72-73 (the noted refinement); docs/adr/ADR-0012-resource-governance.md:97 ('This delivers ADR-0010 dec 6's deferred hard RAM-ceiling rejection')

- **✅ verified.** ADR-0011's 'images deferred to Slice 10' is tracked by the ROADMAP's planned Slice 10
  - Evidence: docs/adr/ADR-0011-body-v1.md:38-39; docs/ROADMAP.md:437-440 (Slice 10 on Vision)

- **✅ verified**. overlay-ux.md §5's deferred multi-chat features are pointed at by the ROADMAP via planned Slice 8.7
  - Evidence: docs/design/overlay-ux.md:152-159; docs/ROADMAP.md:388-401 ('Delivers the overlay's deferred multi-chat features (design/overlay-ux.md §5)')

- **◐ partial.** overlay-ux.md §4's deferred overlay polish is pointed at by the ROADMAP Slice 8 text and mirrored in the runbook, but appears in neither the ledger section nor ADR-0011
  - Evidence: docs/design/overlay-ux.md:129-137; docs/runbooks/body-overlay.md:76-80 (incl. the tighter-CSP item); docs/ROADMAP.md:284-286 (Slice 8 progress pointer); absent from docs/ROADMAP.md:451-565 (the ledger) and from docs/adr/ADR-0011-body-v1.md
  - Adversarial re-check: confirmed. The auditor is correct and the claim stands. The deferred overlay polish (transparent window + click-through margins, OS-window morph to a true screen corner, hide-on-blur, tighter CSP) is genuinely documented, but only in the design doc (overlay-ux.md §4), the runbook (body-overlay.md Notes, which alone carries the CSP item), and the Slice 8 Progress paragraph of the ROADMAP, which points at tho

- **✅ verified**. No deferral language exists in ADR-0001/0002/0005/0006 beyond ADR-0001's open questions, which the ROADMAP explicitly points at
  - Evidence: grep of docs/adr/ADR-0002/0005/0006 for defer/later/punt/revisit/refinement finds nothing actionable; docs/adr/ADR-0001-architecture.md:74-94 (open questions); docs/ROADMAP.md:602-603 ('Deferred decisions live in ADR-0001's open questions')

- **✅ verified**. No runbook other than body-overlay.md carries deferred items
  - Evidence: grep of docs/runbooks/{llamacpp-gpu,subagents-cpu,memory-pgvector,tools-mcp,email-imap,local-dev-wsl}.md for defer/later/revisit/TODO returns no matches

### Gaps (8)

#### G1 · severity medium · **not documented as a deferral**

Direction (a): the ledger's 'Transport retry / reconnect policy' entry sits under a header citing ADR-0003 as its origin, but ADR-0003 (read in full) never mentions retries, reconnection, or backoff. The ADR-side record required by AGENTS.md gate 4 is missing; the only records are the ledger entry itself and docs/modules/body-rpc.md:6.

**Adversarial re-check: reclassified.** Refuted as an 'undocumented deferral': the deferral IS documented, in exactly the place the verification standard accepts. The ROADMAP ledger entry (docs/ROADMAP.md:457-461) fully records the conscious deferral (the no-retries current state, the planned backoff/reconnect refinement behind the unchanged BrainTransport port, and the interim failed-turn-is-terminal behavior), and docs/modules/body-rpc.md:6 records it a second time. Since ANY written record in the ROADMAP ledger or the origin ADR counts as documented, and the auditor's own evidence cites the ledger entry, the 'not recorded as a deferral anywhere' classification is wrong. However, the auditor's underlying factual observation is confirmed correct: ADR-0003 (read in full, no addendum, plus alternate-phrasing greps across every ADR) contains no retry/reconnect/backoff record, so AGENTS.md gate 4's parenthetical '(and at its origin ADR)' is unmet and the ledger preamble (ROADMAP.md:453-454, 'recorded at its origin ADR') over-claims for this one entry. The correct residual finding is a minor doc-consistency defect (add a one-line noted-refinement addendum to ADR-0003 or correct the ledger header/preamble), not an undocumented gap. No decision has been lost.

#### G2 · severity medium · **not documented as a deferral**

Direction (b): ADR-0011's consciously deferred 'multi-turn-within-one-stream + explicit proto Cancel event' refinement ('a later refinement behind the same port', drop-to-cancel covers v1) is missing from the ROADMAP's Deferred refinements ledger. The ledger has no Slice-8/body section at all; the Slice 8 design paragraph states 'cancel = drop the stream' as design, not as a recorded deferral.

**Adversarial re-check: reclassified.** The deferral IS documented at its origin ADR, in explicit deferral language, in the very lines the auditor cited. ADR-0011 decision 1 (lines 36-37) says the design "defers both multi-turn-within-one-stream and the explicit proto `Cancel` event", and the Risks section (lines 134-137) records it a second time as "a later refinement behind the same port (drop-to-cancel covers v1)" with the concrete trigger conditions for picking it up (a turn must be interrupted or client events must interleave). Under the audit rule that ANY written record in the ROADMAP ledger OR the origin ADR counts as documented, this cannot be classified as an undocumented gap ("not recorded as a deferral anywhere"). The auditor's own evidence lines are the record. What survives of the auditor's observation is narrower and accurate: the ROADMAP's "Deferred refinements & later work" ledger (lines 451-565) genuinely has no Slice-8/body section and no entry for this item, and the ledger's own preamble (line 454: "recorded at its origin ADR and collected here so none is lost") plus AGENTS.md gate 4 expect the item in both places, so a ledger-sync omission exists as a documentation-consistency nit. But that is a mis-filed ledger entry for an already-recorded deferral, not a lost/undocumented decision, which is the condition the deferral-ledger audit was testing for. (Note also that the ROADMAP Slice 8 section does track its other conscious deferral ("Deferred overlay polish", lines 284-286), pointing at overlay-ux.md §4, showing Slice 8 deferrals were not systematically dropped.)

#### G3 · severity medium · **not documented as a deferral**

Direction (b): ADR-0010's deferred 'subagent progress reported to the overlay via the Converse status stream (a later refinement); v1 delegation is synchronous within the cortex turn' is missing from the ROADMAP ledger and is not covered by any planned slice text (Slices 8.6/8.7/9.5 do not mention it).

**Adversarial re-check: reclassified.** The auditor mislabeled this as an UNDOCUMENTED deferral. The audit standard states that ANY written record in the ROADMAP ledger OR the origin ADR counts as documented. The origin ADR (ADR-0010, Risks section, lines 121-122) explicitly records the deferral: it tags overlay progress reporting via the Converse status stream as "(a later refinement)" and scopes v1 delegation as synchronous within the cortex turn, a conscious, written-down deferral decision at its origin ADR. The auditor's own cited evidence (ADR-0010:120-122) is itself that record, contradicting the claim that it is "not recorded as a deferral anywhere". The narrower half of the auditor's observation is accurate: I read the entire ROADMAP 'Deferred refinements & later work' section (lines 451-565) and confirmed there is no collected entry for subagent progress reporting, and no planned slice text (7, 8.5, 8.6, 8.7, 9.5) mentions it. The only ROADMAP mention of the Converse status stream (line 618-619) concerns swap-latency reporting. So the ROADMAP-ledger collection is a genuine housekeeping omission under AGENTS.md gate 4 (which requires recording in BOTH places), but per the given documented=true criterion the deferral IS documented, so the finding as reported ("undocumented gap") is refuted.

#### G4 · severity low · **not documented as a deferral**

Direction (b): ADR-0010 increment-2 addendum's deferred richer spawn_subagents schema ('a richer object schema ({instruction, context}[]) is a later refinement behind the same tool'; SubagentTask.context stays "") is missing from the ROADMAP ledger; planned Slice 8.6 grows the spawn schema for per-instruction model choice but does not record the context-field refinement.

**Adversarial re-check: reclassified.** Refuted under the stated documentation standard ('ANY written record in the ROADMAP ledger OR the origin ADR counts as documented'). The deferral IS explicitly written down at its origin ADR: the ADR-0010 increment-2 addendum (docs/adr/ADR-0010-subagents.md:140-142) states that v1 folds per-subtask context into the instruction string, that SubagentTask.context stays "" from the tool, and that the richer {instruction, context}[] object schema 'is a later refinement behind the same tool'. That is a dated, explicit deferral record, so the classification 'UNDOCUMENTED gap (not recorded as a deferral anywhere)' is wrong; the auditor's own evidence cites the record that documents it. Caveat for the parent auditor: the auditor's narrower factual sub-claims are accurate. I confirmed the ROADMAP 'Deferred refinements & later work' section (docs/ROADMAP.md:451-565) has no ADR-0010/Slice-7 block and no mention of this refinement under any wording (searched 'richer', 'object schema', '{instruction', 'context', 'spawn' across docs/, modules/, runbooks/, design/), and planned Slice 8.6 (ROADMAP.md:358-386) grows the spawn schema for per-instruction model choice without recording the context-field refinement (line 373's 'SubagentTask already carries what a subagent needs' is the closest, non-equivalent text). So if the applicable bar is AGENTS.md gate 4's both-places requirement (ROADMAP ledger AND origin ADR), a real ledger-completeness omission exists; but as reported ('undocumented / not recorded anywhere'), the finding is refuted because the origin-ADR record exists.

#### G5 · severity low · **not documented as a deferral**

Direction (c): Slice 8's consciously deferred overlay polish (transparent window + click-through margins done together, OS-window morph to a real screen corner, hide-on-blur, tighter CSP) is recorded in overlay-ux.md §4 and the body-overlay runbook and pointed at from the ROADMAP Slice 8 progress paragraph. Yet it is absent from the canonical 'Deferred refinements & later work' ledger section and from origin ADR-0011, so per the strict two-location DoD both canonical sides are missing (mitigated by the in-ROADMAP pointer). The design doc's smaller 'later' marks (custom theme token sets, licensed @font-face, Ctrl+K palette) are likewise ledger-absent.

**Adversarial re-check: confirmed.** Cannot refute. The deferred overlay polish (transparent window + click-through margins, OS-window morph to a real screen corner, hide-on-blur, tighter CSP) is genuinely recorded only in overlay-ux.md §4, the body-overlay runbook, and the ROADMAP Slice 8 progress paragraph that points at those two. It is absent from both canonical locations the DoD requires: the ROADMAP 'Deferred refinements & later work' ledger (which has per-slice blocks for 2, 3, 4, 5, 6, 6.5, 8.5 and cross-cutting, but none for Slice 8) and the origin ADR-0011 (whose single addendum concerns frontend gating; its only deferral language covers Slice-10 images and the bidi-stream/Cancel refinement, not the polish items). Exhaustive greps across docs/ (adr, modules, runbooks, design, ROADMAP) for every polish term and the smaller design 'later' marks (custom theme token set, licensed @font-face, Ctrl+K command palette) found no other written record. Those smaller marks exist solely inside overlay-ux.md. The auditor's characterization, including the mitigating in-ROADMAP pointer at :284-286, is accurate.

#### G6 · severity low · **not documented as a deferral**

Direction (b): ADR-0012's accepted-tradeoff note that 'a hard wall remains a refinement behind the same port' (the soft CPU/RAM budget bounds only admitted subagents) is a recorded refinement missing from the ROADMAP ledger's Slice-8.5 section, which lists the other five ADR-0012 deferrals.

**Adversarial re-check: reclassified.** The auditor's classification of this item as an UNDOCUMENTED gap ("not recorded as a deferral anywhere") is refuted by the auditor's own evidence. The hard-wall refinement IS recorded as a conscious deferral at its origin ADR: docs/adr/ADR-0012-resource-governance.md:196-199 explicitly says "Deliberate tradeoff; a hard wall remains a refinement behind the same port." Under the audit's documented-standard (ANY written record in the ROADMAP ledger OR the origin ADR counts as documented), this deferral is documented=true. The factual sub-claim that the ROADMAP's Slice-8.5 ledger section (docs/ROADMAP.md:545-559) omits it while listing the other five ADR-0012 deferrals is correct (I verified no "hard wall" phrasing exists anywhere in ROADMAP.md, docs/modules/, docs/runbooks/, or docs/design/), and the ledger preamble (ROADMAP.md:453-454) does promise deferrals are both recorded at the origin ADR and collected in the ledger, so a minor ledger-completeness inconsistency exists (a missing sixth bullet). But that is a lesser bookkeeping nit, not an undocumented deferral: the decision is written down at the origin ADR, and the underlying no-hard-wall constraint is additionally recorded in the ROADMAP Slice-8.5 body (lines 333-336) and in the port/scheduler docstrings.

#### G7 · severity low · **not documented as a deferral**

Direction (b): the injection-defense harness has not been run against the ~31B brain tier ('opt-in via CORTEX_PROBE_BRAIN=1, not yet run', stated in both ADR-0013 and ADR-0004); this pending measurement is missing from the ROADMAP ledger and from the Slice 11 text where the brain pick lands.

**Adversarial re-check: reclassified.** The deferral IS documented at the origin ADR, which under the audit standard ('ANY written record in the ROADMAP ledger or the origin ADR counts as documented') makes the UNDOCUMENTED classification wrong. Both origin ADRs record it deliberately and in nearly identical words: ADR-0013's harness addendum states the ~31B brain tier is 'opt-in via CORTEX_PROBE_BRAIN=1, not yet run' (lines 354-356) and ADR-0004's injection-robustness addendum states 'the brain tier is opt-in and not yet run' (line 182). This is a conscious scoping decision, not an oversight: the harness ships an explicit opt-in mechanism for the deferred run (test file lines 76-96, including a comment explaining the VRAM cost), and both ADRs carry the standing re-run trigger 'Re-run the harness when picks or the preamble change' (ADR-0013:352, ADR-0004:202). The brain pick landing (Slice 11, per runbook llamacpp-gpu.md:145-147) is precisely such a pick change. The auditor self-refutes: the very lines cited as evidence (ADR-0013:355-356, ADR-0004:182) are the written deferral record. Caveat for the parent: the auditor's narrower factual observations are correct. The pending brain-tier run is absent from the ROADMAP 'Deferred refinements & later work' ledger (451-565), from the Slice 11 text (442-449), and from ADR-0013's own Deferred section (228-242). AGENTS.md gate 4 nominally wants ledger AND origin-ADR recording, so a ROADMAP ledger line would still be a fair hygiene improvement, but the item as classified ('not recorded as a deferral anywhere') is refuted.

#### G8 · severity low · **not documented as a deferral**

Direction (a): the ledger's Slice-3 'Session-history windowing / truncation / summarization' entry has no origin-ADR record anywhere. Slice 3 shipped without an ADR, so the ledger entry (plus the brain-core.md full-history statement) is the sole record; the ledger header honestly cites no ADR, but the DoD's 'and at its origin ADR' half is structurally unmet.

**Adversarial re-check: reclassified.** The auditor's classification of this item as an UNDOCUMENTED gap ("not recorded as a deferral anywhere") is refuted: the deferral IS recorded, in full, in the ROADMAP's canonical "Deferred refinements & later work" ledger at docs/ROADMAP.md:463-469, with the deferred behavior also documented in docs/modules/brain-core.md:166. Under the operative standard (ANY written record in the ROADMAP ledger OR the origin ADR counts as documented), this deferral is documented. The git record (commit e221a60, "docs: collect two uncollected Slice 2 & 3 deferrals") further shows it was a consciously collected deferral, not a lost decision. The auditor's factual sub-observations are accurate and I confirmed them: Slice 3 shipped without any ADR (no ADR in docs/adr/ or docs/index.md covers Slice 3's cortex-chat/session work), the ledger section header at ROADMAP.md:463 cites no ADR (unlike the Slice-2 header at line 457 citing ADR-0003 and the Slice-6 header at line 471 citing ADR-0009), and no ADR anywhere mentions session-history windowing/truncation/summarization (ADR-0008:93's summarization note concerns cross-session memory, which the ledger entry itself explicitly distinguishes). But that makes the "and at its origin ADR" half inapplicable rather than unmet-as-undocumented: there is no origin ADR to record it at, and the one canonical place the DoD designates as "the one place none is lost" (the ROADMAP ledger) contains the record. The absence of a Slice-3 ADR is a separate (arguably valid) process observation about the "design doc/ADR per slice" DoD step, not an undocumented deferral; the deferral itself does not belong on an undocumented-gaps list.


## Module contract-doc coverage (AGENTS.md gate 4)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps
### Summary

The module-contract-doc gate is in strong shape: all 16 real modules (9 brain packages, 5 body crates with the three os_* crates deliberately sharing one doc, body/app, and scripts/) map 1:1 onto the 14 docs in docs/modules/, every doc carries the four required sections, and there are no orphan docs describing nonexistent modules. Spot-checking each doc against the code's actual exports (package __init__.py / crate lib.rs / TS bridge types / script CLIs) found the docs remarkably accurate. Env var names, function signatures (e.g. build_subagents), coverage exclusions, and the ResourceBudgetScheduler-replaces-ConcurrencyScheduler history all match the code. docs/index.md lists every module doc, every ADR through 0013, and every runbook. Two low-severity undocumented nits remain: brain-orchestrator.md omits the exported MemoryConfig/ToolsConfig/SubagentsConfig classes and their env contracts despite claiming __all__ is the API, and the index's ADR-0010 blurb still uses the pre-addendum singular tool name spawn_subagent. Neither omission is recorded as a deferral, hence the undocumented-gaps verdict, though both are cosmetic rather than substantive.

### Claims checked (10)

- **✅ verified.** Every real module has a contract doc in docs/modules/: 9 brain packages (core, seam, orchestrator, session, inference, embedding, memory, tools, email), 5 body crates (core, rpc, os_windows/os_linux/os_macos covered jointly by body-os.md), body/app, and scripts/
  - Evidence: ls of /home/david/Files/Git/Cortex/brain/packages, body/crates, body/app, scripts vs docs/modules/ (14 files: brain-core.md, brain-seam.md, brain-orchestrator.md, brain-session.md, brain-inference.md, brain-embedding.md, brain-memory.md, brain-tools.md, brain-email.md, body-core.md, body-rpc.md, body-os.md, body-app.md, repo-gates.md). 1:1 mapping with body-os.md covering the three os_* crates (body-os.md:9-20) and repo-gates.md covering scripts/ (repo-gates.md:1-9). No orphan docs: every doc describes an existing module; planned modules (model_manager, body_client, shared) correctly have no doc yet.

- **✅ verified.** Each of the 14 docs contains the four required sections: purpose, public contract, invariants, dependencies
  - Evidence: All 14 docs read in full; each has **Purpose**, **Public contract**, **Invariants**, **Dependencies** headings (e.g. brain-core.md:3/9/284/299, body-os.md:3/18/32/37, repo-gates.md:3/7/39/48).

- **✅ verified**. brain-core.md's documented public contract matches cortex_core's actual exports, including ResourceBudgetScheduler having replaced ConcurrencyScheduler
  - Evidence: brain/packages/core/src/cortex_core/__init__.py:72-147 (__all__) matches brain-core.md item-for-item; ResourceBudgetScheduler at __init__.py:52,107 and documented at brain-core.md:277-281 with an accurate historical note that it 'Replaces Slice 7's ConcurrencyScheduler'; grep confirms no ConcurrencyScheduler remains in brain/ code. stream_tool_loop/ToolLoopContext/MAX_TOOL_STEPS are documented as living in the tool_loop submodule (brain-core.md:188-195), confirmed at cortex_core/tool_loop.py:30,34,66.

- **✅ verified**. brain-seam.md's listed message classes, servicers/stubs, and add_* helpers match the cortex_seam facade exactly
  - Evidence: brain/packages/seam/src/cortex_seam/__init__.py:60-88 (__all__: 20 message classes + 4 servicer/stub classes + 2 add_* helpers) matches brain-seam.md:9-24 name-for-name, including the retyped add_* Callable annotations (__init__.py:53-58 vs doc:20-24).

- **✅ verified**. brain-session.md, brain-inference.md, brain-memory.md, brain-embedding.md, brain-tools.md, and brain-email.md accurately describe their packages' exports
  - Evidence: cortex_session/__init__.py:6 (DEFAULT_REDIS_URL, RedisSessionStore, RedisTaskStore) = brain-session.md:10-28; cortex_inference/__init__.py:5 (LlamaCppBackend) = brain-inference.md:12; cortex_memory/__init__.py:5 (Database, PgVectorMemoryStore) = brain-memory.md:11-21; cortex_embedding/__init__.py:5 (LlamaCppEmbedder) = brain-embedding.md:13; cortex_tools/__init__.py:6 (LoggingAuditSink, McpSession, McpToolRegistry) = brain-tools.md:11-25; cortex_email/__init__.py:9-19 (EmailConfig, EmailDetail, EmailReader, EmailSummary, ImapMailbox, Mailbox, RawEmail, build_server, main) all named in brain-email.md:10-25 (RawEmail inside the Mailbox bullet, line 14).

- **◐ partial.** brain-orchestrator.md documents everything importable from cortex_orchestrator ('__all__ is the API')
  - Evidence: SeamServerConfig/BrainRuntimeConfig/InferenceConfig env names and defaults verified against cortex_orchestrator/config.py:20-76 (CORTEX_SEAM_*, CORTEX_REDIS_URL, CORTEX_MODEL_CORTEX, CORTEX_VRAM_SOFT_CAP_GB=14.0, CORTEX_VRAM_CORTEX_GB=11.3, CORTEX_INFERENCE_*); build_subagents signature at wiring.py:128-136 matches the doc verbatim; BrainService/converse/create_server/serve/error codes/ORCHESTRATOR_VERSION all present. BUT MemoryConfig, ToolsConfig, SubagentsConfig (exported in __init__.py:6-9,35-38) appear nowhere in brain-orchestrator.md (grep: zero hits), nor do their CORTEX_MEMORY_*/CORTEX_TOOLS_*/CORTEX_SUBAGENTS_* env contracts, despite the doc's claim at brain-orchestrator.md:8 that __all__ is the API.
  - Adversarial re-check: confirmed. The auditor is correct and could not be refuted. brain-orchestrator.md:8 claims the doc covers everything importable from cortex_orchestrator ('__all__ is the API'), and __init__.py exports 21 names including MemoryConfig, ToolsConfig, and SubagentsConfig, but those three classes and their env contracts (CORTEX_MEMORY_BACKEND/DSN/EMBEDDER_ENDPOINT/EMBEDDER_MODEL; CORTEX_TOOLS_BACKEND/ENDPOINT; th

- **✅ verified**. body-core.md, body-rpc.md, and body-os.md match the crates' actual lib.rs exports
  - Evidence: body/crates/core/src/lib.rs:14-16 (HotkeyChord, HotkeyParseError, Modifier; Accelerator, Hotkey, HotkeyCallback, HotkeyError; BrainTransport, SeamHealth, TransportError, TurnEvent) all documented in body-core.md:12-65; body/crates/rpc/src/lib.rs:29 (BrainSeamClient) + the public generated module (lib.rs:19-28) = body-rpc.md:10-37; os_windows/src/lib.rs:12-15 (cfg(windows) WindowsHotkey), os_linux/src/lib.rs (LinuxHotkey unimplemented!() stub with #![cfg_attr(coverage, feature(coverage_attribute))] and #[cfg_attr(coverage, coverage(off))]), os_macos likewise = body-os.md:9-30.

- **✅ verified**. body-app.md accurately describes the overlay/shell contract: BrainBridge port types, the WireMessage seam, the coverage exclusions, and the shell env vars
  - Evidence: body/app/src/bridge/types.ts:6-31 exports TurnEvent, TransportError(Kind), TurnSink, Cancellation, BrainBridge as documented (body-app.md:23-28); src-tauri/src/converse.rs:21 WireMessage matching the TS wire (doc:29-32); vite.config.ts:27-31 excludes exactly src/main.tsx, src/bridge/tauriBridge.ts, src/bridge/demoBridge.ts (doc:26-27); CORTEX_HOTKEY read at src-tauri/src/hotkey.rs:45, CORTEX_BRAIN_ADDR at src-tauri/src/converse.rs:14 (doc:35-36).

- **✅ verified**. repo-gates.md accurately describes scripts/ behavior: linecap skip lists, coverage_gate metrics, and ci_paths' three GITHUB_OUTPUT lines
  - Evidence: scripts/linecap.py:22-30 skip dirs (node_modules, _generated, tests, caches) and SKIPPED_FILE_PATTERNS (test_*.py, *_test.py, conftest.py, *_test.rs) match repo-gates.md:12-16; scripts/ci_paths.py:5,25-29 emits python=/rust=/overlay= with fail-closed ALL verdict, matching repo-gates.md:27-37.

- **◐ partial.** docs/index.md references every module doc and is itself current (ADRs, runbooks, design docs)
  - Evidence: docs/index.md:83-109 lists all 14 module docs with accurate blurbs; ADR list (index.md:15-68) complete through ADR-0013, matching ls docs/adr/; runbook list (index.md:113-126) matches all 7 files in docs/runbooks/; design/overlay-ux.md listed (index.md:74). One stale detail: the ADR-0010 blurb (index.md:49) still names the delegation tool 'spawn_subagent' (singular), but the shipped tool is 'spawn_subagents' (cortex_core/spawn.py:21), a rename recorded in ADR-0010's own 2026-06-29 addendum (ADR-0010-subagents.md:133-135).
  - Adversarial re-check: confirmed. The auditor is correct on every point. docs/index.md:49 does say 'spawn_subagent' (singular) in the ADR-0010 blurb, while the shipped tool is 'spawn_subagents' (spawn.py:21), a rename recorded in ADR-0010's own 2026-06-29 addendum (lines 133-135). No singular-named tool exists anywhere in shipped code (grep for the singular hits only docs and one stale docstring), so the blurb cannot be satisfied 

### Gaps (2)

#### G1 · severity low · **not documented as a deferral**

brain-orchestrator.md omits three exported config classes (MemoryConfig, ToolsConfig, SubagentsConfig at cortex_orchestrator/__init__.py:6-9) and their env contracts (CORTEX_MEMORY_*, CORTEX_TOOLS_*, CORTEX_SUBAGENTS_* incl. the endpoint/budget knobs in config.py:79-162), despite the doc's own claim that '__all__ is the API' (brain-orchestrator.md:8). The opt-in adapters are described narratively under run_from_env, and the knobs are discoverable in config.py docstrings and the runbooks, but the module doc's public-contract section is incomplete. Not recorded in the ROADMAP 'Deferred refinements & later work' section nor in ADR-0008/0009/0010/0012.

**Adversarial re-check: confirmed.** The auditor is correct on both prongs. (1) The omission is factual: cortex_orchestrator exports MemoryConfig, ToolsConfig, and SubagentsConfig in __all__, and brain-orchestrator.md line 8 explicitly claims __all__ is the documented API, yet its public-contract Config section documents only SeamServerConfig, BrainRuntimeConfig, and InferenceConfig; the three opt-in config classes and their CORTEX_MEMORY_*/CORTEX_TOOLS_*/CORTEX_SUBAGENTS_* env contracts (including the subagent endpoint/budget knobs at config.py:127-162) appear nowhere in the doc. Only the wiring builders are described narratively under run_from_env. (2) No deferral is recorded: the ROADMAP "Deferred refinements & later work" section has no entry about this, and ADR-0008/0009/0010/0012 (including all addenda) contain none either. The closest text, ADR-0012 increment 4 ("Docs + ROADMAP"), is a commitment to update the docs as part of the slice, which makes the omitted coverage a genuine undocumented gap, not a recorded deferral. Mentions of the knobs in config.py docstrings, brain-memory.md:47, and runbooks do not satisfy the module doc's own completeness claim and were already acknowledged by the auditor.

#### G2 · severity low · **not documented as a deferral**

docs/index.md:49 still summarizes ADR-0010 as 'a native spawn_subagent tool' (singular), but the implemented built-in tool is spawn_subagents (batch, SPAWN_TOOL_NAME='spawn_subagents' at cortex_core/spawn.py:21). The rename is written down in ADR-0010's addendum (2026-06-29, lines 133-139) and brain-core.md uses the correct name, so only the index blurb is stale; the staleness itself is not acknowledged anywhere.

**Adversarial re-check: confirmed.** The auditor is correct on every checkable fact. docs/index.md:49 summarizes ADR-0010 as "a native `spawn_subagent` tool" (singular), while the implemented built-in is `spawn_subagents` (batch) at cortex_core/spawn.py:21, renamed in ADR-0010's 2026-06-29 increment-2 addendum (lines 133-143). I searched for any written acknowledgment of the index blurb's staleness: the ROADMAP "Deferred refinements & later work" section (lines 451-556) has no Slice-7/ADR-0010 entry at all and nothing about the index; ADR-0010's three addenda (lines 133, 148, 178) record the rename and later revisions but never note the index entry; broad greps across docs/ (adr, modules, runbooks, ROADMAP) for "blurb", "index entry", "stale", "update.*index" found nothing relevant; git log for docs/index.md shows no later fix. Two mitigating observations that do NOT refute: (1) ROADMAP.md:216/220 use the same singular in the Slice-7 design paragraph but the adjacent progress paragraph (lines 230-232) explicitly cites the plural batch tool and the increment-2 addendum, so the ROADMAP self-corrects while the index does not; (2) the index's own convention is to fold in addendum revisions (e.g., the ADR-0001 entry at index.md:17 notes "originally vLLM (superseded by ADR-0005)"), confirming the singular blurb is genuine staleness rather than deliberate original-decision phrasing. The rename itself is documented, exactly as the auditor already conceded, but that is not a record of the index blurb's staleness or a deferral of fixing it. Gap stands, undocumented.


## Hard-gate infrastructure (AGENTS.md gates 1-6)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps
### Summary

The hard-gate infrastructure exists and is wired exactly as AGENTS.md claims: linecap.py counts every line of non-test .py/.rs with _generated dirs excluded and runs first in `just check` plus unconditionally in CI; the brain and scripts trees enforce --cov-branch --cov-fail-under=100, the Rust tree enforces 100% lines/regions via cargo +nightly llvm-cov with branches gated by coverage_gate.py (covered==count, percent untrusted), and the overlay enforces 100% Vitest thresholds; all coverage escape hatches (7 Python pragmas, 2 Rust coverage(off) stubs) carry inline reasons. Integration work is properly quarantined (strict pytest marker excluded by addopts, #[ignore]-marked Rust live tests), pre-commit runs the full `just check`, and CI is GPU-less, runs the same just recipes, and path-filters through the fail-closed in-repo classifier. On the specific probe: a hypothetical audit/ directory of markdown files would trigger NO toolchain jobs (the trailing .md rule classifies them NEITHER, so only linecap runs), while any non-.md file there hits the fail-closed default and triggers all three jobs; that .md carve-out is deliberate and documented in ADR-0006 but is narrower than AGENTS.md's blanket 'unrecognized paths trigger all' phrasing. Two low-severity undocumented drift items: a hard-coded dev Postgres credential (cortex/cortex) in the loopback-only memory compose override with no written carve-out from the 'no secrets in the repo' rule, and the commit-msg hook enforcing CC types/format but not the stated subject-style constraints (≤72 chars, lowercase, imperative). Config-via-env spot checks came back clean everywhere else.

### Claims checked (12)

- **✅ verified**. scripts/linecap.py enforces the 300-line cap counting comments and blanks, on .py/.rs non-test sources, with generated dirs excluded
  - Evidence: scripts/linecap.py:14-15 (DEFAULT_MAX_LINES=300, suffixes .py/.rs), :49-52 (count_lines counts every line via read_bytes().splitlines(), code, comments, blanks), :16-29 (SKIPPED_DIRS includes 'tests' and '_generated'), :30 (test-file patterns test_*.py, *_test.py, conftest.py, *_test.rs). Generated stubs really do live only in _generated dirs: brain/packages/seam/src/cortex_seam/_generated/ and body/crates/rpc/src/_generated/ (find output).

- **✅ verified**. The line cap is wired into `just check` and runs unconditionally in CI
  - Evidence: justfile:13 (check runs check-linecap first), justfile:40-42 (check-linecap recipe runs linecap.py --root ..); .github/workflows/ci.yml:68-81 (dedicated linecap job, exempt from the path filter, runs `just check-linecap` on every run).

- **✅ verified.** Brain pytest config has branch coverage and --cov-fail-under=100, with tests and generated dirs omitted from measurement
  - Evidence: brain/pyproject.toml:66 (addopts: --cov --cov-branch --cov-fail-under=100 --cov-report=term-missing --strict-markers -m "not integration"), :70-74 ([tool.coverage.run] branch=true, omit=["*/tests/*", "*/_generated/*"]). The scripts tree is gated identically: scripts/pyproject.toml:25-28 (--cov-branch --cov-fail-under=100).

- **✅ verified**. Rust coverage runs cargo llvm-cov with failing 100% thresholds; branches gated by scripts/coverage_gate.py; generated dirs excluded
  - Evidence: justfile:67 (cargo +nightly llvm-cov --branch --workspace --all-targets --ignore-filename-regex '/_generated/' --fail-under-lines 100 --fail-under-regions 100 --json), justfile:68-69 (coverage_gate.py checks the JSON because llvm-cov has no --fail-under-branches, per comment at justfile:60-62); scripts/coverage_gate.py:17 (REQUIRED_METRICS = lines, regions, branches), :56-69 (passes only when covered == count; producer percent never trusted).

- **✅ verified**. body/app overlay is gated at 100% coverage via Vitest thresholds
  - Evidence: body/app/vite.config.ts:36 (thresholds: lines/branches/functions/statements all 100, provider v8, all:true), body/app/package.json:11 (test:cov = vitest run --coverage), justfile:74-77 (check-overlay runs npm ci, typecheck, test:cov). Exclusions (main.tsx, tauriBridge.ts, demoBridge.ts, test-setup.ts) are documented at vite.config.ts:5-8 and docs/adr/ADR-0011-body-v1.md:148-155 (addendum: bridge dir excluded as the frontend analog of Rust host adapters).

- **✅ verified.** Coverage escape hatches all carry inline reasons
  - Evidence: All 7 non-generated `pragma: no cover` occurrences have inline reasons: brain/packages/orchestrator/src/cortex_orchestrator/__main__.py:11 and brain/packages/email/src/cortex_email/__main__.py:9 (module entry guards), brain/packages/core/tests/test_scheduler.py:47 and test_model.py:38 (raise-before-body), scripts/linecap.py:111, coverage_gate.py:130, ci_paths.py:107 (CLI entry points, main() unit-tested). Rust: `#[cfg_attr(coverage, coverage(off))]` exists only in the two non-target-OS stubs, each justified in the module doc (body/crates/os_linux/src/lib.rs:3-10,18 and body/crates/os_macos/src/lib.rs, same pattern), matching AGENTS.md gate 2's own examples.

- **✅ verified**. pytest integration marker exists, is strict, and is excluded from default runs and the coverage gate; Rust live tests are #[ignore]-gated
  - Evidence: brain/pyproject.toml:63-66 (marker declared, --strict-markers, addopts -m "not integration"); scripts/pyproject.toml:22-25 (same); 8 live suites carry @pytest.mark.integration (email/tests/test_email_live.py:13, inference/tests/test_injection_defense_live.py:294, tools/tests/test_registry_live.py:22, orchestrator/tests/test_subagent_live.py:42, embedding/tests/test_embedder_live.py:20, session/tests/test_store_live.py:18, inference/tests/test_backend_live.py:24, memory/tests/test_pgvector_live.py:23); manual runs use --no-cov (justfile:115). Rust: body/crates/rpc/tests/live.rs:40,59 (#[ignore = "live seam check: needs a real brain..."]), invoked only via `just seam-health` with -- --ignored (justfile:109-110).

- **✅ verified**. `just check` runs ruff, pyright, pytest+coverage, cargo fmt --check, clippy -D warnings, cargo test, cargo llvm-cov, linecap, and the body/app checks
  - Evidence: justfile:10-37 (check = check-linecap then check-brain/check-scripts/check-body/check-overlay in parallel, any failure fails the gate); check-brain justfile:45-50 (ruff format --check, ruff check, pyright, pytest); check-scripts justfile:53-58 (same for the gate tooling); check-body justfile:63-69 (cargo fmt --all --check, clippy -D warnings, cargo test, cargo +nightly llvm-cov, coverage_gate.py); check-overlay justfile:74-77.

- **◐ partial.** Pre-commit mirrors `just check`; a commit-msg hook enforces Conventional Commits
  - Evidence: .pre-commit-config.yaml:6-14 (local hook `just check`, always_run, pass_filenames false, pre-commit stage only) and :15-20 (compilerla/conventional-pre-commit v4.4.0 at commit-msg with exactly the AGENTS.md type list: feat fix docs test refactor perf build ci chore revert). Partial because the hook validates CC structure and types but does NOT machine-enforce AGENTS.md's stated subject constraints (imperative mood, lowercase, no trailing period, ≤72 chars). Those remain convention-only.
  - Adversarial re-check: confirmed. The auditor stands. Every factual element of their evidence is accurate: the pre-commit stage is a single local `just check` hook (always_run, pass_filenames false, stages [pre-commit]) and the commit-msg stage is compilerla/conventional-pre-commit v4.4.0 with args listing exactly the AGENTS.md type set (feat fix docs test refactor perf build ci chore revert) and nothing else. I searched adversari

- **✅ verified.** CI is GPU-less, path-filtered via scripts/ci_paths.py per ADR-0006, fail-closed, and runs the same just recipes
  - Evidence: .github/workflows/ci.yml:1-2,26,72,86,101,134 (plain ubuntu-latest runners, no CUDA); :37-66 (changes job pipes `git diff --name-only` into python3 scripts/ci_paths.py under `set -euo pipefail`, so a classifier error fails the run; undeterminable range → all three outputs true, fail-closed); :83-96,98-125,131-145 (python/rust/overlay jobs gated on classifier outputs, each running `just check-brain`/`check-scripts`/`check-body`/`check-overlay`); scripts/ci_paths.py:31,78-83 (unmatched paths → DEFAULT all-true fail-closed verdict). The RULES list matches ADR-0006 decision 1 (docs/adr/ADR-0006-gate-performance.md:19-41) rule for rule.

- **◐ partial.** AGENTS.md's 'unrecognized paths trigger all of them (fail closed)' holds for a hypothetical audit/ directory
  - Evidence: Traced through scripts/ci_paths.py:48-66,78-83: `audit/` matches no exact/prefix rule, but any `audit/*.md` file hits the LAST rule (Rule("suffix", ".md", NEITHER) at ci_paths.py:65), so an audit/ dir of pure markdown triggers NO toolchain jobs (python=rust=overlay=false); only the unconditional linecap job (ci.yml:71-81) and the changes job run. Any non-.md file under audit/ (e.g. audit/data.json) falls through to DEFAULT (ci_paths.py:31,83) and triggers ALL THREE jobs. So the fail-closed default is real, but markdown in unrecognized dirs is classified inert by suffix, a deliberate, documented choice (ADR-0006:32-37), slightly narrower than AGENTS.md's blanket phrasing.
  - Adversarial re-check: confirmed. The auditor is factually correct on every point and I could not refute the finding. Direct code reading confirms: audit/*.md matches no exact/prefix rule and hits the last rule (suffix ".md" -> NEITHER, ci_paths.py:65), so a hypothetical audit/ directory of pure markdown yields python=rust=overlay=false and triggers no toolchain job. Only the unconditional linecap job (ci.yml:71-81, which scans o

- **✅ verified.** Config via env only, with no hard-coded paths or secrets in brain/body source
  - Evidence: brain: pydantic-settings BaseSettings everywhere with CORTEX_* prefixes (brain/packages/orchestrator/src/cortex_orchestrator/config.py:20-142. SeamServerConfig, BrainRuntimeConfig, InferenceConfig, MemoryConfig, ToolsConfig, SubagentsConfig; brain/packages/email/src/cortex_email/config.py:11-20). Rust/TS: env-overridable defaults only (body/app/src-tauri/src/converse.rs:92 CORTEX_BRAIN_ADDR, hotkey.rs:45 CORTEX_HOTKEY; body/crates/rpc/build.rs:22 CORTEX_REGEN_PROTO). Greps for /mnt/, /home/, C:\, /Users/ across brain/packages, body/crates, body/app/src source returned nothing. Compose model-dir default is env-overridable (docker-compose.memory.yml:73 ${CORTEX_MODELS_DIR:-./models}, per ADR-0004); the email IMAP password is env-required with no default (docker/docker-compose.email.yml:35 ${CORTEX_EMAIL_IMAP_PASSWORD:?...} plus a NEVER-commit-secrets comment at :9). One exception recorded as a gap: the dev Postgres credential in docker-compose.memory.yml.

### Gaps (3)

#### G1 · severity low · **not documented as a deferral**

docker/docker-compose.memory.yml hard-codes the local Postgres credential: POSTGRES_PASSWORD: cortex (line 32) and the DSN postgresql://cortex:cortex@postgres:5432/cortex (line 20). The service publishes loopback-only (line 46) and it is a throwaway dev credential, but AGENTS.md gate 5 says 'no secrets in the repo' with no written carve-out for dev-stack defaults; ADR-0008 never mentions the password choice (grep for password/credential in ADR-0008 returned nothing) and the ROADMAP deferred-refinements section (docs/ROADMAP.md:451-565) has no entry for it. Contrast: the email override explicitly refuses to default its password (docker-compose.email.yml:9-11,35).

**Adversarial re-check: confirmed.** The auditor is correct. The hard-coded dev credential exists exactly as described, and after searching the origin ADR (ADR-0008, read in full, no addendum), the ROADMAP 'Deferred refinements & later work' ledger, all other ADRs, the memory runbook, the module doc, init.sql, the live integration test, and the introducing commit message, there is no written record of the credential choice, no carve-out from AGENTS.md gate 5's 'no secrets in the repo', and no deferral entry. The nearest candidate, ROADMAP Phase-0 assumption 5 (single-user, loopback-only security model), which the compose file cites for its loopback publish, never mentions the Postgres password and in fact prescribes secrets 'via env', so it reinforces rather than refutes the gap. The email override's explicit refuse-to-default pattern confirms the repo already has a stated convention this file silently violates.

#### G2 · severity low · **not documented as a deferral**

The commit-msg hook (conventional-pre-commit v4.4.0, .pre-commit-config.yaml:15-20) enforces Conventional Commits structure and the allowed type list, but AGENTS.md's additional subject rules (imperative mood, lowercase subject, no trailing period, subject ≤ 72 chars) are not machine-enforced by any hook. AGENTS.md's 'enforced by a commit-msg hook' overstates coverage for those style constraints. Not recorded in the ROADMAP deferred section or any ADR.

**Adversarial re-check: confirmed.** The auditor stands. Verified directly: the commit-msg hook is conventional-pre-commit v4.4.0 whose only args are the type list (.pre-commit-config.yaml:20), which validates the type(scope)!?: subject structure and type set but has no mechanism for imperative mood, lowercase subject, trailing-period, or 72-char subject length; no other enforcement exists (scripts/ holds only linecap.py, coverage_gate.py, ci_paths.py; the justfile has no commit-lint recipe; no .githooks/husky/commitlint files anywhere). Searched for a deferral record exhaustively: the ROADMAP 'Deferred refinements & later work' section (docs/ROADMAP.md:451-565) contains nothing about commit-message style enforcement; repo-wide grep for conventional/commitlint/imperative/commit-msg/72-char across docs/adr (including addenda), docs/modules, docs/runbooks, docs/design, justfile, scripts, and .github hits only .pre-commit-config.yaml and AGENTS.md itself. No ADR covers the conventional-pre-commit hook at all. ADR-0002 decision 9 documents only the just-check pre-commit mirror, and ADR-0006 mentions the hook only for the fixed double-run defect. The adopting commit 790166e even repeats the overstatement ('subject limits ... enforced by the conventional-pre-commit hook'). The gap is real and undocumented.

#### G3 · severity low · documented (docs/adr/ADR-0006-gate-performance.md:32-37 (decision 1: '.md' suffix reached only when no earlier rule matched, precedence deliberate) and the normative-comment cross-reference at scripts/ci_paths.py:42-47)

AGENTS.md gate 3 says 'unrecognized paths trigger all of them (fail closed)', but ci_paths.py's trailing '.md' suffix rule (scripts/ci_paths.py:65) means markdown files in an unrecognized top-level directory (e.g. a new audit/ dir of .md files) are classified NEITHER and trigger no toolchain jobs. Only non-.md files there hit the fail-closed DEFAULT. The behavior itself is deliberate and documented; the drift is only in AGENTS.md's simplified phrasing.

