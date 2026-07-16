# Email write & the Confirmer

This area's deferrals originate in [ADR-0022](../adr/ADR-0022-email-write-confirmer.md), the
email-write and Confirmer decision. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** real-file attachments (bytes the assistant did not author), per-field attachment schema descriptions, trust overlays for remote tools, batching / per-tool session allowlists, ToolActivity wire phase field. Confirm-with-provenance for tainted turns was **declined 2026-07-16** (annotated in place below); subagent tool-step surfacing **landed 2026-07-16** as one side channel with the progress-reporting entry from [subagents.md](subagents.md) (annotated in place below).

**Email-write & the Confirmer in Slice 8.8 ([ADR-0022](../adr/ADR-0022-email-write-confirmer.md)):**
each behind the unchanged `Confirmer`/`ToolDispatcher`/`GatedToolRegistry`/seam shapes.
- **Confirm-with-provenance for tainted turns.** The tainted branch is an unconditional block; a
  provenance-showing confirmation (so the user can knowingly approve) needs structured
  provenance first (the ADR-0013/0019 deferral; its `TurnStamp` seam landed 2026-07-13,
  [ADR-0027](../adr/ADR-0027-turn-provenance.md), the source fields still pending). It also
  reverses a deliberate fail-closed posture, so it is revisited as a decision, never slipped
  in as plumbing. Until then, re-ask in a fresh turn.
  **Declined 2026-07-16 ([ADR-0022 confirm-with-provenance addendum](../adr/ADR-0022-email-write-confirmer.md)).**
  The source fields the entry waited on landed (`TurnStamp.sources`, [ADR-0027 addendum](../adr/ADR-0027-turn-provenance.md)),
  so the decision it always was could finally be made, and it is a decision to keep the block.
  Read against the code first: `ToolDispatcher.dispatch` (`cortex_core/dispatch.py`) returns
  `DENIED_MSG` on a gated call whenever `stamp.tainted`, and the confirmer is **never consulted**
  (`test_gated_tool_on_a_tainted_turn_is_blocked_even_when_a_confirmer_would_approve` asserts
  `confirmer.requests == ()` with an approving confirmer, run green this session). So the posture
  is a hard block, not a confirm-without-provenance, and there is no card on this path to add a
  source line to. Reversing it is rejected for two independent reasons. **The block is a
  deterministic guarantee, not a provenance gap:** after untrusted content enters a turn the
  outbound surface is closed, full stop, because a tainted turn's arguments may be
  injection-authored and a send demanded by injected content must never be merely a confirm-away
  (`cortex_core/untrusted.py`); a source line does not change what the card asks a user conditioned
  to approve to do, and at worst launders the action by implying the system vetted it. The posture
  is **not over-broad**, since the legitimate read-then-reply flow still completes in a fresh turn
  (taint is turn-local, `DENIED_MSG` says to re-ask), so keeping the block costs one extra turn, a
  cost the ADR already accepted, while reversing it reopens the exact path an injection aims for.
  **And the useful provenance is absent anyway:** the only two `Provenance` producers are attested
  (`SourceKind.TOOL` in `cortex_core/tool_loop.py`, `SourceKind.MEMORY` in `cortex_core/engine.py`),
  so a card built today would name the user's own tool use, not the attacker; the `SENDER`/`URI`
  kinds that would name the attacker have no producer (the sidecar-declared-sender deferral in
  [untrusted-content.md](untrusted-content.md)). This is the same fail-closed philosophy as the
  same-day decline of summarizing a tainted exchange: a provenance card makes the **user** the
  injection target, worse than the model. Reopens only if the outbound-on-tainted decision is
  itself revisited with evidence that a card converts reflexive approval into scrutiny, **and** a
  real `SENDER`/`URI` producer exists, not on provenance plumbing alone.
