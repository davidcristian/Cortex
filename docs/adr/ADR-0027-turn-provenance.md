# ADR-0027: Structured turn provenance (`TurnStamp`)

**Status:** Accepted (2026-09-19)

## Context

Four recorded deferrals needed the same missing channel. Closing any of them meant letting "where
did this work come from" travel with what a turn starts:

1. [ADR-0013](ADR-0013-untrusted-content.md) deferred structured provenance beyond the binary taint
   bit (source locator, sender) at the untrusted-content boundary.
2. [ADR-0019](ADR-0019-tainted-memory-recording.md) deferred the same fields on `MemoryRecord`,
   beyond its `tainted` column.
3. [ADR-0022](ADR-0022-email-write-confirmer.md) deferred confirm-with-provenance: the tainted
   branch that needs confirmation blocks outright partly because the confirmation card has no
   source to show.
4. [ADR-0025](ADR-0025-scheduling-reminders.md) deferred session attribution:
   `ScheduledItem.session_id` was stored and sent on the wire but was `""` at creation, because
   the creating tool had no way to learn the turn's session.

The only turn context a dispatched call had was the single `tainted` bool, passed to
`ToolDispatcher.dispatch` as a keyword and overwritten onto the call at dispatch time
([ADR-0018](ADR-0018-heterogeneous-subagents.md) decision 4), where `spawn_subagents` and the
schedule built-ins read it. Adding each deferral the same way would add a parallel keyword and a
second overwritten field per fact. This ADR designs the channel once.

## Decision

### The stamp

1. **One frozen value, `TurnStamp`, owned by the tool domain (`tools.py`).** It holds the work
   identities `session_id` (the originating chat), `turn_id`, `task_id` (the subagent task a call
   was made inside) and `item_id` (the scheduled item whose run made it), each `""` when there is
   none; `tainted` (whether the turn had read untrusted content at dispatch time); and `sources`,
   the structured provenance behind that bit (decision 5). It also holds three live handles the
   turn passes down to work it starts, the dispatch `budget`, the stream's `progress` sink and the
   `escalation` slot, all excluded from equality so two dispatches of one turn stay comparable. A
   field is added only once something reads it, and it is added to this object: a parallel keyword
   on `dispatch` or a second stamped field on `ToolCall` is what this decision rules out.
   `turn_id`, `task_id` and `sources` were all added that way without changing a call site.

2. **The dispatcher is the one place that stamps.** `dispatch(call, *, stamp, confirm_required)` overwrites
   `ToolCall.stamp` with its own argument, so a stamp the model forged is discarded, and the
   capability check decides on the dispatcher's argument (`stamp.tainted`), never on anything the
   model wrote. `UNSTAMPED` (a module constant, since a default must not be a call) is the
   unattributed default: no session, no taint, open on attribution and safe on capability. The
   stamp is transient: the loop stores the calls without it.

3. **Three places build a stamp, under one rule: the caller states the facts it has.**
   - The **cortex turn**: the tool loop builds a fresh stamp per dispatch from its
     `ToolLoopContext` (`dispatch_round._stamp`), because the taint bit and the sources are live
     and can change mid-round as results arrive.
   - The **ticker**: an item's synthetic `spawn_subagents` dispatch uses the item's stored
     `session_id`, its own `item_id` and its taint, so autonomous work is attributed to the chat
     that scheduled it and to the item.
   - A **subagent**: `SubagentTask` holds `session_id`, `turn_id` and `item_id`, written from the
     spawning dispatch's stamp and stored with the task, and the runner stamps the subagent's
     own calls with them and the task's id. A subagent result therefore identifies the turn behind
     it through one `get_task`.

4. **`schedule_task` fills `ScheduledItem.session_id` from the stamp.** Attribution is provenance,
   not display: the listing line does not render it and a creation confirmation does not echo it.

### Sources

5. **A source is a kind plus a value, and the kind says whose word it is** (`provenance.py`).
   `SourceKind` is `TOOL`, `MEMORY`, `SENDER` or `URI`, and `SourceKind.attested` is `True` for
   the first two: their values are strings the brain wrote (a tool name from the registry, a
   memory id it created), while a sender or a locator is what the content claims about itself. A
   consumer needs that distinction before it renders anything, since an attested value reads as a
   label and a claimed one as a quotation. The kind is part of the identity, so eviction by sender
   cannot also remove a URI with the same string.

6. **A value is bounded and sanitized in its own constructor, never at an adapter.** A source
   string can be attacker-chosen, so `Provenance.__post_init__` drops Unicode category `C`
   characters (whitespace exempt, because dropping a newline would join the words it separated),
   collapses whitespace runs to one space, removes `<` and `>` so a value can never form an
   `<untrusted-tool-output id=...>` marker or any other bracketed structure, and caps the result at
   `MAX_SOURCE_CHARS` (96) with an overflow marker. The pass is idempotent and no constructor skips
   it; a value that sanitizes to nothing is refused. The ledger keeps at most `MAX_TURN_SOURCES`
   (8) per turn, the earliest first, so a flood of results cannot grow a turn's provenance or push
   out the source it started from.

