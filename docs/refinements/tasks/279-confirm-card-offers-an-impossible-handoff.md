# The confirm card offers a handoff the machine cannot run

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a user asking why they were asked to approve a deep task that then did not happen, or a deployment configuring escalation without a deep artifact for long enough that the card becomes a nuisance.
**Verified:** 2026-09-12

Opened 2026-08-16 by the close that refuses an impossible handoff before the drain
([R-203](203-escalation-fault-not-remembered.md)), which moved the refusal from after the stall to
before it and left one surface still misstating it: the ADR-0022 confirm card.

On a deployment whose model host carries no deep tier, the cortex still advertises
`escalate_to_brain`, still calls it, and the user is still shown a card saying the deep model will
take over and the machine will be busy for a while. They approve it, and the conductor then
rejects it with the accurate note. Nothing is unloaded and nothing is lost, so what remains is a
question asked under a false premise.

**Where the advertisement is decided, and where a truthful one would have to be read.** The
built-in set carrying `escalate_to_brain` is assembled once at boot (`build_builtin_tools`, on
`escalation=swap is not None`), the dispatcher over it is built once per Converse stream
(`build_cortex_tools` in `StreamEngines.for_stream`, and a stream carries many turns), and the
advertisement itself is re-derived once per turn, by the tool loop's one `describe_tools` walk. The
gate's reason is static config either way (`DispatchPolicy.gate_reasons`, merged from
`ESCALATE_GATE_REASON`). So the surface a fix sits on is `describe_tools`, and it is per turn.

**The cost that argument rests on is one this tree already pays elsewhere.** `SightedToolRegistry`
asks a `VisionProbe` on every advertisement and every call, uncached, for the same shape of fact:
a capability of a process the brain does not own and that can be replaced under it. That reading
is one loopback `GET /props`, measured at 1.5 ms idle. Which route answers is what the cost turns
on, and the two available here are far apart: `unhosted` asks `status`, which takes the
supervisor's per-model lock and was measured at up to 5.80 s queued behind a stop, while
`GET /health` already carries the roster and takes no per-model lock at all. The port has no verb
that reads it.

**What still argues for the card as it stands is visibility, which this entry never stated.** A
tool that is quietly absent produces no user-facing sentence, so a user never asks why the handoff
did not happen and never learns the deployment is misconfigured. That is narrower than it sounds:
the operator is already told once per boot, at error, by `swap_recovery._clear_deep`, naming both
`CORTEX_MODEL_FILE_BRAIN` and `CORTEX_ESCALATION`. What non-advertisement would cost is the
conductor's per-attempt line and the sentence the user reads.

So there are three shapes rather than two. The sweep could grow the deep tier as a tier it observes
for advertisement only, which reopens the question the tier-sweep close settled about what that
record is for; the wrapper could cache the conductor's own answer for the turn that follows it,
which is a cache with the same invalidation problem that close argued its way out of; or a
restrict-only registry combinator could drop the spec while a fresh reading says the tier is
absent, which is what `sighted.py` already does for the screen and which needs neither a cache nor
a record. The third is the one the tree's own precedent points at, and what it leaves open is the
visibility trade above rather than the cost.

## Trail

- 2026-09-10: read against the tree and still not fired. The advertisement is still config alone:
  `build_builtin_tools` appends `EscalateToBrainTool()` on an `escalation` flag the composition
  root sets from `CORTEX_ESCALATION`, nothing there asks the model host which tiers it carries, and
  `config_tools.gate_reason_map` still merges one static `ESCALATE_GATE_REASON` into the card's
  reasons. So a deployment with escalation on and no deep artifact still advertises the tool, still
  shows the card, and still gets the conductor's refusal after the approval. Nothing has fired,
  because the handoff is off unless `CORTEX_ESCALATION` is set and no compose file here sets it;
  `docker/docker-compose.gpu.yml` carries the setting only as a comment telling an operator what to
  add, and it says in the same block that a tier with no artifact file answers 404 rather than
  spawning a doomed process.
- 2026-09-12: re-derived and still not fired, and the reason this waits was wrong. The tool spec is
  not rebuilt per turn: `build_builtin_tools` runs once at boot in `wiring.py`, `build_cortex_tools`
  runs once per Converse stream in `StreamEngines.for_stream`, and a stream carries many turns
  (`converse.py`: the stream stays open for the next `UserTurn`). What is per turn is the tool
  loop's single `describe_tools` walk, which is the surface a fix would sit on, and it is the same
  surface `SightedToolRegistry` already reads a live answer on for `capture_screen`, uncached, at a
  measured 1.5 ms per `GET /props`. That precedent landed on 2026-08-06, ten days before the origin
  addendum rejected this option on the cost of a per-turn control call, and the addendum does not
  cite it. Also read: `GET /health` already returns the roster and takes no per-model lock, so the
  reading need not be the `status` call `unhosted` makes, which was measured at up to 5.80 s queued
  behind a stop. The body now says all of this, names the third shape a fix could take, and states
  the objection that does survive, which is that a quietly absent tool produces no sentence a user
  can ask about, narrowed by the per-boot error line `swap_recovery._clear_deep` already writes.
