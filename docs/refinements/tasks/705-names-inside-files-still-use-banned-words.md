# Names inside the files still use words the prose table bans

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-22

Decision 15 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) says the banned-word
table reaches every name a reader meets in hand-written code and stops at names fixed outside it.
A survey on 2026-09-22 split every identifier in the tracked `.py`, `.rs`, `.ts` and `.tsx` files
on `_` and on case changes and matched the parts against the table. It left out generated code,
`CORTEX_` variables, `cortex_seam`, `RankBasis.SWEEP` and the Rust `Pin` and `pin_mut`. It still
finds 576 distinct names, largest family first:

- `carry`, `carries`, `carried`, `carrying`: 173 names, most of them test names (brain 101,
  scripts 64, body 8).
- `gate`, `gates`, `gated`, `ungated`: 135 names. They are the tool confirmation list
  (`GatedToolRegistry`, `UngatedToolRegistry`, `GatedBackend`), `ReadinessGate` in the residency
  code, and the word the checks under `scripts/` use for themselves (`GATES`, `FLAG_GATE`). The
  variables `CORTEX_TOOLS_GATED` and `CORTEX_TOOLS_GATE_REASONS` stay.
- `seam`: 64 names such as `BrainSeamClient`, `SeamServerConfig` and `DEFAULT_SEAM_HOST`. The
  package, the proto package and the `CORTEX_SEAM_*` variables stay.
- `pinned`, `pin`, `pins`, `pinning`: 63 names, most of them the feature that keeps a chat at the
  top of the list, which waits for the designed name
  [R-701](701-keeping-a-chat-at-the-top-has-no-designed-name.md) asks for. The proto's
  `SetSessionPinned` and `pinned` stay.
- `arm`, `arms`, `armed`: 56 names, mostly the conditions of the live measurement tests
  (`SHIPPED_ARM`, `_ARMS`) and the escalation slot (`armed_slot`). The envelope samples' recorded
  `arm` key, `CORTEX_ENVELOPE_ARMS` and `CORTEX_TURN_COST_ARM` stay.
- `verdict`, `verdicts`: 28 names, among them `Verdict` in the injection probes.
- `land`, `lands`, `landed`, `landing`: 25 names.
- `standing`: 9 names, all but one of them test names under `scripts/`.
- `knob` and `knobs` 9, `honest` and `honestly` 6, `robust` 4, `backstop` 2, `rederive` 1 and
  `sitting` 1.

The overlay's Vitest titles hold 42 more uses of these words. Two kinds of text are outside the
survey on purpose: the email tool descriptions in `cortex_email/values.py` and
`cortex_orchestrator/own_texts.py`, which the model reads, so a change there needs a model
measurement; and the row labels in `test_reply_readings.py`, which match recorded readings.

**What would close it.** Each family renamed as a code change, with the runbook, module doc and
task files that quote a name changed in the same commit, or a decision in ADR-0040 that a family
stays, with the reason. The `pinned` family closes with R-701.

## History

- 2026-09-21: opened by the close of [R-699](699-source-file-names-use-banned-words.md), which
  renamed the files and left the names inside them.
