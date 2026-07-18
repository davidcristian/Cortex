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
| [repo-gates.md](repo-gates.md) | Line cap, dashcheck, coverage config (ADR-0026), gate coverage of the ungated Rust trees (ADR-0011), test-runner mechanics (ADR-0002) | 2 |
| [seam-transport.md](seam-transport.md) | `BrainTransport` retry/reconnect (ADR-0003/0024) | 4 |
| [seam-auth.md](seam-auth.md) | Seam token auth (ADR-0016) | 1 |
| [session-history.md](session-history.md) | Slice 3 history windowing and summarization | 1 |
| [tools-mcp.md](tools-mcp.md) | Dispatch budget/cost/salience, spawn batch cap, MCP registries (ADR-0009/0010) | 6 |
| [untrusted-content.md](untrusted-content.md) | Taint boundary, output guardrail, subagent model safety (ADR-0013/0015/0017/0019/0028) | 14 |
| [memory.md](memory.md) | Store, scoping, rerank/MMR (ADR-0008) | 8 |
| [inference-model-manager.md](inference-model-manager.md) | Model-manager lifecycle, MTP, reasoning status (ADR-0007/0020) | 6 |
| [subagents.md](subagents.md) | Progress reporting, spawn schema, heterogeneous roster (ADR-0010/0018) | 1 |
| [body-overlay.md](body-overlay.md) | Overlay polish, connection indicator, proto Cancel (ADR-0011) | 3 |
| [session-read-seam.md](session-read-seam.md) | Session listing/read seam (ADR-0021) | 3 |
| [resource-governance.md](resource-governance.md) | Scheduler/placer budgets, NPU, drain (ADR-0012) | 5 |
| [email-confirmer.md](email-confirmer.md) | Email write, Confirmer, attachments, `ToolActivity` chip (ADR-0022) | 4 |
| [body-gateway.md](body-gateway.md) | Body gateway, OS actions, hardened posture (ADR-0023) | 6 |
| [scheduling.md](scheduling.md) | Scheduling and reminders, `TurnStamp` provenance (ADR-0025/0027) | 8 |
| [cross-cutting.md](cross-cutting.md) | Pointer input, OS backends, more roles | 3 |

