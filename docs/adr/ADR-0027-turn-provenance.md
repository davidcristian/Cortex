# ADR-0027: Structured turn provenance (the `TurnStamp` seam)

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

Four recorded deferrals converge on the same missing seam, each wanting "where did this
work come from" to travel with what a turn spawns:

1. **ADR-0013** defers structured provenance beyond the binary taint bit (source URI,
   sender) at the untrusted-content boundary.
2. **ADR-0019** defers the same fields on `MemoryRecord`, beyond its `tainted` column.
3. **ADR-0022** defers confirm-with-provenance: the tainted gated branch blocks outright
   partly because the confirmation card has no source to show.
4. **ADR-0025** defers session attribution: `ScheduledItem.session_id` is stored, coded,
   and rides the wire, but is `""` at creation because the creating tool has no channel
   to learn the turn's session.

Today the only turn context a dispatched call carries is the lone `tainted` bool: passed
to `ToolDispatcher.dispatch` as a keyword and overwritten onto `ToolCall.tainted` at
dispatch time (the ADR-0018 stamp), where `spawn_subagents` and the schedule built-ins
read it. Landing each deferral the same way would add a parallel keyword and a second
overwritten field per fact, recreating the divergence one at a time. The channel wants
to be designed once.

## Decision

1. **One frozen value, `TurnStamp`, owned by the tool domain (`tools.py`).** Fields
   today: `session_id` (the originating chat, `""` when the dispatch has none) and
   `tainted` (whether the dispatching turn had read untrusted content at dispatch time).
   Every future provenance fact (source URI, sender, per ADR-0013/0019) joins this
   object. A new parallel keyword or a second stamped field on `ToolCall` is the
   anti-pattern this ADR exists to prevent.

2. **The dispatcher is the one stamping point.** `dispatch(call, *, stamp, gated)`
   replaces the `tainted` keyword, and `ToolCall.tainted` becomes `ToolCall.stamp`. The
   dispatcher overwrites the call's stamp with its own argument, so a model-forged stamp
   is discarded exactly as the forged taint bit was (ADR-0018), and the capability gate
   keeps deciding on the dispatcher's argument (`stamp.tainted`), never on anything the
   model authored. `UNSTAMPED` (a module constant, since the default must not be a call)
   is the unattributed default: no session, no taint, the same fail-open-on-attribution
   and fail-safe-on-gating posture as today's `tainted=False`.

3. **Three stamp sources, one rule: the caller states what it knows.**
   - The **cortex turn**: `ToolLoopContext` grows a required `session_id`, filled by the
     engine from `handle_turn`; the loop builds a fresh stamp per dispatch (the taint
     bit is live and can flip mid-loop as results arrive).
   - The **ticker**: a fired task's synthetic `spawn_subagents` dispatch carries the
     item's stored `session_id` and taint, so autonomous work attributes to the chat
     that scheduled it.
   - A **subagent**: an empty session. `SubagentTask` carries none, and the only
     `session_id` consumer today (`schedule_task`) is cortex-only by construction
     (built-ins never reach subagents, ADR-0010/0013), so nothing real is dropped.
     `SubagentTask` grows the field when a consumer exists, not before.

4. **First consumer: `schedule_task` fills `ScheduledItem.session_id` from the stamp**,
   closing the ADR-0025 attribution deferral. Attribution is provenance, not display:
   the listing line does not render it, and creation confirmations keep not echoing it.

## Consequences

**CI-gated (100% under `just check`, no Redis/GPU/OS):** the stamp value + dispatcher
overwrite (forged-stamp discard included), the loop threading (engine session to
dispatched call end to end), the schedule attribution, the ticker's stored-provenance
stamp, and every updated call site.

