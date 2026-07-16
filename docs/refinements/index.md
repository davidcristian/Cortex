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
behind an unchanged port". That was wrong often enough to mislead planning four times: the
tool-dispatch entry and its ADR both claimed tool spam was bounded by `MAX_TOOL_STEPS` (it was
not, and one round could dispatch unboundedly; [tools-mcp.md](tools-mcp.md)), the
`list_sessions` entry misdiagnosed its own cost *and* proposed a worse fix than the one that
shipped ([session-read-seam.md](session-read-seam.md)), the display-timezone entry bundled
a knob together with a recurrence change that no existing field can express
([scheduling.md](scheduling.md)), and the resource-governance pair claimed two "pure-core scheduler
tweaks behind the unchanged `SubagentScheduler` port" when one needs a port change to express at all
and the other described a wall that port cannot build, while the wall it *could* build already
existed ([resource-governance.md](resource-governance.md)). Entries audited against the code carry
their real cost inline, and the ones that need a **port or protocol change** say so. Treat any
remaining
"behind the unchanged port" phrasing as unverified until you have opened the port and checked
its signature.

## The docs

| Doc | Area | Open |
| --- | --- | --- |
| [repo-gates.md](repo-gates.md) | Line cap, dashcheck, coverage config (ADR-0026), gate coverage of the ungated Rust trees (ADR-0011) | 1 |
| [seam-transport.md](seam-transport.md) | `BrainTransport` retry/reconnect (ADR-0003/0024) | 3 |
| [seam-auth.md](seam-auth.md) | Seam token auth (ADR-0016) | 1 |
| [session-history.md](session-history.md) | Slice 3 history windowing and summarization | 1 |
| [tools-mcp.md](tools-mcp.md) | Dispatch budget/cost/salience, spawn batch cap, MCP registries (ADR-0009/0010) | 7 |
| [untrusted-content.md](untrusted-content.md) | Taint boundary, output guardrail, subagent model safety (ADR-0013/0015/0017/0019/0028) | 16 |
| [memory.md](memory.md) | Store, scoping, rerank/MMR (ADR-0008) | 8 |
| [inference-model-manager.md](inference-model-manager.md) | Model-manager lifecycle, MTP, reasoning status (ADR-0007/0020) | 3 |
| [subagents.md](subagents.md) | Progress reporting, spawn schema, heterogeneous roster (ADR-0010/0018) | 2 |
| [body-overlay.md](body-overlay.md) | Overlay polish, connection indicator, proto Cancel (ADR-0011) | 3 |
| [session-read-seam.md](session-read-seam.md) | Session listing/read seam (ADR-0021) | 4 |
| [resource-governance.md](resource-governance.md) | Scheduler/placer budgets, NPU, drain (ADR-0012) | 6 |
| [email-confirmer.md](email-confirmer.md) | Email write, Confirmer, attachments, `ToolActivity` chip (ADR-0022) | 7 |
| [body-gateway.md](body-gateway.md) | Body gateway, OS actions, hardened posture (ADR-0023) | 6 |
| [scheduling.md](scheduling.md) | Scheduling and reminders, `TurnStamp` provenance (ADR-0025/0027) | 8 |
| [cross-cutting.md](cross-cutting.md) | Pointer input, OS backends, more roles | 4 |

