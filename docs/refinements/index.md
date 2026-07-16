# Deferred refinements: index

Every consciously deferred refinement, one self-contained doc per area, extracted verbatim
from the ROADMAP's "Deferred refinements & later work" section on 2026-07-15. Recording a new
deferral here (in its area doc, on this index, and at its origin ADR) is part of finishing a
slice, per the doc-first Definition of Done in [AGENTS.md](../../AGENTS.md); this backlog must
be empty before the user-facing README ships. Landed entries stay in the area docs as the
historical record of what each deferral became, and several deliberately correct their own
ADRs, which is why the entries are kept verbatim rather than summarized.

**An entry's own cost estimate is a hypothesis, not a finding.** The ROADMAP section this
backlog was extracted from used to open by asserting that every entry was "a small change
behind an unchanged port". That was wrong often enough to mislead planning three times: the
tool-dispatch entry and its ADR both claimed tool spam was bounded by `MAX_TOOL_STEPS` (it was
not, and one round could dispatch unboundedly; [tools-mcp.md](tools-mcp.md)), the
`list_sessions` entry misdiagnosed its own cost *and* proposed a worse fix than the one that
shipped ([session-read-seam.md](session-read-seam.md)), and the display-timezone entry bundled
a knob together with a recurrence change that no existing field can express
([scheduling.md](scheduling.md)). Entries audited against the code carry their real cost
inline, and the ones that need a **port or protocol change** say so. Treat any remaining
"behind the unchanged port" phrasing as unverified until you have opened the port and checked
its signature.

## The docs

| Doc | Area | Open |
| --- | --- | --- |
| [repo-gates.md](repo-gates.md) | Line cap, dashcheck, coverage config (ADR-0026) | 0 |
| [seam-transport.md](seam-transport.md) | `BrainTransport` retry/reconnect (ADR-0003/0024) | 3 |
| [seam-auth.md](seam-auth.md) | Seam token auth (ADR-0016) | 1 |
| [session-history.md](session-history.md) | Slice 3 history windowing and summarization | 1 |
| [tools-mcp.md](tools-mcp.md) | Dispatch budget/cost/salience, spawn batch cap, MCP registries (ADR-0009/0010) | 8 |
| [untrusted-content.md](untrusted-content.md) | Taint boundary, output guardrail, subagent model safety (ADR-0013/0015/0017/0019/0028) | 16 |
| [memory.md](memory.md) | Store, scoping, rerank/MMR (ADR-0008) | 8 |
| [inference-model-manager.md](inference-model-manager.md) | Model-manager lifecycle, MTP, reasoning status (ADR-0007/0020) | 5 |
| [subagents.md](subagents.md) | Progress reporting, spawn schema, heterogeneous roster (ADR-0010/0018) | 4 |
| [body-overlay.md](body-overlay.md) | Overlay polish, connection indicator, proto Cancel (ADR-0011) | 3 |
| [session-read-seam.md](session-read-seam.md) | Session listing/read seam (ADR-0021) | 5 |
| [resource-governance.md](resource-governance.md) | Scheduler/placer budgets, NPU, drain (ADR-0012) | 6 |
| [email-confirmer.md](email-confirmer.md) | Email write, Confirmer, attachments, `ToolActivity` chip (ADR-0022) | 7 |
| [body-gateway.md](body-gateway.md) | Body gateway, OS actions, hardened posture (ADR-0023) | 6 |
| [scheduling.md](scheduling.md) | Scheduling and reminders, `TurnStamp` provenance (ADR-0025/0027) | 10 |
| [cross-cutting.md](cross-cutting.md) | Pointer input, OS backends, more roles | 4 |

The counts are per area as extracted; a few threads appear in two areas (the cross-cutting
"richer memory policies" line is covered by memory.md's items, and subagent tool-step
surfacing appears in both email-confirmer.md and subagents.md as one piece of work).
Scheduling's count holds at 10 rather than dropping: the body-side `Notify` trait closed on
2026-07-16 and opened one entry behind it (toast activation routing), which is the backlog
working as intended rather than a stalled area.

## Recommended order

Ordered by what unblocks the most value soonest. Before starting any item, verify its claims
against the code (the warning above); the entry text tells you which seams it expects to hold.

### Actionable now

1. **Structured provenance (source URI/sender) on the `TurnStamp`**
   ([untrusted-content.md](untrusted-content.md)): the designed convergence seam landed
   (ADR-0027); these fields unblock confirm-with-provenance and per-provenance eviction later.
