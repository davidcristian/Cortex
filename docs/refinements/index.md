# Deferred refinements: index

Every consciously deferred refinement, one self-contained doc per area, extracted verbatim
from the ROADMAP's "Deferred refinements & later work" section on 2026-07-15. Recording a new
deferral here (in its area doc, on this index, and at its origin ADR) is part of finishing a
slice, per the doc-first Definition of Done in [AGENTS.md](../../AGENTS.md); this backlog must
be empty before the ROADMAP's finish line is crossed. Landed entries stay in the area docs as the
historical record of what each deferral became, and several deliberately correct their own
ADRs, which is why the entries are kept verbatim rather than summarized.

**What is not here.** Work that is already built and is waiting on hardware this repo is not
developed on lives in [docs/host/](../host/index.md), extracted from here and from the ROADMAP
on 2026-07-19. The distinction is what kind of not-done an item is: a refinement is built-around
and anyone can pick it up, a host item is built and unrun until it meets a real Win32 desktop
session or a 24 GB GPU. Both must be clear before the README ships.

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

**And an entry's own account of the CODE goes stale the same way, which is worse.** The warning
above is about cost estimates; on 2026-08-06 it landed on itself in the harder form. The composer's
move on a clamped shrink ([body-overlay.md](body-overlay.md)) described a mechanism deleted thirty
two minutes after the entry was written, was restated twice on its own text, and was put to the
user twice as a decision that had not existed since the day it was filed. Two sittings in this very
file measured the closure and recorded it as a null result, because they were checking that their
own change had not moved the composer rather than asking whether anything still did. So: before
starting an entry, and before quoting one back to the user, re-derive its claim from the code and
from a running build. An entry is a record of what somebody once measured, never a reading of what
the tree does now.

**And a count that is right by cancellation hides both of its errors.** The two warnings above are
about an entry's own text; this one is about the arithmetic that navigates to it, and it was earned
on 2026-08-06 by [body-overlay.md](body-overlay.md), whose Open items line had drifted twice in
opposite directions. It still named an entry that landed on 2026-08-03 and it had never picked up
one that opened on 2026-08-06. Eleven names either way, so that header and its cell in the table
below agreed at every moment, and the agreement was worth nothing: a reader following it would have
opened a closed entry and never seen an open one. A count is a checksum over a set, and two errors
of the same size in opposite directions are the one thing a checksum cannot see. So a header and a
cell matching says nobody has miscounted; it does not say either names the right entries, and the
only check that catches this is reading the entries the line claims to summarize. The other half of
the lesson is the memory row, which read 7 for a day because the close that struck two landed
entries from it never added the two it opened, and there the count did move and moved the wrong way.

## The docs

| Doc | Area | Open |
| --- | --- | --- |
| [repo-gates.md](repo-gates.md) | Line cap (the core barrel came off it 2026-08-06, split into area sub-barrels under `cortex_core._surface` with every call site unmoved, ADR-0026), dashcheck, coverage config (ADR-0026), gate coverage of the ungated Rust trees and of the overlay's TypeScript (ADR-0011), the stylesheet still outside the cap, test-runner mechanics (ADR-0002), whose live runs now each own their store after the pgvector one took the `cortex_contract` database 2026-08-06 and the Redis ones took a logical database 2026-08-03, the couplings the cross-language constant scan does not hold yet (ADR-0029), and the compose bind defaults that land in the repo tree, whose two live cases were ignored 2026-08-06 while nothing checks for a third | 6 |
| [seam-transport.md](seam-transport.md) | `BrainTransport` retry/reconnect (ADR-0003/0024) | 4 |
| [seam-auth.md](seam-auth.md) | Seam token auth (ADR-0016) | 1 |
| [session-history.md](session-history.md) | Slice 3 history windowing and summarization, the recap's fold made cheap 2026-08-06 (thinking off and a token cap per request, a floor under a fold, a chip while it runs) and `CORTEX_HISTORY_SUMMARY` moved to on, leaving one open item, restated 2026-08-08 as the half of the one-corpus entry that a run can actually settle: nothing has been measured about a cortex under load, while the corpus being hand built by the feature's author is an authorship caveat that no corpus this repo can build retires (ADR-0014/0038) | 1 |
| [tools-mcp.md](tools-mcp.md) | Dispatch budget/cost/salience, spawn batch cap, MCP registries (ADR-0009/0010) | 6 |
| [untrusted-content.md](untrusted-content.md) | Taint boundary, output guardrail, subagent model safety (ADR-0013/0015/0017/0019/0028), a quoted injection replayed by the plain history window, obeyed 2 of 10 on a bare turn and 0 of 10 behind either standing rule, the plain one landed for the tool-less turn (ADR-0013/0038) | 12 |
| [memory.md](memory.md) | Store, scoping, rerank/MMR, the ranked `select` and its recall trail, and, since the user asked for the end-to-end turn cost before calling it and got 0.515 s of time to first token against a control whose interval spans zero, the judge's default no longer among them: `CORTEX_MEMORY_RECALL` ships as `judge` from 2026-08-08 and `raw` is the opt-out. What is left is the two the ranked-recall close opened and neither this cell nor the area header picked up until 2026-08-06, a cross-encoder rank and an audit of the candidates a rank drops, and, since the judge learned to decline on 2026-08-07, the gap that close named rather than the one it shut, whose premise the flip inverted without closing it: a deployment that opts back out to a geometric policy still hands a turn its nearest misses on a question memory cannot answer (ADR-0008/0038) | 9 |
| [inference-model-manager.md](inference-model-manager.md) | Model-manager lifecycle, MTP, reasoning status, whose disable-thinking and token-cap halves now reach every pass that discards its own deliberation, leaving the user-facing reply as the whole of that entry and the count unmoved for a narrowing (ADR-0007/0020/0038), and, since co-residency closed 2026-08-07 on a card that could finally test it, the two that close opened, of which the first closed hours later the same day: the co-resident deployment's fit is now measured against the card at the one instant it can be, immediately before the load, and the placer's budget stopped naming a cortex the handoff evicted the same day, charging the deep tier's declared cost at the two edges of the swap instead, which leaves the half neither a room check nor an epoch can see, a handoff that spilled anyway and whose only witness is decode rate (ADR-0030) | 7 |
| [subagents.md](subagents.md) | Progress reporting, spawn schema, heterogeneous roster (ADR-0010/0018), and, since the delegated tool step was declined 2026-08-07, nothing left on the outcome path but the record of why a delegated activity is never settled (ADR-0029) | 2 |
| [body-overlay.md](body-overlay.md) | Overlay polish, connection indicator, proto Cancel (ADR-0011), the reserved scrollbar rail's assumed width and spent card inset, the two bounds the panel's section budget left behind it (a section's own frame being under no cap, and the room a closing section hands back arriving in one frame), the liquid edge's backdrop blur, and the whisper's follow-ups (ADR-0037): a pickable voice row, a mid-stream resize keeping the old wrap width, and kerning inside the letter boxes under a changed font (its drain-growth entry landed the day it was filed, and the console outliving a new chat, the reminder stack's per-row exit and the switcher's, the panel's watch on its own box with the arrival-aside correction that came out of it, the demo bridge over the line cap, two sections outrunning the panel on their own, the chat floor's frozen measurement of the empty state, the console tab strip's missing keyboard half, the switcher's disputed listbox role, the two motions its list still made in one frame, and a Thoughts trace opening a reply off the bottom of a full history all landed 2026-08-03, the last of them opening the chrome-side entry that landed 2026-08-04 on the same ride, alongside the cycle keys' silent swap, which opened the focus entry that landed 2026-08-06 as the caret following the conversation into the composer and opened two entries behind it, both landed the same day: the draft named below, and the row gestures that swap nothing, answered by the caret staying in the list and opening the chord and the silent-shrink entries above; the composer's move on a clamped shrink closed 2026-08-06 as moot, its mechanism having been deleted the day it was filed, and the retarget-and-resize pair landed 2026-08-06 as the panel measuring itself in fractional pixels, opening the roll entry that took its place, which landed hours later the same day as the section measuring itself the way the panel does, both published numbers reproducing first and the step at every roll boundary reading 0.000px after, and which opened the whisper-bubble target named above; the composer's draft belonging to no chat landed 2026-08-06 too, the same day it was opened and the same day the user answered it, as unsent text keyed by session id in the reducer, which was the last entry anywhere waiting on a decision rather than on work; the modified chord landed 2026-08-07 as a rule about the text a field would lose rather than about what a chord is, opening the two entries named above, the closing-list caret and the silence of a held chord, and reading this file's entries against its header that day turned up the liquid edge's blur, open here since 2026-07-21, carried in the running record below the whole time and named by no count either doc has published since; and the silent shrink landed 2026-08-07 as the region reporting a list that shrank as well as a conversation that arrived, one out and none in, its chord sibling read alongside it and deliberately left open, and the part only a real screen reader can settle sent to [host/overlay-screen-reader.md](../host/overlay-screen-reader.md); and the whisper bubble's rounded roll target closed 2026-08-07, measured before it was touched as its own text demanded: the published number sat exactly half a pixel under the height the box stands on, no frame of a reply showed the panel moving without the bubble moving it, and what the trace found instead was the prediction doubling as the panel's pinned edge on a summon that lands inside the roll, 316.59375px where the measured height centres at 316.34375px, so the roll now publishes the number its own box carries; and a list the reader closes dropping the caret closed 2026-08-07 as a rule about a section closing rather than about a key, the switcher turning out to close thirteen ways of which ten already answered, opening the mirror entry that closed hours later the same day, with the caret DECLINED on three measured reasons and a sentence landed in its place, the switcher opening thirteen ways of which eleven were inaudible, and opening the key toggling an unseen section named above; and its chord sibling was DECLINED outright 2026-08-07, all four of its shapes, on the measurement that the rename editor holds every chord there is and that seven of the nine measured do something in the field anyway, `Ctrl+Z` undoing the whole edit, so a sentence raised where the hold is decided would be false at most of its doors; and `Ctrl+K` toggling a section nobody can see landed 2026-08-07 as a rule for the whole key table, which is six global keys on one listener of which four already landed where they act: a key aimed at one of the panel's surfaces now puts that surface on screen and off the chat opens rather than toggling, and the entry named one broken key where the table had two, `?` mounting the console behind a panel that was not on screen exactly as `Ctrl+K` mounted the list) | 10 |
| [session-read-seam.md](session-read-seam.md) | Session listing/read seam, the generated title's empty-reply half closed 2026-08-06 by bounding its request (ADR-0021/0038) | 2 |
| [resource-governance.md](resource-governance.md) | Scheduler/placer budgets, NPU, drain (ADR-0012); the cortex reservation was re-measured on 2026-08-07 at the tier's shipped shape and lowered from 11.3 to 8.6 GiB, and the placeholder that correction uncovered was measured the next day and closed, the subagent VRAM ask landing at 3.5 GiB in both of its declarations, so the shipped stack GPU-places a spawn for the first time and every term of that budget is now a measurement | 5 |
| [email-confirmer.md](email-confirmer.md) | Email write, Confirmer, attachments, `ToolActivity` chip (ADR-0022) | 4 |
| [body-gateway.md](body-gateway.md) | Body gateway, OS actions, hardened posture (ADR-0023) | 5 |
| [scheduling.md](scheduling.md) | Scheduling and reminders, `TurnStamp` provenance (ADR-0025/0027) | 8 |
| [vision.md](vision.md) | Screen capture, images, the pixel boundary (ADR-0029) | 12 |
| [cross-cutting.md](cross-cutting.md) | Pointer input, OS backends, more roles | 3 |

The counts are per area as extracted; a few threads appear in two areas (the cross-cutting
"richer memory policies" line is covered by memory.md's items, and subagent tool-step
surfacing appeared in both email-confirmer.md and subagents.md as one piece of work, closed
2026-07-16 by landing one side channel that decremented both counts). A third such thread was
found on 2026-07-19 and is noted here rather than decremented, the same treatment the other two
get: **per-remote-tool trust and gating overrides** is counted in untrusted-content.md and again
as "trust overlays for remote tools" in email-confirmer.md, one piece of work waiting on one thing
(no trusted remote tool exists), and the bucket below points at both docs for it. Until it lands
or is declined, the sum over the table counts it twice.
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
That entry closed on 2026-07-18 with that very increment, taking untrusted content back to 13:
the `opaque` bit landed and the handoff record refuses an image-bearing loop tail the way both
session stores do. The entry's own expectation needed one correction, which is the usual lesson:
it assumed the refusal would key on image-bearing messages, but the handoff codec enumerates
message fields by name and would have dropped `Message.images` silently, so the only signal that
survives the trip is the bit.
It needed a second correction on 2026-07-19, from the audit of that slice, and the closure text
here was wrong in the way this file exists to catch. The refusal shipped **in the escalation
tool**, where it could never fire: `TaintLedger.observe` cannot mark a turn opaque without
marking it tainted, and that tool is gated, so the dispatcher's hard-deny answers every
escalation after a capture before `invoke` runs. Its test reached the branch by calling `invoke`
directly and its "control arm" ran with `tainted=False`, so nothing measured the bit; the
deferral had been closed with exactly the gate-that-cannot-fail it was recorded to avoid. Worse,
the ordering that *is* reachable was unhandled: an approved escalation followed by an ungated
capture reached the record snapshot, whose image invariant raised out of the conductor and killed
the whole Converse stream. The refusal now lives in `SwapConductor._prepare`, keyed on the same
bit, answering a fixed note beside the already-active and store-failed ones, pinned end to end
through the real loop, the real tools and the real conductor; the dead check in the tool is gone
and the taint gate is named as what closes the other ordering. The entry stays closed, and
untrusted content stays at 13: what the fix opened is recorded under vision, not here.
Vision went 15 to 18 the same day, all three from that audit rather than from new work: carrying
a picture (or at least the `opaque` bit) across a swap, which ADR-0029's own Deferred paragraph
named and the closeout missed; an outcome-driven capture indicator, since the overlay's dot is
lit by a pre-dispatch chip and can only honestly say the assistant *asked* to look; and the
host-side Windows validation of the capture path, which was on the ADR's host-only list with no
backlog line of its own.
Body gateway held at 6 on 2026-07-19: its `CaptureScreen` half closed with the vision slice, but
the entry names the remaining `BodyService` RPCs and `InjectInput` is still unbuilt, so the count
does not move until it lands. A cell decremented for a half-closed entry is how an open deferral
gets lost.
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
generated title. **The truncation third of that was overclaimed, and settled 2026-08-03**, found by
the survey behind the cross-language constant scan rather than by a backlog entry. The carry runs
in `headerTitle`, which only a chat being *loaded* reaches; the chat being *had* takes its header
from `turnState.submit`, which derives locally at the overlay's own bound and never revisits it. So
a brand-new chat kept a 32-char header while the turn-completion refresh listed the same first
message at 48 in its own switcher row directly below, measured in Chromium at 42 characters against
33 in a header box that fits 42. The overlay is 48 now, the two declarations are the constant scan's
third registered pair and its first in TypeScript, and the gate was proved to fail on a divergence
before being trusted (ADR-0021 truncation addendum). The area count does not move: this corrects a
landed entry and narrows the residual below rather than closing one or opening one. The entry (and
this index) undersold the carry by claiming it misses adoption and
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
fix-when-it-bites residual behind it, recorded as unverifiable on the 8 GB dev GPU where the cortex
tier does not fit, **which was false and is struck 2026-07-19**: that card runs the real cortex, and
the probe is agent-runnable and now sits under actionable now.
Subagents then went 2 to 1, and email & confirmer 7 to 6, on 2026-07-16 together, when
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
elsewhere, and the 2026-07-16 audit named the wrong "elsewhere" first: it said a model pass cannot
be behavior-validated on the 8 GB dev GPU where the cortex tier does not fit, **struck 2026-07-19**
because that card holds the cortex. What is left of it is real and is enough: `RecallPolicy.select`'s
widening should serve its three deferred consumers (a model rank, the declined blended field, a
recall-observability sink) in one change rather than go async alone now, and summarization's
cache-versus-recompute question is undecided, so both reopen on that design work rather than on
hardware.
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
The audit round on that sub-slice, later on 2026-07-18, moved no counts and corrected two records.
The **real GPU-placed runtime mechanism** had been declared landed with two of its three required
records, the area doc and this index, pointing at ADR-0030 for the decision that relocated it; its
own origin ADR got nothing, while the same file's `drain()` and re-place landings both did. It now
has an ADR-0012 host-half addendum, which is the third place and the one a reader of that ADR's
deferral paragraph reaches. And the entry's claim that `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at the
hosted tier was false: that variable still defaults to the CPU server, deliberately, so hosting the
tier and routing to it are two settings and the entry now says so, with the three-setting opt-in
written in the gpu override's checklist and the subagents runbook.
That round also opened one entry, so inference and model manager went 6 to 7: **checking the
sidecar's stop bounds against the brain's control deadline** rather than only documenting the
pairing. The pairing turned out to have a third term (a `status` queued on the same per-model lock
probes inside it, so the probe timeout is added to a stop), the shipped defaults clear the deadline
with 15 s to spare, and the repair added `GET /health` reporting of the two stop bounds, which is
the half that makes enforcement newly possible. Enforcing it is deferred with its trigger, because
the brain would then have to depend on the sidecar answering at wiring time, which today it
deliberately does not.
Body & overlay held at 3 on 2026-07-18 when the honesty-surfaces sub-slice made `Health` read
residency, which is not a count change but is the biggest movement of the day: **streamed brain
status** was the last entry in this backlog blocked on a *producer*, and it is not any more.
The rule the connection indicator shipped on ("any successful call means the brain is ready") has
expired exactly where the entry predicted it would, and the amber Degraded path it shipped shaped
and tested finally has something to show, with zero overlay change. The entry moved from "blocked
on Slice 11" to "actionable, but a seam or port change comes first", where what it now waits on is
honest: a push RPC is proto plus both stubs plus a consumer that needs the brain to speak first,
which probe-on-summon and the escalating stream's own chips do not yet make anyone want.
Two adjacent entries were re-read against what actually landed rather than left to imply their own
blockers cleared, since both name "the residency state the honesty-surfaces sub-slice introduces".
Neither cleared: the state that landed is one published report about what the GPU is serving, with
no per-tier down-ness (so **admission reopening onto a tier that would not restart** still has
nothing to skip a dead tier by) and no staleness generation (so **reconverging the brain's
residency when the sidecar restarts under it** still has nothing to compare a boot id against, and
gained a second way to go stale: an operator who fixes the GPU by hand leaves the report saying the
usual assistant could not be reloaded until the brain restarts, which the runbook's recovery already
ends with). Both say so in their own entries now.
The audit round on that sub-slice, still 2026-07-18, moved one count and closed a hole this
backlog never held. The hole first: `Health` had been made honest about every window a *swap*
goes through and none that a *boot* does, so a brain whose boot recovery could not settle the
cortex logged "the cortex is not serving" and then answered ready from the same process, which
is the one machine state where a green dot is reached through the runbook's own mandatory
restart. Boot recovery now answers whether it observed the cortex serving and the composition
root publishes that, which is a repair rather than a deferral and so decrements nothing. What it
does change here is the shape of the sidecar-restart entry two paragraphs up: the report now has
a second writer, and a second, opposite staleness (an amber that outlives a GPU which came good
on its own), both recorded there because one fix closes them.
Repo gates went 2 to 3 with **checking the commit body's 72-column wrap**, measured rather than
assumed: `scripts/commitlint.py` gates the header length only, and every one of the seven most
recent commits at that moment had body lines past 72, the worst at 77. It is recorded rather
than fixed because the two-line version would be wrong: a URL, a pasted command, a code fence
and a `BREAKING CHANGE:` footer must all survive a hard wrap, so the exceptions are the design
and the drift is cosmetic until something reads a message in a narrow pager.
Repo gates held at 3 on 2026-07-19 when that very entry landed and opened one behind it, the
backlog working as intended: `scripts/commitlint.py` now measures every line below the header
against `MAX_BODY_WIDTH = 72` in the walker that already read each line for dashes and volatile
references. What opened is the rest of the exception design the entry called "the whole reason
this is not a two-line patch". Four classes were named and one shipped, because the exemption that
landed is a property of the longest **word** (a URL, a path, a long identifier has nowhere to
break) rather than of the line's **kind**, and a pasted command or a fenced line is made of
ordinary short words. Measured against the shipped gate rather than assumed: an indented
`docker compose ... up -d` line at 108 chars, a fenced `uv run pytest ...` line at 82, and a
`BREAKING CHANGE:` footer of short words at 118 draw three complaints and exit 1. The footer is
the one that bites hardest in principle, since [AGENTS.md](../../AGENTS.md) mandates it for a
breaking change, so the gate can refuse a message the commit rules require; it is also the one
that can simply be wrapped, while a command and a fence cannot be reflowed without changing what
they say. That landing also cost this file a record: the same commit changed a gate's behaviour
and touched no deferral record at all, the first in fifty to do so, which is what the doc-first
rule exists to prevent and why three records moved on 2026-07-19 rather than one.
Subagents went 1 to 2 on 2026-07-19, an **arithmetic correction rather than new work**. The
spontaneous-pick nudge's live uptake opened on 2026-07-16 as a fix-when-it-bites residual, is
written up in its area doc, and is listed in the fix-when-it-bites bucket below, but the cell
never counted it: the narrative above shows the slip, two entries closing and one opening moved
the count 4 to 2 rather than 4 to 3, and the following decrement then took it to 1 instead of 2.
Every other area counts its fix-when-it-bites entries, so this was a slip and not a convention. A
count that fails to move for a newly opened deferral loses an open item exactly the way a count
moved for a half-closed one does.
Vision went 18 to 19 the same day with **the two agent-Docker validations the slice listed as
still to run and nothing tracked**. ADR-0029 named four when it was accepted; two ran and are
recorded in its 2026-07-18 agent-validation section (the real `LlamaCppBackend` path, the
injection arm on the shipped payload), and two did not: whether thinking needs disabling on a
vision turn under the shipped parts payload, and `llama-server`'s `mmproj`-less error body text,
which that ADR also carries as an assumption because the bounded 300-character non-2xx excerpt was
built to surface it. They are **agent-side, not host-side**: the same 8 GB dev GPU that ran the
2026-07-18 validation holds the cortex beside its projector, so they are work owed here rather
than a user list item. The same pass settled a naming question this area had been carrying
silently: its Open items line reached 18 names by splitting one bullet (region and window capture,
legibility at 4K) into two and dropping another (the accepted residual the guardrail cannot
catch). Both are now stated in the area doc, and the residual is **deliberately not counted**,
because an accepted limitation with no fix on offer would sit forever in a backlog that must be
empty before the README ships; it stays as the record of what was accepted, the role a declined
entry plays.
Body gateway held at 6 on 2026-07-19 while gaining the third of its three records. Its
`CaptureScreen` half closing with the vision slice, and the entry's own "behind the same seam"
cost claim being wrong (five proto fields plus a new port method), had been written here and in
the area doc while [ADR-0023](../adr/ADR-0023-body-gateway-volume.md) still listed the RPC as
deferred to its slice in three places. That is the same two-of-three species the ADR-0012 host-half
miss was caught for, and it is now closed by a dated ADR-0023 addendum. No count moves: `InjectInput`
is still the unbuilt half of that entry.
Resource governance held at 5 the same day with one sentence corrected rather than a count moved.
Its bucket line below read "Nothing of this area's trio remains here", which is true of the trio's
*entries* (all three landed) but read as if nothing at all were owed, while the area doc says
plainly that real GPU-placed **subagent** validation "is the one piece still owed, and it is
host-side". The bucket now says both. That item is not counted, and neither is the Host-Windows
look at a real toast in scheduling.md, while four other areas do count their host-side validation
item (body gateway's volume check, vision's capture path, untrusted content's confirm card, body
and overlay's window polish). The inconsistency is recorded rather than resolved here: adding two
cells now and removing six later would be churn, and where host-side validation is tracked is a
decision this pass deliberately did not make.
That decision was made later the same day, and it went the other way from "add two cells": **the
total went 96 to 91 when host-side work was extracted to [docs/host/](../host/index.md)**, one
self-contained doc per sitting with the entries kept verbatim, mirroring this backlog's own
extraction from the ROADMAP. Four cells lost one each (body gateway 6 to 5 for the volume check,
body and overlay 3 to 2 for the window polish, vision 19 to 18 for the capture path, untrusted
content 13 to 11 for the confirm card and the ~31B harness run), and the two uncounted residuals
went with them (the toast look, real GPU-placed subagent validation with the placeholder cap
numbers), so the inconsistency the paragraph above recorded is gone rather than papered over.
Each origin keeps a dated pointer stub, the way the ROADMAP kept one for this directory. What did
**not** move is anything whose work is code, even when only the user can see the trigger: the COM
initialization fix, the nudge's live uptake, co-residency, the NPU, and the two model passes all
stay, because moving them would split a design decision from its area. The bucket below says the
same in the place a reader looking for host work will land.
Body & overlay went 19 to 18 on 2026-08-03, when the user answered the one entry here that had been
waiting on a preference rather than on work: a new chat minted while the console is up now closes
the console, because a keystroke aimed at the conversation should put you in the conversation. The
count moves by one and the code moved by two, which is this file's recurring correction and is
recorded in the entry: `openSession` had the identical hole and Ctrl+Up and Ctrl+Down reach it, so
the fix landed as a rule (a conversation arriving on the panel brings the chat with it) rather than
as the single line the entry priced. Both holes are keyboard-only, the pointer doors into either arm
being the header's pencil and the switcher's rows, neither of them clickable while the console is
covering the chat. The two neighbouring arms that keep the console, a delete fired from a switcher
row and a cold-start adoption, were read at the same time, are unchanged, and now carry their
reasons and a
test that pins them as standing, so nobody closes them later for symmetry. Two things about this
paragraph are worth saying plainly rather than leaving to be inferred. The area's count jumped from
2 to 19 between the 2026-07-19 extraction and here with nothing narrated, because the panel motion,
scrollbar, chat floor, console and whisper slices recorded their new entries in the area doc, the
table, and their own bullets under the recommended order (where each carries its opening date and,
where it applies, its closing one) and not in this block. That is not a lost item, every one of the
seventeen being both counted and written up, but it is why this paragraph reads as though eight days
of work happened between two sentences. And this is one of only two entries anywhere in the backlog
whose blocker was a preference rather than work. The other is the composer's move on a shrink
against the ceiling, also in this area, where two designs have been put to the user and neither has
been picked; it stays open. Both are a reminder that an entry can be cheap and still sit, since
nothing about the code was in the way of either of them. (**Corrected 2026-08-06**: only the first
of the two was ever blocked on a preference. The second was measured against a running build that
day and closed as moot, both of its designs already being delivered, so what looked like a second
standing preference was a stale entry restated. The lesson survives the correction and gains a
sharper one beside it: an entry can be cheap, sit, and also be describing code that no longer
exists.)

Body & overlay then **held at 18 on 2026-08-03**, when the reminder stack's per-row exit landed and
opened one entry behind it, the backlog working as intended: the hook it needed is generic, so the
switcher's rows, which the closed entry named as the other consumer, are now a wiring job with a
mechanism already in the tree. The closure is worth reading for what it corrects rather than for
what it built. **The entry was stale about the defect and right about the fix.** It said acking one
reminder of three deleted that row in a frame; the stack had wrapped each row in its own `Collapse`
since the day after the entry was written, and traced at 60Hz that roll was already correct. What
was left underneath was not motion: the first version held the row by holding the ACK, behind a
300ms timer whose unmount cleanup cancelled it, and the stack is keyed to the chat it belongs to, so
acking a reminder and pressing Ctrl+N inside those 300ms sent no ack at all. Measured over the demo
bridge at 900x900, all three cards were still on screen afterwards and a fresh summon listed all
three again. The same local list never forgot an id, so a reminder that came back, which is exactly
what a lost ack leaves behind, was rendered shut and stayed invisible. So an entry filed as
cosmetic was covering a lost user gesture, which is the mirror image of this file's usual lesson
about cost estimates: the entry underestimated what it was worth, not what it would take. Two live
defects were found by measuring rather than by reading, both introduced by the wrapper the stale
half of the entry did not know about: the stack's `<ul>` had `<div>` children and so was not a list
to a screen reader, and the hairline between two rows is an adjacent-sibling rule that two rows in
two wrappers cannot satisfy, so it had been off since 2026-07-20 (all three rows computed
`border-top-width: 0px`). And one lesson that outlives the feature: the hook's first shape kept its
memory in a ref written during the render, passed every test, and dropped the row on the first frame
in a real browser, because `StrictMode` invokes a render twice and the second pass read back what
the first had written. The overlay runs under `StrictMode`, so its hooks are tested under it now.

Body & overlay then went **18 to 16 later on 2026-08-03**, three panel-motion entries closing and
one opening behind them. The three were the ones the backlog itself described as one pickup, and
two of them were: a placement left
computed for a stale height and the composer's own growth are the same `ResizeObserver` and closed
as one. The third was not, and finding that out is the whole of what this closure corrects. **Two
of the three were materially wrong about themselves, in opposite directions.** The stale-placement
entry asked for an observer that would "retire the event too", and it cannot: measured with the
observer itself, a roll ends without changing the panel's size at all, so `cortex:morphend` produces
no notification and stays as the only thing that says a roll is over. The mid-roll-touch entry
priced itself at 2.1px and blamed a prediction; the prediction is exact by construction, the roll's
current height cancelling out of it, and what was actually wrong was that the ride-along asked
whether the section that is ROLLING is the reminder stack where the placement asks whether the view
being placed HAS one. A stack merely standing in the panel was therefore counted into the arrival's
centring and out of the placement's: measured at 900x1000, Ctrl+N with the switcher list open ran
the panel's bottom edge 97px down the viewport across the roll and back at the end of it, and a
touch inside the arrival window left the session pinned 97px low for good. That is 97px, not 2.1,
and it is a different defect from the one the entry names. Both now count the aside through one
function. The `ResizeObserver`'s own design is the other thing worth reading, since it is entirely
about what the observer refuses: a roll owns the height, a move of the panel's own owns it too, a
reading with nothing behind it is answered with nothing, and the watch is lifted for the frame the
panel writes in, because an observer that resizes its own target inside its own callback is the one
case the specification's depth rule cannot deliver and reports as a loop error (one error event per
keystroke that grew the pill before that last rule, zero after). Two entries that share this ground
and are still open were measured on both sides of the change and did not move: the mid-stream
retarget puts the panel through 2 to 3 animations per reply either way, and the composer holds its
bottom edge at 493 through an ack and a switcher round trip either way, so the preference about a
shrink against the ceiling that the user has twice declined to settle is not settled here by
accident. (**Corrected 2026-08-06**: that second reading was the preference's answer and was filed
as a null result. 493 is the composer's bottom at 640x720 with the panel against its ceiling, and
holding it through an ack AND a switcher round trip is exactly the pair the entry said could not be
had together. The sitting was asking whether its own change had moved the composer, which is a
narrower question than whether anything still did, and the wider one had been answered on
2026-07-20.) The one entry opened is the watch's own refusal stated as work: a resize that lands while
the panel's own ease is running waits for that ease rather than joining it, which costs latency and
not a jump (traced at 900x1000, the residue eases 40px over about 120ms with no step at the
hand-back) and whose real fix is the mid-stream retarget's, since both want a move that can be
redirected from where it is without being restarted.

Body & overlay went **16 to 15 and repo gates 3 to 4 on 2026-08-03**, from a finding that is about
this backlog as much as about the code. Reviewing the day's landed change turned up a gate that
could not fail: `scripts/linecap.py` had scanned `.py` and `.rs` only since it was written, which
was right while [ADR-0001](../adr/ADR-0001-architecture.md) open question 6 scoped both the coverage
gate and the 300-line cap away from a "kept minimal" frontend, and wrong from the moment ADR-0011's
2026-07-01 addendum reversed that for coverage and left the cap behind. For thirty-three days
AGENTS.md gate 1 stated a rule over a 65-module tree that nothing measured. **What that cost was
paid here, in this file.** Two entries tracked overlay cap violations by eye across that window and
both drifted, in the two ways an unenforced rule drifts: `bridge/demoBridge.ts` was recorded at 326
on a day it already stood at 351 and was still 351 fourteen days later, and the claim that it was
the only overlay source over the cap was true for exactly one day, `overlay/panelPlacement.ts`
crossing to 304 and then 371 the next morning and sitting there for thirteen days until an unrelated
`ResizeObserver` change took it to 295 by accident. Neither cost anything but its own accuracy,
which is the point: an unenforced rule fails silently, so the backlog that exists to catch lost
decisions was itself the thing keeping the lost decision. The cap now covers `.ts`/`.tsx` with
Vitest's own notion of a test file as its exclusion ([ADR-0011](../adr/ADR-0011-body-v1.md) line-cap
addendum) and `demoBridge.ts` was split rather than exempted, which decrements body & overlay. What
increments repo gates is what turning the gate on made visible: `overlay.css` at **2420 lines**, the
longest hand-written file in the repo, still outside the cap on an argument about cascades that is
honest about the remedy and evasive about the problem ([repo-gates.md](repo-gates.md)). The proto is
the other thing outside, and it is a decision rather than a deferral: capping `proto/body.proto`
(314) would put a gate in direct conflict with AGENTS.md's own invariant that the seam is defined
once, in one file.

