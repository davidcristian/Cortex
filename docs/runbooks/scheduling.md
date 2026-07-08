# Runbook for Slice 9.5: scheduling & reminders

Slice 9.5 (ADR-0025) gives the brain a sense of time: durable schedules in Redis, three
cortex-only tools (`schedule_task` / `list_scheduled` / `cancel_scheduled`), the
`ScheduleTicker` firing what is due, and reminder delivery by pull over
`ListDueReminders`/`AckReminder`, push over `BodyService.Notify` when the body is wired.
The CI-gated half is green under `just check`; this runbook covers bring-up, the
agent-Docker validation, and the host-only half.

## Bring-up

Scheduling is **off by default** (`CORTEX_SCHEDULE_BACKEND=none`): no store, no built-ins,
no ticker, and the pull RPCs answer benignly empty. Enable it on the compose stack (the
base file passes the variable through):

```
CORTEX_SCHEDULE_BACKEND=redis docker compose --project-directory . \
  -f docker/docker-compose.yml up -d --build
```

Schedules live in the same append-only, named-volume Redis as sessions. That is the durability
class the one hard rule already trusts. Knobs (all `CORTEX_SCHEDULE_*`): `POLL_S` (pass
interval, default 5), `LEASE_S` (default 300, to be **kept above the slowest expected task
fire**: a task outrunning its lease is re-claimed and runs twice, the documented
at-least-once trade), `CLAIM_LIMIT` (batch cap per pass, default 8), `MAX_ACTIVE`
(the `schedule_task` creation bound, default 32).

With subagents wired (`CORTEX_SUBAGENTS_BACKEND=llamacpp`) the tool also offers
`kind: "task"`, which is an autonomous subagent run per fire, dispatched through the ticker's own
audited `spawn_subagents` path (`confirmer=None`, so gated tools stay structurally
unreachable; a tainted-created task is refused at creation outright). With the body wired
(`CORTEX_BODY_BACKEND=grpc`) fired reminders also attempt a native-toast push; until the
body's `Notify` trait lands its server answers `Unimplemented`, which the brain treats as
any push failure. The pull path delivers.

**Turning the backend off strands stored deliverables** until re-enabled (the records
persist; nothing lists or fires them).

## Agent half validated 2026-07-08 (ADR-0025 addendum)

Both live checks run against the real containers (no GPU needed):

```
cd brain && uv run pytest -m integration --no-cov \
  packages/session/tests/test_schedule_live.py \
  packages/orchestrator/tests/test_schedule_live_seam.py
```

- `test_schedule_live.py` replays the full fenced-protocol contract suite against live
  Redis (it **skips if real schedules exist**, because the checks assert exact global views and
  claim whatever is due, and refuse to disturb a live deployment's items).
- `test_schedule_live_seam.py` proves the loop end to end: it seeds a due reminder into
  the store, waits for the brain's ticker to fire it, reads it back over
  `ListDueReminders`, acks it over `AckReminder` (second ack: a no-op), and cleans up.
- `just seam-health` confirms the rewired turn path still converses.

## Host-only half on Windows

- **The native toast** (the push half): the body-side `Notify` OS trait + the Tauri-shell
  implementation. Render `title`/`body` as **inert escaped text**, since reminder text can be
  attacker-influenced (`tainted` marks it on the wire) and toast templates are XML.
- **The overlay reminder surface** (the pull half): fetch `ListDueReminders` on open,
  show deliverables (badge `tainted` ones), `AckReminder` on dismiss.

Both land behind the committed seam shapes; nothing brain-side changes.

## Troubleshooting

- **A reminder never fires:** is the backend on (`docker logs cortex-brain-1`, where the
  ticker logs pass failures)? Is the item still PENDING (`list_scheduled` in a chat, or
  `redis-cli zrange cortex:schedules:due 0 -1` on loopback)?
- **A fire repeats:** expected after a crash or a task outrunning `CORTEX_SCHEDULE_LEASE_S`
  (at-least-once by design; the fencing token keeps the duplicate's late finish from
  clobbering state). Raise the lease if tasks legitimately run long.
- **A corrupt record:** the claim path quarantines it to the `cortex:schedules:dead` hash
  (logged loudly) and the pass continues; inspect with `redis-cli hgetall
  cortex:schedules:dead`. Retention/inspection tooling is a recorded deferral.
