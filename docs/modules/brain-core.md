# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types and application logic. Routing lives
here now; handoff orchestration, memory policy, and tool dispatch decisions join it in
later slices. No I/O, ever. This is the hexagon's center.

**Public contract** (everything importable from `cortex_core`; `__all__` is the API):

- `Tier` is an enum of model tiers: `CORTEX`, `SUBAGENT`, `BRAIN` (string values).
- `RoutingHints` is a frozen dataclass: `explicit_tier: Tier | None = None`,
  `needs_deep_reasoning: bool = False`, `is_narrow_delegable: bool = False`.
- `route_turn(hints: RoutingHints) -> Tier` is a pure decision with strict precedence:
  explicit override → deep reasoning (`BRAIN`) → narrow delegable (`SUBAGENT`) →
  default `CORTEX`.

**Invariants.**
- Pure and deterministic: no I/O, no adapter or framework imports, stdlib only.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/`.

**Dependencies.** Python stdlib only.
