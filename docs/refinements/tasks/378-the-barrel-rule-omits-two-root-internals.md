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

The problem is that the rule as written states something the document itself does not hold to, so
a reader cannot tell whether an omission is a decision or an oversight. Two fixes would each make
the document consistent, and they point in opposite directions. Exporting the three costs six
lines in `__init__.py` and makes the rule true, at the price of widening a package's public
surface with types nothing outside it constructs. Narrowing the rule instead ("everything
importable from `cortex_orchestrator`, plus the composition root's own types, which live at their
module path because nothing outside the root builds one") costs a sentence and keeps the
description accurate about what the surface is for.

The second is the better design and the weaker claim to verify, since it changes no code. It
should not be picked without checking the other package contracts for the same rule: whichever fix
is taken should be taken everywhere the sentence appears.

## Trail

- 2026-08-22: Opened by the close of
  [368](368-the-composition-root-has-no-headroom.md), which added the second and third name the
  rule omits. Recorded in the ADR-0009 root-headroom addendum.