- **Richer send shapes.** **cc/bcc/HTML landed 2026-07-13 ([ADR-0022 richer-send-shapes
  addendum](../adr/ADR-0022-email-write-confirmer.md)).** The `EmailSender.send` contract took a
  frozen `EmailDraft` value (to/subject/body + optional cc/bcc/html), so the addition rides a
  value object, not a wider signature; cc/bcc get the recipient's CR/LF header-injection refusal,
  a bcc is stripped from the transmitted message by `send_message` (stdlib), and html composes a
  `multipart/alternative`. Entirely inside the sidecar behind the unchanged brain-side gate
  (still `send_email` in `CORTEX_TOOLS_GATED`, confirm card unchanged); CI-gated at 100% and the
  live round-trip now exercises cc + html.
- **Attachments landed 2026-07-15 ([ADR-0022 attachments
  addendum](../adr/ADR-0022-email-write-confirmer.md)), as authored text.** This entry framed the
  open question as a bytes-transport choice (a base64 blob versus a filesystem path, the latter
  needing a mount *and* a file-read capability on a sidecar that deliberately has neither). Both
  candidates turn out to be disqualified by something cheaper to check than their cost: this
  ADR's own **`arguments_json` is the executed contract** rule. A path puts a *name* on the
  confirmation card and reads the bytes after the click, from a filesystem that can change in
  between; base64 puts bytes on the card that no human can read. So an attachment is
  `EmailAttachment(filename, content, subtype="plain")` on the draft, composed as one `text/*`
  part each: the maintype is not a parameter (as `From` is not), which makes the capability one
  sentence, namely the assistant attaches what it **wrote**. Transport-free (tool arguments
  already arrive as JSON over MCP), so no new capability, no proto/port/gate/taint change, and
  a draft without attachments is byte-for-byte the previous message. Refused rather than
  truncated past five bounds in `SmtpSender._compose` (filename non-empty, CR/LF-free, ≤ 128
  chars; subtype a MIME token; ≤ 8 attachments; ≤ 32768 characters of content in total), each
  mutation-proven. Two costs the entry did not predict, both small: ruff's `max-args = 6` fires
  on the **advertised tool signature**, where the ceiling's own rationale (bundle *collaborators*)
  does not apply, so it takes an inline `noqa` with that reason rather than folding user-visible
  draft fields into an object the model would have to learn; and driving the card in a browser
  found two pre-existing gaps an attachment is the first value to reach, namely `.confirm-draft`
  having no height bound (the first argument *meant* to be long pushed Approve and Deny out of
  view; now `max-height: 42vh` and scrolls) and non-string values being rendered with
  `JSON.stringify` (so a file's newlines reached the user as `\n` escapes; now a generic
  `formatDraftValue`, which knows JSON shapes and nothing about `send_email`).
  Remaining behind the same seam: **bytes the assistant did not author** (a real file), which
  needs the capability grant *plus* a way for the card to bind approval to a payload the user
  cannot read (a digest and size shown, the sidecar re-reading at send and refusing on mismatch);
  and **per-field schema descriptions** inside the nested object. Verified over a real sidecar
  rather than assumed: pydantic lifts the `EmailAttachment` **docstring** into the `$defs`
  entry's `description`, so the model is already told what an attachment is and is not; only
  per-field prose would need `Field(description=...)`, and that would put pydantic in the pure
  values module to say what the type names already say.