2. **Tainted-reminder badge: verify satisfied and close** ([scheduling.md](scheduling.md)): a
   2026-07-14 read of the shipped overlay found the badge, the `repeats` tag, the inert-text
   rule, and the fixed-label open control already at the standard the deferral asks for.
   Confirm against the current tree and record the entry as satisfied rather than polishing
   without a named defect.
3. **Real connection indicator** ([body-overlay.md](body-overlay.md)): the seam's `Health` RPC
   exists and the `BrainBridge` does not carry it yet; absorbs the session-title refresh push
   deferral from [session-read-seam.md](session-read-seam.md).
4. **Surface the blended recall relevance as a distinct field** ([memory.md](memory.md)): the
   one reranker deferral genuinely behind the unchanged seam.
5. **Placement-aware CPU charging + the hard budget wall**
   ([resource-governance.md](resource-governance.md)): pure-core scheduler tweaks behind the
   unchanged `SubagentScheduler` port.
6. **`spawn_blocking` for the sync OS call + `GetVolume` as an overlay volume indicator**
   ([body-gateway.md](body-gateway.md)): small body-side pair behind unchanged seams. The
   `spawn_blocking` half now covers the toast backend too, which is the same shape of
   synchronous OS call awaited inside an async handler.
7. **Task-outcome delivery as a notification + the push retry policy**
   ([scheduling.md](scheduling.md)): unblocked on 2026-07-16, when the body's `Notify` trait
   landed and gave the port they both reuse a real backend.
8. **Per-method / per-error-code retry policy** ([seam-transport.md](seam-transport.md)):
   behind the existing `BrainTransport`/`Sleeper` seams.
9. **Per-round cap on distinct calls** ([tools-mcp.md](tools-mcp.md)): the one dispatch shape
   neither the budget nor salience closes (context growth, not reach).
10. **Occurrence history table** ([scheduling.md](scheduling.md)): also covers unseen-toast
    recovery.
11. **Brain-generated summary titles** ([session-read-seam.md](session-read-seam.md)): behind
    the unchanged `SessionSummary`.
12. **Reasoning persistence/summarization + the collapsed "thoughts" section**
    ([inference-model-manager.md](inference-model-manager.md)): a natural pair over the
    already-shipped `Message.statusState`.
13. **Summarizing a tainted exchange before recording**
    ([untrusted-content.md](untrusted-content.md)).
14. **Spawn-spec tuning + measured trade-off advertisement** ([subagents.md](subagents.md)):
    low stakes, wrong text misleads only the optimization.

### Actionable, but a seam or port change comes first

- **Session deletion / rename / pinning** ([session-read-seam.md](session-read-seam.md)): new
  gated write RPCs on the catalog (proto change + Slice 6.5 gate + Slice 8.8 Confirmer).
- **Structured redaction event for the overlay**
  ([untrusted-content.md](untrusted-content.md)): `OutputFilter.feed` returns `str`, so a
  redaction signal has no channel until that shape widens. Note the in-code counterargument
  first: the guardrail's inline `[link removed: untrusted source]` marker was written so the
  overlay needs no extra event (`guardrail.py`), so this may close as declined.
- **Subagent progress reporting + subagent tool-step chip surfacing**
  ([subagents.md](subagents.md), [email-confirmer.md](email-confirmer.md)): one side channel
  into the `Converse` queue serves both, and `SpawnSubagentsTool` must stop being
  built-once-shared-by-every-turn.
- **Session-history summarization + the model-based reranker**
  ([session-history.md](session-history.md), [memory.md](memory.md)): both blocked on a sync
  port going async (`HistoryWindow.select`, `RecallPolicy.select`) and both inherit the same
  non-reentrant GPU-lease hazard, so they are one design problem.
- **Memory verbs: tiered/self-editing memory, write-salience, per-scope retention**
  ([memory.md](memory.md)): `MemoryStore` is `add` + `search` only; the missing verbs are the
  real cost.
- **Safe `converse` reconnect-before-first-event**
  ([seam-transport.md](seam-transport.md)): needs a replayable request and a signature change.
- **Multi-turn-within-one-stream + an explicit proto `Cancel`**
  ([body-overlay.md](body-overlay.md)): per-turn confirm keying is the known knock-on.
- **Confirm-with-provenance for tainted turns** ([email-confirmer.md](email-confirmer.md)):
  needs the structured-provenance fields above first, and it reverses a deliberate fail-closed
  posture, so it is a decision before it is plumbing.
