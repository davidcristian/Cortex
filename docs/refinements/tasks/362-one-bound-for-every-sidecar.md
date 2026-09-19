# One bound covers every sidecar, so a file read and a mailbox search share a ceiling

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
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
so per-endpoint numbers compose without touching `AggregateToolRegistry` at all. What does change
is the boot check that orders the call bound under the delegated run bound,
`check_tool_call_deadline` in `brain/packages/orchestrator/src/cortex_orchestrator/bounds.py`.
It already prices the walks an aggregate makes, where one `describe_tools` asks every endpoint in
turn: `delegated_call_bounds` counts how many whole bounds a delegated dispatch can spend (three
with one sidecar, seven with two), and `_dispatch_cost` multiplies that count by the one flat
number. With a number per endpoint the count stops being a multiple of anything. The cost becomes
seconds: each walk the sum of every endpoint's bound, plus the largest single bound for the call,
since which endpoint a call will reach is not known at boot. The refusal text and the fields
`_pairing` logs (`call_timeout_s`, `call_bounds_per_dispatch`) name the flat number and would be
rewritten with it, and the two cases in `brain/packages/orchestrator/tests/test_bounds.py` that
hold the shipped pair (ADR-0009 shipped-pair addendum) are where the new arithmetic would be held.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which gave the tool seam its first bound of
  any kind. Recorded in the ADR-0009 bound addendum.
- 2026-09-07: trigger re-derived against the tree and it has not fired. The stack still composes
  exactly two tool sidecars, `CORTEX_TOOLS_ENDPOINTS__FILESYSTEM` in
  `docker/docker-compose.tools.yml` and `CORTEX_TOOLS_ENDPOINTS__EMAIL` in
  `docker/docker-compose.email.yml`, with no third endpoint key anywhere in `docker/`.
  `CORTEX_TOOLS_CALL_TIMEOUT_S` is still one flat number, defaulted to 60.0 in
  `docker/docker-compose.yml` and held as a single `call_timeout_s` field on the tools config, so
  no per-endpoint form of the variable is read. Nothing in the tree records a real call the bound
  cut, and the email sidecar is still untimed: every per-call number in
  [docs/runbooks/tools-mcp.md](../../runbooks/tools-mcp.md) is the filesystem sidecar's. The clause
  is left as written, because both halves name something that can come out false. Recorded in the
  ADR-0009 addendum of this date.
- 2026-09-13: re-derived and left open. The trigger has not fired. `docker/` still spells exactly
  two endpoint keys, `CORTEX_TOOLS_ENDPOINTS__FILESYSTEM` in `docker/docker-compose.tools.yml` and
  `CORTEX_TOOLS_ENDPOINTS__EMAIL` in `docker/docker-compose.email.yml`.
  `CORTEX_TOOLS_CALL_TIMEOUT_S` is still one flat number, defaulted to 60.0 in
  `docker/docker-compose.yml`, read as the single `call_timeout_s` field of the tools config and
  spent by the one `BoundedToolRegistry` that `builders.py` wraps around the dialed endpoint. No
  per-endpoint form of the variable is read anywhere, while the shape the entry points at is still
  in use beside it: `CORTEX_TOOLS_ALLOW__FILESYSTEM` restricts one sidecar by name. The email
  sidecar is still untimed.
- 2026-09-19: re-derived and left open, with the paragraph on building it repaired. The trigger has
  not fired: `docker/` still spells two endpoint keys, `CORTEX_TOOLS_CALL_TIMEOUT_S` is still
  defaulted to 60.0 in `docker/docker-compose.yml` and read as the one `call_timeout_s` field, no
  per-endpoint form is read, no line in the tree records a call the bound cut, and the email
  sidecar is still untimed. The body's picture of `builders.py` holds, and is more exact than the
  bullet above: the loop wraps each endpoint in its own `BoundedToolRegistry`, every one of them
  given the same number. What the entry missed is that a consumer of the flat number has existed
  since the day it was filed. The boot check that orders it under the delegated run bound landed
  the same day and multiplies it by a walk count derived from the sidecar count, so the sum a
  listing costs across an aggregate, which the entry left as a thought for the builder, is already
  computed there for one number and is what a per-endpoint bound would have to rewrite. Recorded in
  the ADR-0009 shipped-pair addendum.
