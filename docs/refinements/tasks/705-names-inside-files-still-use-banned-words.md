# Names inside the files still use words the prose table bans

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-23

Decision 15 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) says the banned-word
table reaches every name a reader meets in hand-written code and stops at names fixed outside it.
A survey splits every identifier in the tracked `.py`, `.rs`, `.ts` and `.tsx` files on `_` and on
case changes and matches the parts against the table's single words. It reads Python names with
`tokenize` and blanks the comments and strings of Rust and TypeScript first, and it leaves out
generated code. On 2026-09-23 it finds 409 distinct names in four families, largest first:

- `carry`, `carries`, `carried`, `carrying`: 169 names, most of them test names.
- `gate`, `gates`, `gated`, `ungated`: 124 names. They are the tool confirmation list
  (`GatedToolRegistry`, `UngatedToolRegistry`, `GatedBackend`), `ReadinessGate` in the residency
  code, and the word the checks under `scripts/` use for themselves (`GATES`, `FLAG_GATE`). The
  variables `CORTEX_TOOLS_GATED` and `CORTEX_TOOLS_GATE_REASONS` stay.
- `seam`: 68 names such as `SeamServerConfig`, `SeamTokenInterceptor` and `DEFAULT_SEAM_HOST`. The
  `cortex_seam` package, the proto package and the `CORTEX_SEAM_*` variables stay.
- `arm`, `arms`, `armed`: 52 names, mostly the conditions of the live measurement tests
  (`SHIPPED_ARM`, `_ARMS`) and the escalation slot (`armed_slot`). The envelope samples' recorded
  `arm` key, `CORTEX_ENVELOPE_ARMS` and `CORTEX_TURN_COST_ARM` stay.

These names stay, because something outside the code or a designed family fixes them:
`RankBasis.SWEEP` and `RankBasis.VERDICT`, members of a designed family (decision 5 of ADR-0040)
whose values the recall audit logs in its `basis` field; the Rust `Pin`, `pin!`, `Box::pin` and
`pin_mut`; and the session store's `_OLD_HOISTED_KEY`, `cortex:sessions:pinned`, until
[R-712](712-the-session-store-still-moves-the-hoisted-sets-first-key.md) closes. Strings are
outside the survey: test data such as a roster entry named `robust`, the recorded model replies,
the row labels in `test_reply_readings.py`, which match recorded readings, and the tool
descriptions the model reads, such as `DEFAULT_SUBAGENT_DESCRIPTION`, where a change needs a model
measurement ([R-707](707-model-read-texts-keep-banned-words.md) lists them). The overlay's Vitest
titles are strings too, and thirteen of them use the `carry`, `gate`, `seam` and `arm` words.

**What would close it.** Each family renamed as a code change, with the runbook, module doc and
task files that quote a name changed in the same commit, or a decision in ADR-0040 that a family
stays, with the reason.

## History

- 2026-09-21: opened by the close of [R-699](699-source-file-names-use-banned-words.md), which
  renamed the files and left the names inside them.
- 2026-09-23: the small families renamed: `land`, `pin`, `standing`, `knob`, `honest`, `robust`,
  `backstop`, `rederive`, `sitting`, `spell` and `earn`, with the Vitest titles that used them.
  `volumecheck.py --rederive` is now `--recompute`. Then `verdict`, whose `Verdict` classes became
  `Outcome` in the injection probes, `Jobs` in `ci_paths.py`, `CheckResult` in `rustcoverage.py`
  and `Finding` in `samplecheck.py`.