- **The structured confirm-resolution event landed 2026-07-14 ([ADR-0022 resolution
  addendum](../adr/ADR-0022-email-write-confirmer.md)).** This entry's cost estimate was the
  understated kind the section warns about: it read as an overlay refinement, and it is a
  **seam change**, because `ServerEvent` had no way to say a confirmation ended (`ConfirmRequest`
  was the only confirm event the brain could emit, and `SeamConfirmer.confirm` just returned
  `False` on timeout). So it touched the proto, both committed stub trees, the confirmer, the
  Rust port + adapter, the Tauri shell's serde mirror, and the reducer. `ConfirmResolved
  {confirm_id, outcome}` (field 7) is emitted **only for the endings the client cannot already
  know**: the confirm timeout (`"timeout"`) and client input half-closing (`"unavailable"`).
  Not the user's own answer (the client authored it and closed its own card), not a cancelled
  or torn-down turn (its terminal event closes the card, as it always has), and not an ask
  refused after `close`, which emitted no request and so has no card to close. That table is
  the contract: the overlay's rule is one line ("a resolution for the card I am showing closes
  it"), and everything absent from it was already handled. `outcome` is a string, like
  `SeamError.code` and `StatusUpdate.state`, so no version skew needs an unknown-enum branch;
  the overlay renders none of it, because the model's own reply is the explanation surface
  (`USER_DECLINED_MSG` tells it to relay the declined action) and a card lingering to repeat
  that would be a second account of one fact. The field rides the wire documented anyway, the
  `DueReminder.session_id` precedent. Two behaviours fall out of the card being gone rather
  than needing code: the second-121 Approve click cannot reach the bridge (`respondConfirm`
  already refuses anything that is not the live question), and the explicit deny every
  turn-ending path sends is skipped for a confirm the brain resolved, keeping the answer the
  user never gave off the wire. The reducer action for the user answering was renamed
  `confirmAnswered` to free the name.
- **Trust overlays for remote tools** are the other half of the ADR-0013 deferral; still nothing
  needs a TRUSTED remote tool.
- **Batching / per-tool session allowlists** against confirmation fatigue, if sends become
  frequent enough to matter.
- **`ToolActivity` landed end to end 2026-07-12 ([ADR-0009 chip addendum](../adr/ADR-0009-tools-mcp.md)).**
  The overlay half landed first (the Slice-8 gap closure's inline chips); the brain half followed
  the same day: `stream_tool_loop` yields a `ToolStep` immediately before each audited dispatch,
  the engine maps it to the ephemeral domain `ToolActivity` (the ADR-0020 ephemerality
  precedent: never reply text, never persisted; its registry-authored fields need no
  guardrail pass; the subagent runner drops it), and the orchestrator maps
  that onto the wire event the proto carried since Slice 2, so the already-shipped chip lit up
  with no overlay change. The summary is registry-authored (spec description first line, capped,
  name fallback), never model-authored arguments (an argument echo would hand injected content a
  display channel the ADR-0015 guardrail never inspects). Remaining behind the same seams: a wire
  `phase` field if the chip ever needs completion states (a proto + both-stub-trees change).
  **Subagent tool-step surfacing landed 2026-07-16 ([ADR-0010 progress addendum](../adr/ADR-0010-subagents.md)),
  the same `ToolStep`-to-`ToolActivity` mapping this chip already uses, now off the `SubagentRunner`
  onto the spawning stream's new `ProgressSink` rather than dropped.** It shares the one side channel
  with the ADR-0010 progress-reporting entry (both surface off the dispatch `TurnStamp`, full record
  in [subagents.md](subagents.md)): the subagent's step is the same registry-authored chip, so the
  overlay renders it with **no wire or reducer change** (the deferral's "the subagent runner drops
  it" note is now "maps it onto the sink when it has one"). The
  **dispatch rate/salience policy** this entry also listed is now complete: its rate half landed
  as the budget and cost addenda, and its salience half 2026-07-14 (the ADR-0009 tools-block
  entry in [tools-mcp.md](tools-mcp.md)), which put a refused repeat above the `ToolStep` yield exactly as the budget did,
  so the chip's "a tool is running now" reading survived a second refusal reason.
- **The subagent-side authoritative gated-name backstop wired 2026-07-12
  ([ADR-0022 addendum](../adr/ADR-0022-email-write-confirmer.md)).** `build_subagents` now receives
  its dispatcher pre-assembled: the composition root calls
  `build_subagent_tools(tool_registry, clock, gated_names=CORTEX_TOOLS_GATED)` and passes the
  result (the builtins-bundling precedent, so no 7th arg trips the PLR0913 cap). The user's
  gated set covers subagents exactly as it covers the cortex and the ticker, closing the
  skip-mode double-walk window; `UngatedToolRegistry` (strip + live-walk refusal) and
  `confirmer=None` stay as the structural layers beneath it.
