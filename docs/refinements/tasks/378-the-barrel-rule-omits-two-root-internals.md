# The barrel rule and the module contract describe two different surfaces

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** something outside `cortex_orchestrator` needs one of the composition root's own
types, or a reader follows the module contract's own rule and cannot import a name it documents.

`docs/modules/brain-orchestrator.md` opens its public contract with "everything importable from
`cortex_orchestrator`; `__all__` is the API", and then documents three names that the barrel does
not export: `stores.RedisStores`, and now `engines.StreamEngines` and `engines.DeepTier`. All
three are composition-root internals with exactly one production caller, `wiring.run_from_env`,
which reaches them by module path, and the tests that touch them import the submodule the same
way. Nothing is broken and nothing is unreachable.

What is wrong is that the rule as written is a promise the doc itself does not keep, so a reader
cannot tell whether an omission is a decision or an oversight. There are two honest endings and
they point in opposite directions. Exporting the three costs six lines in `__init__.py` and makes
the rule true, at the price of widening a package's public surface with types nothing outside it
constructs. Narrowing the rule instead ("everything importable from `cortex_orchestrator`, plus
the composition root's own types, which live at their module path because nothing outside the root
builds one") costs a sentence and keeps the surface honest about what it is for.

The second reads better as design and is the weaker claim to verify, since it changes no code. It
should not be picked without checking the other package contracts for the same rule: whichever
ending is taken, it wants to be the same ending everywhere the sentence appears.

## Trail

- 2026-08-22: Opened by the close of
  [368](368-the-composition-root-has-no-headroom.md), which added the second and third name the
  rule omits. Recorded in the ADR-0009 root-headroom addendum.
