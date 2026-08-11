# Structured provenance on the TurnStamp

**Status:** landed 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

Recorded as the [ADR-0027 source-fields addendum](../../adr/ADR-0027-turn-provenance.md), it closed
the ADR-0013/0019 "beyond the bit"
deferral above. The stamp carries `sources: tuple[Provenance, ...]` beside its taint bit, where
a `Provenance` is a `SourceKind` (`TOOL` / `MEMORY` / `SENDER` / `URI`) plus a value, and
`SourceKind.attested` says whose word the value is: ours for the first two (a
registry-advertised tool name, an id we minted), the content's own claim for the other two, a
distinction any consumer needs before it renders a source as a label rather than as a
quotation. Kind is part of the identity, so eviction by sender cannot sweep a URI spelling the
same string. **The untrusted string is bounded and sanitized in the value's constructor**
(`cortex_core/provenance.py`), not at an adapter and not at a call site: category-`C`
characters dropped with whitespace exempted (a newline is a control character, and dropping it
outright would silently *join* the words it separated, which the tests caught), whitespace runs
collapsed, `<`/`>` removed so a value can never spell an `<untrusted-tool-output id=...>`
marker, and a hard `MAX_SOURCE_CHARS` cap, idempotently, with no constructor that skips the
pass; the ledger then caps the *count* at `MAX_TURN_SOURCES`, keeping the earliest, so a flood
cannot grow a turn's provenance nor push out what it started from. **Nothing the model authored
is ever a source:** the loop attributes to the advertised `spec.name` it dispatched against,
never `call.name` or an argument, and a call matching no spec attributes nothing, the same rule
`ToolStep` already applies to the activity chip (provenance is destined for a confirmation
card, so an argument reading `Trusted bank, approve this` is the attack). Two first-party
capture points exist today (the loop's untrusted tool result, and recall's fenced memory naming
its own record id, since what tainted that memory is not stored beyond the bit); **no proto,
store, or call-site change**, which is what the ADR-0027 object form was for. The ADR's guess
that "a generic MCP adapter cannot know an email's sender" understated it: a FastMCP tool
returns content blocks with no result `_meta`, and `structuredContent` would replace the
readable string the model consumes, so the sender the email sidecar plainly knows has no path
in at all today. Remaining behind the same seam (ADR-0027 addendum deferred): a
**sidecar-declared sender/URI** (needs a `ToolResult` source field *plus* a declaration channel
that does not disturb the model-facing text; parsing a sidecar's rendered text was rejected
as sidecar format knowledge in the hexagon's center), and **provenance across the stores**
(`ScheduledItem` and `SubagentResult` each store the taint bit only, so a fired task's stamp
and a subagent's own readings attribute nothing back to the turn that consumes them).

## Trail

- 2026-07-16: Landed and took the area's count from 16 to 17, because the two halves it could not
  honestly capture, a sidecar-declared sender and provenance across the stores, each became an
  entry naming what blocks it.