**Deferred (recorded in the ROADMAP's deferred-refinements section):**

- **Source URI/sender fields on the stamp** (the ADR-0013/0019 capture slice). The open
  design question is where a locator comes from, since `ToolResult` carries no source
  and a generic MCP adapter cannot know an email's sender; that design lands as its own
  slice against this seam.
- **Confirm-with-provenance** (ADR-0022) stays deferred: it reverses a deliberate
  fail-closed posture and is revisited as a decision, not slipped in as plumbing.
- **`MemoryRecord` provenance** (ADR-0019) rides a later slice consuming the same stamp.
- **`SubagentTask` session attribution**, when a subagent-reachable consumer exists.
- **The audit line** (`ToolInvocation`) gains the stamp when an audit consumer wants
  per-session queries; today no reader joins on it.

## Alternatives rejected

- **A second loose keyword (`session_id=`) on `dispatch`.** Works once, then the third
  fact adds a fourth keyword and every call site churns again; the object form makes the
  next field a no-op at call sites.
- **Stamping at `ToolCall` construction.** The constructors are the model-facing backend
  (which must never author provenance) and call sites that lack the turn context; the
  dispatcher is the single point that both knows the turn and is already trusted to
  overwrite forged fields.
- **A turn-scoped dispatcher constructed per turn.** Dispatchers are wired once at the
  composition root with their gated-name sets and confirmer; rebuilding them per turn
  blurs the wiring/turn boundary for no gain over passing a value.

## Risks

- **The stamp becomes a grab-bag.** Bounded by the consumer rule: a field joins only
  when something reads it (`session_id` lands with `schedule_task` reading it; source
  fields land with their capture slice).
- **`""` conflates "no session" with "unattributed".** Acceptable while the one consumer
  treats both as absent; a structured origin joins with the source fields if a consumer
  ever needs the distinction.

## Addendum (2026-07-16): the source fields land, and where a locator comes from

The deferred **source URI/sender fields** land as `TurnStamp.sources`, a tuple of frozen
`Provenance` values (`cortex_core/provenance.py`), and the open design question above ("where
does a locator come from") is answered by splitting it in two. What follows corrects this ADR's
own framing in one place, noted below.

- **A source is a kind plus a value, and the kind says whose word it is.** `SourceKind` is
  `TOOL` / `MEMORY` / `SENDER` / `URI`, and `SourceKind.attested` is `True` for the first two:
  their values are strings the brain itself authored (a registry-advertised tool name, an id we
  minted), while a sender or a locator is what the content claims about itself. A consumer needs
  that distinction before it renders anything, since an attested value reads as a label and a
  claimed one reads as a quotation. Kind is part of the identity, so eviction by sender cannot
  sweep a URI that spells the same string.
- **Bounded and sanitized in the value's own constructor**, not at any adapter. A source string
  can be attacker-chosen, so `Provenance.__post_init__` runs it through one pass: Unicode
  category `C` characters dropped (whitespace exempted, because a newline is a control character
  and dropping it outright would silently *join* the words it separated), whitespace runs
  collapsed to single spaces, `<` and `>` removed so a value can never spell an
  `<untrusted-tool-output id=...>` marker or any other bracketed structure, and the result capped
  at `MAX_SOURCE_CHARS` with an overflow marker. The pass is idempotent, and no instance can
  exist holding a raw value: there is no constructor that skips it. The ledger then bounds the
  *count* at `MAX_TURN_SOURCES`, keeping the earliest, so a flood of results cannot grow a turn's
  provenance nor push out the source it started from.
- **Nothing the model authored is ever a source.** The loop attributes an untrusted result to
  `spec.name` off the advertisement it dispatched against, never to `call.name` or an argument,
  and a call matching no advertised spec attributes nothing at all. Provenance is destined for a
  confirmation card, which is precisely the display channel `ToolStep` already refuses to let the
  model write into (a call argument reading `Trusted bank, approve this` is the attack).
- **Two capture points exist today, both first-party.** The tool loop notes the advertised tool
  an untrusted result came through (`TaintLedger.observe(result, source=...)`), and the engine's
  recall notes a fenced memory's own record id (`ingest_untrusted(text, source=...)`), which is
  the honest locator there: what originally tainted that memory is not stored beyond ADR-0019's
  bit, so anything finer would be invented rather than known. Each dispatch's stamp copies the
  ledger's sources, as live as the taint bit beside them.
- **The claimed kinds have no producer yet, and that is the honest half.** This ADR guessed that
  "a generic MCP adapter cannot know an email's sender"; reading the code shows the tighter
  statement. `ToolResult` carries no source *and* a FastMCP tool returns content blocks, with no
  result `_meta` to ride: the only structured channel is `structuredContent`, which replaces the
  readable string the model consumes (`cortex_email.server` deliberately returns one). So the
  sender the email sidecar plainly knows has no path into the brain that does not either widen
  `ToolResult` **and** design a sidecar declaration channel, or make the core parse a sidecar's
  rendered text (rejected: that is sidecar format knowledge in the hexagon's center). `SENDER`
  and `URI` therefore ship as shaped, tested, matchable kinds with their capture deferred, so
  the field they arrive in is not designed twice.
- **No proto change, no store change.** `TurnStamp` is brain-internal: nothing serializes it, the
  proto's `tainted` fields are `DueReminder`/`NotifyRequest`'s own, and the loop persists the
  *unstamped* calls. And no call site changed to gain the field, which was the point of deciding
  the object form here rather than adding a keyword per fact.

**Deferred (recorded in `docs/refinements/index.md#untrusted-content`):**

- **A sidecar-declared sender/URI.** Needs the `ToolResult` widening plus a declaration channel
  that does not disturb the model-facing text, per the paragraph above.
- **Provenance across the stores.** `ScheduledItem` and `SubagentResult` each store the taint
  bit only, so a fired task's stamp and a subagent's own readings attribute nothing back to the
  turn that consumes them. Both wait on a consumer, alongside this ADR's `SubagentTask` and audit
  line deferrals.
- **The two named consumers stay deferred and unbuilt**, as this ADR already recorded:
  confirm-with-provenance reverses a fail-closed posture (a decision, not plumbing) and
  per-provenance eviction wants `MemoryRecord` provenance first.

## Addendum (2026-07-16): the sidecar declaration channel exists, and the sender lands

The **sidecar-declared sender/URI** deferred above lands as a sender producer, and in building it the
source-fields addendum's reachability claim proved **false**. That addendum stated that a FastMCP tool
"returns content blocks, with no result `_meta` to ride", so "the sender the email sidecar plainly
knows has no path into the brain" without either `structuredContent` (which replaces the readable
text) or parsing rendered text (rejected). Read against the shipped MCP SDK (1.28.1), the opposite is
true, and it is the clean channel the addendum was looking for.

- **Result `_meta` is reachable through the very client the registry uses.** `CallToolResult` extends
  `Result`, which carries `meta: dict | None` (aliased `_meta`), so `mcp.ClientSession.call_tool`
  returns it and `McpToolRegistry.invoke` can read `result.meta` with no SDK change.
- **A FastMCP tool sets result `_meta` by returning a `CallToolResult`.** The low-level `call_tool`
  handler returns a handler-produced `CallToolResult` straight through (`ServerResult(results)`), and
  FastMCP types a `-> CallToolResult` tool as "return without output-schema validation", so it passes
  the value through untouched, `_meta` and all, with no `structuredContent`. Proven by an in-memory
  client/server round trip: result-level `_meta` survived to the client while the readable string
  stayed in the content blocks, unchanged. The addendum's true constraint was only its own preferred
  channel (`structuredContent`); `_meta` was there the whole time.
- **The transport half.** `read_email` returns a `CallToolResult` whose single text block is the same
  readable message and whose `_meta["cortex/source"]` declares `{"kind": "sender", "value": <From>}`.
  `McpToolRegistry.invoke` reads that key (`_declared_source`) into a new `ToolResult.source`, and the
  loop's `TaintLedger.observe` notes it beside the attested `TOOL` source. The `_meta` key is a
  cross-deployable wire contract, since the email sidecar deliberately cannot import the core.
- **The trust half.** A declaration is attacker-influenceable (a `From` is the sender's to write, and a
  hostile sidecar could name anything), so the pure-core `claimed_source(kind, value)` is the gate: it
  admits only a **claimed** `SourceKind` (`SENDER`/`URI`), dropping any attested kind that would forge a
  trusted-looking label, and sanitizes/bounds the value through `Provenance` like every source. `observe`
  marks taint from `result.trust` before noting any source, so a declared source only ever annotates and
  can never downgrade the turn. The core owns which kinds are declarable and the sanitization; only the
  `_meta` transport detail lives in the adapter.
- **The consumer is thin, honestly.** Nothing reads `SENDER`/`URI` provenance today:
  confirm-with-provenance stays declined (a producer alone does not reverse the fail-closed decision),
  and per-provenance eviction wants `MemoryRecord` provenance first. The producer lands anyway to
  complete the provenance design symmetrically for the claimed kinds, the same "build the field ahead of
  its consumer" logic the source fields themselves landed on. The `URI` kind rides the identical channel;
  its producer arrives with a fetch tool, which does not exist yet.

**Still deferred (recorded in `docs/refinements/`):** provenance across the stores, per-provenance
eviction, confirm-with-provenance (unchanged decision), and a `URI` producer (a fetch tool, feature
breadth).

## Addendum (2026-08-21): both attribution deferrals close, in the audit trail

The two entries this ADR left waiting on a consumer, `SubagentTask` session attribution and the
audit line gaining the stamp, are both closed by one change, argued in the
[ADR-0009](ADR-0009-tools-mcp.md) named-work addendum. The consumer they were waiting for is the
tool audit trail, which now names the work each dispatch was made for.

Three things about this ADR's own framing are worth setting straight here.

- **The stamp does not go on the line.** `ToolInvocation` takes three strings off the stamp
  (`session_id`, `turn_id`, `task_id`) and leaves its live handles behind, an audit record being a
  value that outlives the process the pool, sink and slot live in.
- **The stamp gained an identity it never carried.** `turn_id` and `task_id` join `session_id` on
  `TurnStamp`, which is the shape this ADR predicted for `sources`: a field lands on the one object
  and no call site changes.
- **`""` still conflates "no session" with "unattributed", and now says so out loud.** The risk
  above accepted the conflation while one consumer treated both as absent. The trail is the second
  consumer and treats them the same way, by leaving an absent id off the line entirely rather than
  printing it empty. A structured origin is still what a reader needing the distinction would
  want, and still nothing needs it.
