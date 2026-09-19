# The source declaration key is written in two trees and no check compares them

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`_SOURCE_META_KEY = "cortex/source"` is declared in
`brain/packages/tools/src/cortex_tools/registry.py` and again in
`brain/packages/email/src/cortex_email/server.py`, each with a comment calling it a wire contract
between the two trees because the sidecar cannot import the core, and no `Constant` in any part of
the registry named either site. A rename on one side would leave the brain reading a key the sidecar
no longer writes, every `read_email` would arrive without its sender, and nothing would fail:
`_declared_source` returns `None` for an absent key by design, `TaintLedger.note_source` records
nothing for `None`, and no consumer of the claimed `SENDER` kind exists yet.

## History

- 2026-09-02: opened by the close of [319](319-a-refusal-taints-the-turn.md), whose record cites
  this key as the restatement pattern the own-text build follows and found it unchecked.
- 2026-09-02: closed as one entry in `scripts/emailcouplings.py`, recorded in ADR-0042. Every claim
  above held. The two bindings are the sites, each module's one use of its own binding and the two
  module contracts that quote the key are the mentions, and the live check fails naming both files
  when either side is renamed. The kind word `sender` beside the key has no declaring site on either
  side and is filed as [534](534-the-declared-kind-word-has-no-site-to-hold-it.md).
