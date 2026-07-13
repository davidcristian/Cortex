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