7. **Nothing the model wrote is ever a source.** The loop attributes an untrusted result to the
   `spec.name` of the specification it dispatched against, never to `call.name` or an argument, and
   a call matching no specification attributes nothing. Provenance is destined for a confirmation
   card, a display channel the model must not write into (a call argument reading "Trusted bank,
   approve this" is the attack), which `ToolStep` already keeps closed.

8. **Three capture points, two attested and one claimed.** The tool loop records the tool an
   untrusted result came through (`TaintLedger.observe(result, source=...)`); the engine's recall
   records a fenced memory's own record id (`ingest_untrusted(text, source=...)`), the most
   accurate locator available because what first tainted that memory is not stored beyond
   ADR-0019's bit; and a sidecar may declare the sender its content came from (decision 9). Each
   dispatch's stamp copies the ledger's sources, as live as the taint bit beside them.

9. **A sidecar declares a source in the result's `_meta`.** `CallToolResult` has a `meta` field
   (aliased `_meta`), so `mcp.ClientSession.call_tool` returns it and `McpToolRegistry.invoke`
   reads it with no SDK change; a FastMCP tool typed `-> CallToolResult` passes its value through
   untouched, with the readable text still in the content blocks. `read_email` returns one whose
   `_meta["cortex/source"]` is `{"kind": "sender", "value": <From>}`, and the registry
   (`_declared_source`) reads it into `ToolResult.source`. The key and its two fields are a wire
   contract fixed on both sides, because the sidecar cannot import the core, and
   `scripts/emailcouplings.py` checks that the two agree. `structuredContent` was rejected because
   it replaces the text the model reads, and parsing a sidecar's rendered text because that puts
   sidecar format knowledge in the core.

10. **A declaration is accepted only as a claim.** A `From` is the sender's to write and a hostile
    sidecar could name anything, so the pure-core `claimed_source(kind, value)` accepts only a
    claimed kind (`SENDER`, `URI`), drops a declaration of an attested kind that would forge a
    trusted-looking label, and sanitizes the value through `Provenance`. `observe` marks taint from
    `result.trust` before recording any source, so a declared source only annotates and can never
    lower the turn's trust.

### Where the stamp's facts are kept

11. **The audit record takes the identities, not the stamp.** `ToolInvocation` copies
    `session_id`, `turn_id`, `task_id` and `item_id` off the stamp as strings and leaves the live
    handles behind, because an audit record is a value that outlives the process the pool, sink and
    slot live in ([ADR-0009](ADR-0009-tools-mcp.md) decision 16, names per
    [ADR-0046](ADR-0046-work-identities-on-log-lines.md)).

12. **`""` stands for both "no session" and "unattributed".** Both consumers, the schedule
    attribution and the audit record, treat the two alike: the audit line leaves an absent id out
    rather than printing it empty. A structured origin would separate them, and nothing needs the
    distinction.

13. **The stamp itself is never serialized; one store keeps a turn's whole ledger.** No proto
    change was needed, and the proto's `tainted` fields are `DueReminder`'s and `NotifyRequest`'s
    own. `HandoffRecord` stores `tainted`, `opaque`, `sources` and `untrusted_urls` under the
    escalating turn's id, and `taint_ledger()` rebuilds the ledger after the model swap, asserted
    by the handoff store's contract suite. That is the form a durable per-turn provenance record
    would copy.

## Consequences

- **The claimed kinds are produced before anything consumes them.** Nothing reads `SENDER` or
  `URI` provenance yet. Confirm-with-provenance was declined, since a producer alone does not
  reverse the fail-closed branch ([task 208](../refinements/tasks/208-confirm-with-provenance.md)),
  and per-provenance eviction needs `MemoryRecord` provenance first. A `URI` producer uses the same
  channel and arrives with a fetch tool, which does not exist.
- **What is still missing across the stores is the sources.** A scheduled item that ran identifies
  its chat but not its turn, a subagent result identifies its turn through its task, and no store
  keyed by a turn keeps that turn's sources except the handoff record of a turn that escalated
  ([task 077](../refinements/tasks/077-provenance-across-stores.md)).
- **CI covers it without Redis or a GPU:** the stamp value and the dispatcher's overwrite (a forged
  stamp included), the loop threading, the schedule attribution, the ticker's stamp, the
  sanitizing pass, and the declaration channel over an in-memory MCP client and server.

## Alternatives rejected

- **A second loose keyword (`session_id=`) on `dispatch`.** Each new fact would add another and
  churn every call site; the object form makes the next field free at call sites.
- **Stamping at `ToolCall` construction.** The constructors are the model-facing backend, which
  must never write provenance, and call sites that lack the turn context; the dispatcher both has
  the turn and is already trusted to overwrite forged fields.
- **A turn-scoped dispatcher built per turn.** Dispatchers are wired once at the composition root
  with their capability set and confirmer; rebuilding them per turn blurs that boundary for no gain
  over passing a value.
- **Putting the stamp on the audit line.** Its handles are live objects, not values (decision 11).

## Related

- Module contracts: [brain-core.md](../modules/brain-core.md),
  [brain-tools.md](../modules/brain-tools.md), [brain-email.md](../modules/brain-email.md).
- [ADR-0009](ADR-0009-tools-mcp.md) (dispatch and the audit record),
  [ADR-0013](ADR-0013-untrusted-content.md) (the taint bit),
  [ADR-0018](ADR-0018-heterogeneous-subagents.md) (the first stamped field),
  [ADR-0046](ADR-0046-work-identities-on-log-lines.md) (work identity names).
