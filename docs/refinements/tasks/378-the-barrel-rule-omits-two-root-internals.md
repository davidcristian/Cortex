# The barrel rule and the module contract describe two different surfaces

**Status:** done 2026-09-07
**Area:** repo-checks
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`docs/modules/brain-orchestrator.md` opened its public contract with "everything importable from
`cortex_orchestrator`; `__all__` is the API", and then documented names the barrel does not export.
Five of them are written at their module path: `stores.RedisStores`, `engines.StreamEngines`,
`engines.DeepTier`, `preference_servicer.PreferenceRpcMixin` and
`session_servicer.SessionRpcMixin`. All five are composition-root internals reached by module path
by one caller inside the package, `wiring.run_from_env` for the first three and `server.py` for the
two mixins. Nothing is broken and nothing is unreachable.

The problem is that the rule as written states something the document does not hold to, so a reader
cannot tell whether an omission is a decision or an oversight. Two fixes each make the document
consistent and point in opposite directions. Exporting the five costs ten lines in `__init__.py`
and makes the rule true, at the price of widening a package's public surface with types nothing
outside it constructs. Narrowing the rule instead costs a sentence and keeps the description
accurate about what the surface is for.

## History

- 2026-08-22: Opened by the close of [368](368-the-composition-root-has-no-headroom.md), which
  added the second and third name the rule omits.
- 2026-09-07: Checked, narrowed and left open. Every import of the four submodules is inside
  `cortex_orchestrator` or its own tests: `wiring.py` imports `stores.RedisStores` and
  `engines.DeepTier, StreamEngines`, `server.py` mixes in the two RPC mixins, and
  `tests/test_engines.py` reaches `engines` by module path. Nothing in the brain's other nine
  packages, in `scripts/`, or in the body names one. The trigger's second clause was dropped rather
  than checked, since it described the state this entry is about and no state of the tree could
  make it false. Two measurements were taken: the rule omits five names written at a module path
  rather than three, reading `__all__` out of each package's `__init__.py` and matching every
  ``module.Name`` written in backticks in that package's contract; and the same reading over the
  other nine contracts that open with this sentence returns nothing, so whichever fix is taken is
  taken here and nowhere else.
- 2026-09-07: Done by narrowing the rule, the fix this entry argued for. The public contract of
  `docs/modules/brain-orchestrator.md` now says "everything importable from `cortex_orchestrator`;
  `__all__` is the API, plus the composition root's own types, which stay at their module path
  because nothing outside the root builds one", and names all five. No code moved and the barrel is
  unchanged, so the surface a caller has is what it was; what changed is that the document now
  describes it.