The counts are per area as extracted; a few threads appear in two areas (the cross-cutting
"richer memory policies" line is covered by memory.md's items, and subagent tool-step
surfacing appeared in both email-confirmer.md and subagents.md as one piece of work, closed
2026-07-16 by landing one side channel that decremented both counts).
Scheduling held at 10 on 2026-07-16 when the body-side `Notify` trait closed and opened one entry
behind it (toast activation routing), which is the backlog working as intended rather than a
stalled area; it then went to 9 the same day when the tainted-reminder badge entry was read
against the tree and closed as satisfied with no code change, the first entry here to close that
way rather than by landing something; it then went to 8 the same day when the occurrence-history
table closed as declined for want of a consumer, the same terminal outcome the blended-relevance
field took, since nothing reads a fired occurrence and the "you missed these" recovery view that
would is unbuilt (the store keeping no per-fire record was verified live against the compose
Redis). It then held at 8 again the same day when task-outcome delivery landed and opened one entry
behind it, the backlog working as intended: a finished task's outcome now delivers as a
notification through the very deliverable/ack ladder a reminder already uses (`_fire_task` finishes
deliverable and pushes the outcome under a `TASK_TITLE` toast, `reminder_to_proto` maps the task's
`last_outcome` onto the pull card), reusing it with no store, proto, or overlay change and
double-delivery barred by the same ack (exactly one of push and pull ever clears the slot, mutation
proven, and confirmed live against the compose Redis). The entry it opened is a task/reminder
distinction on that pull surface, which the reuse leaves undistinguished; and its two-part sibling,
the push retry policy beyond next-poll-pull, sharpened to fix-when-it-bites rather than landing,
because a proactive re-push double-delivers on a lost reply without a per-fire delivery id (the
declined occurrence-history record), so the safe retry stays the deliverable-until-acked pull.
Scheduling held at 8 again on 2026-07-16 when toast activation routing was read against the tree
and sharpened rather than built: the `session_id` its obvious fix wants on `NotifyRequest` has no
reader but the host-side `cfg(windows)` toast render until a COM activator exists to act on a
click, so adding it now would be the dead wire the day's other declines refused, and it moved from
actionable-with-a-seam-change to dead-until-a-consumer with its two-part design (the proto field
plus its `launch` embedding, and the COM `INotificationActivationCallback` with a shell-to-overlay
activation channel) and trigger (a second toast-interaction consumer such as snooze-from-the-toast)
recorded. A sharpened deferral is still open, so the count is unchanged.
Untrusted content went 16 to 17 the same day for
the same reason: structured provenance landed, and the two halves it could not honestly capture
(a sidecar-declared sender, provenance across the stores) each became an entry naming what
blocks it. It then went back to 16 the same day when summarizing a tainted exchange before recording
closed as declined, read against the write path: the raw untrusted payload is never persisted (only
the framed, guardrail-scrubbed `User`/`Assistant` exchange is), and a recalled tainted memory is
always re-fenced and re-taints, so a summarization pass would add a second injectable model call on
the record path (`summarize this: {tainted}` makes the summarizer the target) for no safety the
fence does not already give. It then went 16 to 15 the same day when the structured redaction event
for the overlay closed as declined, read against the shipped path: the guardrail's inline `[link
removed: untrusted source]` marker already tells the user a link was removed, in context and durably
(it is part of the persisted reply and survives reload), while the proposed `StatusUpdate`-shaped
event would be ephemeral, dropped by the status chip on settle, and consumed by nothing, so its
`OutputFilter.feed` port cost buys only polish, and a safe event could carry a count but never the
redacted URL. Both halves were observed live over the real guardrail and the real overlay reducer.
It then went 15 to 14 the same day when a sidecar-declared sender landed, giving the claimed
provenance kinds their first producer and refuting the entry's own blocker. The entry (and this
index) had it that a FastMCP tool "returns content blocks with no result `_meta`"; read against the
shipped MCP SDK the opposite is true: `CallToolResult.meta` is reachable through the very client the
registry uses, and a FastMCP tool sets it by returning a `CallToolResult`, proven by an in-memory
round trip in which result `_meta` survived to the client with the readable string untouched. So the
email `read_email` declares the message sender in `_meta["cortex/source"]`, the registry reads it into
a new `ToolResult.source`, and the ledger notes it beside the attested tool source. The trust half is
the pure-core `claimed_source`: it admits only a claimed `SENDER`/`URI` (dropping an attested kind a
hostile sidecar might forge) and sanitizes the value, and `observe` marks taint before noting any
source, so a declaration can only annotate, never downgrade, both mutation-proven and validated live
against the real email sidecar in Docker. The consumer stays thin and is named as such (confirm-with-
provenance remains declined, a producer alone not reversing the fail-closed decision; per-provenance
eviction wants `MemoryRecord` provenance first), but the fields were built ahead of their consumers on
the same logic and this completes them symmetrically for the claimed kinds; the `URI` producer rides
the identical channel and arrives with a fetch tool that does not yet exist.
Untrusted content then went 14 to 13 on 2026-07-17 when taint/provenance persistence across a
mid-turn swap landed as the brain-handoff record's schema (ADR-0030 decision 2, delivered by the
record sub-slice exactly as the ADR's mapping said it would): the `HandoffRecord` carries the whole
`TaintLedger` (bit, ordered sources, laundering-evidence URL set) behind a new `HandoffStore` port
with a fake and a Redis adapter passing one contract suite, whose pinned check round-trips a
real-API-built tainted ledger bit-, order-, and set-exact, mutation-proven and observed live
against the compose Redis; the ledger rides the record beside the tool-loop tail rather than "on
the stored `Role.TOOL` messages" the entry guessed, the escalate tool and conductor that will
write a record mid-turn are the ADR's later sub-slices, and the harness-run sibling stays open
below.
Untrusted content then went 13 to 14 on 2026-07-17 when the gated `escalate_to_brain` trigger
sub-slice landed and opened one entry behind it, the backlog working as intended. The landing
put the tainted-escalation hard-deny live (the gate the ADR-0030 design leaned on now covers
the most disruptive action in the system, approving-confirmer-proof and mutation-proven) and
gave the confirm card its first per-tool reason (`CORTEX_TOOLS_GATE_REASONS`, since the generic
outbound/irreversible line is false about a model swap). The entry it opened is the opaque-turn
escalation refusal: ADR-0030 slotted it into this sub-slice on the assumption that the vision
slice lands first, but ADR-0029 is designed and unimplemented, `Message` carries no pixels and
no `opaque` bit exists, so the refusal has nothing to check yet and faking one would be a gate
that cannot fail; it lands with the vision slice's pixel-taint increment instead.
Body & overlay held at 3 on 2026-07-16 when the connection indicator landed and
opened the push half behind it (streamed brain status, blocked on a producer), while session
read seam went 5 to 4 the same day: the two entries were one deferral written down twice, and
the shared premise (wait for a slice that streams brain status) turned out to be wrong for both.
Body & overlay held at 3 again the same day when multi-turn-within-one-stream plus proto `Cancel`
was read against the code and sharpened rather than built. The entry's framing was outdated: the
proto `Cancel` has existed since the first proto commit, and the server already carries multiple
turns per stream and handles `Cancel` end to end (queue a mid-turn `UserTurn`, stop the in-flight
turn and drop the queue, keep the stream open, drop the partial reply), all proven. The lease-
cancellation crux the entry flagged is clean and got a dedicated proof: the GPU lease is a
non-reentrant lock held across the streaming block, and a mid-inference cancel propagates out
through `async with manager.acquire(...)` and frees it, pinned by a test that suspends a turn with
the lease held, cancels it, and asserts a fresh acquire returns at once (reddened by releasing the
lock outside a `finally`). What remains is body-side only and coupled: the port is one turn per
call, and a client-sent `Cancel` cannot cleanly precede body multi-turn (on the one-turn-per-call
body it ends the stream on a `Protocol` error, so it needs either multi-turn-within-one-stream, which
carries the per-turn-confirm-keying knock-on, or a new terminal cancelled-ack). Today's Stop is
UI-only in the Tauri embedding (it mutes the JS sink without aborting the RPC, so the brain finishes
and persists the full reply), adequate at loopback personal scale and worth a real abort only when
Slice 11's model swap makes mid-turn compute expensive, the same trigger the reconnect and streamed-
status deferrals wait on, so it moved to fix-when-it-bites; a sharpened deferral is still open, so the
count is unchanged.
Session read seam then held at 4 the same day when brain-generated titles landed and opened the
open-chat header-consistency item behind them: the switcher shows the model's title, but the
open-chat header still derives locally, and unifying them wants a title on the `GetSessionMessages`
read path. The titles entry is another that undersold its cost ("behind the unchanged
`SessionSummary`"): the value type held, but the honest build added a `set_title` write method, a
store-layout change, a list-read change, and a tier/timing policy, generated at turn end so it
needs neither the read-path GPU-lease hazard nor an async-port widening. It then went 4 to 5 the
same day when the session deletion/rename/pinning entry was read as three changes, not one: rename
**landed** end to end (a gated user-only write reusing the `set_title` the titles work built, so no
new port method), and pin and delete opened as their own entries. The "gated ... Confirmer" framing
was wrong for a management RPC, the second reads-against-the-code correction of a Confirmer premise
that day (the tainted-turn confirm decline was the first): the `SeamConfirmer` gates a model's
in-turn tool call, while a rename is user-triggered out of band and reaches no tool, so its gate is
structural user-only reachability, not a card. Pin reshapes the tuned read path (does a pin escape
the recency window?) and delete could not then cascade to memory (`MemoryStore` had no delete verb,
since landed the same day as `delete_scope`), so neither could ride rename.
Session read seam then held at 5 again the same day when the open-chat header-consistency item
landed as the **overlay-only carry** and opened one entry behind it, the backlog working as intended.
The carry reads the header title from the already-loaded `state.sessions` (the switcher's own
`SessionSummary.title`) instead of re-deriving it locally, so the header and the switcher read one
snapshot and agree by construction (a stronger guarantee than the `GetSessionMessages` title field,
a second read a change between the two could desync). It closed three disagreements the entry named
only one of: a default-on user rename the header ignored, a 48-vs-32 truncation gap, and the
generated title. The entry (and this index) undersold the carry by claiming it misses adoption and
cycling "which load by id"; read against the code both target a session already in `state.sessions`
(adoption is `sessions[0]`, cycling is `cycleTarget(state.sessions, ...)`), so a reducer lookup
covers switcher-open, cycling, and adoption alike. The residual it opened is the out-of-window
authoritative title: a reminder deep-link to a chat outside the loaded window still derives locally,
not user-visible (the switcher shows no row for an out-of-window chat to conflict with), dead until
a consumer opens such a chat beside the switcher and earns the `GetSessionMessages` title field.
Session read seam then went 5 to 4 the same day when session deletion landed end to end, opening
nothing behind it. All three halves the entry bundled shipped together: a `SessionStore.delete` verb,
a scope-aware memory cascade, and an overlay-local confirm. The entry's one wrong guess was the
tombstone: read against the code the delete is a **hard** delete, since the reads are snapshots and an
unknown session already reads as an empty history, so there is no in-flight id a tombstone would
protect (the same-day `delete_scope` hard-delete reasoning), and a "forget this chat" privacy action
wants true erasure. Its safety design is the point: the forget verb is kept **off** the turn-facing
`MemoryRecaller` (a separate trusted `SessionMemoryCascade` the orchestrator wires into
`DeleteSession` only), the cascade runs only under session scoping with a `GLOBAL_SCOPE` guard checked
first so the shared space can never be swept (mutation-proven with a session literally named
"global"), the gate is the same structural user-only reachability rename got (no tool, not repeatable),
and the overlay handles deleting the currently-open chat by tearing down its turn and falling back to
a fresh chat rather than rendering a deleted transcript.
Session read seam then went 4 to 3 the same day when session pinning landed end to end, the last of
the three management-verb entries and the one whose crux the entry named exactly: the read-path union
was the whole item, not the `set_pinned` verb or the `pinned` field. A pinned chat escapes the recency
window, so `list_sessions` unions a new pinned set (`cortex:sessions:pinned`) into every listing; the
tuned two-round-trip shape held because round trip one reads both indexes in one transaction
(`ZREVRANGE` + `SMEMBERS`) and a pure-core `merge_pinned` gives the fake and the Redis adapter one
shared pinned-first ordering so they cannot drift. The "verb + field across four trees" framing hid
three costs: the union is additive (a pinned catalog lists past `limit`), `delete` must also `SREM`
the pin or leave a dangling member, and the write RPC is **not repeatable** despite being idempotent
by value (the uniform catalog-write convention: a lost reply must not re-assert a pin the user's next
toggle reversed). The flagship distrust-green check pins a chat older than the window and proves it
still lists above the recency group (dropping the union reddens it). It opened nothing behind it.
Repo gates went from 0 back to 1 the same day,
when the two Rust trees `just check` never lints turned out to have been quietly collecting
findings; that entry originates in [ADR-0011](../adr/ADR-0011-body-v1.md) rather than the
ADR-0026 the area doc was extracted under. It held at 1 later the same day when its fmt half
(both trees) and the `os_windows` windows-target clippy landed, leaving one residual, shell
clippy in CI, blocked on the Linux GTK/webkit/dbus dev packages a cold Tauri build needs. The
pass also found `os_windows` fmt had never been a gap: as a workspace member it is already
caught by `check-body`'s `cargo fmt --all`, which formats a member regardless of `cfg`. It held
at 1 again the same day when that residual was read against what CI installs and moved to
fix-when-it-bites rather than wired: the rust CI job provisions no system library at all, so
shell clippy is not a marginal add but a new class of CI dependency (the 630-package Tauri
webkit-dev apt closure, uncacheable per job, plus a cold roughly 150-crate Tauri-graph compile)
for the occasional style lint on 881 lines of host-validated wiring, disproportionate at
personal scale; a sharpened deferral is still open, so the count is unchanged, and its trigger
is CI gaining the Tauri desktop stack for another reason (a future CI-side Tauri build or smoke
job) so shell clippy rides along. It was confirmed clippy-clean live over a permissive
`pkg-config` shim (this host lacks the stack and sudo, and clippy never links), a planted
`useless_format` proving the declined check real by making the exact command fail. This closed
the sweep's last actionable-now item. Memory held at 8 on 2026-07-16 around the first entry
here to close as **declined**: surfacing the blended recall relevance was read against the tree and
no consumer for it exists, which its own origin addendum had made the condition, so cheapness had
been standing in for readiness. It moved to the dead-until-a-consumer list below, and the pass that
closed it opened one entry behind it, recall observability, which is both why the question was hard
to answer and the consumer that would reopen the declined one. Memory then held at 8 again on
2026-07-16 when the delete/forget verb landed: `MemoryStore.delete_scope(scope)` is the one memory
verb with recorded consumers already waiting on it (a session-delete cascade, per-scope eviction),
by scope because the only link from a session to its memories is the scope, and a hard delete
because search is a stateless top-k scan with no in-flight id to protect. It closed no open item,
since the policies the missing verbs were bundled with (self-editing/update, tiered promote/demote/
expire, write-salience, the per-scope retention policy) stay deferred for want of a consumer, so the
"Memory verbs" actionable-with-a-port-change line moved to dead-until-a-consumer (the port change it
waited on is done) and the residual is policy, not seam. Data-loss-safe by construction (memory is
not a tool in any registry, and the turn-facing recaller exposes only record/recall), and the real
DELETE was host-validated against pgvector (rows 3 to 0, count 3, other scopes spared, a no-match
scope returns 0). Resource governance held at 6 on
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
added, a retryable-code table, whose trigger is named. Seam transport then held at 3 again the same
day when safe `converse` reconnect-before-first-event was audited against both sides of the seam and
sharpened rather than built: a turn's first durable effect (the user-message `store.append` in
`handle_turn`) runs before inference and before the first event, on a turn task decoupled from
client reading, and nothing on the wire carries request identity (`ClientEvent`/`UserTurn` have no
request id, the `turn_id` is server-minted), so a reconnect that re-issues the request double-runs
the turn, verified live over the real engine as two user messages under two distinct turn ids. A
provably-safe version needs a client request id or a resumable cursor plus a Redis-backed
dedup/resume registry that survives a model swap, a turn-lifecycle state machine reversing the
disposable-in-flight-turn design, disproportionate at loopback personal scale. It moved to
fix-when-it-bites with its trigger (routine mid-turn evictions once the real swap lands, and turns
costly enough to make a silent re-run worse than dedup), so the count is unchanged: a sharpened
deferral is still open, the same bookkeeping the session-history and reranker sharpen used. Tools & MCP went 8 to 7 on 2026-07-16 when
the per-round cap on distinct calls landed: the entry, its ADR, and this index's own opening
warning had all diagnosed it correctly for once (a context-growth problem, not a reach one), and
it closed by dropping a round's calls past a cap rather than refusing them, since a refusal is
appended to the context exactly as a result is. Nothing opened behind it. It then went 7 to 6 the
same day when structural argument identity in salience closed as declined, read against the code:
the permuted-key evasion it was filed against is already closed by `Mapping.__eq__` (deep and
key-order-independent, pinned by a test that reddens under an unsorted serialization), a schema-free
canonical form closes nothing more and its serialized shape regresses (unsorted reopens permuted
keys, sorted splits `1` from `1.0`), and the only cases a schema would fold are unsound to fold
(JSON Schema `default` is advisory, so folding an omitted optional can refuse a legitimate call)
with a residual the dispatch budget, the round cap, and the tainted-turn denial already bound. It
closes as declined-on-merits, the same terminal outcome the day's other reads-against-the-code
reached, this one turning on a fix that is a no-op at best and unsound at worst rather than on a
missing consumer. Inference & model manager
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
not fit. Subagents then went 2 to 1, and email & confirmer 7 to 6, on 2026-07-16 together, when
the two entries the index had flagged as one piece of work (subagent progress reporting in
subagents.md, subagent tool-step chip surfacing in email-confirmer.md) **landed** as one side
channel, decrementing both counts. Both halves of that entry's cost correction held against the
code: the engine generator really is suspended inside the spawn `dispatch` (so it cannot yield
progress), and `SpawnSubagentsTool` really is built once and shared by every stream. The fix took
the "carry the channel per call" of the two options the entry named rather than a per-stream tool:
a `ProgressSink` port rides the dispatch `TurnStamp` beside `budget`, so the shared tool reads the
stream's sink per call and leaks no per-stream state (a test routes two sinks through one tool to
prove it). It needed **no proto change** (the overlay already renders `ToolActivity`/`StatusUpdate`),
and the real `SeamProgressSink` is credit-balanced rather than the confirmer's over-crediting
control path, since a delegating turn emits many steps; the wording avoids a parallelism claim the
same-day admission-wall measurement showed the wiring does not deliver. Email & confirmer then went
6 to 5 the same day when confirm-with-provenance for tainted turns closed as **declined**, the first
entry the landed structured provenance unblocked and the decision went against building: a gated
call on a tainted turn returns `DENIED_MSG` and never consults the confirmer (`dispatch.py`, pinned
by an approving-confirmer test that stays unconsulted), so there is no card to add a source line to,
and reversing the block reopens the path an injection aims for to save the one extra turn the
turn-local flow already costs. The provenance actually captured is attested (`TOOL`/`MEMORY`), which
names the user's own tool use rather than the attacker; the `SENDER` kind that would name the
attacker gained a producer later the same day (the sidecar-declared sender), but a producer alone
does not reverse the fail-closed decision, so the decline stands on its own merits. It is the same
fail-closed philosophy the tainted-summarization decline turned on, now protecting the user rather
than the model. Email & confirmer then went 5 to 4 the same day when real-file attachments (bytes the
assistant did not author) closed as declined, the capability kept ungranted: send exists but
attaches only authored text, the `mcp-email` sidecar has no `volumes:` to read from, and granting
the one outbound sidecar file-read would fuse read-local with write-remote on the exfil path. The
deeper reason it stays closed is that the taint boundary already denies the useful flow (reading a
file's bytes taints the turn and a tainted gated send is blocked), so a useful real-file attachment
must bypass taint, which is the exfiltration channel, while a digest-bound card binds the bytes but
never the file choice an injection controls. The safe design (a scoped source, the file choice gated
by taint, the digest-bound card on top) is recorded for the consumer that reopens it.
Session history held at 1 and memory at 8 on 2026-07-16 when the summarization and
model-based-reranker pair, which the recommended order lists as one design problem, was audited
against the code and kept deferred with its blocker sharpened. The async `select` widening both wait
on is mechanically clean and contained: `HistoryWindow.select` and `RecallPolicy.select` each have
one production caller (`engine.py`'s `_inference_messages`, `recall.py`'s `MemoryRecaller.recall`),
both already `async`, so the change adds one `await` apiece and cascades no colour upward, and an
`async def` with a synchronous body is gate-clean under this repo's non-preview ruff. The
non-reentrant GPU-lease hazard is navigable by the title generator's sequential-drain discipline
(proven against the real manager: a drained acquire then the reply's acquire succeeds, a held-open
call deadlocks), not the structural nesting the memory entry's "inside a turn that already holds the
lease" implied, since selection completes before the reply stream acquires the lock. What binds is
elsewhere: a model pass cannot be behavior-validated on the 8 GB dev GPU where the cortex tier does
not fit, and `RecallPolicy.select`'s widening should serve its three deferred consumers (a model
rank, the declined blended field, a recall-observability sink) in one change rather than go async
alone now, so both reopen with the real GPU lifecycle.
Cross-cutting went 4 to 3 on 2026-07-16 when pointer-input injection closed as declined, dead until
a consumer, the entry whose premise the tree contradicted most sharply. It read as a small pointer
increment over an existing text/keyboard input-injection capability needing only a proto extension,
but no input injection exists at any tier (no `body_core` trait, no `os_windows` adapter, the body
server answers `inject_input` with `Status::unimplemented`, the brain `BodyGateway` has no inject
method, and no tool drives it), so pointer is not a refinement one level over a built base but part
of the whole unbuilt input-injection slice ADR-0023 defers. It declines on the same want-of-a-consumer
test the day's other declines used, sharpened by being the highest-harm OS action: a model-driven
pointer is irreversible machine control whose gate is a `gated=True` tool inheriting the tainted-turn
denial, so building the `SendInput` adapter ahead of that tool would ship the machine-control
primitive gated only by the seam token. It reopens as one slice (the whole InputInjector trait, text
plus keyboard plus pointer, behind one gated tool, one `SendInput` adapter under a new `unsafe`
authorization, and one proto pointer extension designed with the consumer), the first cross-cutting
entry to close since the extraction.
Resource governance went 6 to 5 on 2026-07-17 when `SubagentScheduler.drain()` landed with the
brain-handoff drain sub-slice, the first of this area's "Blocked on Slice 11" trio to clear now
that its blocker is being built (ADR-0030 decision 4 designed the semantics; the outcome is
recorded at the ADR-0012 drain addendum). It landed exactly as the entry said, an additive port
method composed at the swap orchestrator, plus the reversal verb the entry never named:
`drain(*, timeout_s) -> bool` bounds the wait for in-flight admissions and reports not-clean on
timeout with nothing killed (v1 never kills a subagent mid-stream, so the conductor aborts the
swap before evicting anything), and `undrain()` releases the window in the conductor's `finally`
on swap-back and abort alike. The window refuses instead of queuing, deliberately diverging from
the admission wall's queue-on-transient-fullness philosophy, because a brain-phase spawn queued
against its own drain would deadlock the turn against its own swap; the crux interleaving, a
spawn already waiting on a full budget when the drain begins, is woken and refused rather than
left to sleep through the handoff (mutation-proven, and the drain-resolves-on-release path was
also observed live around a real streaming generation on the compose CPU `llama-server`). The
refusal rides the existing typed `SubagentAdmissionError` the runner already degrades to an
`ok=False` result, which surfaced one text fix: the runner's wrapper claimed every admission
refusal was a permanent misconfiguration, false once a transient drain window exists, so the
cause-specific guidance moved into each raise site's message. CUDA-OOM re-place and the real
GPU-placed runtime stay open below for the model-host sub-slice, per the ADR's mapping.
Three areas each gained one entry on 2026-07-17 from the brain-handoff conductor sub-slice, which
is the backlog working as intended rather than scope leaking: the capability landed, and the
three things it consciously did not do were written down. Inference and model manager went 3 to 4
with **resuming a crashed handoff from its record**, which ADR-0030 names as its recorded
refinement and which is blocked on the same request-identity design the seam-transport reconnect
entry needs, since replaying a deep phase without one risks double-running side-effectful work.
Seam transport went 3 to 4 with **a disconnect mid handoff blocking the stream's teardown**: the
restore is now uninterruptible (a cancellation waits for it) because the chaos suite found that
abandoning it midway left the process with no resident model at all, and the bounded wait that
buys is the deliberate trade, revisited with the in-flight-turn lifecycle. Resource governance
went 5 to 6 with **the drain bound against a fired task's lease**: the shipped defaults make a
handoff requested during a scheduled task abort every time (correctly, before evicting anything),
which is a defaults decision to make against real usage rather than a design change.
Two more areas each gained one entry on 2026-07-18, both from a verification pass over that same
conductor that found no new correctness defect but two deferrals nobody had written down, which
under the doc-first Definition of Done is itself the violation. Inference and model manager went 4
to 5 with **fencing the single-handoff claim across processes**: the rule is enforced by
`SwappingModelManager.handoff_claim`, whose state is one instance attribute, so it binds one
process, while the store-side guard ADR-0030 calls the cross-process backstop is an `active()`
read and a write two awaits later, a check followed by an act. It is not a live defect (the
deployment declares one `brain` service, so the in-process claim is the whole population of
claimants) and it is not cheap either: `put` cannot express "only if no handoff is active", so it
wants a fenced claim verb on the port, an atomic `SET ... NX` under it, and a lease or user id so
a dead holder cannot wedge everyone else, which is a fourth entry whose "behind the unchanged
port" reading would have been wrong. Repo gates went 1 to 2 with **standing test-order
randomization**, the rarer kind of finding: not a defect in the code but in what was claimed about
it. Several repair reports cited `-p no:randomly` as evidence that ordering was controlled for,
and `pytest-randomly` is not installed in either Python workspace, so the flag suppressed a plugin
that was never loaded. The claim was replaced with a measurement rather than an argument (the
plugin supplied for the run only, three seeds over `packages/core` and one over the whole brain
workspace, all green, with the collected order proven to differ between seeds), and making the
shuffle standing was deferred with its trigger.
Resource governance went 6 to 7 later on 2026-07-18, from the pass that made the drain window wait
for the standing residency rather than for the enclosing `finally` to get there first. Closing the
swap generator is what restores the cortex and restarts every evicted tier, and `undrain` runs
after it, so admission cannot reopen mid swap back; what the same reading exposed is that the tier
half of that restore is best effort by design, so **admission reopens even onto a tier that would
not restart**. It is unreachable today (no deployment evicts a tier yet) and its fix belongs with
the residency state the honesty-surfaces sub-slice introduces, so it is recorded rather than
built. The defect behind the pass was real and is fixed, not deferred: the shielded restore waited
for one cancellation, and the seam delivers two.
Resource governance went 7 to 6 on 2026-07-18 when **CUDA-OOM re-place on CPU** landed with the
model-host sub-slice, the second of this area's "Blocked on Slice 11" trio to clear. It is the first
entry here to land while contradicting its own stated premise: the entry (and ADR-0012) said a real
CUDA OOM fails loudly at process start and that a real GPU was needed to trigger it, and the recon
for this sub-slice measured the opposite on the dev GPU, where a 14.4 GB model pinned to `-ngl 99`
on an 8 GB card spills to shared system memory under WSL2 and serves 177 s later. A branch keyed on
an OOM would therefore have been unfireable on this hardware, which is the same vacuous-coverage
defect the entry was written to avoid, so the trigger became any GPU-placed attempt whose backend
did not answer. That widening is not a consolation prize: it is exactly the mitigation the sibling
entry two paragraphs up needs, since a tier the swap back could not restart makes every spawn placed
on it fail at its backend. What stays out of it is deliberate and pinned by mutation (a malformed
constrained reply is not re-placed, the GPU reservation is released before the re-run, and the second
attempt spends the same admission and the same dispatch budget), and the two attempts' taint is
unioned because under-reporting taint costs safety rather than precision.
Two more areas moved later on 2026-07-18 when the rest of that sub-slice landed, the real
`model-host` supervisor sidecar and its compose revision. Resource governance went 6 to 5 with **the
real GPU-placed runtime mechanism**, the last of that area's "Blocked on Slice 11" trio: the GPU
subagent is a hosted tier inside the supervisor container rather than a second sidecar in the
subagents override (ADR-0030 decision 3 relocated it), and the per-container `--cpus`/`--memory`/
`--memory-swap` caps landed on that container and on the CPU one, verified applied by the runtime.
The interpretation that costs something is recorded with it: three tiers in one cgroup means no
per-model cap, only one cap set covering all three, which the security argument buys (a per-model
cap wants a container per model, which wants a controller that can start containers, which is the
docker-socket shape decision 3 rejected). Inference and model manager did **not** decrement, even
though the process-lifecycle half of its oldest entry landed with the same sub-slice, because
co-residency is the other half of that one entry and stays deferred with ADR-0030 decision 8's
brain-runs-alone rule; it went 5 to 6 instead, with **reconverging the brain's residency when the
sidecar restarts under it**. That one was observed rather than reasoned about: killing the daemon
ends its container and takes every child's VRAM with it, `restart: unless-stopped` revives it and its
boot default reconverges, but nothing tells the brain, whose residency bookkeeping is instance state
revisited only at startup. It is invisible with escalation off (the default manager holds no
residency state, confirmed live by a turn answered straight after a restart) and self-limiting with
it on (the handoff fails honestly and releases its claim), so it is recorded with the wire addition
that would close it: a boot id the manager can compare, and `converge_residency` called from
somewhere other than startup.
Two entries elsewhere had claims corrected rather than counts changed, which the sub-slice's own
arrival falsified. **Placement-aware CPU charging** said it reopened with the Slice 11 GPU-placed
runtime; the runtime arrived and did not reopen it, because one hosted GPU tier is still one backend
object per target and the measured serialization argument is unchanged, so the entry now names the
condition ADR-0030 decision 8 actually gives it, a second GPU-capable executor. And **admission
reopening onto a tier that would not restart** said nothing was at stake because no deployment
evicts a tier; a deployment can now name a GPU subagent artifact and list that tier in
`CORTEX_SWAP_EVICT_MODELS`, so it is reachable by configuration for the first time (the shipped
defaults still leave both empty), while its cost fell in the same sub-slice, a spawn placed on a
dead tier now re-running once on the CPU rather than only reporting.

## Recommended order

Ordered by what unblocks the most value soonest. Before starting any item, verify its claims
against the code (the warning above); the entry text tells you which seams it expects to hold.

### Actionable now

None. The last actionable-now item, `cargo clippy` for the Tauri shell in CI, moved to
fix-when-it-bites on 2026-07-16 (see below) once reading what the rust CI job installs (no system
library at all) showed it is not a marginal add but a new class of CI provisioning. Everything
that remains is gated on a seam or port change, on the Slice 11 GPU lifecycle, on host-side
Windows validation, on a consumer that does not yet exist, or is a bounded fix-when-it-bites
contingency. That is the sweep working as intended: no item is left that is both worth doing now
and free of a prior blocker.

### Actionable, but a seam or port change comes first

- **The opaque-turn escalation refusal** ([untrusted-content.md](untrusted-content.md)): the one
  consciously deferred piece of ADR-0030's escalation trigger sub-slice (landed 2026-07-17). The
  refusal is keyed on image-bearing messages and the `opaque` bit, both of which arrive with the
  designed-but-unimplemented vision slice (ADR-0029), so today it has nothing to check and a
  stand-in check would be a gate that cannot fail. Lands with (or immediately after) the vision
  slice's pixel-taint increment: a typed refusal in `escalate.py` telling the model to ask the
  user to retry in a fresh message, so escalation never widens pixel persistence.
- **Session-history summarization + the model-based reranker**
  ([session-history.md](session-history.md), [memory.md](memory.md)): both blocked on a sync
  port going async (`HistoryWindow.select`, `RecallPolicy.select`) and both inherit the same
  non-reentrant GPU-lease hazard, so they are one design problem. The declined blended-relevance
  field widens the same `select` return, so a consumer for it reopens the work here rather than
  on its own. **Audited 2026-07-16:** the async widening is mechanically clean and contained (one
  already-async caller each, no colour cascade, gate-clean under this repo's non-preview ruff) and
  the lease hazard is navigable by the title generator's sequential-drain discipline (the reply's
  lock is not yet held at selection time), so neither is the binding blocker; what binds is that a
  model pass cannot be validated on the 8 GB dev GPU (the cortex tier does not fit) and that
  `select`'s widening should serve its three deferred consumers in one change, so this reopens with
  the real GPU lifecycle.

### Blocked on Slice 11 (real model swap / GPU lifecycle)

- Co-residency, the open half of model-manager process lifecycle, co-residency, and the real swap
  ([inference-model-manager.md](inference-model-manager.md)). The **pure half landed 2026-07-17**
  with the brain-handoff conductor sub-slice (the `ModelHost` port and its scriptable twin, the
  `SwappingModelManager` with its segregated residency scope, the `SwapConductor`, the deep
  model's phase, boot recovery, and the escalating turn wrapper, all proven over fakes by a
  chaos suite that kills a handoff at every step boundary) and the **real process lifecycle landed
  2026-07-18** with the model-host sub-slice: the supervisor sidecar behind that same port, one
  `llama-server` child per tier, mechanism-validated in Docker on the dev GPU with two small
  artifacts (tier scale stays host-side). What stays open is **co-residency**, which ADR-0030
  decision 8 keeps deferred with the brain-runs-alone rule, now exercisable for the first time on
  hardware that fits the tiers it would keep alive.
- Nothing of this area's trio remains here ([resource-governance.md](resource-governance.md)):
  `SubagentScheduler.drain()` **landed 2026-07-17** with the brain-handoff drain sub-slice
  (refuse-not-queue for the handoff window, a bounded wait that kills nothing, reversible via
  `undrain`; see the ADR-0012 drain addendum), and **CUDA-OOM re-place on CPU** and **the real
  GPU-placed runtime mechanism** both **landed 2026-07-18** with the model-host sub-slice, the
  re-place not as a CUDA-OOM check (on this stack an over-committed GPU-placed model spills to
  shared memory and serves rather than failing) and the runtime inside the supervisor container
  rather than as a second subagents sidecar. **Placement-aware CPU charging** joined them on
  2026-07-16, declined where it stood: `admit` is entered before `place`, so the charge cannot see a
  target without a port change, and no spawn is GPU-placed in the shipped wiring anyway. It used to
  say it reopened with that runtime; the runtime landed and did not reopen it, so its condition is
  now the one ADR-0030 decision 8 gives it, a **second** GPU-capable executor.
- The ~31B brain-tier injection-harness run ([untrusted-content.md](untrusted-content.md)).
  Its taint/provenance-persistence sibling **landed 2026-07-17** as the brain-handoff record's
  schema and pinned tainted-ledger round trip (ADR-0030), and the conductor sub-slice then
  exercised that schema across a swap the same day: the deep model's phase rebuilds the ledger
  from the record, so a tainted turn stays tainted and the output guardrail opens over the URL
  evidence the cortex collected (mutation-proven). Only the harness run itself, which needs the
  real ~31B tier, remains here.
- **Streamed brain status** ([body-overlay.md](body-overlay.md)): the push half of the landed
  connection indicator. It waits on a *producer*, not a consumer: `Health` answers ready
  unconditionally today, so nothing can report a state the overlay cannot ask for, and a swap
  that makes the brain not-ready between turns is what would create one. The rule that any
  successful call means the brain is ready expires at the same moment. Half of that producer
  arrived on 2026-07-17: an escalating turn now streams `StatusUpdate(state="swapping")` through
  drain, load, work, and restore on the stream the user already holds (no proto change, the
  overlay renders it as a chip today). The entry stays blocked on the other half, `Health`
  answering `ready=false` with a truthful detail **between** turns, which ADR-0030 keeps in its
  honesty-surfaces sub-slice.

### Host-side Windows validation only

- The real Core Audio "set volume to 30%" check ([body-gateway.md](body-gateway.md))
- Whether a real reminder toast appears and reads well, the one half of the landed `Notify`
  backend no gate can reach ([scheduling.md](scheduling.md))
- Windows-native validation of the confirm card ([untrusted-content.md](untrusted-content.md))
- The OS-window half of the overlay polish: transparent window + click-through, the morph to a
  real screen corner, hide-on-blur ([body-overlay.md](body-overlay.md))

### Dead until a consumer exists

- Structural argument identity in salience: the permuted-key evasion it was filed against is
  already closed by `Mapping.__eq__` (key-order-independent at every nesting level, pinned by
  `test_arguments_compare_structurally_rather_than_by_key_order`, which reddens under an unsorted
  serialization). A schema-free canonical form closes nothing more and its serialized shape
  regresses (unsorted reopens permuted keys, sorted splits `1` from `1.0`), and the cases a schema
  would fold are unsound to fold: JSON Schema `default` is advisory, so folding an omitted optional
  onto it can collapse two calls a tool runs differently and refuse a legitimate call, the
  non-benign failure the two-not-one salience cap avoids. The residual is bounded by
  `MAX_TOOL_DISPATCHES` (32), `MAX_CALLS_PER_ROUND` (16), and the tainted-turn denial (a gated call
  on a tainted turn gets no card whatever its spelling), so no spelling evasion becomes a flood or a
  breach. Declined 2026-07-16; reopens only if a real wired tool shows a semantic-equivalence
  evasion those bounds do not cover, and even then the sound fix is a per-tool domain normalizer
  (the model judgment the ADR rejected), not schema folding ([tools-mcp.md](tools-mcp.md))
- Token rotation / multiple tokens: needs a second seam client ([seam-auth.md](seam-auth.md))
- Trust/gating overrides for remote tools: no trusted remote tool exists
  ([untrusted-content.md](untrusted-content.md), [email-confirmer.md](email-confirmer.md))
- Real-file email attachments (bytes the assistant did not author): declined 2026-07-16, the
  capability kept ungranted. Send exists and attaches only authored text
  (`EmailAttachment.content` is a string composed as a `text/<subtype>` part); the `mcp-email`
  sidecar declares no `volumes:`, so a real file means granting the one outbound sidecar the power to
  read local disk, fusing read-local with write-remote in the process built to leave the machine.
  And the taint boundary already closes the useful path: reading a file's bytes taints the turn and a
  tainted gated send is `DENIED_MSG`, so a useful real-file attachment must bypass taint, which is
  the exfiltration channel itself; a digest-bound card binds the bytes but never the file *choice*,
  which is what an injection controls. Reopens on a real consumer that must attach bytes the
  assistant did not author, built then to the ADR-0022 real-file addendum's scoped-source,
  taint-gated-choice, and digest-bound-card shape, never by handing the egress sidecar a path
  ([email-confirmer.md](email-confirmer.md))
- Confirm-with-provenance for tainted turns: the provenance it waited on landed, so the decision
  it always was got made, and it is to keep the fail-closed block. A gated call on a tainted turn
  returns `DENIED_MSG` and never consults the confirmer (observed in `dispatch.py`, with an
  approving-confirmer test asserting it stays unconsulted), so there is no card to add a source
  line to; letting one reach the card reopens the path an injection aims for, to save the one extra
  turn the taint-is-turn-local flow already costs, which the ADR accepted. The only provenance
  captured is attested (`TOOL`/`MEMORY`), which names the user's own tool use, not the attacker; a
  `SENDER` producer that would name the attacker landed later the same day (the sidecar-declared
  sender), so one of the two reopen conditions is now met, but the other is not. Declined 2026-07-16;
  reopens only if the outbound-on-tainted decision is revisited with evidence a card converts
  reflexive approval into scrutiny, now that a real `SENDER`/`URI` producer exists, not on provenance
  plumbing alone ([email-confirmer.md](email-confirmer.md))
- Session+global union read policy and cross-scope recall ranking: nothing writes durable
  global facts under scoping yet ([memory.md](memory.md))
- Self-editing memory (`update` in place), tiered promote/demote/expire, write-salience, and the
  per-scope retention *policy*: the delete/forget verb these were bundled with as their shared
  missing seam landed 2026-07-16 (`MemoryStore.delete_scope`, [memory.md](memory.md),
  [ADR-0008](../adr/ADR-0008-memory-v1.md)), so what remains is policy with no consumer, not a port
  change. Per-provenance eviction wants a different filter (a record stores only the taint bit, not
  ADR-0027 structured provenance), so it stays fix-when-it-bites, not here. Reopens when a
  memory-compaction or self-editing feature needs them ([memory.md](memory.md))
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
- **Pointer-input injection**: declined 2026-07-16, dead until a consumer. The entry read as a
  small pointer increment over an existing text/keyboard input-injection capability, needing only a
  proto extension, but input injection is unbuilt at every tier: the `InjectInput` RPC and its
  `TypeText`/`KeyChord` messages are Slice 2 forward-looking stubs (like `CaptureScreen`), there is
  no `body_core` input trait (only `Hotkey`/`AudioControl`/`Notify`), no `os_windows` adapter, the
  body server answers `inject_input` with `Status::unimplemented` (pinned by
  `capture_screen_and_inject_input_are_unimplemented`), the brain's `BodyGateway` carries no inject
  method, and no tool drives it. So pointer is part of the whole input-injection slice ADR-0023
  defers, not a refinement over a built base, and it is the highest-harm OS action to ship
  speculatively: a model-driven pointer is irreversible machine control whose gate is a `gated=True`
  audited tool inheriting the tainted-turn denial (`dispatch.py`), so building the Windows
  `SendInput` adapter ahead of that tool would let the body move the real mouse for anyone holding
  the seam token. Reopens with a real consumer, built then as one slice (the whole InputInjector
  trait, text plus keyboard plus pointer, behind one gated tool, one `SendInput` adapter under a new
  `unsafe` authorization, and one proto pointer extension whose coordinate space, buttons, and
  scroll are designed against that use) ([cross-cutting.md](cross-cutting.md))
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
  a queryable history wants. **Its one-shot-*task* half narrowed 2026-07-16** when task-outcome
  delivery landed: a fired task now finishes deliverable, so its outcome survives its fire (until
  acked) instead of being deleted with the record; the reminder-side unseen-toast gap and the
  queryable series history stay open ([scheduling.md](scheduling.md))
- A task/reminder distinction on the pull surface: opened 2026-07-16 behind the landed task-outcome
  delivery, which reused the `DueReminder`/`Reminders.tsx` reminder card for a task's outcome with
  no wire change. The reuse is safe (a task outcome is a store row no guardrail saw, badged if
  tainted, nothing linkified, the reminder card's own posture), but the outcome reads as a reminder:
  `DueReminder` carries no `kind` and the overlay labels the stack "Due reminders". Telling them
  apart is a `kind` (or distinct field) on `DueReminder` plus overlay rendering, a proto + four-tree
  + overlay change. Dead until the surface must distinguish them (a task icon, a "task ran" label, a
  task-only action), not built speculatively ([scheduling.md](scheduling.md))
- **Toast activation routing**: sharpened 2026-07-16, dead until a second consumer of toast
  interaction. Clicking a toast does nothing, and the obvious fix (route the overlay to the
  reminder's origin chat) has no reader but a host-side Windows one, so adding the `session_id` it
  wants to `NotifyRequest` now would be the dead wire this sweep declined repeatedly. The push path
  is fire and forget: `_deliver` reads only `shown` (`ticker.py`), the gateway returns only
  `reply.shown`, the body's `OsService.notify` builds a `Notification` and discards all but `shown`
  (`body/crates/rpc/src/server.rs`), `WindowsNotify.show` renders a fire-and-forget toast read back
  by nothing (`body/crates/os_windows/src/notify.rs`), the Linux/macOS backends are
  `unimplemented!()`, and the overlay never sees the call (it is a `BrainService` client, while
  `Notify` is a `BodyService` RPC the body serves, so nothing under `body/app/src` references it).
  The only reader of any toast payload beyond `shown` is the `cfg(windows)` `toast_xml`, never
  measured in CI, and the only thing that could act on a clicked toast is a COM activator that does
  not exist. The two-part design (the `NotifyRequest` `session_id` plus its `launch` embedding, and
  the COM `INotificationActivationCallback` with a shell-to-overlay activation channel) and the
  trigger (a second toast-interaction consumer, snooze-from-the-toast, that shares the COM cost, the
  field then designed with its reader) are recorded in the area doc and its origin ADR
  ([scheduling.md](scheduling.md))
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
- **Out-of-window authoritative title**: opened 2026-07-16 behind the overlay-only header-title
  carry that closed the open-chat consistency item. The carry reads the header title from the loaded
  `state.sessions`, so a chat outside the loaded recency window (reachable today only by a reminder
  deep-link to a chat past `listSessions(50)`) still derives its header locally. Not user-visible:
  the switcher has no row for an out-of-window chat, so no header/switcher disagreement can be seen,
  which is why the overlay-only carry was preferred over the proto field. The closure is the `title`
  field on `GetSessionMessages` the consistency entry named, the same read path the reasoning-persistence
  entry above independently wants widened; reopens with a consumer that opens an out-of-window chat
  beside the switcher (toast activation routing once `NotifyRequest` carries a `session_id`, or a
  search / deep-link by id) ([session-read-seam.md](session-read-seam.md))
- Provenance across the stores: `ScheduledItem` and `SubagentResult` each carry the taint bit
  and no sources, so a fired task's stamp and a subagent's own readings attribute nothing back
  ([untrusted-content.md](untrusted-content.md))
- Structured redaction event for the overlay: the guardrail's inline `[link removed: untrusted
  source]` marker already surfaces the redaction in context and durably (it is part of the persisted
  reply, so it survives reload), whereas the proposed `StatusUpdate`-shaped event is ephemeral by
  contract and the status chip drops on settle, so it would be dead on reload and nothing in the
  overlay consumes it; a safe event could carry a count but never the redacted URL, and the count
  adds nothing the visible markers do not. Its real cost is the `OutputFilter.feed` port widening.
  Both the marker in the guardrail output and the overlay rendering it verbatim were observed live.
  Declined 2026-07-16; reopens only if the overlay grows a redaction surface the inline marker cannot
  serve (a persisted count badge, distinct styling), which needs a durable channel designed with its
  record, not the ephemeral status one ([untrusted-content.md](untrusted-content.md))
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
budget / circuit-breaker, joined on 2026-07-16 by a retryable-code table beyond `Unavailable`
(whose trigger is a brain that starts answering `RESOURCE_EXHAUSTED` or `ABORTED`) and, the same
day, by safe `converse` reconnect-before-first-event (sharpened from "a replayable request and a
signature change" into the store-backed dedup/resume protocol a no-double-run version would need,
whose trigger is routine mid-turn evictions once the real model swap lands plus turns costly enough
that a silent re-run beats paying for dedup) ([seam-transport.md](seam-transport.md)); multi-turn-within-one-stream
plus a client-sent `Cancel`, moved here on 2026-07-16 when the entry was read against the code and
found proto-and-server complete (the proto `Cancel` and the whole multi-turn+cancel server path exist
and are proven, lease release on mid-inference cancel included), leaving only body-side glue whose two
parts are coupled (a client `Cancel` on the one-turn-per-call body ends the stream on a `Protocol`
error, so it cannot cleanly precede body multi-turn, which itself carries the per-turn-confirm-keying
knock-on), and whose trigger is the same Slice 11 model swap: today's Stop mutes the sink without
aborting the RPC, so the brain finishes the turn and persists the full reply, adequate while compute is
cheap and worth a real abort only when a swap makes mid-turn compute expensive
([body-overlay.md](body-overlay.md)); the tunnel
fallback, the
hardened non-loopback posture, a safe Core Audio wrapper, and the unbalanced COM
initialization the blocking-pool hop made visible, whose trigger is a COM failure or thread
growth on Windows after a long session
([body-gateway.md](body-gateway.md)); paging/cursor and the live-suite fixed-window residual
([session-read-seam.md](session-read-seam.md)); the Postgres durable twin, cron expressions,
and automated dead-letter retention, joined on 2026-07-16 by the push retry policy beyond
next-poll-pull (sharpened when task-outcome delivery landed: the safe retry is the
deliverable-until-acked pull, and a proactive re-push double-delivers because a stable
`reminder_id` cannot tell a retry from a legitimate re-fire, so it wants the per-fire delivery id
the declined occurrence-history record would carry; its trigger is a body reconnecting between a
failed push and the next overlay open often enough that a stuck-until-open outcome is a real gap)
([scheduling.md](scheduling.md)); MTP variants and the
disable-thinking / token-budget caps ([inference-model-manager.md](inference-model-manager.md));
the ANN index, and recall observability, whose trigger is a visibly wrong recall no one can inspect
after the fact ([memory.md](memory.md)); the four guardrail tails (whitespace-split hosts, full
UTS-39 confusables, further encodings, footer heuristics), the GBNF alternative, the
fence-without-block recall mode, per-provenance eviction, and the screening subagent
([untrusted-content.md](untrusted-content.md)); per-field attachment schema descriptions and
send batching / session allowlists ([email-confirmer.md](email-confirmer.md)); the NPU as a
third placement target pending its feasibility pass, plus the two the admission wall opened,
a bounded admission wait and a read timeout on the subagent HTTP client, whose triggers are a
turn observably stalled in admission and a wedged `llama-server` stream respectively, joined on
2026-07-18 by admission reopening onto a tier the swap back could not restart (the drain window
now waits for the standing residency, but restarting an evicted tier is deliberately best effort,
so a tier that refuses to come back is logged and admission reopens onto it anyway; nothing is at
stake until `CORTEX_SWAP_EVICT_MODELS` is non-empty, and the fix wants residency state the placer
can skip a downed tier by, not a scheduler change)
([resource-governance.md](resource-governance.md)); fencing the single-handoff claim across
processes, opened here on 2026-07-18 because today's deployment runs one brain process, so the
in-process claim covers every claimant there is and the racy store check backstops nothing that
exists, whose trigger is a second process able to swap (a replica, a worker sharing the Redis, or
a swapping supervisor sidecar) and whose fix is a fenced claim verb on `HandoffStore` with a lease
([inference-model-manager.md](inference-model-manager.md)); standing test-order randomization,
opened here the same day when `-p no:randomly` turned out to name a plugin neither Python
workspace installs, whose trigger is a test that passes alone and fails in a suite and whose fix
is adding `pytest-randomly` as a dev dependency ([repo-gates.md](repo-gates.md)); shell `cargo clippy` in CI, moved here on
2026-07-16 when reading what the rust CI job installs (no system library at all) showed it is
not a marginal add but a new class of CI provisioning, the 630-package Tauri webkit-dev apt
closure (uncacheable per job) plus a cold Tauri-graph compile, disproportionate to the
occasional lint on 881 lines of host-validated thin wiring, whose trigger is CI gaining the
Tauri desktop stack for another reason (a future CI-side Tauri build or smoke job) so shell
clippy rides along, or shell findings outpacing the user's local checks; confirmed clippy-clean
live over a `pkg-config` shim, with a planted lint proving the declined check real
([repo-gates.md](repo-gates.md)).

### Feature breadth, on request

- macOS/Linux OS backends behind the existing traits ([cross-cutting.md](cross-cutting.md))
- More subagent roles ([cross-cutting.md](cross-cutting.md))
