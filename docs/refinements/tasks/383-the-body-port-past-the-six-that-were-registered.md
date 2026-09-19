# The body port appears in twelve more files and only six of them are registered

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

[R-356](356-the-body-port-is-a-bare-literal.md) promoted the body's bind port to
`DEFAULT_BODY_PORT` and tied it to six places: the body override's endpoint default, three runbook
sentences, and the brain's live gateway fallback. It recorded six files as writing the number.
Eighteen do, outside the backlog.

The unregistered ones: [host/index.md](../../host/index.md) and the three host tasks under it
state it as an operator prerequisite; [modules/body-app.md](../../modules/body-app.md),
[modules/brain-body-client.md](../../modules/brain-body-client.md) and
[modules/brain-orchestrator.md](../../modules/brain-orchestrator.md) restate it;
`docker/docker-compose.body.yml` writes it three more times in comments; the gateway's docstring
writes `host:50151` as the shape of an endpoint. ADR-0023 writes it four times and is out by the
rule that an ADR records what was decided on a date.

Three more are not registrable and should be written down as such: `test_config.py`,
`test_vision_wiring.py` and `test_wiring.py` each set `CORTEX_BODY_ENDPOINT` to a string and check
that the composition root read it back. Any port would pass, so registering them would tie a
fixture value to a deployment default and fail on a change that broke nothing.

The work left was to sort the twelve by the same test, a sentence that becomes wrong being
registrable and one that becomes a record of the past not being one. The host tasks were the
judgement call, since they read as live prerequisites while the work is open and as a record once
it is done. [382](382-the-paired-numbers-quoted-in-prose.md) asks the same question about a
different value.

## History

- 2026-08-22: opened by the close of [R-356](356-the-body-port-is-a-bare-literal.md), whose own
  count of the files writing the port was a list rather than a survey.
- 2026-08-23: closed. The file count held and two smaller numbers here did not: ADR-0023 writes
  the port seven times rather than four, and counting files hid eight occurrences inside files
  that were already registered, `docs/runbooks/body-volume.md` alone writing it six times against
  one. Counted off the tree, the port appears 33 times in 17 files outside the decision records
  and the backlog. The entry went from five registered places to twenty three, and every place
  outside the decision records, the backlog and the three wiring tests is now covered. Four search
  texts encode the sorting without fixing a word of the sentence around the number: `default
  127.0.0.1:` for a stated bind, `CORTEX_BODY_ADDR=0.0.0.0:` for the export the container path
  needs, `host.docker.internal:` for the endpoint the brain dials, and the declaring module's own
  two doc comments. Those shapes do the excluding: the volume runbook's record of a fake server
  once serving on that address writes the address alone, so no search text reaches it, which is
  right for a dated reading. The three wiring tests stay out for the reason above, and the
  contrast that makes the rule usable arrived the same day: a test constant is registrable when
  the test is wrong without it and a fixture when the test is merely specific. The judgement call
  is settled as in: a host file is a live instruction and not a record, because its prerequisites
  open "A session fails on setup", a completed check's file shrinks to a heading, its status and a
  pointer, and a stale port there costs a session on hardware nobody here has. Eighteen planted
  changes each made the check fail and four controls each left it passing. The host-file ruling is
  ADR-0042 decision 11, recorded in `body/app/src-tauri/src/body_server.rs` and
  [modules/body-app.md](../../modules/body-app.md), whose accounts of what was tied were stale,
  and in [modules/repo-checks.md](../../modules/repo-checks.md). One narrower entry opens in its
  place, the brain's own port being registered in code and in no prose at all
  ([389](389-the-brain-port-is-held-in-code-and-not-in-prose.md)).
