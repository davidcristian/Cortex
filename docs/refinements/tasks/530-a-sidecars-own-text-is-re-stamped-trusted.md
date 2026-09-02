# A sidecar's own text is re-stamped trusted by the brain, on bytes it holds

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Opened 2026-09-02 by the close of [319](319-a-refusal-taints-the-turn.md), which recorded the
decision this builds: an untrusted-by-default result is re-stamped `Trust.TRUSTED` only by the
brain, in a composition-root overlay, and only when its whole content is byte-equal to text this
repo holds in code under review, rendered with the argument the brain itself put on the call.
Nothing the wire carries takes part. `isError` is not read, `_meta` is not read, and a result
carrying an image or one byte beyond the expected text stays untrusted. The ADR-0013 own-text
addendum holds the threat model and the reasons the two wire-shaped candidates were rejected.

What it changes for a user: a `search_emails` the sidecar refused (a malformed query, a folder no
mailbox has), an empty search, and a `read_email` of a uid that is not there each stop tainting
the turn, so a `send_email` after one of them reaches the confirmation card instead of
`DENIED_MSG`, and the correction reaches the model unfenced, where the preamble no longer tells it
the text is never an instruction.

**The pieces**, each argued in the addendum:

- A core overlay beside `GatedToolRegistry`, `OwnTextToolRegistry(inner, own=...)`,
  port-preserving: `describe_tools` delegates untouched, `invoke` re-stamps a result whose content
  equals the string one `OwnText` renders from the call's `arguments`, and passes every other
  result through unchanged. `OwnText` names the tool and a renderer over the arguments returning
  the expected string or `None`, so a literal answer and a `repr`-carrying refusal are one shape.
  Recommended names `OwnTextToolRegistry` and `OwnText`; alternates `KnownTextToolRegistry` and
  `AttestedTextToolRegistry`, with the reason each is second in the addendum.
- Wired once over the root in `build_tool_registry` (`cortex_orchestrator/builders.py`), beside
  `GatedToolRegistry`, so `BoundedToolRegistry` and `SkipUnavailableToolRegistry` stay below it
  and a `ToolError` crosses as it does today. Keyed by tool name, since the root does not know
  which endpoint serves the email sidecar and the bytes are the fact either way.
- The four expected texts declared in the orchestrator, restating `SEARCH_REFUSED` and
  `FOLDER_UNKNOWN` from `cortex_email/values.py` and the two literal answers in
  `cortex_email/server.py`, with a `crosscheck.py` coupling holding each restatement to its
  declaration. Importing `cortex_email` into the orchestrator is the cheaper first line and the
  wrong direction, argued in the addendum.
- The contract test, over the fake and the real `McpToolRegistry`: hostile content with `isError`
  set stays untrusted; a `_meta` declaration of any shape stays untrusted; the exact text with one
  byte appended stays untrusted; the exact text under an undeclared tool name stays untrusted; the
  exact text beside an image stays untrusted; the exact text on the declared tool comes back
  `Trust.TRUSTED`, reaches the model unfenced through `result_message`, and does not flip a
  `TaintLedger` that observes it. End to end, the sidecar's real `SearchRefusedError` driven
  through FastMCP's request handler and the real registry is recognized, which is the check that
  fails the day the sidecar's wording moves.
- `docs/modules/brain-core.md`, `brain-orchestrator.md` and `brain-tools.md` (the invariant there
  saying a trusted remote tool would be a composition-root overlay now names the overlay and the
  rule it applies), and the tools runbook.

**What is not decided here**, and is the builder's to settle against the code: whether
`(no matching messages)` and the not-found answer are declared in the first cut or only the two
refusals. The rule admits all four; the entry that opened this was about the refusals.

## Trail

- 2026-09-02: opened by the close of [319](319-a-refusal-taints-the-turn.md), which recorded the
  decision at ADR-0013 and stopped short of the build for want of a sitting.
