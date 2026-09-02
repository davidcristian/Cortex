# The source declaration key is spelled in two trees and no gate holds them equal

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-02 by the close of [319](319-a-refusal-taints-the-turn.md), whose design restates
a sidecar's text brain-side under a `crosscheck.py` coupling and cited the source declaration key
as the precedent. Reading the registry found the precedent half there. `_SOURCE_META_KEY =
"cortex/source"` is declared in `brain/packages/tools/src/cortex_tools/registry.py` and again in
`brain/packages/email/src/cortex_email/server.py`, each with a comment calling it a wire contract
between the two trees because the sidecar cannot import the core, and no `Constant` in any part of
the registry names either site. A rename on one side would leave the brain reading a key the
sidecar no longer writes, every `read_email` would arrive without its sender, and nothing would
fail: `_declared_source` returns `None` for an absent key by design, `TaintLedger.note_source`
records nothing for `None`, and no consumer of the claimed `SENDER` kind exists yet to notice.

**What would close it.** One `Constant` in `emailcouplings.py` (the part that already holds the
sidecar's shipped answers) or `seamcouplings.py` (the part for the other tree's code), with the
registry module's binding as the site and the server module's as a second site or a mention,
whichever the reducer reads a string binding as. Then the mutation: rename one side and watch
`check-crosscheck` fail naming both files.

## Trail

- 2026-09-02: opened by the close of [319](319-a-refusal-taints-the-turn.md), whose addendum
  cites this key as the restatement pattern the own-text build follows and found it unheld.
