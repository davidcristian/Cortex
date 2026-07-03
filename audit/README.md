# Slice implementation audit (2026-07-02)

An independent audit of every slice `docs/ROADMAP.md` marks **done** (Slices 0, 1, 2, 3,
4, 5, 6, 6.5, 7, 8, 8.5), answering two questions per slice:

1. **Was it actually implemented?** Every concrete claim in the slice's ROADMAP text
   (files, ports, classes, tests, compose services, env vars, proto RPCs, runbooks, ADR
   addenda) was verified against the tree.
2. **If anything was consciously left undone, is the deferral written down** (in the
   ROADMAP's "Deferred refinements & later work" ledger and/or the origin ADR), per the
   AGENTS.md gate-4 Definition of Done?

## Method

- One dedicated audit agent per slice (11) plus three cross-cutting auditors
  (deferral-ledger consistency in both directions, module-doc coverage/accuracy,
  hard-gate infrastructure). All read-only, evidence as `file:line` references.
- **Every reported discrepancy was re-checked by an independent adversarial verifier**
  instructed to refute it (search under alternate names, later-slice supersessions, all
  ADR addenda). Findings below survived that pass; refuted findings were reclassified
  and are annotated in the per-slice reports.
- `just check` was run in full on the audit date and **passed** (exit 0): ruff, pyright,
  pytest with 100 % line+branch coverage, cargo fmt/clippy/test, cargo-llvm-cov at
  100 %, the 300-line scan, and the overlay's Vitest suite at 100 % across all metrics.

## Headline

**Every done slice is substantively implemented.** No promised port, adapter, test,
tool, or compose service is missing outside of items the repo already records as
deferred. The gates the slices claim to prove are real and wired. What the audit found
instead is **documentation drift**: stale text left behind as later slices revised
earlier decisions, a handful of deferrals recorded in only one of the two places the
DoD requires, and four medium-severity items listed below.

| Slice | Implementation | Documentation | Report |
|---|---|---|---|
| 0 (Governance) | ✅ complete (docs-only slice) | 2 stale-text items in ARCHITECTURE.md | [slice-0.md](slice-0.md) |
| 1 (Walking skeleton) | ✅ complete | clean with zero findings | [slice-1.md](slice-1.md) |
| 2 (The seam) | ✅ complete | stale runbook tense; ADR-side record missing for one ledger entry | [slice-2.md](slice-2.md) |
| 3 (Chat w/ fake inference) | ✅ complete (restart acceptance proven in test + live) | 1 stale in-code promise (backpressure) | [slice-3.md](slice-3.md) |
| 4 (Real inference) | ✅ complete | all deferrals documented (cleanest paper trail) | [slice-4.md](slice-4.md) |
| 5 (Memory v1) | ✅ complete **except automated DB sync** (see below) | otherwise documented | [slice-5.md](slice-5.md) |
| 6 (Tools via MCP) | ✅ complete | server-pin discrepancy; `--jinja` condition never marked met | [slice-6.md](slice-6.md) |
| 6.5 (Untrusted-content boundary) | ✅ complete **except `trust` in the durable log** (see below) | stale fake names in ADR-0013 | [slice-6.5.md](slice-6.5.md) |
| 7 (Subagents) | ✅ complete | user-closure recorded in ROADMAP only; compose/runbook left stale by 8.5 | [slice-7.md](slice-7.md) |
| 8 (Body v1) | ✅ complete + host-validated | polish deferral outside the central ledger; stale ADR-0011 addendum | [slice-8.md](slice-8.md) |
| 8.5 (Resource governance) | ✅ complete (CI half; host half is a documented Slice-11 deferral) | **stale subagents compose now crashes the brain** (see below) | [slice-8.5.md](slice-8.5.md) |

Cross-cutting results (deferral ledger, module docs, gates infrastructure):
[cross-cutting.md](cross-cutting.md).

## The four medium-severity findings (all adversarially confirmed)

1. **The automated Postgres dump/sync into `D:\Software\AI\Database` was never built**
   (Slice 5). ROADMAP:90-91 and the ADR-0004 addendum promise "an automated dump/sync
   job"; ADR-0008 decision 7 phrases it in the present tense as if delivered. What
   exists is a manual `pg_dump` procedure in `docs/runbooks/memory-pgvector.md:63-74`.
   Not recorded as a deferral anywhere. The plug-and-play guarantee currently depends
   on the user remembering a manual step.
2. **`LoggingAuditSink` drops `ToolInvocation.trust` from the durable log** (Slice 6.5).
   The dispatcher stamps provenance on every invocation (`dispatch.py:101`) and ADR-0013
   decision 2 promises it as "a durable forensic fact", but the only production sink
   (`brain/packages/tools/src/cortex_tools/audit.py:22-32`) never emits the field, so
   the durable trail cannot answer "did this turn read untrusted content?". Undocumented.
3. **`docker/docker-compose.subagents.yml` + `docs/runbooks/subagents-cpu.md` were left
   behind by the Slice 8.5 config change, and the compose now crashes the brain**
   (Slices 7/8.5). The override sets the removed `CORTEX_SUBAGENTS_MAX_CONCURRENCY` and
   flips `CORTEX_SUBAGENTS_BACKEND=llamacpp` without the now-required
   `CORTEX_SUBAGENTS_GPU_ENDPOINT` (`config.py:154-162`), so the documented bring-up
   fails at startup with a ValidationError. The compose/runbook *update* is a documented
   Slice-11 deferral (ADR-0012:180-183), but the interim breakage is flagged nowhere.
4. **The Slice 7 user closure has a ROADMAP-only paper trail.** ROADMAP marks the
   cortex-driven GPU path "host-closed 2026-07-01", but ADR-0010:173-175, the
   subagents runbook (:79-80), and ADR-0004:161 all still describe it as pending, and no
   dated addendum records what was run, unlike every sibling host validation.

## Ledger-sync omissions (documented at the origin ADR, missing from the central ledger)

AGENTS.md gate 4 wants each deferral recorded in **both** the ROADMAP ledger and its
origin ADR. These are recorded at the ADR only (so nothing is lost, but the ledger's
"collected here so none is lost" promise is incomplete):

- ADR-0011: multi-turn-within-one-stream + explicit proto `Cancel` event.
- ADR-0010: subagent progress reporting over the `Converse` status stream.
- ADR-0010: richer `spawn_subagents` object schema (`{instruction, context}[]`).
- ADR-0012: a hard budget wall behind the scheduler port (soft budget is admission-only).
- ADR-0013/0004: the injection-defense harness has not been run against the ~31B brain
  tier (`CORTEX_PROBE_BRAIN=1`, opt-in, not yet run).
- Slice 8's overlay polish (transparent window + click-through, corner morph,
  hide-on-blur, tighter CSP), recorded in `overlay-ux.md` §4 + the runbook and pointed
  at from the slice text, but in **neither** canonical location (no ledger entry, no
  ADR-0011 record).

And two inverse cases: the ledger's Slice-2 transport-retry entry cites ADR-0003, which
never mentions it; the Slice-3 windowing entry has no origin ADR at all (Slice 3 shipped
without one).

## Notes

- **This `audit/` directory is inert to CI by design:** `scripts/ci_paths.py`'s trailing
  `.md` rule classifies markdown in an unrecognized directory as touching no toolchain,
  so these files trigger no CI jobs (deliberate per ADR-0006 decision 1, though AGENTS.md's
  blanket "unrecognized paths trigger all of them" phrasing is slightly wider than the
  implementation; see [cross-cutting.md](cross-cutting.md)).
- The audit is a point-in-time snapshot (2026-07-02, working tree at commit `87f137d`).
  Line references will drift as files change.
