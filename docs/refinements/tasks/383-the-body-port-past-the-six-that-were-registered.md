# The body port is spelled in twelve more files and only six of them are held

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Opened 2026-08-22 by the close of [R-356](356-the-body-port-is-a-bare-literal.md), which promoted
the body's bind port to `DEFAULT_BODY_PORT` and tied it to six places: the body override's endpoint
default, three runbook sentences, and the brain's live gateway fallback. That entry recorded six
files as spelling the number. Eighteen do, outside the backlog itself.

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
tie a fixture value to a deployment default and would fail on a change that broke nothing.

**What would close it.** Sort the twelve by the tense test the compose survey settled, a sentence
that becomes wrong being a far side and one that becomes history not being one, and register the
ones that state. The header comments are the same shape the body override's other comment already
holds, so those are rows rather than decisions. The host tasks are the judgement call: they read as
live prerequisites while the sitting is open and as a record of what was run once it is done, and
whichever way that goes it is the reading this task must leave written down. The entry worth
reading first is [382](382-the-paired-numbers-quoted-in-prose.md), which asks the same question
about a different value.

## Trail

- 2026-08-22: opened by the close of [R-356](356-the-body-port-is-a-bare-literal.md), whose own
  count of the files spelling the port was an enumeration rather than a survey, which is what
  turned a finished registration into a sorting task.
- 2026-08-23: landed. The file count held up and two smaller ones in this file did not: ADR-0023
  spells the port seven times rather than four, and counting files hid eight spellings inside files
  that already carried a row, `docs/runbooks/body-volume.md` alone spelling it six times against
  one. Counted off the tree, the port is written 33 times in 17 files outside the decision records
  and the backlog. The entry went from five far sides to twenty three, and every place outside the
  decision records, the backlog and the three wiring tests is now held. Four needle shapes carry
  the sort so that none pins a word of the sentence around the number: `default 127.0.0.1:` for a
  stated bind, `CORTEX_BODY_ADDR=0.0.0.0:` for the export the container path needs,
  `host.docker.internal:` for the endpoint the brain dials, and the declaring module's own two doc
  comments. The shapes do the excluding: the volume runbook's record of a fake server once served
  on that address writes the address alone, so no needle reaches it, which is right for a dated
  reading. The three wiring tests stay out for the reason this file gives, and the contrast that
  makes the rule usable arrived the same day: a test constant is a far side when the test is wrong
  without it and a fixture when the test is merely specific. **The judgement call is settled in:**
  a host file is a live instruction and not a record, because its prerequisites open "Sittings die
  on setup", a completed check's file shrinks to a heading, its status and a pointer, and a stale
  port there costs a sitting on hardware nobody here has. Eighteen planted drifts each made the
  gate fail and four controls each left it green. Recorded in the ADR-0023 port-prose addendum, in
  `body/app/src-tauri/src/body_server.rs` and
  [modules/body-app.md](../../modules/body-app.md), whose accounts of what is tied were stale, and
  in [modules/repo-gates.md](../../modules/repo-gates.md). One narrower entry opens in its place,
  the brain's own port being held in code and in no prose at all
  ([389](389-the-brain-port-is-held-in-code-and-not-in-prose.md)).
