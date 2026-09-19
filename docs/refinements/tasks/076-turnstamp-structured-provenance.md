# Structured provenance on the TurnStamp

**Status:** done 2026-07-16
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

The stamp now has `sources: tuple[Provenance, ...]` beside its taint bit, where a `Provenance` is
a `SourceKind` (`TOOL`, `MEMORY`, `SENDER` or `URI`) plus a value, and `SourceKind.attested` says
whose word the value is: ours for the first two, a registry-advertised tool name and an id we
created, and the content's own claim for the other two. Any consumer needs that distinction before
it renders a source as a label rather than as a quotation. Kind is part of the identity, so
eviction by sender cannot also remove a URI written as the same string. Recorded as
[ADR-0027 decisions 5 to 8](../../adr/ADR-0027-turn-provenance.md), closing the "beyond the bit"
item that [R-072](072-tainted-memory-recording.md) left.

The untrusted string is bounded and sanitized in the value's constructor
(`cortex_core/provenance.py`), not at an adapter and not at a call site: category-`C` characters
are dropped with whitespace exempted (a newline is a control character, and dropping it outright
would join the words it separated, which the tests caught), whitespace runs are collapsed, `<` and
`>` are removed so a value can never write an `<untrusted-tool-output id=...>` marker, and there
is a hard `MAX_SOURCE_CHARS` cap. The pass is idempotent and no constructor skips it. The ledger
then caps the count at `MAX_TURN_SOURCES`, keeping the earliest, so a flood can neither grow a
turn's provenance nor push out what it started from.

Nothing the model authored is ever a source: the loop attributes to the advertised `spec.name` it
dispatched against, never `call.name` or an argument, and a call matching no spec attributes
nothing. Provenance is meant for a confirmation card, so an argument reading
`Trusted bank, approve this` is the attack.

Two first-party capture points exist today: the loop's untrusted tool result, and recall's fenced
memory naming its own record id, since what tainted that memory is not stored beyond the bit. No
proto, store or call-site change was needed, which is what the object form was for.

The ADR's guess that a generic MCP adapter cannot know an email's sender understated it: a FastMCP
tool returns content blocks with no result `_meta`, and `structuredContent` would replace the
readable string the model consumes, so the sender the email sidecar plainly knows has no way in at
all today.

Two things were left behind it: a sidecar-declared sender or URI
([R-078](078-sidecar-declared-sender.md)), which needs a `ToolResult` source field plus a
declaration channel that does not disturb the model-facing text, parsing a sidecar's rendered text
having been rejected as sidecar format knowledge in the core; and provenance across the stores
([R-077](077-provenance-across-stores.md)), since `ScheduledItem` and `SubagentResult` each store
the taint bit only.

## History

- 2026-07-16: Shipped. The two halves it could not capture accurately, a sidecar-declared sender
  and provenance across the stores, each became an entry naming what blocks it.
