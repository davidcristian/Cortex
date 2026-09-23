# Names inside the files still use words the prose table bans

**Status:** done 2026-09-23
**Area:** cross-cutting
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)

Decision 15 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) says the banned-word
table reaches every name a reader meets in hand-written code and stops at names fixed outside it.
A survey splits every identifier in the tracked `.py`, `.rs`, `.ts` and `.tsx` files on `_` and on
case changes and matches the parts against the table's single words. It reads Python names with
`tokenize` and blanks the comments and strings of Rust and TypeScript first, and it leaves out
generated code. On 2026-09-23 it finds 124 distinct names in one family, `gate`, `gates`,
`gated` and `ungated`. They are the tool confirmation list (`GatedToolRegistry`,
`UngatedToolRegistry`, `GatedBackend`), `ReadinessGate` in the residency code, and the word the
checks under `scripts/` use for themselves (`GATES`, `FLAG_GATE`). The variables
`CORTEX_TOOLS_GATED` and `CORTEX_TOOLS_GATE_REASONS` stay.

The names that stay, and why, are listed in decision 15 of
[ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md).

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
  and `Finding` in `samplecheck.py`. The same words in the `replay` recipe's output opened
  [R-714](714-the-text-a-recipe-prints-is-outside-the-prose-check.md). Then `seam`, which became
  `rpc` for the body to brain gRPC boundary (`BrainRpcClient`, `RpcServerConfig`, the
  `rpc-health` recipe) and `boundary` in one crosscheck test. Then `arm`, 52 names: a condition of
  a measurement or a contract test became a `variant` (`SHIPPED_VARIANT`, `_VARIANTS`, the
  `turn-cost` recipe's `variant`), the escalation slot a `prepared_slot`, and every other use says
  the step it stood for, such as `set_to_fail` and `reschedules`. The samples' `arm` key,
  `CORTEX_ENVELOPE_ARMS` and `CORTEX_TURN_COST_ARM` stay. Then `carry`, 166 names: each test
  name now says what its test checks (`contains`, `has`, `keeps`, `passes`, `includes`), a
  guardrail test says a link split across chunks `is_held_not_lost`, `DroppedCandidates.carried`
  became `listed`, and the eight Vitest titles that used the word changed with them. Then
  `gate`, 124 names, which closed the task. A tool the user must approve is `confirm_required`
  (`ConfirmRequiredToolRegistry`, `ConfirmFreeToolRegistry`, `DispatchPolicy.confirm_names`),
  and the tools settings fields are `confirm_names` and `confirm_reasons`, which read
  `CORTEX_TOOLS_GATED` and `CORTEX_TOOLS_GATE_REASONS` as aliases. `ReadinessGate` became
  `ReadinessCheck`, the swap tests' `Gate` a `PausePoint`, and `scripts/` says `check` or
  `scripts` (`FLAG_CHECK`, `SCRIPTS`). The survey now finds only the names decision 15 keeps.
