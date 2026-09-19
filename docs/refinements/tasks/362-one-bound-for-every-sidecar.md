# One bound covers every sidecar, so a file read and a mailbox search share a limit

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
**Trigger:** A legitimate call on one sidecar that a bound sized for another cuts, or a deployment
that wants a tight bound on the fast sidecar without loosening the slow one. Neither has happened:
the only two sidecars this repo ships are a filesystem server measured at 154 ms a call and an
email server nobody has timed.

`CORTEX_TOOLS_CALL_TIMEOUT_S` is one number, used by the `BoundedToolRegistry` wrapped around every
configured endpoint alike. The endpoints are already per-sidecar in every other respect: each
contributes its own `CORTEX_TOOLS_ENDPOINTS__<name>` key so layered compose overrides can coexist,
and `CORTEX_TOOLS_ALLOW__<name>` already restricts one of them by name. So the form a per-endpoint
bound would take is there, `CORTEX_TOOLS_CALL_TIMEOUT_S__<name>`, merged under the flat default the
way `costs` and `gate_reasons` merge their built-ins under the user's.

It was not built with the bound because one number is the defensible starting point when one of the
two sidecars has never been measured. A per-endpoint setting shipped today would offer an operator
a choice between a guess and a different guess, and the flat 60 s is already some four hundred
times the only call this repo has timed.

If it is built, note the effect on the boot check that orders the call bound under the delegated
run bound, `check_tool_call_deadline` in
`brain/packages/orchestrator/src/cortex_orchestrator/bounds.py`. It prices the walks an aggregate
makes, where one `describe_tools` asks every endpoint in turn: `delegated_call_bounds` counts how
many whole bounds a delegated dispatch can use (three with one sidecar, seven with two), and
`_dispatch_cost` multiplies that count by the one flat number. With a number per endpoint the count
stops being a multiple of anything: the cost becomes each walk the sum of every endpoint's bound,
plus the largest single bound for the call, since which endpoint a call will reach is not known at
boot. The refusal text and the fields `_pairing` logs (`call_timeout_s`,
`call_bounds_per_dispatch`) name the flat number and would be rewritten with it.

## History

- 2026-08-21: Filed by the close of [341](341-nothing-declines-work-it-cannot-finish.md), which
  gave the tool interface its first bound of any kind. Recorded in ADR-0009 decision 10.
- 2026-09-07: Trigger checked against the tree and it has not fired. The stack still composes
  exactly two tool sidecars, `CORTEX_TOOLS_ENDPOINTS__FILESYSTEM` in
  `docker/docker-compose.tools.yml` and `CORTEX_TOOLS_ENDPOINTS__EMAIL` in
  `docker/docker-compose.email.yml`, with no third endpoint key anywhere in `docker/`.
  `CORTEX_TOOLS_CALL_TIMEOUT_S` is still one flat number, defaulted to 60.0 in
  `docker/docker-compose.yml` and read as a single `call_timeout_s` field. Nothing in the tree
  records a real call the bound cut, and the email sidecar is still untimed: every per-call number
  in [docs/runbooks/tools-mcp.md](../../runbooks/tools-mcp.md) is the filesystem sidecar's.
- 2026-09-13: Checked again and left open. `docker/` still has exactly two endpoint keys,
  `CORTEX_TOOLS_CALL_TIMEOUT_S` is still one flat number defaulted to 60.0 and used by the one
  `BoundedToolRegistry` that `builders.py` wraps around the endpoint, and no per-endpoint form of
  the variable is read anywhere, while `CORTEX_TOOLS_ALLOW__FILESYSTEM` restricts one sidecar by
  name beside it. The email sidecar is still untimed.
- 2026-09-19: Checked again and left open, with the paragraph on building it repaired. The trigger
  has not fired: two endpoint keys, the flat 60.0 default, no per-endpoint form read, no line in
  the tree recording a call the bound cut, and the email sidecar still untimed. The description of
  `builders.py` is more exact than the entry above: the loop wraps each endpoint in its own
  `BoundedToolRegistry`, every one given the same number. What the entry missed is that a consumer
  of the flat number has existed since the day it was filed: the boot check that orders it under
  the delegated run bound arrived the same day and multiplies it by a walk count derived from the
  sidecar count, so the sum a listing costs across an aggregate is already computed there for one
  number and is what a per-endpoint bound would have to rewrite (ADR-0047 decision 3).