The counts are per area as extracted; a few threads appear in two areas (the cross-cutting
"richer memory policies" line is covered by memory.md's items, and subagent tool-step
surfacing appears in both email-confirmer.md and subagents.md as one piece of work).
Scheduling held at 10 on 2026-07-16 when the body-side `Notify` trait closed and opened one entry
behind it (toast activation routing), which is the backlog working as intended rather than a
stalled area; it then went to 9 the same day when the tainted-reminder badge entry was read
against the tree and closed as satisfied with no code change, the first entry here to close that
way rather than by landing something; it then went to 8 the same day when the occurrence-history
table closed as declined for want of a consumer, the same terminal outcome the blended-relevance
field took, since nothing reads a fired occurrence and the "you missed these" recovery view that
would is unbuilt (the store keeping no per-fire record was verified live against the compose Redis). Untrusted content went 16 to 17 the same day for
the same reason: structured provenance landed, and the two halves it could not honestly capture
(a sidecar-declared sender, provenance across the stores) each became an entry naming what
blocks it. It then went back to 16 the same day when summarizing a tainted exchange before recording
closed as declined, read against the write path: the raw untrusted payload is never persisted (only
the framed, guardrail-scrubbed `User`/`Assistant` exchange is), and a recalled tainted memory is
always re-fenced and re-taints, so a summarization pass would add a second injectable model call on
the record path (`summarize this: {tainted}` makes the summarizer the target) for no safety the
fence does not already give. Body & overlay held at 3 on 2026-07-16 when the connection indicator landed and
opened the push half behind it (streamed brain status, blocked on a producer), while session
read seam went 5 to 4 the same day: the two entries were one deferral written down twice, and
the shared premise (wait for a slice that streams brain status) turned out to be wrong for both.
Session read seam then held at 4 the same day when brain-generated titles landed and opened the
open-chat header-consistency item behind them: the switcher shows the model's title, but the
open-chat header still derives locally, and unifying them wants a title on the `GetSessionMessages`
read path. The titles entry is another that undersold its cost ("behind the unchanged
`SessionSummary`"): the value type held, but the honest build added a `set_title` write method, a
store-layout change, a list-read change, and a tier/timing policy, generated at turn end so it
needs neither the read-path GPU-lease hazard nor an async-port widening.
Repo gates went from 0 back to 1 the same day,
when the two Rust trees `just check` never lints turned out to have been quietly collecting
findings; that entry originates in [ADR-0011](../adr/ADR-0011-body-v1.md) rather than the
ADR-0026 the area doc was extracted under. It held at 1 later the same day when its fmt half
(both trees) and the `os_windows` windows-target clippy landed, leaving one residual, shell
clippy in CI, blocked on the Linux GTK/webkit/dbus dev packages a cold Tauri build needs. The
pass also found `os_windows` fmt had never been a gap: as a workspace member it is already
caught by `check-body`'s `cargo fmt --all`, which formats a member regardless of `cfg`. Memory held at 8 on 2026-07-16 around the first entry
here to close as **declined**: surfacing the blended recall relevance was read against the tree and
no consumer for it exists, which its own origin addendum had made the condition, so cheapness had
been standing in for readiness. It moved to the dead-until-a-consumer list below, and the pass that
closed it opened one entry behind it, recall observability, which is both why the question was hard
to answer and the consumer that would reopen the declined one. Resource governance held at 6 on
2026-07-16 when its two-part first entry closed as two different outcomes, which is why an entry
naming two things should be read as two. Placement-aware CPU charging was **declined**: `admit` is
entered before `place` by design, so no charge can see a placement without a port change, and the
one backend lock per roster entry means admitting more spawns cannot make them run at once
(measured live, two concurrent spawns are exactly serial). The hard budget wall turned out to
**already exist** and to be delivered as a turn-killing exception; making it refuse as a value, and
refusing the misconfiguration at boot, opened the two entries behind it (a bounded admission wait,
a read timeout on the subagent HTTP client) that name the waits nothing bounds. Body gateway held
at 6 on 2026-07-16 when its two-part first entry closed as two different outcomes, the second area
in one day to show that an entry naming two things is two entries. `spawn_blocking` **landed** and
grew: the reminder toast is the same shape of synchronous OS call, so it covers three handlers, and
the safety question (a `spawn_blocking` that moves a `!Send` COM object is a bug, not a fix) was
answered from the backends' types before the change was made. `GetVolume` as an overlay volume
indicator was **declined** on the sharper of the two tests the day's other declines used: not only
does nothing read it, nothing could keep it true, since volume changes with nothing to tell the
overlay. It also named the wrong seam, being an RPC the body *serves*. The pass opened one entry
behind it, unbalanced COM initialization now that the calls run on an ephemeral thread pool.
Seam transport held at 3 on 2026-07-16, the third area in two days whose first entry named two
things and closed as two outcomes. Its "behind the existing seams" claim was the rare one that
held exactly. The **per-method policy landed**: the audit it began with found that nothing
non-idempotent was ever retried, so the defect it might have exposed does not exist, but the
split was enforced only by two hand-written `impl` bodies, and this backlog already queues write
RPCs for that port, so the silent copy was coming. The gate is now a single door that can answer
`None`, and the `Health` probe got a budget, so raising the reads' retry knobs can no longer slow
what the connection indicator claims. The **per-error-code half was declined** for want of a
producer, the same test that closed blended relevance and `GetVolume`: the brain emits three
statuses and all three are already classified correctly. It reopens as the one entry this pass
added, a retryable-code table, whose trigger is named. Tools & MCP went 8 to 7 on 2026-07-16 when
the per-round cap on distinct calls landed: the entry, its ADR, and this index's own opening
warning had all diagnosed it correctly for once (a context-growth problem, not a reach one), and
it closed by dropping a round's calls past a cap rather than refusing them, since a refusal is
appended to the context exactly as a result is. Nothing opened behind it. Inference & model manager
went 5 to 3 on 2026-07-16 when its actionable reasoning pair closed as two outcomes without a seam
change, over the already-shipped `Message.statusState`: the collapsed "thoughts" section **landed**
(the reducer now also concatenates every guardrail-scrubbed thinking delta into a new
`Message.thoughts`, and the settled reply renders the trace as a collapsed disclosure above the
bubble, the live chip's retrospective counterpart), while reasoning persistence/summarization was
**declined** for want of a consumer, the same terminal test the day's other declines used: nothing
reads a stored trace, and the two consumers that would (a `GetSessionMessages` reasoning field for
reload re-display, a summarization feed that reverses the ADR's "never fed back") are both unbuilt,
the second re-raising the non-reentrant GPU-lease sequencing the title generator navigates. The
declined half moved to the dead-until-a-consumer list below. Subagents went 4 to 2 on 2026-07-16
when its bundled actionable item (spawn-spec tuning plus measured trade-off advertisement)
**landed** as one prose change: the spawn tool advertised that subagents "run concurrently" and
delegation was "worth parallelizing", a blanket parallel claim the same-day admission-wall
measurement had already contradicted (each roster entry holds one backend whose lease serializes
same-model spawns, so two same-model spawns took 10.0 s against 4.8 s across two backends). The
description now names the measured trade-off (distinct-model spread is the wall-clock lever,
same-model subtasks serialize), which doubles as the spontaneous-pick nudge finding 1 wanted. The
entry's *other* reading, deriving the config description strings from numbers, stayed declined
(deployment-specific text, safety deterministic), and the nudge's live uptake opened one
fix-when-it-bites residual behind it, unverifiable on the 8 GB dev GPU where the cortex tier does
not fit.

## Recommended order

Ordered by what unblocks the most value soonest. Before starting any item, verify its claims
against the code (the warning above); the entry text tells you which seams it expects to hold.

### Actionable now

1. **Task-outcome delivery as a notification + the push retry policy**
   ([scheduling.md](scheduling.md)): unblocked on 2026-07-16, when the body's `Notify` trait
   landed and gave the port they both reuse a real backend.
2. **`cargo clippy` for the Tauri shell in CI** ([repo-gates.md](repo-gates.md)): the residual
   of the ungated-trees entry, whose fmt half (both trees) and `os_windows` windows-target
   clippy landed 2026-07-16 in `check-body` (with `body/app/src-tauri/` reclassified to rust so
   a shell change gates the job that fmt-checks it). Shell clippy still runs nowhere in CI
   because, unlike shell fmt (parse only) and `os_windows` clippy (a target add, no link), it
   needs the Linux GTK/webkit/dbus dev packages and a cold Tauri build. Last because it
   unblocks no capability, but it is the one lint a shell change can still dirty unseen.

### Actionable, but a seam or port change comes first

- **Open-chat header title consistency** ([session-read-seam.md](session-read-seam.md)): opened
  2026-07-16 behind the landed brain-generated titles. The switcher shows the brain title, but the
  open-chat header re-derives locally, so they can disagree; unifying them needs a `title` on the
  `GetSessionMessages` read path (a proto field + overlay plumbing). A smaller overlay-only
  alternative (carry the switcher's title into `openSession`) covers the open path but not
  cold-start adoption or cycling.
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
  non-reentrant GPU-lease hazard, so they are one design problem. The declined blended-relevance
  field widens the same `select` return, so a consumer for it reopens the work here rather than
  on its own.
- **Memory verbs: tiered/self-editing memory, write-salience, per-scope retention**
  ([memory.md](memory.md)): `MemoryStore` is `add` + `search` only; the missing verbs are the
  real cost.
- **Safe `converse` reconnect-before-first-event**
  ([seam-transport.md](seam-transport.md)): needs a replayable request and a signature change.
- **Multi-turn-within-one-stream + an explicit proto `Cancel`**
  ([body-overlay.md](body-overlay.md)): per-turn confirm keying is the known knock-on.
- **Confirm-with-provenance for tainted turns** ([email-confirmer.md](email-confirmer.md)): the
  structured-provenance fields it waited on landed 2026-07-16, so what remains is the decision:
  it reverses a deliberate fail-closed posture, and is that before it is plumbing.
- **A sidecar-declared sender or source URI**
  ([untrusted-content.md](untrusted-content.md)): the two *claimed* provenance kinds ship shaped
  and tested with no producer, because `ToolResult` carries no source and a FastMCP tool returns
  content blocks with no result `_meta`, while `structuredContent` would replace the readable
  string the model consumes. Needs both halves designed together; parsing a sidecar's rendered
  text in the core is not the answer.
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
  mechanism ([resource-governance.md](resource-governance.md)). **Placement-aware CPU charging**
  joined them on 2026-07-16, declined where it stood: `admit` is entered before `place`, so the
  charge cannot see a target without a port change, and no spawn is GPU-placed in the shipped
  wiring anyway. It reopens here, with the executors that would make the discount mean something.
- Taint/provenance persistence across a mid-turn swap, and the ~31B brain-tier
  injection-harness run ([untrusted-content.md](untrusted-content.md))
- **Streamed brain status** ([body-overlay.md](body-overlay.md)): the push half of the landed
  connection indicator. It waits on a *producer*, not a consumer: `Health` answers ready
  unconditionally today, so nothing can report a state the overlay cannot ask for, and a swap
  that makes the brain not-ready between turns is what would create one. The rule that any
  successful call means the brain is ready expires at the same moment.

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
- A distinct blended-relevance field on a recall hit: nothing reads `ScoredMemory.score` at all
  (the turn renders a memory's text, the seam carries no memory, the recall path has no log or
  audit sink), and the three opt-in policies rank by three different quantities, one of them
  incomparable between hits. Declined 2026-07-16; when a consumer appears it is a
  `RecallPolicy.select` change, so it reopens with the model-based reranker
  ([memory.md](memory.md))
- `GetVolume` as an overlay volume indicator: nothing in the overlay reads or changes volume,
  and nothing could keep the number true, since it changes from hardware keys and other apps
  with nothing to tell the overlay, beside an OS tray icon that is always right. Declined
  2026-07-16; it also named the wrong seam (`GetVolume` is an RPC the body *serves*, so the
  overlay would need a new body-local port, not `BrainBridge`). Reopens with an overlay control
  that *changes* volume, or a host-side change event to push it
  ([body-gateway.md](body-gateway.md))
- `SubagentTask` session attribution and the `ToolInvocation` audit-line stamp: no consumer
  reads either yet ([scheduling.md](scheduling.md))
- Occurrence history / unseen-toast recovery: nothing reads a fired occurrence. The store keeps
  only a transient `deliverable_since` slot (cleared at `ack`, coalesced on a re-fire) and a single
  `last_outcome`; a terminal one-shot is deleted at `finish`, and a pushed one-shot reminder is
  acked-and-deleted on a toast the user may never have seen (verified live: after such a fire the
  record left no `cortex:*` key). The seam exposes no history view, and a "recently fired"/"you
  missed these" surface is a full store-read + RPC + overlay stack that does not exist. The origin
  ADR rejected per-occurrence records for the same want of a reader. Declined 2026-07-16; reopens
  with a recovery surface, designed with the record, and likely reopening the Postgres durable twin
  a queryable history wants ([scheduling.md](scheduling.md))
- Reasoning persistence / summarization: the live status and its landed collapsed "thoughts"
  section are served entirely by the overlay's in-memory `Message.thoughts`; nothing reads a
  *stored* trace. Re-display on session reload needs a reasoning field on the `GetSessionMessages`
  read path (the path the open-chat title-consistency entry independently needs widened) plus the
  store to keep the trace, a real storage-growth decision at the observed ~13,882-char single-turn
  scale; summarization feeding future context reverses the ADR's "never persisted, never fed back"
  and is another inference call with the title generator's non-reentrant GPU-lease sequencing.
  Persisting reverses a deliberate ephemeral decision, so it is a design change, not a cheap
  follow-on. Declined 2026-07-16; reopens the day a reload re-display or a summarization consumer
  appears, designed with the record the reader needs ([inference-model-manager.md](inference-model-manager.md))
- Provenance across the stores: `ScheduledItem` and `SubagentResult` each carry the taint bit
  and no sources, so a fired task's stamp and a subagent's own readings attribute nothing back
  ([untrusted-content.md](untrusted-content.md))
- Summarizing a tainted exchange before recording: declined 2026-07-16 on two findings. **No
  consumer reads a summarized gist differently from a fenced exchange:** recall already fences a
  stored tainted memory and re-taints the turn, and the raw untrusted payload is never persisted
  (only the framed, guardrail-scrubbed `User`/`Assistant` exchange), so nothing verbatim is left to
  summarize away. **And summarization is not a safe mitigation:** `summarize this: {tainted}` makes
  the summarizer the injection target on the small tier where framing is unreliable, and its output
  is still untrusted-derived, so it stays `tainted=True` and re-fenced anyway, adding an inference
  call on the record path for no safety gain. Reopens only inside a general memory-compaction
  feature (ADR-0008/0014), and even there the summary stays tainted and its input is fenced to the
  summarizer, not the safety win the entry imagined ([untrusted-content.md](untrusted-content.md))
- The per-role escape hatch: unimplemented by design, no role justifies it
  ([subagents.md](subagents.md))
- Per-task caller-supplied subagent schema: revisited only for a structured
  subagent-result feature ([untrusted-content.md](untrusted-content.md))
- The `ToolActivity` wire `phase` field: only if the chip ever needs completion states
  ([email-confirmer.md](email-confirmer.md))

### Fix when it bites

Bounded contingencies, each named in its doc with the condition that would activate it: the
salience limit knob, cross-loop salience, the `CORTEX_SUBAGENTS_MAX_BATCH` knob, the
cost-aware batch cap, the fair-share policy, and the sidecar session cache/pool, whose own entry calls the per-call handshake acceptable at personal scale ([tools-mcp.md](tools-mcp.md)); the
spontaneous-pick nudge's live uptake, joined on 2026-07-16 when the measured trade-off
advertisement landed, whose trigger is a live cortex on user-tier hardware still under-reaching
for distinct models and whose fix is stronger nudging behind the same spec seam
([subagents.md](subagents.md)); the retry
budget / circuit-breaker, joined on 2026-07-16 by a retryable-code table beyond `Unavailable`,
whose trigger is a brain that starts answering `RESOURCE_EXHAUSTED` or `ABORTED`
([seam-transport.md](seam-transport.md)); the tunnel fallback, the
hardened non-loopback posture, a safe Core Audio wrapper, and the unbalanced COM
initialization the blocking-pool hop made visible, whose trigger is a COM failure or thread
growth on Windows after a long session
([body-gateway.md](body-gateway.md)); paging/cursor and the live-suite fixed-window residual
([session-read-seam.md](session-read-seam.md)); the Postgres durable twin, cron expressions,
and automated dead-letter retention ([scheduling.md](scheduling.md)); MTP variants and the
disable-thinking / token-budget caps ([inference-model-manager.md](inference-model-manager.md));
the ANN index, and recall observability, whose trigger is a visibly wrong recall no one can inspect
after the fact ([memory.md](memory.md)); the four guardrail tails (whitespace-split hosts, full
UTS-39 confusables, further encodings, footer heuristics), the GBNF alternative, the
fence-without-block recall mode, per-provenance eviction, and the screening subagent
([untrusted-content.md](untrusted-content.md)); per-field attachment schema descriptions and
send batching / session allowlists ([email-confirmer.md](email-confirmer.md)); the NPU as a
third placement target pending its feasibility pass, plus the two the admission wall opened,
a bounded admission wait and a read timeout on the subagent HTTP client, whose triggers are a
turn observably stalled in admission and a wedged `llama-server` stream respectively
([resource-governance.md](resource-governance.md)).

### Feature breadth, on request

- macOS/Linux OS backends behind the existing traits ([cross-cutting.md](cross-cutting.md))
- More subagent roles ([cross-cutting.md](cross-cutting.md))