- **Real-file email attachments** ([email-confirmer.md](email-confirmer.md)): needs a
  capability grant on a sidecar that deliberately has none, plus a digest-bound approval card.
- **Structural argument identity in salience** ([tools-mcp.md](tools-mcp.md)): normalizing
  needs the advertised parameter schema at the policy.
- **Toast activation routing** ([scheduling.md](scheduling.md)): opened 2026-07-16 behind the
  landed toast. Clicking a toast does nothing, and the obvious fix (open the origin chat, the
  control the overlay's card already has) cannot be built as the seam stands: `NotifyRequest`
  carries no `session_id`, unlike `DueReminder`. It also wants a COM activator on the Windows
  side, so wait for a second consumer of toast interaction.
- **Pointer-input injection** ([cross-cutting.md](cross-cutting.md)): extend the proto first.

### Blocked on Slice 11 (real model swap / GPU lifecycle)

- Model-manager process lifecycle, co-residency, and the real swap
  ([inference-model-manager.md](inference-model-manager.md))
- `SubagentScheduler.drain()`, CUDA-OOM re-place on CPU, and the real GPU-placed runtime
  mechanism ([resource-governance.md](resource-governance.md))
- Taint/provenance persistence across a mid-turn swap, and the ~31B brain-tier
  injection-harness run ([untrusted-content.md](untrusted-content.md))

### Host-side Windows validation only

- The real Core Audio "set volume to 30%" check ([body-gateway.md](body-gateway.md))
- Whether a real reminder toast appears and reads well, the one half of the landed `Notify`
  backend no gate can reach ([scheduling.md](scheduling.md))
- Windows-native validation of the confirm card ([untrusted-content.md](untrusted-content.md))
- The OS-window half of the overlay polish: transparent window + click-through, the morph to a
  real screen corner, hide-on-blur ([body-overlay.md](body-overlay.md))

### Dead until a consumer exists

- Token rotation / multiple tokens: needs a second seam client ([seam-auth.md](seam-auth.md))
- Trust/gating overrides for remote tools: no trusted remote tool exists
  ([untrusted-content.md](untrusted-content.md), [email-confirmer.md](email-confirmer.md))
- Session+global union read policy and cross-scope recall ranking: nothing writes durable
  global facts under scoping yet ([memory.md](memory.md))
- `SubagentTask` session attribution and the `ToolInvocation` audit-line stamp: no consumer
  reads either yet ([scheduling.md](scheduling.md))
- The per-role escape hatch: unimplemented by design, no role justifies it
  ([subagents.md](subagents.md))
- Per-task caller-supplied subagent schema: revisited only for a structured
  subagent-result feature ([untrusted-content.md](untrusted-content.md))
- The `ToolActivity` wire `phase` field: only if the chip ever needs completion states
  ([email-confirmer.md](email-confirmer.md))

### Fix when it bites

Bounded contingencies, each named in its doc with the condition that would activate it: the
salience limit knob, cross-loop salience, the `CORTEX_SUBAGENTS_MAX_BATCH` knob, the
cost-aware batch cap, the fair-share policy, and the sidecar session cache/pool, whose own entry calls the per-call handshake acceptable at personal scale ([tools-mcp.md](tools-mcp.md)); the retry
budget / circuit-breaker ([seam-transport.md](seam-transport.md)); the tunnel fallback, the
hardened non-loopback posture, and a safe Core Audio wrapper
([body-gateway.md](body-gateway.md)); paging/cursor and the live-suite fixed-window residual
([session-read-seam.md](session-read-seam.md)); the Postgres durable twin, cron expressions,
and automated dead-letter retention ([scheduling.md](scheduling.md)); MTP variants and the
disable-thinking / token-budget caps ([inference-model-manager.md](inference-model-manager.md));
the ANN index ([memory.md](memory.md)); the four guardrail tails (whitespace-split hosts, full
UTS-39 confusables, further encodings, footer heuristics), the GBNF alternative, the
fence-without-block recall mode, per-provenance eviction, and the screening subagent
([untrusted-content.md](untrusted-content.md)); per-field attachment schema descriptions and
send batching / session allowlists ([email-confirmer.md](email-confirmer.md)); the NPU as a
third placement target, pending its feasibility pass
([resource-governance.md](resource-governance.md)).

### Feature breadth, on request

- macOS/Linux OS backends behind the existing traits ([cross-cutting.md](cross-cutting.md))
- More subagent roles ([cross-cutting.md](cross-cutting.md))
