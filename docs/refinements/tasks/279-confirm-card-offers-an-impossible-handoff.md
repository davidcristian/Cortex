# The confirm card offers a handoff the machine cannot run

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a user asking why they were asked to approve a deep task that then did not happen, or
a deployment configuring escalation without a deep artifact for long enough that the card becomes a
nuisance. Both happen outside this repo. What the tree can answer is whether any stack it ships can
reach the state: that needs `CORTEX_ESCALATION` set while `CORTEX_MODEL_FILE_BRAIN` keeps its empty
default (`docker/docker-compose.gpu.yml:71`). The gpu overlay passes the switch through by name,
so a host `.env` can reach the state, and `grep -rnE 'CORTEX_ESCALATION: *[^ ]' docker/` finding
nothing says no shipped file does.
**Verified:** 2026-09-24

Opened 2026-08-16 by the close that refuses an impossible handoff before the drain
([R-203](203-escalation-fault-not-remembered.md)), which moved the refusal from after the stall to
before it and left one surface still misstating it: the ADR-0022 confirm card.

On a deployment whose model host has no deep tier, the cortex still advertises `escalate_to_brain`,
still calls it, and the user is still shown a card saying the deep model will take over and the
machine will be busy for a while. They approve it, and the conductor then refuses it with an
accurate note. Nothing is unloaded and nothing is lost, so what remains is a question asked under a
false premise.

The advertisement is decided in three places. The built-in set containing `escalate_to_brain` is
assembled once at boot (`build_builtin_tools`, on `escalation=swap is not None`), the dispatcher
over it is built once per Converse stream (`build_cortex_tools` in `StreamEngines.for_stream`, and
a stream covers many turns), and the advertisement itself is rebuilt once per turn by the tool
loop's one `describe_tools` walk. The confirmation reason is static config either way
(`DispatchPolicy.confirm_reasons`, merged from `ESCALATE_CONFIRM_REASON`). So a fix sits on
`describe_tools`, once per turn.

The cost this was declined on is one the tree already pays elsewhere. `SightedToolRegistry` asks a
`VisionProbe` on every advertisement and every call, uncached, for the same kind of fact: a
capability of a process the brain does not own and that can be replaced under it. That reading is
one loopback `GET /props`, measured at 1.5 ms idle. Which route answers matters: `unhosted` asks
`status`, which takes the supervisor's per-model lock and was measured at up to 5.80 s queued
behind a stop, while `GET /health` already returns the roster and takes no per-model lock. The port
has no method that reads it.

What still argues for the card as it stands is visibility. A tool that is quietly absent produces
no user-facing sentence, so a user never asks why the handoff did not happen and never learns the
deployment is misconfigured. That is narrower than it sounds: the operator is already told once per
boot, at error level, by `swap_recovery._clear_deep`, which names both `CORTEX_MODEL_FILE_BRAIN`
and `CORTEX_ESCALATION`. What dropping the advertisement would cost is the conductor's per-attempt
line and the sentence the user reads.

There are three shapes rather than two. The periodic tier poll could cover the deep tier for
advertisement only, which reopens what that record is for; the wrapper could cache the conductor's
own answer for the turn that follows it, which has the invalidation problem that close argued its
way out of; or a restrict-only registry combinator could drop the spec while a fresh reading says
the tier is absent, which is what `sighted.py` already does for the screen and which needs neither
a cache nor a record. The third is what the tree's own precedent points at, and what it leaves open
is the visibility trade rather than the cost.

## History

- 2026-09-10: Checked against the tree and not triggered. The advertisement is still config alone:
  `build_builtin_tools` appends `EscalateToBrainTool()` on an `escalation` flag the composition
  root sets from `CORTEX_ESCALATION`, nothing there asks the model host which tiers it has, and
  `config_tools.confirm_reason_map` still merges one static `ESCALATE_CONFIRM_REASON`. No compose file
  here sets `CORTEX_ESCALATION`; `docker/docker-compose.gpu.yml` has it only as a comment telling
  an operator what to add, and says in the same block that a tier with no artifact file answers 404
  rather than starting a doomed process.
- 2026-09-12: Checked again, still not triggered, and the reason this waits was wrong. The tool
  spec is not rebuilt per turn: `build_builtin_tools` runs once at boot in `wiring.py`,
  `build_cortex_tools` runs once per Converse stream, and a stream covers many turns. What is per
  turn is the tool loop's single `describe_tools` walk, which is the same surface
  `SightedToolRegistry` already reads a live answer on for `capture_screen`, uncached, at a
  measured 1.5 ms per `GET /props`. That precedent was built on 2026-08-06, ten days before
  ADR-0030 rejected this option on the cost of a per-turn control call, and the rejection did not
  cite it. Also read: `GET /health` already returns the roster and takes no per-model lock.
- 2026-09-17: Checked again, still not triggered. No commit since touched the sites named above.
  `build_builtin_tools` still appends `EscalateToBrainTool()` on the escalation flag
  (`dispatch_builders.py:73`) and is still called once for the cortex and once for the deep phase
  at boot (`wiring.py:154` and `:168`); `StreamEngines.for_stream` still builds the dispatcher per
  stream (`engines.py:116`); `confirm_reason_map` still merges the static `ESCALATE_CONFIRM_REASON`
  (`config_tools.py:172`). The route claim holds: the model host's `GET /health` handler takes no
  per-model lock (`api.py:67`), while `ModelSupervisor.status` takes one (`supervisor.py:187`). The
  trigger gained the in-tree precondition and the command that reports it. That command is enough
  because no compose file here has an `env_file` key, so a `.env` alone cannot put
  `CORTEX_ESCALATION` into the brain container: an operator has to edit a compose file or add an
  override.
- 2026-09-24: Not triggered. The grep finds nothing, and the trigger's line citation is corrected
  to where `CORTEX_MODEL_FILE_BRAIN` is now. The gpu overlay passes `CORTEX_ESCALATION` to the brain
  as a bare key, so the point above about `env_file` no longer decides it: a value set on the host
  reaches the container. The advertisement is still decided at the same sites, now
  `dispatch_builders.py:68`, `wiring.py:96` and `:103`, `engines.py:61` and `config_tools.py:93`.
  The card is shown only on an untainted turn, since `dispatch.py` denies a tainted turn's
  escalation without asking.
