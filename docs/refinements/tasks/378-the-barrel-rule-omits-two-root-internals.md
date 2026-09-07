# The barrel rule and the module contract describe two different surfaces

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** something outside `cortex_orchestrator` imports one of the composition root's own
types. That is countable by searching the tree for an import of `cortex_orchestrator.stores`,
`cortex_orchestrator.engines`, `cortex_orchestrator.preference_servicer` or
`cortex_orchestrator.session_servicer` from a file outside that package: the trigger fires when one
is found.

`docs/modules/brain-orchestrator.md` opens its public contract with "everything importable from
`cortex_orchestrator`; `__all__` is the API", and then documents names that the barrel does not
export. Five of them are spelled at their module path: `stores.RedisStores`,
`engines.StreamEngines`, `engines.DeepTier`, `preference_servicer.PreferenceRpcMixin` and
`session_servicer.SessionRpcMixin`. All five are composition-root internals reached by module path
by one caller inside the package, `wiring.run_from_env` for the first three and `server.py` for the
two mixins, and the tests that touch them import the submodule the same way. Nothing is broken and
nothing is unreachable.

The problem is that the rule as written states something the document itself does not hold to, so
a reader cannot tell whether an omission is a decision or an oversight. Two fixes would each make
the document consistent, and they point in opposite directions. Exporting the five costs ten
lines in `__init__.py` and makes the rule true, at the price of widening a package's public
surface with types nothing outside it constructs. Narrowing the rule instead ("everything
importable from `cortex_orchestrator`, plus the composition root's own types, which live at their
module path because nothing outside the root builds one") costs a sentence and keeps the
description accurate about what the surface is for.

The second is the better design and the weaker claim to verify, since it changes no code. The
survey it was waiting on is done, and it says the narrowing belongs to this contract alone: the
same sentence opens nine other package contracts and none of them names a module-path internal its
barrel omits.

## Trail

- 2026-08-22: Opened by the close of
  [368](368-the-composition-root-has-no-headroom.md), which added the second and third name the
  rule omits. Recorded in the ADR-0009 root-headroom addendum.
- 2026-09-07: checked, narrowed and left open. The trigger has not fired. Every import of the four
  submodules is inside `cortex_orchestrator` or its own tests: `wiring.py` imports
  `stores.RedisStores` and `engines.DeepTier, StreamEngines`, `server.py` mixes in the two RPC
  mixins, and `tests/test_engines.py` reaches `engines` by module path. Nothing in the brain's other
  nine packages, in `scripts/`, or in the body names one.

  The second clause was dropped rather than checked. "A reader follows the module contract's own
  rule and cannot import a name it documents" describes the standing state this entry is about, so
  it was true the day the entry was filed and no state of the tree could make it false. What
  replaces it is the countable first clause alone.

  Two measurements were taken while checking. The rule omits five names spelled at a module path
  rather than three: reading `__all__` out of each package's `__init__.py` and matching every
  ``module.Name`` written in backticks in that package's contract adds
  `preference_servicer.PreferenceRpcMixin` and `session_servicer.SessionRpcMixin`, both documented
  in the same sentence as `RedisStores`. The body above now names all five. The same reading over
  the other nine contracts that open with this sentence returns nothing, so whichever fix is taken
  is taken here and nowhere else, which is the survey the entry said the choice was waiting on.