Vision went **18 to 17 and repo gates 4 to 5 on 2026-08-03**, from the third cross-tree scan
landing beside the other two, and the entry that asked for it turned out to be wrong about itself
in the direction that matters. It claimed the two byte ceilings had "nothing mechanical coupling
them: an edit to one leaves both suites green". Measured before building anything, per this file's
own warning that a cost claim is a hypothesis: an edit to `MAX_CAPTURE_BYTES` **alone** fails
`body-core`'s suite at exit 101, because that side pins its own literal. What actually drifts is an
edit to the constant and its pin together, which is the ordinary shape of a deliberate change to
one side rather than a careless one, and with both raised to 8 MiB the Rust and Python suites are
all green while the trees disagree by 2 MiB. So the pin was not weak enforcement of the coupling,
it was enforcement of the wrong thing: a suite can only ever compare a tree with itself. The
estimate held (one small script, `scripts/crosscheck.py`, wired into `just check` and CI's
unconditional `cross-tree` job) but the shape did not. Rather than asserting one pair, it holds a
registry of constants, each naming two or more declaration sites, comparing the sites with each
other rather than against a master so that editing either side alone fails; `proto/body.proto` is
not that master, because protobuf has no constant and a number in a comment there would be a third
uncoupled copy of the kind the 1600 px default edge already has four of
([ADR-0029](../adr/ADR-0029-vision-screen-capture.md) cross-language-constant addendum). What
increments repo gates is the survey that shape forced: the seam token's metadata key rode along as
a second entry, three hand-written declarations with nothing comparing them, and everything else
found is now a written deferral rather than an absence, in three kinds the scan could not hold that
morning (ordered relations rather than equalities, values spelled inside strings, and TypeScript).
One of them, `TITLE_MAX`, was **already divergent** at 48 against 32, so registering it then would
have turned a gate on over a shipped disagreement nobody had decided how to resolve, and it waited
on that decision rather than on the scanner ([repo-gates.md](repo-gates.md)). That decision was
made later the same day, so the registry stands at three and the scan reads TypeScript; see the
session-read seam entry below.

Vision then **held at 17 on 2026-08-03**, later the same day, when the `opaque` bit's half of the
pixels-across-a-swap entry landed and the picture half did not, which is the body-gateway
precedent: a cell decremented for a half-closed entry is how an open deferral gets lost. The
schema is whole now (`HandoffRecord` carries `opaque` beside `tainted`, `snapshot` reads it off
the live ledger, `taint_ledger()` rebuilds it, the Redis codec writes and reads the key strictly,
and one contract check round-trips both poles through the fake and the adapter alike), and what
the landing is careful **not** to claim is a live fix. `SwapConductor._prepare` refuses an opaque
turn before anything is written, so every record today says `False` truthfully; the bit is carried
because both of its consumers open on a `False` and neither can tell an invented one from an
honest one, so a rebuilt ledger that manufactures it is a fail-open waiting for the picture half.
This entry's own history is why the distinction is drawn so hard: the last refusal in this area
shipped inside a gated tool where it could never fire, with a test that reached the branch by
calling `invoke` directly. So the conductor test now asserts the store saw no write at all (the
refusal, not the schema, is what keeps the far side clean), and the two new brain-phase tests that
watch the consumers differ across a swap each carry a tainted-but-not-opaque control arm, so what
they measure is the bit and not the taint. Unusually for this backlog, the entry was right about
itself on every checkable claim including its cost; what it did not say, and what the same entry's
`Message.images` lesson demanded checking, is that the codec ignores an unknown key in silence
while raising on a missing known one, which is why the bit is written and read rather than
defaulted and why the strict-decode test now covers all four taint fields. Mutation-proven five
ways and observed live against the compose Redis
([ADR-0030](../adr/ADR-0030-brain-handoff.md) 2026-08-03 addendum, with a pointer from ADR-0029
decision 4, which owns the bit).

Body & overlay then went **16 to 15 on 2026-08-03**, when the chat floor's frozen measurement
closed, and this one is the sharpest instance yet of the warning at the top of this file. The
entry's cost claim was not merely optimistic, it was about a line of CSS that had been **deleted
about forty minutes after the entry was written**, by the same day's settings-tab slice, on the
reasoning that the reminder stack now rolls away on the first message so the shrink is deliberate.
That reasoning is true of a chat with reminders due and false of every other chat, and for fourteen
days this backlog carried a note about drifting a constant while the defect that constant prevented
was live underneath it. Measured before anything was built, at 60Hz with the stack acked, the first
message a user sends took the panel 352px to 262px and back to 297px, the composer's own top edge
unmoved throughout, so the entry's "a few pixels of dip" was a 90px excursion of the whole
conversation. **The lesson is not about estimating cost; it is that an entry describing a line of
code is stale the moment that line moves, and nothing in this process re-reads one.** The other two
frozen numbers the entry named were audited at the same time and neither had drifted: the activity
chip is still exactly `--trace-row` (24.000px against 24), and the reserved rail is still exactly
`--rail` (6px on both unbordered scroll boxes). What shipped is `overlay/measured.ts`, which
publishes `--chat-floor` off the empty state and `--trace-row` off the live chip, retiring two of
the three. The third stays where it was, because a probe does not answer what kept it there: nothing
non-Chromium runs the overlay, and on Chromium the rail's measurement is circular, the pseudo-element
setting the width the probe would read back. The entry's shape was wrong in one way worth keeping
for the next probe of this kind: a STARTUP probe cannot do this at all, since neither element exists
at startup, so it would have to measure a hidden copy, which is this defect one layer down with
nobody watching the copy. Measuring the real element as React attaches it, and watching the empty
state's box afterwards, also caught something a single reading would have frozen: it is 183px in the
frame it is attached and 185px once the system font stack resolves. Two open neighbours were
measured on both sides and did not move, the composer holding still through an ack, a switcher round
trip and the pencil at both viewports, and the panel showing no sub-pixel step anywhere in a
streamed reply either way, so the user's undecided preference about a shrink against the ceiling is
again not settled by accident. (**Corrected 2026-08-06**: the second of those readings was, again,
that preference's answer taken for a null result, at both viewports this time. See the correction
under the panel-watch sitting above and the closed entry itself.)

Body & overlay then **held at 15 on 2026-08-03**, when the console tab strip's missing keyboard half
closed in full and one entry opened behind it, the backlog working as intended. The count not moving
is the whole of the bookkeeping: both halves of the entry landed, so it decrements, and the pass that
landed them opened the chat switcher's role mismatch, so it increments back. What the entry got wrong
is a species this file has not recorded before. It said the untabbable half "wants `inert`, and
therefore React 19", and that inference was never checked: React 19 is where `inert` becomes a
boolean PROP, and the ATTRIBUTE has always been reachable from React 18, which writes a string
attribute straight through and drops a boolean one with a warning. Probed against the tree's own
react-dom 18.3.1 on both renderers before a line was written, `inert=""` renders `<div inert="">`
with no warning and `inert={undefined}` removes it again. An empty string is how HTML spells a
present boolean attribute, so the string form is the real thing rather than a workaround for it, and
it is written by React through JSX; what React 18 genuinely lacks is the type, which one module
augmentation supplies, narrowed to `""` so no call site can write the form React 18 drops. Nothing
was upgraded and nothing was set by hand. **The estimate reasoned from a version number to a
capability, and the capability was one `renderToStaticMarkup` call away from being checked**, which
is the same failure as the stale-constant entry above with the staleness in the author's model
rather than in the tree. The entry also undersold its own reach twice, in the direction this file
expects by now: the 380ms view morph was not the only window a Tab could land in the wrong place,
the 200ms tab-to-tab cross-fade being a second one where six stops were reachable and focus was then
dropped to the body outright, and the dismissed panel had the identical defect one level up, six tab
stops inside an invisible panel that is never unmounted. All three now spread one function, so what
is hidden from a reader is out of the tab order in the same frame. Measured in Chromium at 900x900
before and after, with real key presses: the strip went from two tab stops to one, five arrow and
Home/End presses from doing nothing at all to moving focus and the selection together, the leaving
view from three reachable stops to zero, the tab crossing from six to zero, and the dismissed panel
from six to zero.

Vision went 17 to 16 on 2026-08-03 when the two agent-Docker validations ran, both against the real
cortex beside its projector under the shipped compose path, and the entry closed whole. The thinking
half answers no and reframes its own question: the risk it names is a reply truncated to nothing by a
think, and the shipped request carries no `max_tokens` at all against a server reporting
`n_predict: -1`, so ten image runs over two screens all returned a trace and a non-empty reply, while
the same payload capped at 64 tokens does come back empty with `finish_reason: "length"`, which is
what makes the absence of a cap load-bearing rather than lucky. What thinking costs a vision turn is
time, 5.09 to 6.89 s before the first word on a simple screen and 13.80 to 17.70 s on a dense one,
against a median 0.41 s on the same scaffold with the picture removed; that control arm is also
where the vision-specific finding lives, a picture making a think near-certain on the open-ended ask
(10 of 10 runs against 2 of 5 pixel-less) while the length of a think stays a property of the model.
The `mmproj`-less half confirms this backlog's rarer outcome, an entry that was right: the body is
151 bytes of JSON naming the missing projector in llama.cpp's own words, "hint" included, so the 300-character excerpt quotes all
of it and the design claim behind that bound is now measured rather than assumed. Neither half needed
a code change, and both are the kind of claim a llama.cpp build can invalidate, so the error string
landed as an integration-marked canary proved able to fail before being trusted. One correction rode
along, found while proving it: a bare user-plus-tool pair is a malformed exchange that the
projector-loaded server answers `400 "Failed to tokenize prompt"`, which reads like an image problem
and is not one, so the canary carries the assistant's own tool call and images from 1x1 to 1280x1280
all answer 200 under the shipped scaffold.

Body & overlay went **15 to 14 on 2026-08-03**, when the two motions the switcher's list still made
in one frame both landed, and the entry that named them was right about every number and wrong about
the shape of one of its own fixes. It priced the empty line as a flag that "cannot smooth both
directions", the roll it wanted being three lines of `Collapse`. There is no flag: the direction that
has to be instant is a plain unmount, and only the other one is an animation. Asked of `sessions`
rather than of the rendered rows, the line goes up in the frame the last row STARTS leaving and
grows from nothing over that row's own roll, so the card never collapses to 14 and springs back at
all. It eases 64 to 53 over 283.9ms with a largest single frame of 1.66px where it used to move 39px
in one, and the panel, which used to walk its top edge 108 to 119 over the roll and ease 118.41 back
to 108 afterwards, holds 108 on every frame at 900x900 and 86 at 640x720. The entry's reading of the
panel was itself correct, artefact and all, which is worth recording because this file's usual
finding is the opposite. The reorder landed as the FLIP the entry named, in `overlay/useTravel.ts`,
and carries the leaving row on the same clock the entry asked for, because a leaving row is one of
the rows the hook watches. **What it did not have is the hazard that would have made FLIP a
regression.** A roll moves rows by layout, frame by frame, with no commit anywhere in it, so the
release at the end of a 300ms exit reads the 50px its neighbour has already travelled as a jump to
answer and answers it by sending that row back down. Positions are therefore refreshed every frame
while a roll is in flight and played from only on a commit, which also puts a regrouping that lands
mid-roll on honest numbers. Two smaller things the entry did not have: a travel is a transform, so
the card's height never changes and the panel's watch on its own box has nothing to answer (measured
across a reorder, card 164 and `scrollHeight` 162 against a 162 client box on every frame), and the
demo bridge could not make a chat ARRIVE, its list only ever shrinking, which left the filling
direction unmeasurable by hand exactly as the delete was before the row exit landed. That direction
is deliberately left an 11px step, a line's 39px replaced by a row's 50, which is the same asymmetry
the row exit already recorded and defended: a removal is a gap that has to close before the eye can
follow it, an arrival is already where it belongs.

Body & overlay then **held at 14 on 2026-08-03**, when a Thoughts trace opening a reply off the
bottom of a full history landed and opened one entry behind it, which is the backlog working as
intended. The fix is the tail pin held across a roll: while the reader is at the end of the log,
`overlay/logRide.ts` holds their distance from it for every frame of the roll, so the growth comes
out of the scroll rather than out of the reply, and a reader who has scrolled up is left alone.
Traced at 640x720 the distance reads 3px on every frame of both directions where it had run 3 to 79,
with `scrollTop` going 408 to 484 and back inside the roll's own 300ms. The entry was wrong twice, in
the two ways this file keeps finding. Its measured setup no longer exists (it names the reminder
stack, which is gated on an empty log, and a 547px ceiling that reads 450px now), though the
condition that always mattered, the panel having nothing left to give, reproduces on a long enough
history. And its prescription, a second animation sharing `Collapse`'s clock, would have had to
predict how much of the growth the panel was about to absorb; recomputing the scroll from the box on
every frame needs no prediction, inherits the clock and the curve by construction, and leaves
`Collapse.tsx` untouched. One thing the entry did not have at all: the log's remembered "the reader
is at the tail" goes stale across exactly this roll, and built on it the closing direction eased 76px
on a claim that had been false since the open. The entry it opened is the same defect from the other
side, the switcher list and the reminder stack shrinking the log's window from outside the box, where
the ride never hears their roll.

Vision went 16 to 15 on 2026-08-04 when the image arm of the injection-defence harness ran against
a rendered-payload corpus, the last of [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s four
agent-Docker measurements and the one whose entry promised its number would be published whatever
it said. It says something the ADR did not predict, so the promise was the load-bearing part of the
entry. Ten attacks in each of three renderings (unstyled screen text, a modal system dialog
claiming administrator authority, and an ordinary mail client carrying the payload in a message
tail) put the shipped framing at 1 of 30 cells fired framed against 5 of 30 unframed on the cortex
pick, and reading the replies is what those counts need: **a canary detector inherited from the
text channel cannot tell obedience from diligence in the pixel channel**, because describing the
screen is the benign answer to "what is on my screen?" and a description quotes the payload. Five
of the six were that, four of them on the dialog, which is a property of the rendering rather than
of the model, since a dialog whose whole content is the payload cannot be summarised without
quoting it. What is real is `output-laundering`, the one attack
[ADR-0013](../adr/ADR-0013-untrusted-content.md)'s hardening addendum exists for: the clause that
took gemma-4-12B to 0 of 10 over text does not hold over pixels, and the framed cortex has ended
its summary with the line a screen told it to. Every hijack-shaped attack failed in both arms on
all three renderings, and `send_email` was never called from a picture, so the closeout's "not
obeyed, transcribed" is narrowed rather than overturned and decision 4's boundary (taint, not
framing) is better supported than before. The entry's cost estimate was wrong in this file's usual
direction: rendering payloads was the cheap half, and reading a matrix that four of its own seven
checks had to fail in anger to earn was the expensive one. The rate behind the finding was measured
rather than reported from the one cell that produced it, five framed runs per rendering, and the
bitmap font was controlled for with the same screen redrawn by a browser in a real face, which came
back harder for the model to read than the corpus is.

