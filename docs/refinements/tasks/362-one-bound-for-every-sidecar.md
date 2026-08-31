# One bound covers every sidecar, so a file read and a mailbox search share a ceiling

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** A legitimate call on one sidecar that a bound sized for another cuts, or a deployment
that wants a tight bound on the fast sidecar without loosening the slow one. Neither has happened:
the only two sidecars this repo ships are a filesystem server measured at 154 ms a call and an
email server nobody has timed.

`CORTEX_TOOLS_CALL_TIMEOUT_S` is one number, spent by the `BoundedToolRegistry` wrapped around
every configured endpoint alike. The endpoints are already per-sidecar in every other respect: each
contributes its own `CORTEX_TOOLS_ENDPOINTS__<name>` key so layered compose overrides coexist, and
`CORTEX_TOOLS_ALLOW__<name>` already restricts one of them by name. So the shape of a per-endpoint
bound is sitting there, `CORTEX_TOOLS_CALL_TIMEOUT_S__<name>`, merged under the flat default the
way `costs` and `gate_reasons` merge their built-ins under the user's.

It was not built with the bound because one number is the defensible starting point when one of the
two sidecars has never been measured. A per-endpoint knob shipped today would offer an operator a
choice between a guess and a different guess, and the flat 60 s is already some four hundred times
the only call this repo has timed. The knob is worth having when a real call is cut, and cutting a
real call is also what would produce the measurement to set the second number from.

Note the interaction with the aggregate if this is built: the bound sits innermost, per endpoint,
so per-endpoint numbers compose without touching `AggregateToolRegistry` at all. What does need
thought is `describe_tools` through an aggregate, where one walk asks every endpoint in turn, so
the worst case a listing can take is the sum of the endpoints' bounds rather than any one of them.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which gave the tool seam its first bound of
  any kind. Recorded in the ADR-0009 bound addendum.
