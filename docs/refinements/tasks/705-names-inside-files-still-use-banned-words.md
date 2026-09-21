# Names inside the files still use words the prose table bans

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-21

[R-699](699-source-file-names-use-banned-words.md) renamed the source files named after a word the
table in AGENTS.md bans. The names inside those files, and some names no check reads, still use
the same words:

- Identifiers in the renamed modules: `TRACE_LEVER_PROBE_TIMEOUT_S` in `trace_probe.py`,
  `TierHealer`, its `heal` argument and `DEFAULT_TIER_HEAL_INTERVAL_S` in `residency_recheck.py`,
  `sweep_tiers` in `residency_pass.py`, `COLON_SPELLING`, `SOLIDUS_SPELLING` and `DOT_SPELLING` in
  `url_separators.py`, `rideTail` in `logRoll.ts` and `rideAlong` in `panelRoll.ts`. The panel's
  `pinnedBottom` in `panelEdge.ts` uses the word that
  [R-701](701-keeping-a-chat-at-the-top-has-no-designed-name.md) asks a designed name for.
- The brain's log line `trace lever probe answered` with its `lever=` field, which
  `docs/runbooks/llamacpp-gpu.md` shows an operator, and the environment variable
  `CORTEX_SWAP_TIER_HEAL_S`, which a deployment sets.
- Test names in `scripts/tests/test_crosscheck.py` that end in
  `_needles_hold_over_the_files_they_name`.
- The `description` of `body/app/src-tauri/Cargo.toml` and of `body/crates/rpc/Cargo.toml`, prose
  that no check reads.
- 97 of the backlog's own task file names, whose titles were rewritten and whose slugs were not.

**What would close it.** A decision on where the table stops: at prose, at file names, or at every
name a reader meets. Each group above is a separate rename with its own cost. The log words and
the variable change what an operator types, so they move with their runbooks, and the task slugs
move with every link to them. A decision that some groups stay, with the reason, closes it too.

## History

- 2026-09-21: opened by the close of [R-699](699-source-file-names-use-banned-words.md), which
  renamed the files and left the names inside them.