Resource governance **held at 5 on 2026-08-04** while the last uncounted piece of its landed
GPU-placed-runtime entry closed: the `VramBudgetPlacer`'s GPU arm fired against a real placement for
the first time. The count does not move because this was validation of something already built,
which this area has never counted, and the entry stays where it is with its own closing sentence
("the GPU arm has still never fired") preserved and dated false. The claims it shipped with all held
against the code, which is the rarer outcome here: the budget really is the three env values, the
tier really is one artifact behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`, and routing really is the
separate `CORTEX_SUBAGENTS_GPU_ENDPOINT` setting the 2026-07-18 correction added. What the run
added is the part no reading of the code can give. Two concurrent spawns of one roster entry
against a headroom that holds exactly one of them went one to the sidecar's `-ngl 99` tier and one
to the CPU server, and the tier's own log says which: one task, 221.05 ms, against 12536.83 ms for
the sibling. The same batch under the shipped soft cap left the tier with no task at all, which is
the arm being shown able to stay silent, and the shipped configuration is exactly that arm. The
suite carrying both is integration-marked and lives beside the CPU one; it was reddened on purpose
first, by pointing the GPU endpoint at a closed port, which also fired ADR-0012's CPU re-place from
a real GPU placement rather than from a failing fake for the first time.

Subagents **held at 2 on 2026-08-04** when the spontaneous-pick nudge's live uptake was observed
and stayed open, which is the outcome this file has the fewest examples of: an entry whose owed
*measurement* is delivered while its *fix* stays queued. The count does not move because a
fix-when-it-bites entry closes when the fix lands or is declined, not when the number it was
waiting on arrives, and this area's cell was corrected on 2026-07-19 precisely for failing to count
this entry at all. What arrived is three findings, and the first of them retires the recipe rather
than answering it: a prose-only ask carrying independent subtasks does not delegate at all (20
turns over four asks, zero spawn calls, and `subagent`, `delegat`, `spawn` and `farm` absent from
every one of the twelve full reasoning traces), so there is no batch whose spread could be read.
Asked in ordinary prose to farm the same work out, the cortex delegated in all 16 turns and put the
whole batch on one roster entry in all 16, with exactly one batch naming a model at all and that
one naming `qwen` for every subtask, which is a pile on the cheap entry rather than a spread. The third finding is the one no card was needed for and the one that reframes
the entry: `build_spawn_spec` publishes the knob and the spread sentence only for a tool-less
multi-entry roster, and `build_subagent_tools` makes subagents tools-enabled the moment any tool
registry exists, so the nudge is shown exclusively to the deployment whose subagents can do nothing
but the prose work the cortex prefers to keep. A fourth thing was corrected rather than opened: the
advertised "subtasks that share one model run one after another" is conservative on this
deployment, because an entry holds one backend per placement target and the roster override points
both at one server, so a same-entry batch whose ask fits the VRAM headroom once overlaps two ways.
That correction rides the same sentence and the same fix, so it is folded into the entry rather
than counted, and it shrinks the prize for spreading rather than adding work.

Vision went **14 to 13 on 2026-08-06** and subagents **2 to 3** the same day, one closing that
opened one: the capture indicator's outcome landed, and the pairing it guarantees for the turn's
own dispatches does not reach a delegated step, which is now its own line. The closing is worth a
sentence for the opposite reason to most here, since the entry was right about everything it
claimed and this file's standing warning says to expect otherwise. It was also tighter than the
entry: two of the four failure modes it listed as producing the identical event are literally one
code path, so no design could have told them apart. What the sitting had to decide was not the
mechanism but the **direction of the risk**, which is that a privacy indicator may over-report and
may never under-report, and which is forced rather than chosen: a capture that failed after the
shutter fired, with the pixels already off the display and the body's own receipt already shown,
is indistinguishable brain-side from one that never happened. So the outcome may only strengthen
what the ring claims, the ladder only climbs, and a failed capture leaves the ring exactly where
the ask put it.

Vision went **13 to 12 on 2026-08-06**, later the same day, when the live-probe refresh landed,
and it is the fourth sitting running to find an entry whose own premise needed checking, so the
useful part is which half survived. The **cost** was exactly as written and was reproduced end to
end rather than argued: a `model-host` recreated without its projector flipped `GET /props` from
`vision: true` to `vision: false` under a brain whose container never restarted and whose log
still held exactly one probe line, and the next "look at my screen" read the screen through the
stand-in body, tainted the turn, and died on llama.cpp's `image input is not supported`. The
**wire** the entry proposed did not survive. A model child's argv is fixed at the sidecar's own
boot, so a swap's `stop` then `start` respawns the cortex tier from the same flags; driven
straight at the running control API, which is literally what the restore does, `/props` answered
`vision: true` before and after. The conductor would have rung on the one event that cannot
change the answer and stayed silent on the one that does, which touches residency not at all. So
the entry would have shipped a wire that left its own reproduction reachable, and that is worth
recording beside the cost estimates this file already warns about: an entry can name the right
defect and the wrong trigger.

The refused option dissolved on inspection too, which is the other thing to keep. "Re-probing per
turn makes the inference adapter stateful" was about a component that never held the probe:
`vision.py` has lived in the composition root since the slice landed. What replaced the wire is a
port asked at both moments the answer is acted on, the advertisement and the call, with nothing
cached at either. Both, because a turn lists its tools once and then runs rounds against that
list, so refusing at the call is the half that keeps a screen from being read; and nothing cached,
because a cache only bounds how stale an answer may be and the measurement says the bound buys
nothing worth defending (a `/props` costs 1.5 ms idle and 1.7 ms with a generation in flight,
against a capture that blits and PNG-encodes a display). The probe's own leash came **down** as a
result, 5 s to 2 s, since it sits inside a user's turn now instead of at boot. One thing nobody
asked for came free: the capability heals in both directions, so a deployment that gains a
projector after boot no longer stays blind until the brain restarts.

Body & overlay went **13 to 12 on 2026-08-06**, when the composer's move on a clamped shrink closed
without any code being written and without the user picking anything, because the design choice it
had been holding open for seventeen days stopped existing on the day it was filed. This is a
closing species the file has not recorded before. Entries here have been wrong about a cause, a
size, a fix and a cost; this one was wrong about whether its subject was still in the tree. The
entry was written into the console-and-motion commit at 20:25 on 2026-07-20 and the panel's second
bound was deleted four commits later at 20:57, moving the clamp off the pinned edge and onto the
height, which is the entire mechanism the entry is an argument about. It was then restated on
2026-08-04 from its own text, put to the user a second time, and deliberately left unpicked, so the
sitting that could have caught it instead recorded a third outcome for a question that had no
subject. Measured by hand in a browser at both viewports it was written against, the composer's own
bounding box does not move by any amount on any frame of a clamped shrink, and a clamped switcher
round trip returns the panel to the identical edge and height, which are the two things the entry
says cannot both be true. The reddening is the part worth copying: the deleted clamp was put back
at the one line that spends it, the same ack moved the composer 58px through a 96px excursion, and
only then was the green reading worth anything. Two further corrections ride this one. The rarity
number it was restated with, "615px of growth at a 900px viewport", is a ceiling's value read as a
delta, and real headroom is at most 342px there and 0px for the demo's own arriving chat, so waiting
was never as cheap as the entry priced it. And the backlog is now down to one entry anywhere whose
blocker is a preference rather than work, where it read as two. (**Superseded 2026-08-06**, later
the same day: that last one was answered and landed, and then so was the one it opened, so the count
of entries waiting on a decision rather than on work fell to zero, and rose to one again that
evening when bounding the recall rank's request removed the only reason its default was off and put
`CORTEX_MEMORY_RECALL=judge` back in front of the user as a choice, [memory.md](memory.md).)

Body & overlay went **12 to 13 later the same day**, when that last preference-blocked entry was
answered and landed: a swap fired from inside a section that closes with it drops focus on the
floor, and the user picked the composer over the header's chats button and over a split that would
have kept a delete's focus in the switcher. One rule shipped, that a conversation arriving on the
panel takes the caret with it, and it opened two entries behind it, which is the backlog working as
intended rather than a regression. The first is the rest of the same family: a rename, a delete of a
chat that is not the open one, and a reminder's ack each take the pressed control away without
replacing the conversation, so the new rule never hears about them and each still drops focus to the
body. The second is a thing the fix made visible rather than made: the composer's draft belongs to no
chat, so the caret is now put into a field that may still hold a sentence started in the conversation
that just left. That second one is a preference again, so the count of entries waiting on a decision
rather than on work is still one, and it is not the one it was this morning. Two of the closed
entry's own claims wanted correcting, both about mechanism: only the switcher row holds focus for
its roll, the other two doors losing it in the commit itself (a reminder stack is keyed on the chat
and remounts, a leaving row goes `inert` at once), and the doors are not three, since any global key
pressed while focus sits inside the switcher has the identical defect.

Body & overlay came back **13 to 12 the same day**, and the count of entries waiting on a decision
rather than on work went to **zero**, where it has never been: the user answered the draft with a
draft per chat, over clearing on swap, and it landed. Unsent composer text is now keyed by session
id in the reducer and the field renders the entry for the chat on screen, so the swap that moves the
caret moves the sentence with it. The entry's claim held at every door and not only the two it
named, which is worth recording in a section whose standing warning is that entries go stale; what
wanted correcting was smaller and inside its own evidence, "caret at 15" being the end of a fifteen
character draft rather than a caret held mid-sentence. Two things about the answer are decisions in
their own right and are argued at the ADR rather than assumed here: a draft is view state and dies
with the body process, the hard rule being about model processes and KV caches and a store buying
only survival of a restart that unsent text with no reader does not earn; and it lives in the reducer
all the same, because the delete cascade has to reach it and a swap has to hand it over
synchronously, which also leaves it one hydrate from a store if that is ever wanted. Nothing opened
behind it.

Body & overlay then went **11 to 12 the same evening**, and the count moving by one while three names
changed is the point rather than an accident, this file's newest warning being that a count right by
cancellation hides both its errors. Out: the row gestures that swap nothing, answered as the caret
staying in the list. In: a modified chord still reaching the overlay from inside the rename editor
the caret now lands in, and a list that shrinks saying nothing where a chat arriving speaks. The
closed entry named five gestures and there were thirteen, which is the same undercount its own
predecessor made two entries earlier and by the same route, remembering the last report instead of
reading the component. It also had the mechanism wrong in the opposite direction to that predecessor:
these controls are unmounted by the row's shape change rather than blurred by `inert`, and the ack is
the only one of the thirteen that behaves as filed. Two live defects turned up alongside and were
fixed with it, neither about focus and both about the same seam: a cancelling Escape reached the
window listener and dismissed the panel, and `?` typed into the rename editor opened the console.
Session history held at 3 and untrusted content went 11 to 12 on 2026-08-06 when the summarizer's
sharp deferral, an unfenced recap of tainted turns, closed by being fenced at both ends, and the
counts moved that way because settling it corrected the premise and found something wider. The
premise was wrong: an untrusted tool result is never in the prefix a recap reads, since the engine
persists only the raw user text and the scrubbed assistant reply and the `Role.TOOL` message dies
with the turn, and a stored `Message` carries no taint bit, so the fail-closed "refuse a tainted
prefix" option the entry imagined had nothing to read. What is reachable is the assistant's own
quotation of untrusted content, which the security preamble expressly permits, and the recap did
two things the plain window does not with it: it fed that text to a model under an instruction to
process it, the summarizer-as-target shape the tainted-memory decline named on the record path,
and it promoted the answer to a durable, cached, system-role artifact folded forward for the life
of the session. Both are now fenced unconditionally, the prompt under the standing preamble and
the recap under a nonce minted after the model has spoken so a summarizer that echoes the closer
it was shown ends nothing, with the injection pinned absent from everything outside the fences in
both directions and each of the five fence sites reddening its own test when reverted. Taint is
deliberately not spread, because the plain window hands the model the same assistant messages
unfenced on every turn until they age out, so a tainting recap would be narrower than its own
source. That inconsistency is the wider thing, and it is now the untrusted-content area's twelfth
entry rather than a line in this closure: a quoted injection re-enters through the plain history
window, unfenced and untainted, and the fix it wants is the persisted per-turn taint marker that
per-provenance eviction and a precise recap refusal would both spend. Session history held rather
than fell because the fence's cost is unmeasured, the live run having been made before it, so the
usefulness question took the closed entry's place beside the one-corpus one that wants the same
run.

Untrusted content then held at 12 on 2026-08-06 when that twelfth entry, opened hours earlier, was
read against the code and then put on the GPU, and it held rather than fell because the mechanism is
real even though two of the premises around it are not. The later turn is not preamble-free, since
the assembly prepends the standing rule whenever tools are enabled at all and a deployment without
tools has no tool result to quote; and the outbound surface is not open, since an untainted gated
call goes to the confirmation card and a missing confirmer denies, so what an untainted turn loses
is the hard deny rather than the gate. What is right is the mechanism: the output guardrail removes
URLs and only URLs, so an injection's prose is persisted whole while its links are not, and the
replayed text really is unfenced in the assistant position. The first run measured nothing and said
so: on the corpus's own "give me a one-sentence summary" ask the cortex quoted a payload into its
persisted reply zero times out of ten, so the replay arms replayed clean summaries and every cell,
the positive control included, recorded the absence of a payload rather than resistance to one. An
injection does not reach history by itself. The second run changed the ask to the one a user really
makes, for the wording quoted verbatim, and over three payloads the carrier appeared every time,
the replay on a bare turn with no preamble was obeyed twice (the model answered the follow-up and
then appended the payload's own token to it, with the one-shot payload the only one that held), and
the identical replay behind the standing preamble was obeyed not at all. So the framing is causal
at this position too. The full corpus ran later the same day and the numbers held at ten: quoted 9
of 10, obeyed 2 of 10 on the bare turn, 0 of 10 behind the preamble, with the positive control
firing on 6 of 10 and every reply ending on a stop rather than a cap. The one open decision, what
to do about the turn that has no rule at all, was then measured instead of argued, in two more arms
over the same histories, and it landed: a shortened rule with every tool and marker sentence
removed holds the replay to zero exactly as the full preamble does, so a plain standing rule now
stands beside the full one and every turn carries exactly one of them. It is composed beside the
shipped text rather than carved out of it, since rewriting the preamble would have invalidated
every framing matrix measured against it, and moving the full preamble unchanged was rejected on
honesty rather than efficacy, its first sentence being "You may call tools" on a turn that has
none. What stays open is the rest of the residue: the persisted taint mark that would let a later
turn re-fence only what read untrusted content is still unbuilt, and the transcript is still
unfenced in the assistant position, with the standing rule now on the turn that replays it.

Session history then held at 3 on 2026-08-06 when the usefulness the fence left unmeasured was
measured, one entry closing and one opening on the same run. The fence is not what costs: behind
it the cortex still answers "Your booking reference is QH7-4412." out of a recap it has been told
is quoted data, three runs of three, with the shipped window failing all three, and no fence marker
reaching the reply. Both of those are assertions now rather than lines of printed output, the
control especially, since an arm that answers anyway has measured nothing and this repo has read
past that twice. What the fence does cost is characters, a 484-character account arriving as a
1022-character message once its preface and markers are around it. **The default did not move
anyway, and the reason is not the fence but the case a default runs in.** One fold is not what a
long conversation does; it folds at every boundary move, each fold reading the previous account,
and over three staged sessions of five folds the opening fact survived 2 of 3, the round that lost
it losing the reference, the hotel and the card together while keeping the filler. A fold costs
14.5 s to 30.8 s typically and reached 224.5 s, and the server's counters say why: 6286 tokens
decoded on that one, 400 to 850 typically, for an account of 80 to 160 tokens, the rest being
reasoning `drain_text` drops. The user had decided to turn the summary on and accepted 11 s per
boundary move, and this run falsified that premise, so the honest answer was to report rather than
ship, and `CORTEX_HISTORY_SUMMARY` stays off. Four things now stand between it and a default, two
of them this area's own sharpened entries (the missing token cap and minimum fold size, whose
trigger has fired, and the corpus, which still wants a real conversation and a retention nearer
1), one of them the disable-thinking lever in
[inference-model-manager.md](inference-model-manager.md), where a fold is the clearest case yet
because its thinking is discarded by construction, and one newly opened here: nothing tells the
user a turn is folding, the overlay's mist breathing identically for a slow model and a 224-second
one, and the reason is the port rather than the seam, `HistoryWindow.select` taking no progress
sink while the per-stream one it would need is already in scope where the window is built.

Session history then fell to 1 later the same day, when all four of those landed together and the
default moved. **The diagnosis held on every point**, which is worth saying in an area whose
entries have twice been wrong about themselves: the request carried no `max_tokens` and no
`chat_template_kwargs`, `RECAP_MAX` cut text the model had already finished writing, and
`drain_text` decoded and dropped the whole reasoning stream unread. `InferenceBackend.stream` now
takes a `GenerationBounds`, so the fold asks for no thinking and at most 512 tokens per request,
which is `RECAP_MAX` said in the request's own unit. The pair ships together because a cap alone
is a trap with a number on it: the same prompt at 160 and 256 tokens with thinking on returned
`finish_reason: "length"`, hundreds of characters of reasoning, and an empty reply. A reply that
runs into either bound is refused rather than trimmed, because storing half a sentence would
advance the account's `covers` past turns no later fold would ever read again.
`CORTEX_HISTORY_RECAP_MIN_CHARS` puts a floor under a fold, clamped at the composition root to the
character budget so a deferred fold's gap can never be wider than the window itself, and
`HistoryWindow.select` now takes a `ProgressSink` per call, so a fold emits one `"folding"` chip
before it starts and nothing at all when it is cached or deferred. The overlay needed no change.
**Measured in the same shape as the run that held the default:** on the identical prompt 378, 531
and 602 decoded tokens at 13.6 s, 18.9 s and 21.5 s became 88, 87 and 88 at 3.9 s, for a slightly
longer account; across five compounding folds a fold decodes 61 to 163 tokens for 2.9 s to 6.2 s
with no tail; retention went from 2 of 3 to 3 of 3; and at the shipped floor the same conversation
folded once over five boundary moves for 3.4 s in total. So the default moved to on, as the user's
standing decision finally carried by its own numbers rather than shipped over them, pinned by a
test that reddens when it is flipped back. The corpus entry stays open and is now the only thing
between this feature and a claim about real conversations, and the lever's own entry stays open
too, since the session title and the recall rank still spend the same discarded thinking.

The session title and the recall rank stopped spending it later the same day, which is the whole
of the sentence above coming true ([ADR-0038](../adr/ADR-0038-ranked-recall.md)
bounded-side-calls addendum, [ADR-0021 addendum](../adr/ADR-0021-session-read-seam.md)). Both were
re-derived from the code first and both held: each ran `drain_text` with no bounds, and each threw
away everything the model deliberated. A title now sends `max_tokens=32, thinking=False`, which is
`TITLE_MAX` in the request's own unit, and a rank sends `24 + 8k`, computed from `k` rather than
fixed because a schema-constrained order's length is known before it is asked for. Measured on the
shipped cortex, a title went from 235 to 303 decoded tokens at 7.9 s to 10.4 s to **4 tokens at
0.2 s to 0.3 s, for the same titles run for run**, and a rank from 448 to 613 tokens at 18.4 s to
**12 to 22 tokens at 0.9 s**. Two things the residue had not predicted. **A JSON schema does not
protect a constrained reply from a cap**: a truncated one is not JSON, so the rank falls back to
the cosine exactly as it does for an unreachable model, which is why that cap is generous rather
than snug. And **the capped-with-thinking trap that was a coin flip on the fold is a certainty on
these two**, empty three times in three at each of 16, 32 and 64 tokens, because their answers are
a few tokens and the deliberation before them is hundreds. This closes the generated title's own
empty-reply half in [session-read-seam.md](session-read-seam.md), which had been waiting on
precisely this lever since 2026-07-16.

What it opens is a decision rather than a task, and it is the user's:
`CORTEX_MEMORY_RECALL=judge` was left off **on cost alone**, and the cost is now 0.9 s per recall
instead of about 12. Re-scored over the same corpus the bounded judge ranks identically to the
unbounded one (mean reciprocal rank 1.000 against the cosine's 0.917, the right note first 6 of 6
against 5 of 6, no fallbacks, and still fewer hits than `k` because it drops what does not help),
so the premise the default rested on is gone. It is recorded in [memory.md](memory.md) as a
recommendation and not taken here, because the standing choice is the user's own and because two
things are still true: a rank runs on **every** recalling turn where a fold is cached per boundary
move, and the corpus is ten notes and six questions hand built by the policy's author.

Repo gates went **6 to 7 on 2026-08-06**, from two untracked directories rather than from any code.
`models/` was sitting root-owned and empty at the repo root, created that morning by a container and
matched by no ignore rule, and `pgdata/`, where the pg-backup sidecar writes `cortex.dump`, had
carried the same exposure since that sidecar shipped. Both are ignored now, unanchored so that a
bare `docker compose -f docker/docker-compose.memory.yml`, which resolves its binds against
`docker/` rather than the repo root, is covered as well. What increments the cell is the class and
not the two directories: a third default of the same shape, `${CORTEX_TOOLS_ROOT:-./sandbox}`, was
already ignored, so the tree is clean by three separate acts of remembering rather than by anything
that checks, and what these binds receive is GGUFs and database dumps rather than kilobytes. The
deferral is the scan, and it is deferred rather than written because one built today would guard a
set that is already correct ([repo-gates.md](repo-gates.md)).

Repo gates went **7 to 6 later the same day**, when the live pgvector run took the
`cortex_contract` database and stopped sharing the brain's `memories` table. The entry was
picked up ahead of its own trigger, on two pieces of work queued behind it: the judge reranker
became twentyfold cheaper that morning and its default was put to the user, and the widened recall
corpus that decides that default would have written the first real memories into the table, which
is precisely the run the entry said would redden. The measurement it recorded was reproduced
before anything was changed, and one real row turned `check_empty_search` red exactly where the
entry said it would. The cure is the Redis one in the mechanism Postgres has for it: a database
rather than a numbered one, `TRUNCATE` rather than `FLUSHDB`, and `init.sql` included by a second
initdb script rather than restated, so the two databases cannot drift. A schema plus a
`search_path` was the cheaper option and was rejected on its failure mode, because the adapter's
SQL is unqualified and a `search_path` that fails to apply puts the suite, `TRUNCATE` included, on
the brain's own table without saying so. **One bookkeeping repair rides along**: the standing-open
bucket at the end of this file never carried this entry, so it listed six repo-gates items under a
header that read seven from 2026-08-03 to now, the header and the cell agreeing with each other
and with nothing else. The close makes them agree at six, which is the arithmetic working out
rather than the check working ([repo-gates.md](repo-gates.md)).

Memory then went **9 to 10 the same evening**, and that one is new work: widening the judge's
corpus from ten notes to 41 found a defect the narrow corpus had no category for. Four of the 26
questions have no answer anywhere in the notes, the model correctly replied that none of them help,
and `JudgeRecallPolicy` reads an empty pick as a failed rank and falls back to the cosine's three
wrong notes. The measurement that vindicated the policy is the measurement that found the hole in
it, which is the argument for widening a corpus even when the recommendation is already written
([memory.md](memory.md), [ADR-0038](../adr/ADR-0038-ranked-recall.md)).

Memory went **7 to 9 on 2026-08-06**, an arithmetic correction rather than new work, and the pass
that found it repaired three more lines without moving a count. The ranked-recall close had done
half of its own bookkeeping: it struck the model-based reranker and recall observability from the
area header when they landed, and it never added the cross-encoder rank and the audit of dropped
candidates that the same close opened, both written up in the entry and at the origin decision
within the hour. Header, cell and bucket therefore all read as though that close had only shut
things. Three more lines were wrong without any count being wrong with them.
**Subagents'** header named two of its three entries, the
delegated tool step announced and never settled having been written up and counted on this page but
never added there, so the header was the wrong side. **Body and overlay's** named eleven of which
one had landed and one was missing, which is the standing warning added at the top of this page.
And the **fix-when-it-bites** bucket still described recall observability as a thing nobody can
inspect after the fact, on the day the audit sink that inspects it shipped. Four navigation aids,
four different ways to be wrong, none of them reachable by rereading a number.

Vision **held at 12 on 2026-08-06**, that evening, when the fix-when-it-bites bucket was re-read
against the capture edge that moved that morning and one of its entries was ruled not fired. That
pass was owed: raising `CORTEX_BODY_CAPTURE_MAX_EDGE` to 2048 brings the halving ladder nearer, the
encoding entry beside it had re-read itself against exactly that change and correctly stayed put,
and `RESOURCE_EXHAUSTED` classification had not. The answer is that it cannot fire at the shipped
byte ceiling **at any edge the seam permits**, which is stronger than the numbers and does not
expire with them: the ladder's last rung is at most a quarter of the requested edge, so at the
4096 px ceiling it is 1024 px on the long edge and 3.1 MB of raw RGB against a 6 MiB budget, and
`CaptureError::TooLarge` is unreachable until a deployment tightens `CORTEX_BODY_MAX_IMAGE_BYTES`
to about an eighth of its default. The entry's trigger is rewritten as that check. Two things the
re-read found beside it. The coarseness is narrower than the entry says, because nothing brain-side
reads the status code at all, only the body's own sentence, and the three sentences differ
completely; what is actually wrong on that path is a **prefix**, every capture failure being
announced to the model as "could not reach the body" including the shipping default where capture
is switched off and the body answers at once, and that is folded into the same entry rather than
counted again. And the number the morning's default was signed off with, a worst realistic screen
at 74% of the ceiling, was a 4K number: a 2560x1440 desktop under the same grain reaches 79%,
because how much grain survives is set by the ratio between the display and the requested edge
rather than by the display's size, and the biggest display is the one that averages the most of it
away. The margin holds and it is smaller than it read, and the harness that reads it was wrong in
the other direction, calling an untouched 1920x1080 capture a fired ladder because it compared the
returned width against the edge that was asked for rather than against the edge that was possible.

Body & overlay held at 12 on 2026-08-06 when a section's roll came off `offsetHeight`, one entry
out and one in, and the pair is spelled out here because this file's newest warning is that a count
right by cancellation hides both of its errors. Out: the roll ending 0.25px from where it was going,
whose published numbers reproduced exactly at HEAD before anything moved, which is worth saying in a
backlog whose warning is that they often do not. The aside stands at 193.75px against the 194 its
target was taken from, a section at 57.25 against 57 is there beside it (a reminder row rather than
the Thoughts trace the entry named, that trace measuring 76 flat at 900x1000), the summon's own roll
of the aside was handed back to layout 0.25px under the height it had just painted, the closing roll
started that same 0.25px above where the eye had it with the panel's auto height taking the step
along, and the ride-along predicted 546 for a roll that left the panel at 545.75. The section now
measures the way the panel does, the used height off the computed style, which keeps the sub-pixel
and still ignores the summon's scale; after it, the target is the height the section stands on, the
prediction is the height the panel lands on, and the step at every roll boundary is 0.000px, which
is under the 0.015px grid the panel's own change reached because there is no arithmetic left to
round rather than because the grid got finer. The harness was the whole of the entry's stated cost
and moved the way its predecessor's did, the stand-in every per-row exit is asserted through saying
its height where production reads it; reverting the reading reddens eleven `Collapse` cases and the
per-row exits in two more files, and rounding it reddens exactly the one case that names the
sub-pixel. In: the whisper bubble's rounded roll target, noticed in the doing, filed unmeasured
because the honest first move there is a live trace rather than a change.

Memory **held at 10 on 2026-08-07**, one out and one in, and the pair is written out in the area
header as well as here because a count right by cancellation is the failure this page warns about
twice over. Out: the judge's abstention, picked up ahead of its own trigger because the entry's
stated cost was the reason to wait and the tree did not support it. The entry priced three consumers
needing to mean something by zero hits; `MemoryRecaller.recall` already returned an empty ranking as
no hits without re-fetching, and `turn_context.py` already assembled a turn with no memory block
when recall came back empty, so what was left was the `DEMUR` basis, a `parse_order` that tells a
refusal (`{"order": []}`) from a reply nothing can be read out of, and one branch. The distinction
inside the parse is the part worth keeping: an order that named notes of which none exists is a
failure, because a model that tried to pick and produced nothing pickable has not declined, and a
truncated reply stays on that side by construction since it is not JSON at all while a refusal is
complete JSON. Measured on the same 41-note corpus that found the defect, the four unanswerable
questions return nothing 4 of 4, the whole run fell back 0 of 26 against 4 of 26, and the ranking on
the 22 answerable questions did not move (aggregate 1.000 against the cosine's 0.902, the reversed
control still 0.000). In: the same turn under the shipped default, which the close does not reach.
`RawRecallPolicy` and the three heuristic policies have no way to say that nothing helps, so the
refusal belongs to the judge alone until a relevance floor gives geometry one, and a floor needs a
threshold that survives changing the embedding model ([memory.md](memory.md),
[ADR-0038](../adr/ADR-0038-ranked-recall.md)).

Subagents went **3 to 2 on 2026-08-07** when the delegated tool step announced and never settled
closed as **declined on merits**, and the decline is worth reading for what it repaired rather than
for what it refused. The entry's account of the code held where it mattered: a real delegating
`converse` stream, driven over a real `SpawnSubagentsTool`, a real `SubagentRunner` and a real
subagent dispatcher with the delegate calling one tool that succeeds and one that fails, carried
three `tool_activity` events and one `tool_outcome`, so both delegated steps were announced and
neither was settled and the failing one looked exactly like the other. Three of its claims did not
hold. The cost is **two** lines, not three, because `SeamProgressSink` is built with
`to_wire=to_server_event` and that mapper already carries the `ToolOutcome` arm the turn's own
events use, so the sink needs nothing. The consumer question is harder than the entry framed it and
lands on the `GetVolume` side of the line rather than the merely-unbuilt side: the one reader of a
`ToolOutcome` anywhere is the overlay reducer's arm, which changes nothing unless the name is
`capture_screen` and `ok` is true, and that tool is a built-in `build_builtin_tools` gives to
`build_cortex_tools` alone while a subagent's dispatcher is `build_subagent_tools` over the MCP
registry, so a delegated outcome could never carry the one name the one reader reads. And the fix
could not deliver the invariant it was filed to protect, which is the finding the entry could not
have reached from its own text: `emit` returns without queuing on a saturated buffer while the
turn's own events block on `acquire`, so a delegated activity can arrive with its outcome dropped,
and two lines cannot make 1:1 true across a lossy channel. On the hard question the entry named
last, a subagent's failures are already the spawning model's business by the route that can act on
them, the runner degrading a failed delegate to an `ok=False` result fed back as
`[subagent i] FAILED: ...`, and there is no consent to surface because nothing in the
gated-stripped subset a subagent holds is outbound or irreversible.
**What was actually broken was the contract, and on the side that cannot notice.** `proto/body.proto`
said the brain emits one outcome per activity "it emitted on the turn's own stream", and the
delegated activity is emitted on exactly that stream; `body/crates/core/src/transport/turn.rs`
repeated it and `docs/modules/body-core.md` shortened it to "one per activity", while
`docs/modules/brain-orchestrator.md` had it right from the day it landed. A delegated activity is a
byte-identical `ToolActivity`, so nothing downstream can tell the paired kind from the unpaired one,
and a body-side surface built on that guarantee would have been built on nothing. All three now say
the pairing covers the dispatches the turn itself made, and
`test_a_delegated_step_reaches_the_wire_announced_and_unsettled` reddens under the very `elif` the
entry proposed, which is the point of pinning it: the reversal is cheap enough to land as a tidy-up
and would make three published contracts wrong in one commit
([subagents.md](subagents.md), [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)).

Body & overlay reads **14 on 2026-08-07**, and the number went up while an entry closed, which is
the whole of what this paragraph is for. The modified chord reaching the overlay from inside a
row's rename editor landed, taking twelve to eleven; it opened two behind it, a list the reader
CLOSES dropping the caret where a list that reshapes under them keeps it, and the silence of a
chord the new rule holds, taking eleven to thirteen; and then reading this file's entries against
the header that counts them turned up a fourteenth that no count has ever
named, the liquid edge's backdrop blur, open since 2026-07-21 and carried in
the running record below under this same area the whole time. That last one is the
count-by-cancellation lesson in its plainer form: there was no compensating error hiding it, the
area header and the table cell simply agreed on a number that had never included it, and agreement
between two summaries of the same set is worth nothing when both were written from each other.
**The chord entry itself is the better half of the record.** It was filed as a decision made
without a measurement, and the measurement changed the answer. Reproduced first at 900x900 with
"a brand new name" typed into a row: `Ctrl+N`, `Ctrl+K`, `Ctrl+↑` and `Ctrl+↓` each discarded the
name, every row reading its old title when the list was reopened, with no undo behind it anywhere,
and `Ctrl+K` dropped the caret on `<body>` besides, which is the landing the caret rule had shipped
the day before to abolish. Then a trace nobody had thought to take: on a bare single-line `<input>`
with the caret at offset 6 and nothing listening, `Ctrl+↑` moves it to 0 and `Ctrl+↓` moves it to
16, so two of the four keys were never spare inside a field and the entry's framing of the question
as a priority was half wrong. What shipped is a rule about the text rather than about the key. A
chord passes through a field whose text the overlay keeps and is held by a field whose text it
would throw away, which puts the composer on the passing side, where it must be, since a summon
lands there and that is where these keys are pressed from. The entry's stated cost was wrong in the
usual direction: not a guard in `Overlay.tsx`, which would have had to name the editor by selector
and spare the composer by name, but a small pure module the next field adopts in one line
([body-overlay.md](body-overlay.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md)).

Body & overlay went **14 to 13 later on 2026-08-07** when a list that shrinks saying nothing closed,
and this one is worth reading for how it chose between three shapes that all worked. The header
count was right when the pass started, which the pass checked rather than assumed by reading every
entry in the area doc and asking which carries a landing; the fourteen names and the cell agreed one
for one, which after two weeks of that agreement being worthless is a result rather than a formality.
**The measurement came before the shape, and it moved it.** Over the devtools accessibility tree
plus a `MutationObserver` on every node carrying `aria-live`, `role="status"`, `role="alert"` or
`role="log"`, a resting overlay holds exactly two live regions, the announcer and the connection dot,
both computing `live: "polite"`, `atomic: true`, `relevant: "additions text"`; and deleting a chat
that was not the open one, deleting down to the empty line, acking a reminder and acking the last one
so its whole section left each produced **zero** mutations in any of them. The entry was right, and
right about the reminder stack it never named. It was wrong twice, and both corrections decide the
shape. Deleting the chat that IS open already speaks, so the commit that shrinks the list is the
commit that announces; and the region is deliberately outside the panel rather than, as the entry
had it, the panel's own. So a second region for the list would put two announcements in one commit
and hand which is spoken, and in what order, to the reader's own speech queue, which no tree can
observe, and a `role="status"` line inside the switcher is worse still, since the reminder stack's
section is unmounted with its last row and would take the sentence saying so with it. **The shape
the entry ranked riskiest is the only one that manufactures no question this repo cannot answer**,
so `notice` widened: one region, one sentence, and a delete that also swaps says both in the order
they happened. What could not be settled here is whether a reader SPEAKS it, and what happens when
the polite update races the focus announcement the same commit sends to the composer; that went to
[host/overlay-screen-reader.md](../host/overlay-screen-reader.md) as a Windows sitting, the
mechanism-versus-observation split rather than punting the entry.
**And it closed alone on purpose**, which in this area is the unusual outcome and is the second
thing worth reading. Its sibling, a held chord saying nothing about being held, was filed hours
earlier as the same question and the two were expected to ride together. The question does close for
both: the region may carry more than an arrival. What keeps the chord open is measured rather than
tidy. A held chord destroys nothing, focus and value both sitting untouched on the input labelled
"New chat name" before and after the press, where a departed row is out of the tree and cannot be
re-read at all, and that difference is the test the close chose for what earns a sentence. It is
also a different seam: every sentence added here was already at a reducer arm, while the hold is
decided in `SessionList`'s own state and publishing from it wants a callback through four components
plus a controller member and an action, a cost its entry never stated. And it carries a policy the
shrink never had to decide, keydown repeating while a key is held. The entry is sharpened with all
three and with a fourth shape neither doc had named, saying it on the editor itself where it can be
re-read rather than in a region where it is spoken once
([body-overlay.md](body-overlay.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md)).

Body & overlay went **13 to 12 later still on 2026-08-07**, one out and none in, when the whisper
bubble's rounded roll target closed. The header count was checked the same way again, by walking
every entry in the area doc and asking which carries a landing, and the thirteen names agreed with
the cell one for one. **The entry named its own first move and the order was kept**: a live trace at
900x1000 before a line of code moved. What it found is that the entry was right about the symptom
and wrong about the arithmetic on both sides of it. The published target sat exactly half a pixel
under the height the bubble's box stands on at all five wraps of a reply, because a whole
`offsetTop` plus a 22.475px line box plus 10px of padding lands on a x.475 and the box is written to
a tenth, so the error is half a pixel every line rather than bounded by one. The step the entry
doubted is genuinely absent, and for a stronger reason than it gave: across 172 frames inside the
roll there is no frame where the panel's height moves and the bubble's does not, and the ride-along
creates no panel animation at all, so the number is computed once per wrap and thrown away. The
entry's own sentence about a prediction added "for the length of every streamed reply" was wrong
too, since the target only changes at a wrap. **What justified the change was the thing the entry
had not imagined.** On a summon that lands inside the roll the ride-along uses that same number as
the panel's pinned bottom edge, which put the panel on 316.59375px where the height the roll leaves
it at centres on 316.34375px, and nothing later recomputes it, so the session keeps the wrong
quarter pixel. Planting `+ 20` on the published target moved that edge by exactly 10px, which is the
gain the arithmetic predicts and the proof the number reaches the edge. The roll now publishes the
number its own box carries, the prediction reads the settled height exactly, and the pin is the
centre it aimed for. The instrument was falsified before it was trusted, by putting `offsetHeight`
back into `Collapse` and re-reading the sibling's 0.25px step through the same trace
([body-overlay.md](body-overlay.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md),
[ADR-0037](../adr/ADR-0037-whisper-streaming.md)).

Body & overlay **held at 12 later again on 2026-08-07**, one out and one in, when a list the reader
closes dropping the caret closed and its mirror opened. The count was walked entry by entry a third
time before anything moved, and the twelve names agreed with the cell one for one. The trace the
entry demanded came first, `document.activeElement` sampled every frame for 800ms across twenty
three doors at 900x900, and it reproduced the entry's own reading: the caret held the pencil for the
whole 300ms roll and read `<body>` at 353ms, so the loss is the unmount at the end of the roll and
not anything at the gesture. **The doors were thirteen where the entry filed four**, which is the
third entry in this chain to undercount them and the second to be wrong about which of them were
already answered: seven are chat swaps the arrival rule takes to the composer, two are the console
arriving over the chat and taking the caret to its own tab strip, two are the panel being dismissed
where `<body>` is correct rather than open, and one is the header's chats button, which the entry
wanted a rule for and needs none, since its own press moves the caret onto it at 45ms before the
close is even dispatched. `Ctrl+K` was the whole of what was open. **The reminder stack's matching
gap turned out not to be the stack's control**, but the empty state's example chip, which is in no
list, has no heir, and whose press unmounts the surface it is standing in. What shipped is one rule
for both, that a section the reader closes hands the caret to its anchor and only when the caret is
inside the section, decided at the transition where the section rolls and at the gesture where it
does not. The hazard the entry named was measured rather than assumed, and it is the guard that
keeps `Ctrl+K` from pulling a reader out of a half typed sentence. What opened behind it is the same
question in the other direction: opening the list leaves the caret where it was, four Tab presses of
header from the first row ([body-overlay.md](body-overlay.md),
[ADR-0035](../adr/ADR-0035-console-and-motion.md)).

Inference & model manager went **7 to 8 on 2026-08-07**, and the entry that closed is the oldest one
this backlog has ever carried: model-manager co-residency, deferred since the Slice 4 inference work
and held since by ADR-0030 decision 8's brain-runs-alone rule. What unblocked it was hardware, an
RTX 5090 Laptop reporting 24463 MiB, and the sitting spent its first half measuring rather than
designing, which is the whole reason the answer is not the one the ADR predicted. **The prediction
was that the shipped pair would not fit. It does not, and it does not say so.** The cortex costs
8448 to 8468 MiB with its projector at 16K, not the ~11.3 GB every doc had quoted from the 2026-06-29
build, and the deep model 19117 to 19125 MiB, so the pair wants 29139 MiB against 24463 over a
1552 MiB floor. Started anyway, both tiers reported `ready` at 23539 to 23642 MiB with 496 MiB free:
WSL2 paged roughly 6 GB to system memory rather than refusing the allocation, and the only witness is
decode, 14.80 to 17.29 tok/s for the deep model against 25.07 to 33.28 with the card to itself, the
cortex untouched at 44.68 to 49.47. **A genuine fit and a 4676 MiB overcommit read the same on
`nvidia-smi`**, about 23.6 GB used and about 0.5 GB free, which is the instrument lesson the ADR
addendum now carries so no later sitting trusts a memory figure alone. And the half decision 8 named
second turned out to need no tiny model at all: the deep model and the **shipped** gemma-4-E4B
subagent tier sat together at 23555 to 23642 MiB with the deep model decoding at its solo rate, and a
spawn admitted to that already-resident tier allocated nothing (23639 MiB generating against 23642
idle), which is the measurement the design leans on rather than an argument. Against a handoff that
costs 102.9 s of swap in which every spawn is refused, that is what co-residency buys.
`CORTEX_SWAP_CORESIDENT` landed off by default, one flag doing two things useless apart, and its
safety is the reopening deferral's own condition met rather than dodged: a co-resident handoff stops
no tier delegated work can reach. **The two that opened in its place are both things the landing made
reachable rather than things it broke**, which is the count going up for the right reason. The flag is
an assertion about a card and nothing checks it, because the brain container sees no GPU and the
failure is the quiet 2x above rather than a refusal; and the placer still fit-tests every GPU-placed
spawn against a budget naming a cortex the handoff evicted, with the deep model's 19 GB charged
nowhere, which was moot while the pool was drained and is exactly what co-residency reaches
([inference-model-manager.md](inference-model-manager.md),
[ADR-0030](../adr/ADR-0030-brain-handoff.md), [ADR-0004](../adr/ADR-0004-model-lineup.md)).

The first of that pair closed the same day, hours later, and the count stayed at **8**: one out,
one in. **What made it buildable was the instrument warning, not the flag.** The entry asked for a
check "at wiring time or at swap-in", and reading its own text against the measurement rules out
the first half: a card's free memory changes by the gigabyte while the machine runs, and at boot
the cortex is resident, which is not the residency the deep model loads into. The same measurement
rules out reading the card *after* the load too, since that is the reading a fit and a 4676 MiB
spill agree on. **Free memory is evidence at exactly one instant**, before the allocation and after
everything the handoff means to unload is gone, which is inside `swap_in` between the last `stop`
and the `start`, and that is where the refusal went. The sidecar answers `device_memory()` off its
existing `GET /health` over an `nvidia-smi` seam (any failure, and any second visible GPU, reported
as no reading rather than a guess), the deployment declares the deep tier's cost as
`CORTEX_SWAP_BRAIN_VRAM_MIB`, and a card that is short, or a host that can see none at all, fails
the handoff closed with the standing residency untouched. `CORTEX_SWAP_CORESIDENT` without that
figure is now a boot failure on the real supervisor, which catches the constant half of the claim
where it is constant. Live, on the same card as the morning's measurement: **14905 MiB free of
24463 with the cortex resident refused a declared 19125 MiB in 0.03 s and started nothing**, and
the same call with the cortex evicted passed and loaded the deep model to `ready` in 69.24 s with
3579 MiB to spare. The entry's own price is corrected in its close: the brain still does not depend
on the sidecar answering at wiring time, so the stop-bounds entry's objection never applied. What
opened in its place is the honest residue, and it is the instrument lesson from the other side: a
declared figure nobody verified, or a gigabyte taken by the desktop during the load, both spill
past a check that already answered, and **the only witness of a spill is decode rate, which nothing
in the brain watches** ([inference-model-manager.md](inference-model-manager.md),
[ADR-0030](../adr/ADR-0030-brain-handoff.md)).

The second of that pair closed a few hours after the first, on the same day it opened, and the
count went **8 to 7**: one out and none in. It was filed fix-when-it-bites, and taking it anyway is
the judgement worth recording, because its trigger is not an event anybody waits for but a setting
a deployment turns: raise `CORTEX_VRAM_SOFT_CAP_GB` far enough to admit a GPU-placed spawn at all,
which a 24 GB card invites, and every co-resident handoff reaches it. Both of the entry's claims
about the code were re-derived first, as this file's standing warning demands, and both held, the
port change included, which is the claim this area has twice got wrong. What landed is the
placement epoch the entry named: `SubagentPlacer` grows `charge_handoff(resident_gb=...)` and
`charge_standing()`, written by the residency scope at the two edges of the swap, so the fit-test's
resident term names the model that is on the card rather than the cortex the handoff evicted. **The
figure charged is the declared one and not a fresh reading**, which is the design decision inside
the design: `place` is synchronous and lock-free so a batch of concurrent spawns races the ledger
correctly, and a `device_memory()` call there would put HTTP inside a fit-test to re-buy accuracy
the swap already bought, since the room check compares that same declared figure against the real
card at the one instant a reading means anything. The two compose by ordering rather than by
agreement: the charge is written **before** `swap_in`, so it holds while the check reads the card
and while the weights load, which shuts the one gap the check cannot see, a spawn admitted into the
room the reading just measured. The reversal fires only once the cortex is genuinely serving again,
so a restore that gave up keeps spawning on the CPU rather than admitting GPU work onto a card
nobody can describe, and a deployment that declared no figure keeps the arithmetic it always had,
because charging a zero would hand the whole soft cap to the pool. Live on the 24 GB card through
the real sidecar and a real residency change: **15061 MiB free of 24463 with the cortex resident,
19553 MiB free inside the window**, a charge of 18.68 GiB leaving 4.32 GiB of headroom against the
shipped 5.5 GiB ask, so one spawn lands GPU, CPU and GPU again across the two edges. What it does
not close is what nothing here measures: a declared figure that is too low, which is the sibling
entry above, and a ledger that charges per spawn for a standing tier a spawn allocates nothing on
([inference-model-manager.md](inference-model-manager.md),
[ADR-0030](../adr/ADR-0030-brain-handoff.md),
[ADR-0012](../adr/ADR-0012-resource-governance.md)). One thing there is nothing to strike for: the
bucket below never carried this entry, though it was filed fix-when-it-bites in the morning and its
sibling was listed the same day, so a reader finding no struck line there is seeing an omission
rather than a close that missed one.

Resource governance went **5 to 6 on 2026-08-07**, and both halves of that are unusual. The item
that landed was `CORTEX_VRAM_CORTEX_GB`, the term the placer subtracts from the soft cap on every
spawn's fit-test, and **it had been deferred at two ADRs and recorded on no index at all**: ADR-0004
saw the cortex read about 9.7 GB against its own 11.0 and asked a later sitting which figure the
deployment pays, and the co-residency close that morning measured 8448 to 8468 MiB and deliberately
left the reservation alone, on the correct reasoning that lowering it widens what the placer admits.
Neither wrote a line anywhere that counts open work, so for three days a number bounding every
admission sat outside every count, which is the doc-first rule's own failure mode and is recorded in
the area doc rather than quietly repaired. **The published figure was an idle one and a reservation
has to cover a peak**, which is why this was never the one-line edit it looked like. At the shipped
tier shape, read out of the running child's argv rather than the compose file, the cortex is 8400 to
8484 MiB idle and **8573 MiB at its peak** above a floor read with the tier stopped at both ends of
the session, 1261 to 1301 then 1259 to 1308 MiB, agreeing within 7 MiB so no drift is folded in. A
13180-token prompt with 924 tokens decoded allocated **nothing**, llama.cpp taking the 16K KV and
the compute buffers at load; the only thing that arrives with the work is the vision path's 70 to 90
MiB on the first image, and it stays allocated afterwards. And most of the apparent gap was a unit
rather than a build: 11.3 was `nvidia-smi` total used with the desktop's own floor inside it, while
every other term in that budget is a tier's own cost, so the reservation was about 1.7 GiB high read
its own way and about 2.6 GiB high read the budget's. The default is **8.6 GiB**, 233 MiB over the
peak, a margin sized against the sampler's in-phase spread, the floor bracket and one more
vision-sized allocation rather than picked round. Headroom goes 2.7 to 5.4 GiB, so a spawn declared
at the GPU tier's measured 3319 MiB is placed on the GPU where nothing ever was. **What opened is
the term the sitting refused to bend.** 8.5 would have exactly admitted the 5.5 GiB
`docker-compose.subagents.yml` asks, and choosing it would have been choosing the answer on a 131
MiB margin; the ask is itself about 2.3 GiB above what the tier measures, so correcting the
reservation to match it would have left two wrong numbers agreeing. It is now the only reason the
shipped stack still refuses a GPU placement, it is pinned by a test so a later reservation change
cannot flip that silently, and it is filed fix-when-it-bites
([resource-governance.md](resource-governance.md),
[ADR-0012](../adr/ADR-0012-resource-governance.md), [ADR-0004](../adr/ADR-0004-model-lineup.md)).

Body & overlay went **11 to 10 on 2026-08-07**, one out and none in, and the entry that closed was
filed about one key and answered for a table of six. `Ctrl+K` toggling a section nobody can see is
now a rule rather than a fix: a global key aimed at one of the panel's surfaces puts that surface on
screen, and off the chat it opens rather than toggling, because what a reader can see is a shut
switcher whatever the flag says. The key table was enumerated from the code before anything was
decided, and it is six keys on one listener, `Escape`, `?`, `Ctrl+N`, `Ctrl+K` and the two cycle
keys, with the summon outside it as a host hotkey. Four already landed where they act, and **the
entry named one broken key where the measurement found two**: `?` from a tucked panel mounted the
console and took the chat pane `inert` and `aria-hidden` behind a window that was not on screen,
which is the same defect a key over and would have survived a rule written for `Ctrl+K` alone. That
is the sixth entry in this chain to undercount its own doors. The argument for summoning rather than
refusing is the precedent already in `sessionState.ts`, where a cycle key loading a conversation
behind a standing console is called a surprise and answered by taking the console off; the shipped
change is nine lines, the whole on-the-chat column of the trace is bit identical afterwards, and the
`onChat` predicate that used to decide whether a sentence would be true now decides whether a press
is a toggle or a request. Nothing was deferred behind it
([body-overlay.md](body-overlay.md), [ADR-0035](../adr/ADR-0035-console-and-motion.md)).

Resource governance went **6 to 5 on 2026-08-08**, one out and none in, and the entry that closed
was one day old: the subagent VRAM ask, which the reservation re-measurement the evening before had
left as the only term still refusing every GPU placement. It was filed fix-when-it-bites and taken
straight away for the reason the reservation's own close gives, that the trigger is a deployment
wanting GPU subagents and the shipped stack is that deployment the moment the arithmetic allows it.
The ask is **3.5 GiB** in both of its declarations. Measured at the shape read out of the running
child's argv rather than the compose file (`-ngl 99 --ctx-size 8192 --parallel 2`, thinking off, no
projector), with the cortex resident throughout and `nvidia-smi` total used sampled every 0.2 s, the
tier is 3228 to 3355 MiB idle and peaks at **3410 MiB** above a floor read with it stopped at both
ends of the session, 10448 to 10500 then 10428 to 10493 MiB, agreeing within 20 MiB. Twelve requests
each filling its slot's whole half of the 8192 KV, 3803 prompt tokens plus 293 decoded for exactly
4096, moved nothing past the idle band's own spread: this tier carries no projector, so unlike the
cortex the peak is a load-time figure with no late allocation at all, and the 174 MiB margin covers
the sampler's spread and the floor bracket twice over. **The entry was right about the placeholder
it named and wrong about the one it mentioned in passing**, which is the part worth carrying
forward: 5.5 was about 2.1 GiB high as recorded, but the code default of 2.0, the one every doc
called GPU-less-safe, was about 1.3 GiB **low**, so a deployment wiring subagents without that
compose file was admitting a spawn onto room the tier would overrun. Proven on the stack rather than
in the gate alone: under the old ask the live GPU arm could not select itself and the tier served no
task, under the new one it places a spawn that answers in 152.11 ms against 13134.73 ms for the
sibling that overflowed, and the arm was reddened first by pointing the GPU endpoint at a closed
port. What it does not close is what nothing here measures: the ledger charges one tier's whole
footprint per spawn while a second spawn onto that standing process allocates nothing, so the
refusal of the second buys decode speed rather than memory, which is the older modelling gap
([resource-governance.md](resource-governance.md),
[inference-model-manager.md](inference-model-manager.md),
[ADR-0012](../adr/ADR-0012-resource-governance.md)). Every term of that budget is a measurement now,
and the two declarations of this one are tied together by nothing but the comments that say so,
`crosscheck.py` reading module-level constants where these are a pydantic field default and a
compose environment value.

## Recommended order

Ordered by what unblocks the most value soonest. Before starting any item, verify its claims
against the code (the warning above); the entry text tells you which seams it expects to hold.

### Actionable now

- **The recall rank's default, which is now a decision rather than a measurement**
  ([memory.md](memory.md)): `CORTEX_MEMORY_RECALL=judge` was left off on cost alone, and bounding
  its request on 2026-08-06 took that cost from about 12 seconds per recall to 0.9 while the
  ranking stayed exactly where it was (mean reciprocal rank 1.000 against the shipped cosine's
  0.917, the right note first 6 of 6 against 5 of 6, no fallbacks, and fewer hits than `k` because
  it drops the notes that do not help). **The corpus objection was answered the same evening** and
  the entry is stronger for it: 41 notes and 26 questions across six categories, five of them cases
  the judge could have lost, scored through the shipped pool width with a reversed-cosine control
  arm at 0.000 to prove the scorer could fail. The judge is worse nowhere, ties at 1.000 wherever
  the geometry was already right, and beats the cosine on the vocabulary trap (1.000 against 0.806)
  and on superseded facts (1.000 against 0.750), at 0.75 s per recall. It is still hand built by an
  interested party, which no amount of widening fixes. What is left to weigh is that a rank runs on
  every recalling turn, where the history fold it borrows the lever from is cached per boundary
  move, and that on a question memory cannot answer the judge's correct refusal is currently spent:
  the policy reads an empty pick as a failure and returns the cosine's wrong notes instead, filed
  as its own entry. Nothing is blocked: it is one env variable either way, and
  `CORTEX_MEMORY_RECALL_AUDIT=1` reports which policy actually ranked each recall afterwards.
  **Closed 2026-08-08, measurement first and then the flip.** The one objection that survived every
  widening was that a rank is not a turn, so the turn was measured: 48 real turns an arm through the
  seam on the 24 GB card, in A/B/A order with a raw block either side of the judged one, each turn a
  fresh session pre-seeded with the same 41 notes. **Time to first token rises 0.515 s** (95% CI
  0.116 to 0.915), the whole turn 0.526 s, while raw against raw is -0.158 s with an interval
  spanning zero, so the harness separates the arms it should and not the arms it should not. The
  turn pays less than the rank's own 0.877 s at the pool assembly asks for, because a rank that
  keeps 1.17 notes leaves the reply less to read than the cosine's 5. It is paid every turn and
  nothing caches it, which is confirmed rather than softened. `CORTEX_MEMORY_RECALL` now defaults to
  `judge` and `raw` is the opt-out. The refusal entry below closed the day before this, so the flip
  ships the abstention it was the trigger for rather than the defect it would have exposed.
- **The abstention the judge can reach and its policy cannot report**
  ([memory.md](memory.md)), opened 2026-08-06 by the widening above. Asked a question nothing in
  memory answers, the model replies `{"order": []}`, which is correct, complete and unparseable as
  a pick, so `JudgeRecallPolicy` falls back to the cosine and hands the turn three irrelevant
  notes. Needs a third `RankBasis` and a `select` that may return nothing, which changes what a
  recall can mean rather than how it ranks. **Trigger:** flipping the default to `judge`, since
  nothing can hit this while the policy is off. **Landed 2026-08-07 ahead of that trigger**, the
  deferral's stated cost being the reason to wait and the code not confirming it: two of the three
  consumers it named already meant the right thing by zero hits, so the change is the `DEMUR` basis,
  a `parse_order` with three outcomes rather than two, and one branch in `select`. Measured on the
  corpus that found it, the four unanswerable questions now return nothing 4 of 4, the run fell back
  0 of 26 where it fell back 4, and the ranking on the 22 answerable questions did not move. What
  the close leaves behind is filed in its place below: the refusal is the judge's alone, so a
  deployment on any geometric policy still gets its nearest misses.
- **The vision measurements this repo owes itself** ([vision.md](vision.md)): an image arm of the
  injection-defence harness against a rendered-payload corpus, plus the two agent-Docker checks
  ADR-0029 listed as still to run and nothing tracked until 2026-07-19 (whether thinking needs
  disabling on a vision turn under the shipped parts payload, and `llama-server`'s `mmproj`-less
  error body text, which the bounded 300-character non-2xx excerpt was built to surface). Nothing
  blocks any of the three. They are agent-side under [AGENTS.md](../../AGENTS.md)'s rule that "on
  the host" includes the agent, and the same 8 GB dev GPU that drove the real cortex beside its
  projector on 2026-07-18 is enough for all of them. The hand-run injection arm in that ADR's
  closeout is one corpus of one, which is exactly why the harness arm is still owed and why its
  number gets published whatever it says. **The two agent-Docker checks ran and closed 2026-08-03**,
  leaving the harness arm as the whole of this item: thinking needs no disabling because the shipped
  request carries no `max_tokens` against a server reporting `n_predict: -1`, so a vision reply
  cannot be truncated to nothing, and what thinking costs is 5 to 6 seconds before the first word on
  a simple screen against 0.4 on the pixel-less control arm; and the `mmproj`-less body is 151 bytes
  of JSON naming the projector in llama.cpp's own words, well inside the excerpt bound, now pinned
  by a live canary that was proved able to fail. **The harness arm ran and closed 2026-08-04, so
  this whole item is done**, and its number does what the entry promised it might: against a corpus
  of ten attacks in each of three renderings, the shipped preamble holds over pixels for every
  hijack-shaped attack and does **not** hold for content manipulation, which is the one attack the
  preamble was hardened for over text. The expensive part was not the rendering, it was learning
  that a canary detector inherited from the text channel cannot tell obedience from diligence in
  the pixel one, since describing the screen is the benign answer and a description quotes the
  payload.
- **The `VramBudgetPlacer`'s GPU arm against a real placement**
  ([resource-governance.md](resource-governance.md)), the mechanism half of what was filed whole as
  host work on 2026-07-19 and split back the same day. A GPU placement **beside a resident cortex**
  needs the 24 GB card and stays item 6 of
  [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md), because this card holds the cortex with
  roughly 470 MiB to spare. The arm firing at all does not need a cortex resident: the budget is
  three env values, the tier is one small artifact behind `CORTEX_MODEL_FILE_SUBAGENT_GPU` on the
  supervisor's `:8083`, and what gets proven is the route from a GPU verdict to an `-ngl 99` process
  and the ledger that accounts for it. Same mechanism-versus-tier-scale split the swap already runs
  on. **It ran and closed 2026-08-04**, and the arm fired: with the soft cap sized to the real card,
  two concurrent spawns of one entry went one to the hosted `-ngl 99` tier and one to the CPU
  server, the GPU one answering in 221.05 ms against the overflow's 12536.83 ms, and with the
  shipped soft cap the same batch left the tier untouched. Its own suite was proved able to fail
  first, by pointing the GPU endpoint at a closed port: the placement then re-runs on the CPU and
  the assertion reddens on the third one. **The split this bullet describes then dissolved.** The
  "roughly 470 MiB to spare" above is the 8 GB card's remainder and not this one's, so the run kept
  the cortex resident and the placement beside it was simply what happened: host item 6 closed the
  same day, its finding being that the shipped placeholders and not the card are why nothing was
  ever GPU-placed.
- **A delegated tool step is announced and never settled** ([subagents.md](subagents.md)), opened
  2026-08-06 by the capture indicator's outcome landing and **closed 2026-08-07 as declined on
  merits**, its reopening trigger recorded on the dead-until-a-consumer list below. The gap was
  real and reproduced on the first run (three `tool_activity` events against one `tool_outcome` on
  a real delegating stream), and the entry was wrong about the cost, about the consumer test, and
  about what the fix would buy. What the pass actually repaired is the contract: the proto, the
  body's `TurnEvent` and `docs/modules/body-core.md` all stated the pairing as a property of the
  stream, which the delegated activity riding that same stream makes false.
- **The spontaneous-pick nudge's live uptake** ([subagents.md](subagents.md)), whose fix stays
  fix-when-it-bites but whose *observation* is runnable here: a resident cortex at 4K with the
  CPU roster up, given a prose-only ask carrying independent subtasks, either reaches for distinct
  roster models or does not. Listed here because the entry said for three days that no card
  available to the agent could answer it. **It ran 2026-08-04 and did not close the entry**, which
  is the honest outcome rather than a stalled one: the observation this bullet owed is published
  and the fix it feeds stays queued. The recipe above was wrong about its own premise, since a
  prose-only ask produces no batch to spread (20 turns over four such asks, zero spawn calls, and
  the four words a delegating trace would use absent from every full reasoning trace). Invited to
  delegate in plain prose it delegated in all 16 turns and put the whole batch on one roster entry
  in all 16. Reading the spec builder afterwards found the sharpest part: the knob and the spread
  sentence are advertised only to a tool-less multi-entry deployment, since any tool registry makes
  subagents tools-enabled and swaps in the pinned note. The run also outgrew this bullet's own
  recipe by using the production 16K context rather than 4K, so what stays host-side is real use
  over time and not a context size.
- **An exit for the switcher's rows** ([body-overlay.md](body-overlay.md)), opened 2026-08-03 as
  the reminder stack's per-row exit closed and left the hook behind for it, and **closed 2026-08-03**
  by wiring the switcher to that same hook. It called itself mostly wiring and was about half of
  one: the shared hook put a departed row back at the index it held, which the reminder stack can
  rely on because it only ever loses rows and the switcher cannot because it re-lists pinned-first
  after every write, so a row that leaves now goes back under the row it was UNDER, with the index
  as the fallback. Two of the three hazards the entry named did not apply (the switcher draws no
  hairline between rows, and all four of its hover, pinned, rename and confirm rules read down to a
  descendant and follow the row's box inside the wrapper), and the one that mattered was not on its
  list: `min-height: 50px` outside the roll is a floor the roll cannot get under. Two more the entry
  did not have: a row held after its chat is gone is 300ms of live buttons offering to open and
  re-delete it, and the demo bridge could not delete at all, which made the whole thing
  unmeasurable by hand. What it left behind is the entry below.
- **Two motions in the switcher's list are still instant** ([body-overlay.md](body-overlay.md)),
  opened 2026-08-03 with the exit above and **closed 2026-08-03**, both motions landing and the
  first one not by the fix the entry proposed. Every number it published measured true again,
  including its reading of the panel, and what was wrong is that it is one flag at all: the
  direction that must be instant is a plain unmount and only the other one is an animation. The
  empty line is asked of `sessions` now, so it goes up in the frame the last row STARTS leaving and
  grows from nothing over that row's own roll (`Collapse` gained an `enter` prop, read once at
  mount), and it is unmounted in the frame a chat arrives. The card never returns to 14: it eases
  64 to 53 over 283.9ms at a largest single frame of 1.66px, and the panel, which used to walk 108
  to 119 and correct itself afterwards, does not move at all. The filling direction stays an 11px
  step on purpose, a line's 39px replaced by a row's 50. The reorder landed as FLIP, as the entry
  described it, with the leaving row on the same clock because it is one of the rows the hook
  watches. Two things it did not have: a travel is a transform, so the panel cannot be fought by it,
  and FLIP's "before" cannot be read at the previous commit, a roll moving rows by layout with no
  commit in it, so the record is refreshed every frame while a roll runs and played from only on a
  commit.
- **A shrink against the ceiling still moves the composer, and the user picks the fix**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20 and **closed 2026-08-06 as MOOT, with
  nothing for the user to pick**. The entry held that reversible switcher round trips and a composer
  that never moves are the same statement with opposite signs once the panel is clamped. HEAD
  delivers both, so there is no opposition and there was never a decision to make: the mechanism the
  entry describes, a clamp applied to the pinned EDGE, was deleted thirty two minutes after the
  entry was written on 2026-07-20 and replaced by a clamp on the HEIGHT, which is why nothing pulls
  the bottom edge back on a shrink. Driven by hand in a browser at 640x720 with the panel against
  its 450px ceiling, the composer's own box top reads 445 on every frame of an ack that gives back
  58px of content and on every frame of a switcher round trip, which returns the panel to the
  identical 184px edge and 450px height; acked all the way off the ceiling, the panel gives the room
  up at its TOP edge (86 to 184) with the bottom edge and the composer unmoved. Same at 900x900, at
  a 274px edge with the composer at 535. The arm was reddened first by restoring the deleted clamp,
  where the same ack settles the composer 58px away through a 96px excursion. Its rarity number was
  wrong too: 615 is not a growth delta but the ceiling's VALUE for a 546px panel centred at 900px,
  real headroom being `342 - h/2` there, at most 342px for any panel and 0px for the demo's own
  arriving chat. **Put to the user 2026-07-20 and again 2026-08-04**, both times as a live choice,
  and both times it had already been answered by the code. This was the one actionable-now item
  whose whole remaining cost was a decision; the bucket now has none.
- **A placement can be left computed for a height the panel no longer has**
  ([body-overlay.md](body-overlay.md)), found 2026-07-20 and **closed 2026-08-03** as the
  `ResizeObserver` it names, `overlay/panelWatch.ts`, driving the same placement the roll's end
  event drives. That event is NOT retired and cannot be: measured with the observer itself, a roll
  ends without changing the panel's size, so nothing but the event says a roll is over. The
  published cost did not move, being at most a pixel, and the case it was measured on no longer
  settles at HEAD; the general case does, and 40px appended straight into the log now eases over
  about 120ms where it went in one frame.
- **A touch mid-roll leaves the session pinned to a prediction, not to a measurement**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20 and **closed 2026-08-03 by something
  other than what it asked for, at 97px rather than 2.1**. The prediction is exact, the rolling
  section's current height cancelling out of it. What was wrong was the aside: the ride-along asked
  whether the section that is ROLLING is the reminder stack where a placement asks whether the view
  being placed HAS one, so a stack merely standing in the panel was counted into the arrival's
  centring and out of the placement's. Both now count it through `centringHeight`, bounded at
  `openHeight` first because that is the order the measurement happens in.
- **The composer's own growth is the one resize the panel never eases**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20 and **closed 2026-08-03** on the same
  watch as the stale-height entry, with which it did share the whole of its fix. All four steps are
  paced eases now, the largest single frame 17.67px where a Shift+Enter moved 52px in one and
  26.27px where a paste moved 98 (the 122 the entry published is 98 once the panel is on its own
  ceiling and the history absorbs the rest).
- **Sections tall enough to outrun the panel on their own**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20 and **closed 2026-08-03** as the cap
  that knows about its neighbours, with three of its own claims corrected upward
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). It was not a corner needing both
  sections full: the demo's own two chats and three reminders put the hint strip 29.75px outside
  the panel the moment the switcher opened, this entry having weighed the sections against the
  547px panel of an 86px pinned edge where the state it describes stands 450px tall on a 184px one.
  It was not bounded at the hint strip either: with both sections at their caps and no draft at all, the composer was 204px
  outside and the hint strip 246px. And it is worse on a bigger screen, the caps being viewport
  fractions where the panel's ceiling is not (450px outside at 640x1400). It is a pair and not a
  family, the stylesheet's other two `vh` caps being inside the scrolling history where they cannot
  reach the panel's edge. The panel's ceiling is now published as `--ceiling` beside the
  `max-height` it equals, the column's own furniture is reserved off it (the header, the composer's
  84px floor and its margins, the hint strip, the history's padding), and the two sections split
  what is left four sevenths to three, which is the 40 and the 30 they were already written in. The
  composer and the hint strip cannot lose because they are never in the budget. All five states
  read 1px inside the edge afterwards; two bounds were opened behind it.
- **The two unpicked directions for the settings and shortcuts views**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-19 and **closed 2026-07-20**: the user
  picked both at once, and both landed as predicted, a component change on unchanged plumbing. The
  two views are one console with a tab strip and the theme choices are thumbnails of the panel
  wearing each theme ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 1).
- **Two overlay modules over the 300-line cap** ([body-overlay.md](body-overlay.md)), open from
  2026-07-20 and **closed the same day**, along the two seams the entry named: the turn-event fold
  left the reducer for `overlay/turnState.ts` (394 to 241) and the chat catalog left the controller
  for `overlay/useSessionCatalog.ts` (321 to 181), both re-entering through the module they left so
  no call site moved. Its closing line, that AGENTS.md's cap "is now met", was **corrected
  2026-08-03**: it held for one day, until `overlay/panelPlacement.ts` went to 304 and then 371 on
  2026-07-21 and stayed over the cap for thirteen days, since nothing but attention was measuring.
- **`bridge/demoBridge.ts` stays over that cap** ([body-overlay.md](body-overlay.md)), open from
  2026-07-20 and **closed 2026-08-03**, along the seam it named but against a corrected cost and
  two corrected numbers. Its 326 was stale the day it was filed (the file already stood at 351, and
  still did fourteen days later), and "the last overlay source above 300" was true for one day, per
  the correction above. The canned script left for `bridge/demoScript.ts` (141) and the bridge went
  351 to 234. The entry was right that an exclusion is required, measured rather than assumed: an
  unexcluded `demoScript.ts` reports 0% and takes the overlay from 100% to 97.45%, exit 1. It was
  wrong that this is the bigger concession, because the demo bridge has been coverage-excluded since
  it was written, so the cost is one explicit path extending an exclusion that already exists rather
  than a new kind of unmeasured file. The comparison had been drawn against a cap nothing enforced.
- **The chat floor's frozen measurement of the empty state**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20 and **closed 2026-08-03 as the custom
  property it asked for, over a defect it did not know it had** ([ADR-0035
  addendum](../adr/ADR-0035-console-and-motion.md)). The constant this entry was about had not
  existed for fourteen days: `.log`'s `min-height` was deleted about forty minutes after the entry
  was written, by the settings-tab slice, on the reasoning that the reminder stack now rolls away on
  the first message so the shrink is deliberate, which is true of a chat with reminders due and
  false of every other chat. Measured at 60Hz with the stack acked, at 900x900 and 640x720 alike,
  the first message took the panel 352px to 262px and back to 297px, with the composer's own top
  edge unmoved for every frame, so the entry's "a few pixels of dip" was 90px and arrived by
  deletion rather than by drift. `.log` now floors on `--chat-floor`, published by
  `overlay/measured.ts` from the empty state's own box, and the panel holds one height across the
  send in all four cases. Two of the three frozen numbers it named are retired: `--trace-row` goes
  too, the chip publishing its own box now that its floor (a no-op restating that box back at
  itself) is gone. The rail does not, for the reason below. The entry was wrong about the shape in
  one way worth keeping: a STARTUP probe cannot do this, there being no empty state and no chip at
  startup, so it would have to measure a hidden copy, which is this defect one layer down. The real
  elements are measured instead, as React attaches them and again whenever their box moves, because
  a single reading in the commit frame catches the empty state at 183px against the 185px it settles
  at once the system font stack resolves. Neither of the two numbers had drifted when audited, which
  is why the demonstration is the evidence: lengthening the invitation by one wrapped line takes the
  empty state to 201px, and the measured floor holds the panel at 368px across the send where the
  frozen 185px drops it to 352.
- **A Thoughts trace opening a reply off the bottom of a full history**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20, when the disclosure learned to roll,
  and **landed 2026-08-03** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The roll
  left the history's `scrollTop` alone and cost the tail of the reply once the panel could no longer
  grow: the distance from the log's bottom edge to the end of the answer ran 3px to 79px over one
  76px trace. It is the tail pin held across a roll now (`overlay/logRide.ts`): while the reader is
  at the end of the log, their distance from it reads the same on every frame of the roll, traced at
  640x720 as 3px throughout both directions with `scrollTop` running 408 to 484 and back, the largest
  single frame 12px, and the movement landing inside the roll's own 300ms. A reader who has scrolled
  up is left alone, since a section growing pushes only what is below it. The entry was wrong twice
  over. Its setup does not reproduce (the reminder stack is gated on an empty log and the ceiling at
  that viewport reads 450px, not 547px), and the second animation it prescribed is not what landed:
  the scroll is recomputed from the box on every frame of the roll, and the box is being resized by
  the roll's own height animation, so it inherits the clock and the curve by construction with
  `Collapse.tsx` untouched and no prediction of what the panel is about to absorb. The second job is
  done too, so `overflow-anchor: none` now gives up nothing: closing a trace scrolled off the top of
  the window eases `scrollTop` 487 to 411 with the visible content holding to under a pixel. It
  opened one entry behind it, the panel's own chrome shrinking the log from outside the box, which
  closed the next day on the same ride.
- **A section rolling in the panel's chrome shrinks the log, and nothing answers it**
  ([body-overlay.md](body-overlay.md)), open from 2026-08-03, when the ride above landed, and
  **closed 2026-08-04 on that same ride**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The setup reproduced exactly (the
  log's window 293px to 73px with `scrollTop` untouched, the reader's distance from the end of the
  reply 3px to 223px, the start event reaching the column and the panel and never the box), and the
  sentence that sized the work did not: **wiring the ride up with its arithmetic untouched changed
  nothing at all.** The cap that keeps a rolling section's top edge on screen reads the room between
  that edge and the box's, and a section in the chrome sits above the box for every frame, so the
  floor under that room froze the ride where it started (`scrollTop` 173 on every frame, byte for
  byte the trace with nothing listening). One line says what the cap always meant, that only a
  section INSIDE the box is something the reader can be carried away from. The entry's pair is also
  one section and a family: the reminder stack is gated on an empty log, so it can never cost a
  reader anything (0 and 0 on all 21 painted frames of an ack), while every ROW inside those lists
  rolls the same way and a deleted chat moves the log exactly as its list does. After, the tail
  holds at 3px for all 19 painted frames of the switcher's roll in each direction, `scrollTop`
  running 173 to 393 and back to the pixel it started from, and the three panel motions the entry
  asked to be measured against are each clean: a summon with the roll landing 100ms into its
  arrival, a new chat that empties the log, and the ack above.
- **The console's tab strip is a tab list by role but not yet by keyboard, and the pane it is
  leaving stays tabbable while it fades** ([body-overlay.md](body-overlay.md)), open from
  2026-07-20, when the two settings views became one console, and **both halves closed 2026-08-03**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Focus already travelled with the
  view, which is what made the leaving pane's `aria-hidden` take effect at all; what landed is the
  rest of the pattern. The strip is one stop in the tab order (a roving `tabIndex` needing no state
  of its own, since selection follows focus), the arrows walk it and wrap while Home and End go to
  the ends and do not, and the leaving pane is `inert` as well as `aria-hidden`, from one function
  used in all three places the overlay holds something mounted that is not on screen. The entry's
  React 19 blocker was not real: only the type is missing from React 18, the attribute itself being
  written straight through from a string, which one probe against the tree's own react-dom settled.
  The 380ms morph was also not the only window; the 200ms tab crossing and the dismissed panel had
  the same defect, at six reachable stops each. What it consciously did not do is the switcher's
  role mismatch, the next bullet.
- **The chat switcher claims a listbox role its own rows do not satisfy**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-03 by the pass above, which checked the
  overlay's other lists and found one whose gap is a different shape, and **closed the same day** by
  the user's answer: the role comes off and the switcher is the list of composite rows it already
  behaves like ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The entry was right
  that this was a decision rather than a defect list and understated the defect twice. A `<li>`
  inside a listbox is not a listitem, so the rows were not announced as anything at all: Chromium
  read `listbox "Recent chats"` over three children of role `none`, a listbox with no options in it
  holding twelve loose buttons, and with the role off the same tree reads `list` over three
  `listitem`s with nothing written on the `<li>` to get them. And "nothing else changes" missed a
  channel, since which chat is open was a background tint and nothing more, so the row button
  carries `aria-current` now, `aria-selected` being exactly what the dropped role would have cost
  it. The tab order is untouched at four stops a row, twelve across the demo's three chats, and
  Ctrl+Up and Ctrl+Down needed no reconciliation, being an application-wide cycle rather than
  movement inside a list. The reminder stack was read in the same pass and needs nothing, and a
  section rolling shut is deliberately left tabbable, being still announced too.
- **The chat cycle keys swap the conversation without saying so**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-03 by the answer above, which left Ctrl+Up
  and Ctrl+Down as the application-wide cycle they are. A press replaces the whole conversation
  with focus left where it was, and nothing announces it: measured at 900x900, two presses walk the
  header title through three chats while focus stays on the header's chats button, the first press
  closes the switcher, and the page's only live region is the link indicator reading the brain's
  health. The listbox shape would have answered this by moving focus, which is the shape that was
  rejected, so what fits is a polite live region naming the chat that arrived rather than a focus
  move, plus a look at the other doors into the same swap so a reader is not read back a title it
  just clicked. **Closed 2026-08-04** by the region it asked for, which says `Switched to <title>`
  at the overlay's root ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Every number
  above measured true again first. The entry was wrong four times over and each one moved the fix:
  the page's live regions are one only as the page happens to stand (the capture ring and an
  errored bubble mount conditionally beside the dot); `state.title` holds the arriving title only
  after the swap, so the notice is the title the reducer arm computes rather than one read at the
  keypress, a failed history load leaving the old chat in place; the doors are seven rather than the
  two it named, `Ctrl+N` and the chat replacing a deleted one being just as silent; and the rule
  cannot live in the reducer arm, one arm serving a switcher row and a cycle key both, so the flag
  travels with the action. Speaking: the cycle keys, `Ctrl+N`, a reminder's open control, and the
  chat that replaces a deleted one. Silent: a switcher row and the header's pencil, both already
  named for what arrives, and cold-start adoption. Two things the entry did not have: a silent door
  clears the notice, and a count keys the region's child so a second chat under one title is a
  second announcement. It opened the focus entry below.
- **A swap fired from inside a section that closes with it drops focus on the floor**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-04 by the answer above, which put the
  arriving chat into speech and left focus alone on purpose. A switcher row, a reminder card's open
  control and a delete confirm all sit inside sections the swap takes away, and `Collapse` unmounts
  its child at the end of the roll, so the focused control stops existing and the browser falls
  back to `<body>`: measured at 900x900 on all three. Nothing is misannounced (a live region reads
  regardless of focus, which is why it did not block that answer), but the reader ends up outside
  the panel entirely. The work is deciding where focus belongs after a swap, the composer and the
  header's chats button being the two candidates and a delete wanting a third answer again, since
  the switcher deliberately stays open behind it; the wiring is small once that is settled.
  **Closed 2026-08-06** by the user's answer, which is the composer, for the delete confirm as well
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). One rule ships, that a conversation
  arriving on the panel takes the caret with it, as a count each swap arm raises and the composer's
  existing focus effect reads. Unlike the notice above it, nothing travels with the action: this
  rule is about the transition rather than the gesture, so every door on an arm gets the same
  landing. The entry was right about one door of its three, the switcher row, which holds focus for
  its roll and reads the body after; the other two lose it in the commit itself, a reminder stack
  being keyed on the chat and remounting rather than rolling, and a leaving row going `inert` at
  once. And the doors are not three: `Ctrl+N` from a switcher row has the identical defect, so this
  belongs to where the gesture was made rather than to which control made it. After, every door
  that swaps reads the composer at 0ms and holds it, and the panel's roll under the swap is frame
  for frame what it was. It opened the two entries below.
- **The switcher's and the reminder stack's own row gestures drop focus with the row**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-06 by the answer above, whose rule reaches
  only the gestures that replace the conversation. A rename opened, a rename committed, a delete
  asked, a delete confirmed on a chat that is not the open one, and a reminder acked each take the
  pressed control away and swap nothing, so each still ends on the body (the ack after its roll, the
  rest at once, all measured at 900x900). Each wants an answer of its own shape rather than the
  composer, a rename editor its own input and a leaving row the row or the list around it, so it is
  one decision about what a list does with focus when it changes shape under the hand plus small
  wiring per gesture. Nothing blocks it. **Closed the same day, the decision being the
  implementer's** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)): a list that reshapes
  under the hand keeps the caret. A row that changes shape hands it to the control the new shape puts
  in the place of the one that left, a row that leaves hands it to the same control in the row that
  inherits its place, and a list with no row left hands it to its anchor, which is the header's chats
  button for the switcher (still open, saying it holds nothing) and the composer's field for the
  reminder stack (whose section leaves with its last row). The entry filed five gestures and there
  are thirteen, its predecessor's lesson repeating one entry later, and the mechanism is an unmount
  rather than the `inert` that predecessor found: a row's shape change takes the pressed control out
  of the tree. Two findings it did not have, both fixed here: Escape cancelling a rename also
  dismissed the whole panel, and `?` typed into that editor opened the console, the global guard
  having named the composer's textarea alone. And two decisions made against measurement rather than
  practice: the confirm opens on its cancel, since with focus on its yes one further Enter deleted
  the chat, and the caret moves at the commit rather than at the end of the roll, since the control
  aimed at was on screen all along. It opened the two entries below.
- **A modified chord still reaches the overlay from inside a row's editor**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-06 by the answer above, which made the rename
  editor somewhere the caret lands rather than somewhere it is clicked into. Escape and `?` are
  answered there now; `Ctrl+N`, `Ctrl+K` and the cycle keys are not, so `Ctrl+N` mid rename mints a
  new chat and discards the edit. Arguably correct, a chord being a deliberate act rather than a
  character somebody is typing, which is why it was not changed with the other two; recorded because
  it was decided rather than measured and because the next field the overlay grows asks it again.
  Nothing blocks it. **Landed 2026-08-07 as a rule about what a field would LOSE rather than about
  what a chord IS** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Measured first, at
  900x900 with "a brand new name" typed into a row: all four chords discarded the name and the row
  read its old title when the list was reopened, `Ctrl+K` leaving the caret on `<body>` besides. Two
  of the four turned out not to be the overlay's to take at all, `Ctrl+↑` and `Ctrl+↓` moving a bare
  input's caret to 0 and to 16 from offset 6 with nothing listening, so half of this was a collision
  rather than a priority. A chord now passes through a field whose text the overlay keeps and is
  held by one whose text it would throw away: the composer keeps every keystroke under its chat, so
  every global key still works from where a summon lands, and the rename editor keeps nothing, so it
  holds the press until Enter or Escape has settled the name, both one press and both leaving the
  caret on the pencil. Auto-committing was rejected as a store write nobody asked for, and the delete
  confirm still passes chords, holding no text to lose. The entry's stated cost was wrong: it landed
  as `overlay/fieldKeys.ts` plus the row, not as a guard in `Overlay.tsx`, which would have had to
  name the editor by selector and spare the composer by name. It opened the entry below.
- **A list the reader opens leaves the caret four Tab presses from itself**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-07 by the close below, which settled the
  closing direction and left the opening one exactly as it found it. Measured at 900x900: `Ctrl+K`
  from the composer opens the switcher and leaves the caret in the field, six Shift+Tab presses away
  from a row (the chips, the mark, both reminder rows), and opening it with the header's chats button
  leaves the caret on the button, three Tab presses of header ahead of the first row. A keyboard
  reader is shown the list and left standing away from it. The decision is not a line: moving the
  caret into an opening list would pull a reader out of a half typed sentence, which is the hazard
  the closing rule guards against, and it has to choose a row and answer an empty list; the cheaper
  shapes are a header order that puts the list beside the control that opens it, or nothing at all.
  Wants the same trace across the opening roll plus a tab order walk written down. Nothing blocks it.
  **Closed 2026-08-07 with the caret DECLINED and a sentence landed in its place**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The trace and the walk came first,
  over thirteen doors rather than the two the entry counted, and **its central claim held while
  every number in it was wrong**: the caret is untouched at all thirteen, but the six Shift+Tab
  presses are ten on the empty state and two in a chat that has messages, the distance being a
  property of what happens to be on screen between the composer and the list rather than of the
  design. Only its headline survived, the fourth Tab from the chats button reaching the first row.
  **The caret is declined on three measured reasons**: a guard is not optional, since `Ctrl+K` is
  pressed as often from the composer, and the mirror of the closing rule's guard is "only when the
  caret is on the anchor", which is the chats button, whose `aria-expanded` already reports the
  change under the caret that pressed it; the shape cannot answer an empty list, having no row to
  hand the caret to; and it would have to choose a row where the open chat frequently has none. The
  header reorder is declined too, buying three presses at that same answered door with a visual
  change made for a reading-order fact. **What the measurement found instead is that an opening list
  is inaudible**: eleven of the thirteen doors move no caret, change no control the reader stands
  on, and raise nothing in any live region, and on an empty list the tab order walks past the line
  saying so, which is text rather than a tab stop. So a list the reader opens now says what it holds
  (`Recent chats open. 3 chats.`), the contents and not the toggle, which is why closing has no
  mirror; the door decides as the swap arms' doors do, so the key speaks and the header's button
  does not; and a list that opened where nobody could see it says nothing. It opened the entry below.
- **`Ctrl+K` toggles a section nobody can see** ([body-overlay.md](body-overlay.md)), opened
  2026-08-07 by the close above, which measured the door and declined to answer it there. The chords
  are live while the panel is not on screen by design, and the ones that summon it set `mode` on
  their way through where `toggleSwitcher` sets nothing: measured at 900x900, `Ctrl+K` from a tucked
  panel mounts the list with its three rows and turns `aria-expanded` true with nothing on screen,
  and with the console up it does the same behind a chat view that is `inert` and `aria-hidden`, so
  the next summon finds the list open without anybody having opened it in front of them. The new
  sentence stands down for both, so the overlay no longer claims otherwise, but the toggle is
  untouched. The shapes are for the key to summon the panel the way `Ctrl+N` does, for it to be
  refused while the chat is not the view on screen, or for nothing at all. It is a decision about
  what the overlay's keys mean while it is tucked, which reaches the whole key table rather than one
  key. Nothing blocks it.
  **Landed 2026-08-07 as the summon, and for the whole key table rather than the one key**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Enumerated first: six global keys on
  one listener, four of which already set `mode: "panel"` and cleared the console on their way
  through or acted on whatever was topmost. **Two did not, where the entry counted one.** `?` from a
  tucked panel mounted the console and took the chat pane `inert` and `aria-hidden` behind a panel
  that was not on screen, with the caret left on `<body>`, so a rule written for `Ctrl+K` alone would
  have left its neighbour. Both now land on the chat, and off the chat both OPEN rather than
  toggling, which is what stops one press shutting a list the reader was never shown: measured after,
  `Ctrl+K` from behind a console with the list already open leaves the console and keeps the list,
  where it used to shut it silently. The announcement's stand-down went with the state it guarded,
  the key now speaking a sentence that is true, and the on-the-chat column of the trace is bit
  identical before and after. Five mutations redden five distinct cases. Nothing opened behind it.
- **A list the reader closes drops the caret, where a list that reshapes keeps it**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-07 by the close above, which shut one door
  onto it and left the others. The caret rule answers a row changing shape, a row leaving and a list
  running out of rows; a list the reader closes is none of those, and measured at 900x900 with the
  caret on a resting row's pencil, `Ctrl+K` left `document.activeElement` on `<body>`. Not one line:
  the switcher closes four ways, two of which already answer through the arrival rule, so what is
  wanted is a rule for the key and the header's chats button that moves the caret only when the
  caret is inside the list, or `Ctrl+K` from the composer would pull the reader out of a sentence.
  The anchor the list already carries is the landing. Wants the caret rule's own trace,
  `document.activeElement` sampled across the roll, before a shape is picked. Nothing blocks it.
  **Landed 2026-08-07 as a rule about a section CLOSING rather than about a key**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). The trace came first and the entry's
  own reading held: the caret rode the pencil for the whole 300ms roll and read `<body>` at 353ms,
  the loss being the unmount at the end of the roll rather than anything at the gesture. **The
  switcher does not close four ways but thirteen, and ten already answered**: seven are chat swaps
  the arrival rule takes to the composer, two are the console arriving over the chat and taking the
  caret to its own tab strip, and one is the header's chats button, which the entry wanted a rule for
  and needs none, its press putting the caret on it at 45ms before the close is dispatched. Two more
  are the panel being dismissed, where `<body>` is right rather than open. What shipped: a section the
  reader closes hands the caret to its anchor, and only when the caret is inside the section, the
  anchor being the one each section already carries for its emptied case. The guard was measured
  rather than assumed, `Ctrl+K` from a composer holding a half typed question leaving its caret at
  offset 4, and the rule stands down explicitly when a conversation arrived in the same commit rather
  than letting effect order decide. The reminder stack's own gap turned out not to be the stack's
  control at all but the empty state's example chip, whose press unmounts the surface it stands in;
  it is answered by the same rule told at the gesture. It opened the entry above.
- **A held chord says nothing about being held** ([body-overlay.md](body-overlay.md)), opened
  2026-08-07 by the same close. The new rule is deliberately silent: the press is stopped and the
  editor stays as it was, which is the whole explanation for a reader who can see it and thin for
  one who cannot, since focus sits on an input labelled "New chat name" and `Ctrl+N` produces no
  event, no focus move and no announced change. The shapes are the overlay's live region saying the
  editor is waiting, a `role="status"` line the editor owns, or nothing at all on the argument that
  a key doing nothing needs no narration. Wants the same measurement in a real reader the
  silent-shrink entry below wants, and the two are probably one pickup, both being about what that
  region's contract may carry beyond "the conversation that arrived". Nothing blocks it.
  **Sharpened 2026-08-07 by that entry's close, which answered the shared question and did not bundle
  this.** The contract is settled (the region may carry more than an arrival, and everything it may
  say is built in `overlay/notice.ts`), so the first shape is unblocked; three measured reasons keep
  it separate. A held chord destroys nothing, focus and value both sitting untouched on the input
  labelled "New chat name" before and after the press, where a deleted row is out of the tree and
  cannot be re-read. It is a different seam: every sentence the shrink added was already at a reducer
  arm, while the hold is decided in `SessionList`'s own state and publishing from it wants a callback
  through four components plus a controller member and an action, which is the entry's real cost and
  was never stated. And it carries a policy the shrink did not, keydown repeating while a key is
  held, so this is the one sentence a reader can raise dozens of times without moving. A fourth shape
  is now on the table too: say it on the editor itself, as a description the input carries while a
  chord is pending, which is re-readable rather than spoken once.
  **DECLINED 2026-08-07, all four shapes**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)), and the deciding fact is not the one
  either doc was arguing about. Its own reading reproduced first: the focused node is a `textbox`
  named "New chat name" holding `a brand new name`, with no description, identically before and
  after all four chords, which raise zero live-region mutations and leave the editor open; and the
  instrument was shown able to see a change, the same observer catching a delete's sentence and the
  same window listener recording the press in the two surfaces that pass chords. **What neither doc
  had is that the hold is not four keys but every chord there is**, `fieldKey` asking only whether a
  press is modified so that both sides of the window listener share one definition. Nine measured
  through that branch, all nine stopped, and **seven of them did something anyway**: the cycle keys
  moved the caret 6 to 0 and 6 to 16, `Ctrl+A` selected all sixteen characters, the word keys moved
  it 6 to 2 and 6 to 7, `Ctrl+Backspace` deleted a word, and `Ctrl+Z` undid the whole edit. So a
  sentence raised where the hold is decided would be false at most of its doors, and making it true
  means teaching `fieldKeys.ts` the overlay's key table, which is the coupling the hold rule removed
  by deciding about text rather than about keys. The `role="status"` line adds the
  region-inside-a-section defect the shrink close already measured, the editor leaving in the commit
  after its own sentence; the description is the key table in the markup, or else it misdescribes a
  field where seven of nine chords do not wait. And the silence passes the contract's own test: the
  shrink earned its place by what a gesture DESTROYS, and a held chord destroys nothing, measured to
  the attribute. The repeat policy is left unanswered rather than answered, a rule raising no
  sentence needing no latch, but was measured for whatever speaks per keydown next: thirty
  consecutive keydowns dispatched at the editor, twenty nine of them carrying `repeat: true`, were
  all seen, nothing in the path filtering one. Nothing opened
  behind it.
- **A list that shrinks says nothing, where a chat arriving speaks**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-06 by the caret rule above, which is named
  rather than pointed at now that its chord entry and that entry's own two successors stand between.
  Each landing puts focus on a control whose accessible name says what it is, which is why no live
  region shipped with the rule, but the change to the list is silent: a reader who deletes a chat
  never hears that a row left, that one is left, or that the list is empty, where the swap rule's
  region says which chat arrived. The shapes are a second region, a `role="status"` line inside the
  switcher, or widening `notice`, and the last risks the most, its contract today being
  "the conversation that arrived". Wants a measurement in a real reader before a shape is picked.
  Nothing blocks it.
  **Closed 2026-08-07 on the third shape, the one it ranked riskiest and the measurement ranked
  safest** ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Measured first over the
  devtools accessibility tree plus a `MutationObserver` on every live-region-shaped node: a resting
  overlay has exactly two, the announcer and the connection dot, both computing `live: "polite"`,
  `atomic: true`, `relevant: "additions text"`, and four of the list changes (a chat deleted, the
  list emptied, a reminder acked, the stack emptied) produced zero mutations in any of them. The
  entry was right, and on the reminder stack it did not name as well. It was wrong about two things:
  deleting the OPEN chat already speaks, so the commit that shrinks the list is the commit that
  announces, and the region is outside the panel rather than in it. Both decide the shape. A second
  region would put two announcements in one commit and hand the ordering to the reader's speech
  queue, which no tree can observe; a line inside the switcher is worse, the reminder stack's section
  being unmounted with its last row. One region says both in one sentence
  (`Chat deleted. 1 chat left. Switched to New chat.`), the empty-list words are one string shared
  with the switcher's own line, and every list change now makes exactly one mutation. What a tree
  cannot answer, whether a reader speaks it and what happens when the polite update races the
  composer's focus announcement, went to
  [host/overlay-screen-reader.md](../host/overlay-screen-reader.md).
- **The composer's draft belongs to no chat, and the caret now lands in it**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-06 by the same answer. The field is never
  unmounted, which is what carries a draft to the console and back, and it carries it across a chat
  swap too: measured, a half-typed question is still in the field, caret intact, after a cycle key
  loads another conversation. That cost nothing while focus was landing on the body and costs
  something now that the swap puts the caret there. The two shapes are a draft per chat, kept beside
  `messages` and restored on arrival, or a draft cleared by a swap, which is cheaper and throws work
  away; it wants the user's answer before either, and is the one entry anywhere whose blocker is a
  preference rather than work. **Closed the same day on the user's pick of a draft per chat**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)), which takes the backlog's count of
  entries waiting on a decision to zero. Unsent text is keyed by session id in the reducer and the
  composer is a controlled field over the entry for the chat on screen, so a swap hands the arriving
  conversation its own sentence in the commit that swaps the transcript, with no arm parking anything
  and no frame able to paint the wrong one. Its claim held at all seven doors and not the two it
  named; the correction is inside its own evidence, "caret at 15" being the end of a fifteen
  character draft. It stays in the body's reducer rather than going behind a store port, and the ADR
  argues why rather than assuming it: the hard rule is about model processes and KV caches, a store
  buys only survival of a body restart, and unsent text that no surface promises to keep does not
  earn that, where the delete cascade and a synchronous swap are what keep it out of the component.
  An empty field stores nothing, which is the whole eviction policy. The caret lands at the end of a
  restored draft, which is where the next character goes. And the panel does not jump: at 900x900 a
  swap into a chat holding a draft at the field's ceiling eases 108 to 174 over 12 frames against 108
  to 273.19 over 18 for a chat holding none, zero direction reversals in either, and at 640x720 the
  laden swap moves it not at all.
- **A new chat minted while the console is up leaves the console up**
  ([body-overlay.md](body-overlay.md)), open from 2026-07-20, when verifying the console merge put
  a name to behaviour that predates it, and **closed 2026-08-03** by the user's answer: Ctrl+N
  closes the console. `newChat` cleared the switcher and any pending confirm but not the console
  tab, so Ctrl+N emptied the chat behind the console and left it showing (measured at
  900x900), which is older than the merge, the two sheets the console replaced not having been
  cleared either. The entry was right that the answer belonged to the user and wrong about the cost
  by one arm: `openSession` had the identical hole and its version is reachable by keyboard, since
  Ctrl+Up and Ctrl+Down cycle chats globally while the switcher row that normally loads one sits
  behind the console. So "one line in one reducer arm" was two lines in two, and what shipped is a
  rule rather than a keystroke's special case, that a conversation arriving on the panel brings the
  chat with it ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)).
- **A move retargeted mid-stream restarts from a rounded height** and **a resize that lands inside
  the panel's own move waits for that move** ([body-overlay.md](body-overlay.md)), found 2026-07-20
  and 2026-08-03, **both closed 2026-08-06** as the one piece of work the second of them said they
  were ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Both reproduced at HEAD, which
  is worth saying in a section whose standing warning is that they often do not: 310 of 330 readings
  of the panel's `offsetHeight` over one streamed reply threw a sub-pixel away, all three of its
  moves opened on a whole number, and the painted top edge stepped back 0.281px; the 40px that
  landed inside a 255ms ease was invisible for 188ms and then eased from a standstill. The panel now
  reads its used height off the computed style, which keeps the fraction and still ignores the
  summon's scale (356.266 under `scale(0.92)` where the rect reads 327.764), and its watch asks what
  the panel WOULD be by handing the box back to layout for one read, an important inline declaration
  outranking the animation origin. After: no opening is whole, the worst step is 0.015px on
  Chromium's own 1/64px grid, and the growth is answered one frame after it lands. Two things
  neither entry named came out of it, one fixed and one filed. The bottom edge had the identical
  rounding and a larger one (a whole ease painted 324.5 while the element carried 325), and it is
  fixed here. A section's own roll still measures its target with `offsetHeight` and is filed below.
- **A section's roll ends 0.25px from where it was going** ([body-overlay.md](body-overlay.md)),
  opened 2026-08-06 by the change above and **closed hours later the same day**
  ([ADR-0035 addendum](../adr/ADR-0035-console-and-motion.md)). Both published numbers reproduced
  at HEAD before anything moved: the reminder stack's aside stands at 193.75px with an
  `offsetHeight` of 194, and a section at 57.25 against 57 is there too, though it is a reminder row
  rather than the Thoughts trace the entry named, that trace measuring 76 flat at this viewport. The
  summon's own roll of the aside opened `0px` to `194px` and was handed back to layout at 193.75,
  the closing roll started at 194 with the eye on 193.75 (a 0.25px step in one frame, the panel's
  auto height taking it along, 545.75 to 546), and the ride-along predicted 546 for a roll that left
  the panel at 545.75. The roll now measures with the same used height the panel reads its own box
  with, so both sides of the contract hold one number: the aside rolls to 193.75, the prediction is
  the height the panel lands on, and the step at every roll boundary is 0.000px. The harness cost
  the entry priced was the whole cost, and it landed the way its predecessor's did, as the fakes
  saying the height through the computed style rather than a rewrite per file.
- **The whisper's bubble publishes a rounded roll target while its own height carries a decimal**
  ([body-overlay.md](body-overlay.md)), opened 2026-08-06 in the doing of the entry above and read
  from the code rather than measured. `useWhisperClock` rounds the height it announces and writes
  the box to a tenth of a pixel, so the panel's ride-along adds a whole number to fractional heights
  for the length of every streamed reply. It is listed here rather than fixed on the spot because
  the bubble is never handed back to layout the way a section is, so the visible symptom may not
  exist at all; the first move is a live trace of a reply at 900x1000, not a change. **Landed
  2026-08-07, and the trace came first.** The published target sat exactly half a pixel under the
  height the box stands on at all five wraps of a reply, not the fraction of one the entry allowed
  for, and the step it doubted is genuinely absent: no frame of the reply shows the panel moving
  without the bubble moving it, and the ride-along creates no panel animation at all, so the number
  was computed once per wrap and discarded. What the entry did not know is that on a summon landing
  inside the roll that same number is also the edge the panel pins itself to, which put the panel on
  316.59375px where the height the roll leaves it at centres on 316.34375px and kept it there for
  the session. The roll now publishes the number its own box carries, and the pin is the centre it
  aimed for.

Everything else that remains is gated on a seam or port change, on hardware that fits two model
tiers, on a consumer that does not yet exist, or is a bounded fix-when-it-bites contingency. The
list used to end with "on host-side Windows validation" too; since 2026-07-19 that class lives in
[docs/host/](../host/index.md) and what stays here is the handful of entries whose cost is code
even though only the user can observe the trigger. This section read "None" from 2026-07-16, when
the last item then
listed (`cargo clippy` for the Tauri shell in CI) moved to fix-when-it-bites once reading what the
rust CI job installs (no system library at all) showed it is not a marginal add but a new class of
CI provisioning, until 2026-07-19. What changed is worth stating plainly rather than quietly: it
was not that new work appeared, but that three actionable things had never been written down, and
then that two more turned out to be actionable once the false "the cortex does not fit the dev GPU"
premise was struck across the docs that same day. On **2026-08-06** the section came within one
entry of reading "None" again and did not. Everything above it had closed, and the last item whose
whole remaining cost was a decision was answered and landed the same day (the caret following a
chat swap into the composer), but it opened two entries behind it and they stand in its place, one
of them a decision again. The retarget-and-resize pair that stood beside them, one piece of work
written as two bullets since the second was opened, closed later that same day and opened one entry
behind itself: the reading it moved off `offsetHeight` was the panel's, and a section's own roll
still measures the old way. The shape repeats often enough to be worth naming. An entry that closes
here rarely closes alone, because the thing it fixes is usually one instance of a reading or a rule
that has siblings, and the siblings only become visible once the first one is right.

**That paragraph stopped a few hours short of its own day, corrected 2026-08-06.** Written in the
afternoon, it ends on the composer's draft standing "in its place" as a decision again, and the
draft was answered and landed that same afternoon, taking the count of entries waiting on a
decision to zero for the first time. Then the evening put one back, and it is the **first bullet of
this section**: bounding the recall rank's request removed the only reason `CORTEX_MEMORY_RECALL`
defaults to `raw`, so the judge's default is a choice in front of the user with no work behind it.
The paragraph above therefore reads as though this bucket's decision-only item were behind it while
the item is above it, which the narrative on this page had right all along, recording the fall to
zero and the rise back to one in the same sentence. A closing paragraph that summarizes a day is a
claim about the tree like any other, and this one aged in hours. **And so did this correction**: the
user answered that choice on 2026-08-08, asking for the end-to-end turn cost first and flipping the
default to `judge` on the number that came back, so the count of entries waiting on a decision is
zero again and the item is closed in place at the top of this section rather than pending anywhere.

### Actionable, but a seam or port change comes first

- **Region or window capture** ([vision.md](vision.md)): the fix for the vision slice's headline
  risk, which is that a 4K desktop downscaled to 1600 px may render small text unreadable. The
  **first** mitigation needs no code at all (llama.cpp's `--image-max-tokens` is a deployment
  flag), which is why this sits behind it; the real fix needs the `display_index`/`region` proto
  fields ADR-0029 deliberately refused to add without a consumer, so it is a seam change with a
  design attached rather than an increment. Take the env var first and measure before spending
  the fields.

  **The env var was taken and measured 2026-08-06, and the entry survives it demoted**
  ([ADR-0029 legibility addendum](../adr/ADR-0029-vision-screen-capture.md)). Five 3840x2160
  desktops carrying 47 ground-truth strings from 15 px to 52 px, through a transcription of the
  body's own box filter and the shipped request scaffold: the shipped deployment reads 6 to 8 of
  them, the raised budget alone reads 24 to 26, and the raised budget with
  `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` reads 36 to 38, against a 400 px control at 2. So 13% to 79% for
  about 400 MiB of VRAM and 0.6 s of time to first token, and the risk this entry names was not
  overstated. "Needs no code at all" was the wrong half of the estimate twice over, which is this
  section's standing warning arriving on schedule: the flag was **unreachable** (nothing in
  `ModelHostConfig` passed it to the cortex tier's argv) and it is **unsafe alone** (a budget over
  llama.cpp's 512 micro-batch aborts the server with SIGSEGV on the first oversized picture, met in
  anger). Both are now one knob, `CORTEX_IMAGE_MAX_TOKENS`, emitting the flag and its
  micro-batch together, and **the pair is the default from the same day on**, the maintainer having
  decided the reading is worth the 400 MiB and the 0.6 s. Both halves had to move, since the budget
  alone at the body's 1600 px is the 24 to 26 row. Flipping it cost one number this entry had only
  as a worry: through the body's own downscaler a real 4K screen at 2048 px costs 243 KB of text
  desktop to 4.67 MB of grainy photograph, so the worst realistic one sits at 74% of the 6 MiB
  ceiling and only per-pixel noise crosses it. What keeps the entry open is the residue the knob
  cannot reach: 15 px text on an unscaled monitor stays at 4 of 16 even at 1982 image tokens, a
  2048 px capture pushes a pathological screen to 6.50 MB and into the halving ladder (and a full
  3840 px one takes an ordinary photograph there), and none of this was ever the privacy argument.
  A raised default sharpens the case rather than settling it, since the deployment now spends
  1010 tokens on a whole screen where a region would spend them on the part that was asked about.
  The measurement is the design input the fields were waiting for, since the binding
  quantity turns out to be source pixels per image token: `region` wants physical display
  coordinates rather than normalized ones, `display_index` is required beside it, and a window
  handle would serve the common ask better than either.
- **A cross-language check on the byte ceiling** ([vision.md](vision.md)), open from 2026-07-18
  and **closed 2026-08-03** as `scripts/crosscheck.py`, the third cross-tree scan. Its cost
  estimate held ("one small script" beside `linecap.py` and `dashcheck.py`) and its diagnosis did
  not, in the direction this section's own warning is about. "An edit to one leaves both suites
  green" is not what happens: each side's pin catches an edit to its constant alone, at exit 101,
  and what actually drifts is an edit to the constant **and** its pin, which is the ordinary shape
  of a deliberate change to one side. The scan therefore compares declaration **sites** with each
  other rather than asserting two literals against a number, holds a registry so the next coupling
  costs three lines instead of a rewrite, and fails closed on every way of not finding a value,
  since a scan that cannot find its constants would agree with itself forever. It was also filed
  under this heading and needed no seam change at all, which the entry itself said. The couplings
  the registry deliberately does not hold yet moved to [repo-gates.md](repo-gates.md).
- **An outcome-driven capture indicator** ([vision.md](vision.md)): the overlay's capture dot is
  lit by the `ToolActivity` chip, which the brain emits just *before* the dispatch, so it can
  honestly say the assistant **asked** to look at the screen and no more. A capture the host kill
  switch refused, one whose self-exclusion failed closed, one the body never answered, and a
  gated one the user declined all produce that same event. Making the dot mean "the screen was
  read" needs a post-dispatch signal on the `Converse` stream: a proto field, a tool-loop emission
  point, and a reducer arm, which is why it is a seam change rather than a wording fix. It matters
  because this dot is one of the three consent surfaces that justify shipping capture ungated.

  **Closed 2026-08-06** ([ADR-0029 outcome
  addendum](../adr/ADR-0029-vision-screen-capture.md)). Right about its own premise, which under
  this file's standing warning is not the way to bet: driven through the real loop over the real
  dispatcher and the real `CaptureScreenTool`, all four modes yield exactly
  `ToolStep(tool_name="capture_screen", ...)` and nothing else, identical to a successful capture.
  Two of them are tighter than the entry knew and are **one code path**, since the shell wires
  `DeniedScreenCapture` whether the host switch is off or the self-exclusion failed, so those two
  are indistinguishable in the error text and no design could separate them. What landed is
  `ToolOutcome { tool_name, ok }` as a new `ServerEvent` arm (a field on `ToolActivity` would mean
  a second chip, a `StatusUpdate` would land plumbing in the reasoning channel), carrying a bit
  rather than a taxonomy: the indicator has two honest rungs, and "the user declined" cannot be
  told from "no confirmer was configured" without lying. **The direction of the risk is the
  design.** The brain cannot tell a capture that failed after the shutter fired from one that
  never happened, so `ok=false` changes nothing on screen; the ladder
  (`state.capture: "asked" | "read" | null`) only ever climbs, and the ring only ever gains ink.
  It opened one entry under [subagents.md](subagents.md) and fixed one defect found while proving
  the motion: the reduced-motion block clamped `*`, which does not match pseudo-elements, so five
  motions including two infinite ones ran at full speed for a user who asked for none.
- **Carrying the `opaque` bit across a model swap** ([vision.md](vision.md)), the cheap half of
  the pixels-across-a-swap entry and the one with a real fail-open behind it, open from 2026-07-19
  and **closed 2026-08-03**. It was right about itself throughout, which is worth saying under a
  heading whose standing warning is the opposite: `HandoffRecord` did carry the ledger minus
  `opaque`, both consumers (strict URL redaction, the durable-memory block) are real and are
  reached by the deep phase, and "a record field, a codec line, and the store contract's round
  trip" was the whole cost. It was right that this is defence in depth, so the landing claims no
  more than that: `SwapConductor._prepare` still refuses an opaque turn before any record exists,
  and the conductor test that drives the reachable ordering end to end now also asserts the store
  saw no write at all. What the carried bit buys is that neither consumer can be handed a
  manufactured `False` the day the picture half relaxes that refusal. It also needed no seam or
  port change and was filed under this heading anyway, the second entry today to sit here without
  belonging to it. The pixels half stays open, so vision's count holds.
- **A live-probe refresh** ([vision.md](vision.md)): the `/props` vision probe ran **once at
  startup**, so a `llama-server` restarted without `--mmproj` mid-session left `capture_screen`
  advertised, and the next capture paid the full privacy cost (a screen read, a notified user, a
  tainted turn) for an image the model cannot read. Re-probing per turn was refused because it
  makes the inference adapter stateful; the cheap version re-probes when a swap changes residency,
  since that is the only thing in the system that restarts a model server, and it needs the
  conductor's residency change to reach the adapter, which is a wire that does not exist. Placed
  here for the first time on 2026-07-19, and it is no longer hypothetical: the real swap restarts
  model servers, so the staleness this describes is reachable.
  **Closed 2026-08-06** ([ADR-0029 live-probe addendum](../adr/ADR-0029-vision-screen-capture.md)):
  the cost was reproduced end to end and was exactly as described, the proposed wire was
  falsified, and what shipped is a `VisionProbe` port asked per advertisement and per call with
  nothing cached anywhere.
- **Streamed brain status** ([body-overlay.md](body-overlay.md)): the push half of the landed
  connection indicator, unblocked on 2026-07-18 and now waiting on a seam change plus a consumer
  rather than on a producer. Both halves of the producer exist: the escalating turn streams
  `StatusUpdate(state="swapping")` through drain, load, work and restore (2026-07-17), and
  `Health` now answers `ready=false` with a truthful residency detail **between** turns
  (2026-07-18, ADR-0030 decision 6), which lit the landed indicator amber with zero overlay
  change. So the rule that any successful call means the brain is ready has expired, as this
  entry predicted, and what is left is the push itself: a server-streamed status RPC is
  proto + both stubs + a consumer, and probe-on-summon plus the stream's own chips cover personal
  scale. Pick it up when something needs the brain to speak first (a status the overlay cannot
  ask for at the moment it changes, rather than on its next 5 s recheck).
- **Session-history summarization + the model-based reranker**
  ([session-history.md](session-history.md), [memory.md](memory.md)): both blocked on a sync
  port going async (`HistoryWindow.select`, `RecallPolicy.select`) and both inherit the same
  non-reentrant GPU-lease hazard, so they are one design problem. The declined blended-relevance
  field widens the same `select` return, so a consumer for it reopens the work here rather than
  on its own. **Audited 2026-07-16:** the async widening is mechanically clean and contained (one
  already-async caller each, no colour cascade, gate-clean under this repo's non-preview ruff) and
  the lease hazard is navigable by the title generator's sequential-drain discipline (the reply's
  lock is not yet held at selection time), so neither is the binding blocker. That audit then gave a
  hardware blocker, "a model pass cannot be validated on the 8 GB dev GPU (the cortex tier does not
  fit)", **struck 2026-07-19**: the card holds the cortex and a model pass is judgeable here at 4K.
  What binds is that `select`'s widening should serve its three deferred consumers in one change,
  plus summarization's undecided cache-versus-recompute question, so this reopens on that design
  work and not on a card.
  **The design work was done and the reranking half landed 2026-08-06
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md)).** `RecallPolicy.select` was widened once, to
  `async def select(hits, *, query, now, k) -> Ranking`, and all three of its waiting consumers
  arrived on it: the model rank (`JudgeRecallPolicy`, measured against the shipping cosine at 0.917
  to 1.000 mean reciprocal rank on a small built-for-disagreement corpus), the blended-relevance
  field (**the decline is reversed**, as a key on the policy's own return rather than a field on the
  store's output type), and the recall trail (`RecallAuditSink` plus a logging sink that carries the
  rank key and no text). Summarization's own question is **settled as cache rather than recompute**,
  in Redis behind `SessionStore`, safe because that port has no verb that edits a message so a
  prefix summary can only go incomplete and never wrong; and the lease sequencing is settled as a
  `drain_text` helper that leaves the adapter's acquire block in a `finally`, which the title
  generator now also uses. What is left is the summarizer's implementation, with the `async`
  widening of `HistoryWindow.select` beside it rather than as an empty async layer, since that port
  has one waiting consumer where the other had three. Three of this entry's own claims did not
  survive re-derivation: both halves name a caller (`_inference_messages` in `engine.py`) that no
  longer exists, and neither noticed that `select` did not carry the query a model rank has to rank
  against. **The summarizing half landed the same day and shipped on by default 2026-08-06**
  (ADR-0038 summarizing, untrusted-recap, re-measured-behind-the-fence and cheap-fold addenda),
  after two passes that measured it and held the default off. `HistoryWindow.select` widened twice
  in the end, once for the `async` and the session id and once for a progress sink, which is the
  outcome this entry's guidance existed to avoid; the reason it was still right to split them is
  that the sink had no consumer until a fold was slow enough to need narrating and cheap enough to
  ship. **This entry is closed.**

### Blocked on hardware that fits two model tiers

**Renamed 2026-07-19, emptied 2026-08-07.** This bucket read "Blocked on Slice 11 (real model
swap / GPU lifecycle)" after that slice was marked done on 2026-07-18, which named a blocker that
had stopped existing. Its one remaining entry, co-residency, was blocked on a card that fits the
tiers it would keep alive; that card arrived, the measurement was taken, and the entry closed, so
**nothing is open here**. The bucket is kept as the record of what an area's deferrals became, and
the heading stays because the next entry blocked on hardware belongs in it rather than in a new
one.

- Co-residency, the open half of the model-manager process-lifecycle entry
  ([inference-model-manager.md](inference-model-manager.md)). The **pure half landed 2026-07-17**
  with the brain-handoff conductor sub-slice (the `ModelHost` port and its scriptable twin, the
  `SwappingModelManager` with its segregated residency scope, the `SwapConductor`, the deep
  model's phase, boot recovery, and the escalating turn wrapper, all proven over fakes by a
  chaos suite that kills a handoff at every step boundary) and the **real process lifecycle landed
  2026-07-18** with the model-host sub-slice: the supervisor sidecar behind that same port, one
  `llama-server` child per tier, mechanism-validated in Docker on the dev GPU with two small
  artifacts (tier scale stays host-side). **Co-residency closed 2026-08-07** on the 24 GB card
  this bucket was waiting for, measured before it was designed. The shipped pair does not co-fit
  and misses by 4676 MiB, but it does not miss loudly: WSL2 pages the overcommit and serves the deep
  model at half its decode rate while `nvidia-smi` reads the same ~23.6 GB used as a genuine fit.
  What does fit is the deep model beside the shipped subagent tier, at 23555 to 23642 MiB with the
  deep model's decode unchanged, so `CORTEX_SWAP_CORESIDENT` landed **off by default**: a handoff
  that stops the cortex and nothing else, and no drain window, which is safe because it stops no
  tier delegated work can reach. Two refinements opened in its place, both in that area doc.
- Nothing of this area's trio remains here as an **entry**, though two pieces of the third are
  still owed and are host-side ([resource-governance.md](resource-governance.md)):
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
  now the one ADR-0030 decision 8 gives it, a **second** GPU-capable executor. **Corrected
  2026-07-19:** this line used to stop at "nothing remains", which the area doc contradicts. What
  was validated is the runtime's **mechanism**, in Docker on the dev GPU with two small artifacts;
  real GPU-placed **subagent** validation and the placeholder cgroup numbers were not, and both
  **moved to [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md) the same day** as items 6
  and 7 there. **Split again the same day:** the subagent validation's own reason ("needs a card
  that holds the cortex first") assumed the dev GPU cannot hold the cortex, and it can, so what
  needs the 24 GB card is a placement **beside** a resident cortex while the placer's GPU arm
  firing against a real placement is agent-side and sits under actionable now. The cap numbers are
  host work unchanged. None of this ever carried a count here. **The agent-side half ran on
  2026-08-04** and the arm fired, both verdicts witnessed against live tiers by
  `test_subagent_gpu_live.py`; the cap numbers are the only piece of this entry still owed.
- The ~31B brain-tier injection-harness run **moved to
  [docs/host/gpu-tier-scale.md](../host/gpu-tier-scale.md) on 2026-07-19**, where it sat behind
  the deep-model pick with the other four capstone items
  ([untrusted-content.md](untrusted-content.md) keeps its pointer stub).
  Its taint/provenance-persistence sibling **landed 2026-07-17** as the brain-handoff record's
  schema and pinned tainted-ledger round trip (ADR-0030), and the conductor sub-slice then
  exercised that schema across a swap the same day: the deep model's phase rebuilds the ledger
  from the record, so a tainted turn stays tainted and the output guardrail opens over the URL
  evidence the cortex collected (mutation-proven). The harness run itself, which needs the
  real ~31B tier, is the only part that outlived this bucket, and it left it for the user
  directory rather than staying. **It ran there on 2026-08-04**, by the agent once the hardware
  premise that filed it was found false: 0 of 10 framed injections obeyed, the escalation stance
  unchanged, and the procedure it owed written into
  [runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md). The stub carries the detail.
- Nothing of the overlay's streamed-brain-status entry remains here: its producer became whole on
  2026-07-18 and the entry moved up to "actionable, but a seam or port change comes first"
  ([body-overlay.md](body-overlay.md)).

### Host-side work: moved out on 2026-07-19

This bucket is now a pointer, not a list. Everything that needs the host's hardware left for
**[docs/host/](../host/index.md)** on 2026-07-19, extracted the way this whole backlog was
extracted from the ROADMAP: one self-contained doc per **sitting**, wording kept verbatim, plus an
index with prerequisites, a recommended order, and a status line per item. Five entries and two
uncounted residuals went, listed here so nothing has to be re-derived:

- The real Core Audio "set volume to 30%" check (was [body-gateway.md](body-gateway.md), counted)
- Windows-native validation of the confirm card (was
  [untrusted-content.md](untrusted-content.md), counted)
- The OS-window half of the overlay polish (was [body-overlay.md](body-overlay.md), counted, and
  the only **authoring** entry this backlog held)
- The whole screen-capture path on a real desktop (was [vision.md](vision.md), counted)
- The ~31B injection-harness run (was [untrusted-content.md](untrusted-content.md), counted)
- Whether a real reminder toast appears and reads well (was inside a landed entry in
  [scheduling.md](scheduling.md), never counted), joined there by the pull surface's own check,
  which had no backlog line although ADR-0025's host line and the runbook both named it
- Real GPU-placed subagent validation and the placeholder cgroup numbers (were inside a landed
  entry in [resource-governance.md](resource-governance.md), never counted). The first of those came
  back the same day, split: only a placement beside a resident cortex needs the 24 GB card. **Both
  halves of that one closed on 2026-08-04**, together, because firing the arm with the cortex up is
  the placement beside it; the cgroup numbers are the only piece of the pair still owed

Each origin doc keeps a dated pointer stub in place of the entry, so the trail from an ADR through
this backlog still resolves. **Why they moved rather than staying with a tag:** the two backlogs
now hold different kinds of not-done. This one holds deferred *design*, work anyone can pick up
once a seam or a consumer unblocks it, and its emptiness gates the README. That gate is dishonest
if it also waits on the user pressing a hotkey, and it is worse than dishonest for the overlay
polish, which would have meant this backlog could not empty until the maintainer wrote Rust. The
inconsistency the 2026-07-19 pass recorded rather than resolved (four areas counting their
host item, two not) is resolved by the move: none of them counts here now.

What stays here despite needing the host's hardware to *observe* or *judge*, because the work
itself is code and belongs with its area: unbalanced COM initialization on the blocking pool
([body-gateway.md](body-gateway.md)), the spontaneous-pick nudge's live uptake
([subagents.md](subagents.md)),
and the NPU as a third placement target
([resource-governance.md](resource-governance.md)); the model passes behind history
summarization left this list on 2026-08-06 by being built, and reranking's own left it the same
day, having been run and measured against the real cortex in Docker
([memory.md](memory.md)). The user index lists them under a heading that says exactly that.

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
- Measuring the scrollbar rail instead of assuming it: no non-Chromium engine runs the overlay.
  Every scroll container reserves `--rail` (6px) and pays for it out of its own inline-end padding,
  which is exact wherever `::-webkit-scrollbar` sets the width. Chromium prefers the standards
  properties over the pseudo-elements when both are set (measured 2026-07-20: `scrollbar-width:
  thin` beside the 6px webkit rail reserves 10px, not 6), so the standards path is fenced to
  engines that have no pseudo-elements, and there the UA picks `thin`'s width and the subtraction
  leaves the inline-end margin a few px wider than the other side. Nothing shifts when the bar
  appears on either engine, so what is deferred is symmetry on an engine the body does not ship on.
  Reopens if the body ever runs on one, and the fix is then to read a probe's
  `offsetWidth - clientWidth` once at startup and publish it as `--rail`, which is a module and its
  tests rather than a CSS line. **Re-read 2026-08-03 when that module was built for the chat floor
  (`overlay/measured.ts`), and it stays here rather than riding it**: on the engine that ships the
  reading is circular, `::-webkit-scrollbar { width: var(--rail) }` setting the width the probe
  would read back, so the fenced version needs a SECOND property and therefore a change to every
  subtraction in the stylesheet, not a line of wiring. Measured while auditing it, `.history` and
  `.field` reserve exactly 6px, and the recipe above holds only on a box with no border, `.reminders`
  answering 8px for a 6px rail inside two 1px edges ([body-overlay.md](body-overlay.md))
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
- **`InjectInput`, the last unbuilt `BodyService` RPC** ([body-gateway.md](body-gateway.md)):
  counted in that area since the extraction and never given a line of its own here until
  2026-07-19, surfacing only inside the pointer-input decline above. Same blocker and same shape:
  input injection is unbuilt at every tier, so the RPC reopens with its consumer as one slice
  rather than as a wired handler waiting for the gated tool that would make it safe. Its sibling
  `CaptureScreen` closed with the vision slice on 2026-07-18, which is what leaves this one alone
  in the entry and why the area holds at 6 rather than decrementing
- **Three vision surfaces nothing reads** ([vision.md](vision.md)), placed here 2026-07-19: a
  content-addressed **`AttachmentStore`**, since a reopened chat shows no evidence of what the
  assistant saw and the audit line keeps dimensions, a byte count and a timestamp only, which is a
  deliberate cost and reopens only if accountability outweighs zero retention (it is also the
  expensive half of carrying a picture across a swap, and the capability argument still says no,
  because no brain-tier candidate on the mount has a projector); **multi-monitor and DPI
  reporting**, where nothing enumerates monitors, which is exactly why `CaptureScreenRequest` left
  field 2 unassigned, so its consumer is the one region capture is already waiting for; and
  **pixel-level screening in the body**, the only side that knows what is on the screen before it
  crosses the seam and so the only side that could redact a region rather than refuse a whole
  capture, with nothing yet asking it to
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
  search / deep-link by id). Narrowed 2026-08-03 without closing: with the two `TITLE_MAX`
  declarations now equal, the local fallback renders exactly what the brain would have listed for
  the same first message, so what remains open is only what the fallback cannot know, a stored
  rename or generated title ([session-read-seam.md](session-read-seam.md))
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
- **A delegated tool step announced and never settled**: declined 2026-08-07 on three findings, the
  sibling of the `ToolActivity` `phase` field two lines below and the same design space. The gap is
  real and was reproduced before anything was decided (a real delegating `converse` stream carried
  three `tool_activity` events and one `tool_outcome`, the delegate's failing step announced exactly
  like its succeeding one). **Nothing could read a delegated outcome**, which is the `GetVolume`
  decline's sharper test rather than the usual want of a reader: the only consumer anywhere is the
  overlay reducer's `toolOutcome` arm, which returns the state untouched unless the name is
  `capture_screen` and `ok` is true, and that tool is a built-in `build_builtin_tools` feeds to
  `build_cortex_tools` alone while a subagent's dispatcher comes from `build_subagent_tools` over
  the MCP registry. **There is no consent to surface**, since a subagent is handed the
  gated-stripped subset and nothing it can call is outbound or irreversible, while its failures
  already reach the cortex as an `ok=False` result fed back as `[subagent i] FAILED: ...`. **And
  the fix could not deliver the pairing**: `SeamProgressSink.emit` drops on a saturated buffer where
  the turn's own events block for a credit, so an outcome could be lost while its activity got
  through. The entry's cost was wrong too, two lines rather than three (the sink's
  `to_wire=to_server_event` already maps a `ToolOutcome`). What the pass repaired instead is the
  contract, on the body's side, where a delegated activity is byte-identical to the turn's own:
  the proto, `body/crates/core/src/transport/turn.rs` and `docs/modules/body-core.md` all stated
  the pairing as a property of the stream and now state it of the turn's own dispatches, with
  `test_a_delegated_step_reaches_the_wire_announced_and_unsettled` pinning the asymmetry. Reopens
  on a surface that renders how a step ended for its own sake (a settled or failed state on the
  activity chip, a delegated-work panel listing a batch's steps), which reopens the lossy channel
  with it ([subagents.md](subagents.md), [ADR-0029](../adr/ADR-0029-vision-screen-capture.md))
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
advertisement landed and **observed live on 2026-08-04** (a prose-only ask never delegates at all,
an invited one piles the whole batch on one entry every time, and the knob is not advertised at all
once subagents hold tools), whose trigger is now a deployment that delegates unprompted and pays
for the pile rather than a cortex merely under-reaching, and whose fix is stronger nudging behind
the same spec seam ([subagents.md](subagents.md)); checking the sidecar's stop bounds against the brain's control
deadline instead of only documenting the pairing, joined on 2026-07-18 with the audit round that
found the pairing had a third term and added the `GET /health` reporting that would make the check
possible, whose trigger is either side's timing being tuned or a handoff aborting on an eviction
that in fact completed, and whose stated price (that the brain would then have to depend on the
sidecar answering at wiring time) was quoted by the co-residency fit entry on 2026-08-07 and turned
out not to transfer, that check having landed at the swap instead
([inference-model-manager.md](inference-model-manager.md)); noticing a handoff that spilled
anyway, joined on 2026-08-07 the moment the fit check landed, because a check taken before the
load cannot see a figure the deployment under-declared nor a gigabyte the desktop takes during it,
and the spill it leaves reports `ready` on both tiers and reads like a fit on `nvidia-smi`, so the
trigger is a deep phase that is slow rather than absent and the fix is the deep phase watching
llama.cpp's own `timings.predicted_per_second`, which the backend currently discards
([inference-model-manager.md](inference-model-manager.md)); the shipped subagent VRAM ask, joined on
2026-08-07 when the cortex reservation was re-measured and stopped being the term that refused every
GPU placement, leaving `CORTEX_SUBAGENTS_VRAM_GB=5.5` about 2.3 GiB above the 3319 MiB the GPU tier
measures and the only reason nothing is placed, whose trigger was a deployment that actually wants
GPU subagents and whose fix was measuring one spawn of the roster's default entry rather than
arithmetic, **struck 2026-08-08** when that measurement was taken and the ask landed at 3.5 GiB in
both declarations, so the shipped stack GPU-places a spawn and the code default of 2.0 this entry
mentioned in passing turned out to be the unsafe one, about 1.3 GiB under the tier's peak
([resource-governance.md](resource-governance.md)); the three exceptions the commit-body
wrap gate did not ship, which replaced their own parent here on 2026-07-19 when the wrap check
itself landed, because the exemption that shipped is a property of the longest **word** rather
than of the line's **kind**, so a pasted command, a fenced code block, and a `BREAKING CHANGE:`
footer of short words are all rejected (measured against the shipped gate: three complaints and
exit 1), and closing it wants a line-kind exemption, whose trigger is the first commit that
genuinely needs a command or a block in its body ([repo-gates.md](repo-gates.md)); the retry
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
([body-overlay.md](body-overlay.md)); the switcher's and the reminder stack's whole 6px inset being
spent on the reserved scrollbar rail, joined on 2026-07-20 when scrollbars became reserved chrome,
which keeps both cards' resting geometry exactly as it was and costs a row's box reaching the
reserved band (the painted thumb clears the right-most child box by 1px, though only the box gets
that close: the hairline between two reminders curves away on the row's own 12px radius and fades
out nine columns clear of the thumb, and text stays 9px to 11px clear on the rows' own padding),
whose
trigger is either a row dropping its horizontal padding or the maintainer reading the rail as touching
the chrome, and whose fix is the 6px going back on the card at the cost of a 12px inline-end inset
against a 6px left, or a narrower rail for those two cards
([body-overlay.md](body-overlay.md)); the two bounds the panel's section budget leaves behind it,
joined on 2026-08-03 when the budget landed, both measured rather than assumed: a section's own
border, padding and air (14px plus 6px) sit under no cap at all, so two open sections cost 40px the
budget cannot reach and the hint strip is 34px outside at a 640x240 viewport, everything being
inside again by 640x300 against a body window of 720 (trigger: a screen the overlay is never opened
on today, and the fix is a section whose share cannot hold one row leaving rather than standing
there as a frame); and the room a closing section hands back arrives in a single frame, because the
share reads the tree and a section rolling shut is in the tree until React removes it, traced at
640x720 as the switcher stepping 127.14 to 227 in one frame with the panel's own box never moving at
all (trigger: the maintainer reading that reveal as a jump, and the fix is the share following the
roll's published target rather than the tree)
([body-overlay.md](body-overlay.md)); the whisper's two bounded follow-ups, joined on
2026-07-21 when the streaming redesign landed (ADR-0037): a streamed bubble's wrap width
measured once (trigger: a resizable overlay window), and kerning pairs lost across the letter
spans (trigger: adopting a licensed face); a third, drain growth the panel's measured moves
never see, landed the day it was filed when the first live look surfaced the same
stale-measurement root as per-token jitter, fixed by the bubble joining the roll contract
(ADR-0037 addendum) ([body-overlay.md](body-overlay.md)); the tunnel
fallback, the
hardened non-loopback posture, a safe Core Audio wrapper, and the unbalanced COM
initialization the blocking-pool hop made visible, whose trigger is a COM failure or thread
growth on Windows after a long session
([body-gateway.md](body-gateway.md)); paging/cursor, the live-suite fixed-window residual having
closed 2026-08-03 when the live Redis runs took a logical database of their own
([session-read-seam.md](session-read-seam.md), [repo-gates.md](repo-gates.md)); the Postgres
durable twin, cron expressions,
and automated dead-letter retention, joined on 2026-07-16 by the push retry policy beyond
next-poll-pull (sharpened when task-outcome delivery landed: the safe retry is the
deliverable-until-acked pull, and a proactive re-push double-delivers because a stable
`reminder_id` cannot tell a retry from a legitimate re-fire, so it wants the per-fire delivery id
the declined occurrence-history record would carry; its trigger is a body reconnecting between a
failed push and the next overlay open often enough that a stuck-until-open outcome is a real gap)
([scheduling.md](scheduling.md)); MTP variants, and the
disable-thinking / token-budget caps, **narrowed on 2026-08-06 rather than closed**, because the
lever shipped that day as `GenerationBounds` on `InferenceBackend.stream` and all three passes that
throw their own deliberation away took it (the history recap's fold, the session title, the
model-based recall rank), leaving the user-facing reply as the whole of what stays deferred, since
it sends no bounds by design; the trigger is unchanged and now applies to that case alone, a
runaway trace on a real answer or a user who minds the wait, and the area's count deliberately did
not move for a narrowing ([inference-model-manager.md](inference-model-manager.md));
the ANN index; **recall observability, which this bucket claimed until 2026-08-06 and which is
false about the tree**, its trigger having read "a visibly wrong recall no one can inspect after the
fact" while the inspection had shipped that same day as the `RecallAuditSink` port and
`LoggingRecallSink` (`cortex_memory/audit.py`, one structured line per recall behind
`CORTEX_MEMORY_RECALL_AUDIT=1`), so the line is struck rather than retriggered; and, in its place,
the two that the same close opened, joined here 2026-08-06: a **cross-encoder rank**, the
other form of a model reranker, wanting a scoring-model port rather than a chat completion and so a
new adapter rather than a policy, whose trigger is a measured shortfall of the judge on a real
corpus or a latency budget it cannot meet; and **auditing the candidates a rank dropped**, which
`RecallAudit` does not carry because a non-picked candidate's `SPREAD`/`SWEEP` key is not well
defined, whose trigger is the first investigation that needs to know why a specific memory was not
returned; joined on 2026-08-07 by **a geometric policy that still cannot decline**, opened by the
close that taught the judge to, since `RawRecallPolicy` and the three heuristic policies always
return their nearest `k` and a deployment that has opted **out** of the judge therefore still
receives three nearest misses on a question memory cannot answer (that clause read "has not opted
in" until 2026-08-08, when the default moved to `judge` and inverted which way the opt runs, which
makes the entry smaller and not moot), whose fix is a relevance floor on
a fifth policy (not on `RawRecallPolicy`, whose promise is byte-for-byte v1 recall) and whose trigger is a
deployment wanting recall to stay geometric and still say nothing, or a calibration giving the floor
a number that means something behind more than one `Embedder` ([memory.md](memory.md)); the four guardrail tails (whitespace-split hosts, full
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
([repo-gates.md](repo-gates.md)); and the overlay stylesheet outside the line cap, opened here on
2026-08-03 behind the cap reaching the overlay's TypeScript, which turned an oversight into a
decision: `body/app/src/overlay.css` is 2420 lines and uncapped on the argument that the cap's
"split by responsibility" remedy presumes a module with a public contract while a stylesheet is one
cascade whose ordering is load-bearing, whose fix is a split by layer imported in a fixed order from
one entry sheet (one suffix in the scanner, everything else in the CSS), and whose trigger is an
edit landing in the wrong cascade position because the file is too long to hold in view, or a second
stylesheet appearing and forcing the ordering question anyway ([repo-gates.md](repo-gates.md)); and
the couplings the cross-language constant scan does not hold yet, opened here on 2026-08-03 behind
that scan landing, which turned every unregistered coupling into a decision rather than an absence,
in three kinds needing three answers (ordered relations the equality comparator cannot express, such
as `MAX_EDGE_CEILING` at or below `MAX_IMAGE_EDGE`; values spelled inside strings rather than
declared, such as the compose healthcheck's fourth copy of the seam-token key and the two ports; and
TypeScript, where the overlay matched `capture_screen` and `thinking` against the brain by hand and
the scan had no declaration syntax at all), whose fix is a comparator field, a `.ts` syntax, and a
resolution for the one pair that was **already divergent** (`TITLE_MAX`, 48 in the brain against 32
in the overlay, which is why registering it that morning would have turned a gate on over a shipped
disagreement). **Two of those three landed later the same day** with the truncation bound settled
below: the scan reads TypeScript, and `TITLE_MAX` is its third registered constant. What is left is
the comparator field, the copies that are not declarations, the TypeScript names whose far side is a
CSS use, and `thinking` still being a bare literal rather than a named constant; the trigger is now
just the first coupling that actually drifts ([repo-gates.md](repo-gates.md)); and a compose bind
default that lands in the repo tree being stageable, opened here on 2026-08-06 when the two live
cases were ignored and the class was not, since `models/` and `pgdata/` are now matched at any
depth and `./sandbox` always was, leaving the tree clean by three separate acts of remembering
rather than by anything that checks, whose fix is a scan comparing the `${VAR:-./path}` bind
defaults in `docker/*.yml` against `.gitignore` and whose trigger is the next override that adds
one, a scan written today having nothing to catch ([repo-gates.md](repo-gates.md)).

Four entries opened by the brain-handoff sub-slices were written up in their area docs and in the
narrative above but had no line here until 2026-07-19, so nothing said when to pick them up.
**Resuming a crashed handoff from its record** instead of failing it, which waits on the same
request-identity and dedup design the `converse` reconnect entry needs, since replaying a deep
phase without one risks double-running side-effectful tool work, and after which resuming is a
small addition to `recover_handoffs` ([inference-model-manager.md](inference-model-manager.md)).
**Reconverging the brain's residency when the model-host sidecar restarts under it**, which labels
itself fix-when-it-bites and whose fix is a boot id on `GET /health` plus a caller for the
already-written `converge_residency`: invisible with escalation off (the default manager holds no
residency state) and self-limiting with it on (the handoff fails honestly and releases its claim),
its trigger being a sidecar that restarts under a running brain
([inference-model-manager.md](inference-model-manager.md)). **A disconnect mid handoff blocking
the stream's teardown** until the cortex is back, the deliberate other side of making the restore
uninterruptible after the chaos suite found an abandoned restore left the process with no resident
model at all, its trigger being a deployment where that wait holds a teardown long enough to
matter ([seam-transport.md](seam-transport.md)). And **the drain bound sitting below a fired
task's lease**, so with the shipped defaults an escalation during a scheduled task aborts every
time, correctly and before anything is evicted, which makes it a defaults decision against real
usage rather than a design change ([resource-governance.md](resource-governance.md)).

Four vision entries joined on the same day, each with the trigger its own entry implies
([vision.md](vision.md)). **JPEG or WebP for a photographic screen**, a body-side swap behind an
unchanged seam (measured at roughly a quarter of PNG's bytes on incompressible content), whose
trigger is bytes on the wire starting to matter, which they do not while PNG's losslessness is
worth more than the open legibility risk. **Per-source memory rules**, so a vision turn can be
remembered deliberately rather than dropped from durable memory outright, which rides the
per-provenance eviction entry above rather than standing alone. **A uniform per-call deadline on
`BodyService`**, where capture is the first call to carry one because a blit plus an encode is the
first that can park a host thread, and changing the three live-validated no-deadline calls is not
a change that slice earned, so the trigger is a second call that can park a thread. And
**`RESOURCE_EXHAUSTED` classification**, a small mapping change on both sides whose absence leaves
a capture the ladder refuses indistinguishable from a broken backend. Its trigger was "the first
time that coarseness sends a reader to the wrong place" and is now a check instead, **re-read
2026-08-06 against the raised capture edge and ruled not fired**: the refused arm cannot be reached
at the shipped byte ceiling at any edge the seam permits, since the ladder's last rung is a quarter
of the requested edge and always fits, so the entry fires when a deployment sets
`CORTEX_BODY_MAX_IMAGE_BYTES` under roughly 450 KB and not before. It also now carries the one
live thing that pass found, which is that every capture failure reaches the model behind a
"could not reach the body" prefix that is false for all but one of them.

### Feature breadth, on request

- macOS/Linux OS backends behind the existing traits ([cross-cutting.md](cross-cutting.md))
- More subagent roles ([cross-cutting.md](cross-cutting.md))
- **The user-attached image path** (`UserTurn.images`, [vision.md](vision.md)): the proto field has
  existed since Slice 2 and is still ignored, and it is a genuinely different design rather than a
  smaller version of capture. A different seam direction, a different transport limit in a
  different package, the first path where Cortex would **decode a foreign image**, a four-layer
  TypeScript bridge change, and a persistence answer the capture path deliberately refused to give
  (pixels there are turn-local). Nothing blocks it but scope: it lands with its own design. Placed
  here 2026-07-19
- **The remaining `ScreenCapture` backends** ([vision.md](vision.md)), placed here 2026-07-19:
  Linux and macOS carry `unimplemented!()` stubs that satisfy the trait like every other OS port,
  and are the same ask as the line above them. `Windows.Graphics.Capture` is the one that buys
  something GDI cannot, since GDI renders hardware-overlay and DRM-protected surfaces **black,
  silently**, with no `CaptureError` to tell that from a genuinely dark screen, and WGC brings a
  free yellow OS capture border, the best privacy affordance on offer and the one thing
  consciously given up. It costs async frame arrival against a deliberately synchronous port,
  WinRT interop, a D3D11 staging copy, and a Windows 11 22H2 floor to control the border, behind
  the unchanged trait either way
- **The liquid edge's backdrop blur** ([body-overlay.md](body-overlay.md)), placed here
  2026-07-21: a path-clipped panel cannot keep `backdrop-filter` (Chromium composites the blur
  un-clipped, measured), so liquid window styles paint the near-opaque `--panel-solid` token
  instead, at zero visible cost while the v1 window's ground is opaque. Picks itself up with the
  transparent-window pass; the candidate fix is the same outline as a `mask-image`, which the
  pitch measured clipping the blur correctly
- **The voice as a fourth picked row** ([body-overlay.md](body-overlay.md)), placed here
  2026-07-21: the whisper landed as the one streaming effect (ADR-0037), but it was chosen from
  a pitched family and sits behind one component seam, so a registry beside the theme, the iris
  and the dream (the Face's anatomy extending to a voice) is data plus a swatch row. Trigger:
  the user wanting a second voice back
