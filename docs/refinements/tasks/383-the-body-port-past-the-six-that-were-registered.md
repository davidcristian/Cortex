# The body port is spelled in twelve more files and only six of them are held

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-22 by the close of [R-356](356-the-body-port-is-a-bare-literal.md), which promoted
the body's bind port to `DEFAULT_BODY_PORT` and tied it to six places: the body override's endpoint
default, three runbook sentences, and the brain's live gateway fallback. That entry believed six
files spelled the number. Eighteen do, outside the backlog itself.

**Where it is still loose.** Four files carry it as an operator prerequisite,
[host/index.md](../../host/index.md) and the three host tasks under it. Three module contracts
restate it: [modules/body-app.md](../../modules/body-app.md) in the config list beside the
`body_server` entry that is now held, [modules/brain-body-client.md](../../modules/brain-body-client.md)
as the endpoint example on `GrpcBodyGateway.connect`, and
[modules/brain-orchestrator.md](../../modules/brain-orchestrator.md) in the `BodyConfig` field
description. `docker/docker-compose.body.yml` spells it twice more in its own header comment and
once in the inline comment above the substitution that is held. The gateway's docstring writes
`host:50151` as the shape of an endpoint. ADR-0023 spells it four times and is deliberately out,
by the standing rule that an ADR records what was decided on a date.

**Three of the eighteen are not far sides and should be recorded as such rather than skipped.**
`test_config.py`, `test_vision_wiring.py` and `test_wiring.py` each set `CORTEX_BODY_ENDPOINT` to a
string and assert the composition root read it back. Any port would pass. Registering them would
tie a fixture value to a deployment default and would redden on a change that broke nothing.

**What would close it.** Sort the twelve by the tense test the compose survey settled, a sentence
that becomes wrong being a far side and one that becomes history not being one, and register the
ones that state. The header comments are the same shape the body override's other comment already
holds, so those are rows rather than decisions. The host tasks are the judgement call: they read as
live prerequisites while the sitting is open and as a record of what was run once it is done, and
whichever way that goes it is the reading this task must leave written down. The neighbour worth
reading first is [382](382-the-paired-numbers-quoted-in-prose.md), which asks the same question
about a different value.

## Trail

- 2026-08-22: opened by the close of [R-356](356-the-body-port-is-a-bare-literal.md), whose own
  count of the files spelling the port was an enumeration rather than a survey, which is what
  turned a finished registration into a sorting task.
