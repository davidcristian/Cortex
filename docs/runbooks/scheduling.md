# Runbook for Slice 9.5: scheduling & reminders

Slice 9.5 (ADR-0025) gives the brain a sense of time: durable schedules in Redis, five
cortex-only tools (`schedule_task` / `list_scheduled` / `cancel_scheduled` /
`snooze_scheduled` / `edit_scheduled`; `snooze_scheduled` postpones the next fire by
`for_seconds` from now, moving only the next occurrence of a recurring item and pinning its
grid so the series keeps its cadence per the occurrence-snooze addendum, and `edit_scheduled`
retexts / re-recurs an item in place without moving its next due time, per the edit
addendum), the `ScheduleTicker` firing what is due, and reminder delivery by pull over
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
(the `schedule_task` creation bound, default 32), `TZ` (the IANA zone model-facing times
render in, default `UTC`).

### Display timezone

`CORTEX_SCHEDULE_TZ` (an IANA key such as `Europe/Bucharest`, passed through by the base
compose file) sets the zone `schedule_task`, `list_scheduled`, and `snooze_scheduled` render
in, and the zone an `at` without an offset is read as. It is **display only**: stored due
times stay UTC instants, so changing the knob re-renders existing items and moves nothing.

```
CORTEX_SCHEDULE_BACKEND=redis CORTEX_SCHEDULE_TZ=Europe/Bucharest docker compose \
  --project-directory . -f docker/docker-compose.yml up -d --build
```

An unknown key **fails the brain at startup** (a `ValidationError` naming it), by design: a
silent fallback would render every time in the wrong zone. Check `docker compose logs brain`
for `unknown timezone` if the container will not come up after changing it. An `at` that
carries an explicit offset is always honored; a bare wall time reads as this zone, and the two
DST irregularities resolve with `fold=0` (an ambiguous hour takes the earlier offset, a
skipped one lands just past the gap).

### Recurrence: an interval, or a wall-clock rule

There are two shapes, and an item takes exactly one (ADR-0025 calendar addendum):

- `every_seconds` is a **fixed interval**, unchanged. It is the right shape for "every 90
  minutes"; across a DST transition it keeps its interval, so its wall-clock time shifts.
- `at_time` (`HH:MM`, in `CORTEX_SCHEDULE_TZ`) with an optional day selector is a **wall-clock
  rule**. It is the right shape for "every weekday at 09:00": it keeps the clock time across a
  DST transition, where a 86400-second interval would drift an hour. The first fire is computed
  from the rule, so `at_time` replaces `at`/`in_seconds` rather than accompanying them. The
  selector is at most one of:
  - `on_days` (`["mon","tue",...]`, omitted = every day), the weekly window.
  - `on_month_days` (`[1, 15]`, integers `1..31`), the monthly one (ADR-0025 monthly addendum).
    A day a short month lacks fires on that month's **last** day rather than skipping the month,
    so `[31]` is how to say "the last day of every month" and `[30, 31]` fires once in February.
  - `on_dates` (`["12-25", "01-01"]`, `MM-DD` strings with no year), the yearly one (ADR-0025
    yearly addendum). Use it for anniversaries and renewals: a 365-second-based interval drifts
    a day every leap year, which is exactly what the rule shape exists to avoid. `02-29` is
    accepted and fires on the 28th in a common year (the same clamp policy), while a date no
    year contains (`02-30`) and a full ISO date (`2026-12-25`, whose year would have to be
    silently dropped) are both refused with a correction.

  Giving more than one selector in a single call is refused: a rule holds exactly one.

  An optional `in_zone` (an IANA key such as `"America/New_York"`, ADR-0025 per-rule addendum)
  names the zone the `at_time` wall clock is in, for a reminder that should fire on another zone's
  clock ("09:00 New York time" while the deployment renders Bucharest). Omit it to use
  `CORTEX_SCHEDULE_TZ`. It is meaningful only with `at_time` (an interval has no wall clock to
  place), and an unknown key comes back as a correction. A per-zone item lists and confirms its
  due time in its own zone, so the shown wall time matches the rule.

A calendar occurrence that lands in a spring-forward gap fires just past the gap (late, never
skipped); one in a fall-back repeat fires once, on the earlier of the two readings, in whichever
zone governs the rule (its own `in_zone`, else `CORTEX_SCHEDULE_TZ`). Because a rule names a wall
time rather than an instant, **changing `CORTEX_SCHEDULE_TZ` moves existing calendar schedules
that did not name their own `in_zone`** to the new zone's 09:00, while a rule that pinned an
`in_zone`, and every interval and one-shot item (stored as UTC instants), only re-render. That is
deliberate: a zone-less 09:00 reminder follows its user, a pinned one stays put.

`edit_scheduled` changes recurrence in place in either direction: `at_time` (with an optional
`on_days`, `on_month_days`, or `on_dates`, so a rule can also switch between weekly, monthly,
and yearly, plus an optional `in_zone`) sets or retimes a rule, `every_seconds` replaces one with
an interval, and
`every_seconds: 0` stops it repeating. The two forms are mutually exclusive in one call, since
an item carries one recurrence shape. Retiming a rule **moves the next fire** to that rule's own
next occurrence and reports it, unlike an interval change, which leaves the armed fire alone and
takes effect from the following one; a fired-but-undelivered reminder retimed this way re-arms
and fires fresh rather than re-delivering the stale one (ADR-0025 rule-edit addendum).

With subagents wired (`CORTEX_SUBAGENTS_BACKEND=llamacpp`) the tool also offers
`kind: "task"`, which is an autonomous subagent run per fire, dispatched through the ticker's own
audited `spawn_subagents` path (`confirmer=None`, so gated tools stay structurally
unreachable; a tainted-created task is refused at creation outright). A finished task's
**outcome delivers as a notification** the same way a reminder's text does (ADR-0025 task-outcome
addendum): the outcome (not the standing instruction) becomes the toast body under a `Cortex task`
title and, if the push does not land, waits in the store for the overlay's next pull. So a one-shot
task's result now survives its fire instead of being deleted with the record, and a task that
finishes while the body is down is recovered, not lost.

With the body wired (`CORTEX_BODY_BACKEND=grpc`) fired reminders and task outcomes both attempt a
native-toast push. A toast the host shows is delivery, so the ticker acks the item at once and the
overlay will not show it again; a declined or failed push leaves it deliverable and the pull path
delivers. There is no proactive re-push beyond that next pull (a re-push without a per-fire
delivery id would double-deliver; deferred, see
[docs/refinements/scheduling.md](../refinements/scheduling.md)).

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

- **The native toast** (the push half) **landed 2026-07-16** as the `body_core::os::Notify`
  port with a real `WindowsNotify` WinRT backend (ADR-0025 notify addendum). The inert-text
  rule, the untrusted-source attribution line, and the XML escaping are all CI-gated in the
  core, so what is genuinely host-side is whether a toast **appears** and reads well:
  1. Run the body with the brain wired for push, as in [body-volume.md](body-volume.md)
     (`CORTEX_BODY_ADDR=0.0.0.0:50151` plus the shared `CORTEX_SEAM_TOKEN`, and the brain up
     with `-f docker/docker-compose.body.yml` so `CORTEX_BODY_BACKEND=grpc`).
  2. In a chat: *"remind me to stretch in one minute"*. When it fires, a toast should appear
     carrying the reminder text, and summoning the overlay afterwards should show **no** card
     for it (a shown toast is delivery, so the ticker acked it).
  3. Check the hostile case with a reminder whose text is markup, e.g. one containing
     `<b>bold</b> & "quotes"`. It must appear as those literal characters. A toast that never
     appears for such a reminder means the escaping failed and the payload would not parse.
  4. **If no toast ever appears**, the likely cause is the app identity rather than the code:
     Windows attributes a toast to an `AppUserModelID` that an installed Start Menu shortcut
     must carry, and a `npm run tauri dev` run has none. Set `CORTEX_TOAST_APP_ID` to an
     already-registered identity to confirm (PowerShell's,
     `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`, is the
     usual borrowed one), or test from an installed build, whose shortcut carries
     `dev.cortex.body`, the default.
  Clicking the toast does nothing by design for now (deferred, see
  [docs/refinements/scheduling.md](../refinements/scheduling.md)).
- **The overlay reminder surface** (the pull half) **landed 2026-07-14** and is CI-gated over
  the fake bridge, so what remains here is looking at it on the real hotkey path: summon the
  overlay with something due and the card stack sits above the history, each card carrying its
  text, how long ago it fired, `repeats` on a recurring series, and a dashed, faintly red-tinted
  `untrusted source` badge when `tainted`. Dismissing (the check button) acks it. Both themes and
  the eleven-card scroll case were checked in headless Chromium against the demo bridge, so what
  is genuinely host-side is the real hotkey path: whether the stack reads well over the live
  window and whether killing the brain mid-session leaves the cards in place (it should: a failed
  pull dispatches nothing) rather than emptying the surface.

Both halves landed behind the committed seam shapes; nothing brain-side changed for either.

## Troubleshooting

- **A reminder never fires:** is the backend on (`docker logs cortex-brain-1`, where the
  ticker logs pass failures)? Is the item still PENDING (`list_scheduled` in a chat, or
  `redis-cli zrange cortex:schedules:due 0 -1` on loopback)?
- **A fire repeats:** expected after a crash or a task outrunning `CORTEX_SCHEDULE_LEASE_S`
  (at-least-once by design; the fencing token keeps the duplicate's late finish from
  clobbering state). Raise the lease if tasks legitimately run long.
- **A corrupt record:** the claim path quarantines it to the `cortex:schedules:dead` hash
  (logged loudly) and the pass continues. See the next section.

## Dead-letter quarantine

A record that fails to decode on the claim path is quarantined (field = item id, value = the
raw bytes) so one corrupt record degrades the pass by one item instead of poison-pilling it.
Inspection is operator-side only, never a model tool, because the bytes are exactly the
corrupt or hostile content the codec refused (ADR-0025 dead-letter addendum):

```bash
cd brain && uv run python -c "
import asyncio
from cortex_session import RedisScheduleStore

async def main() -> None:
    store = RedisScheduleStore.from_url()
    for letter in await store.dead_letters():
        print(letter.item_id, repr(letter.raw[:120]))
    await store.aclose()

asyncio.run(main())"
```

`redis-cli hgetall cortex:schedules:dead` is the raw equivalent; drop one entry for good
with `store.purge_dead_letter(item_id)` (or `redis-cli hdel cortex:schedules:dead <id>`).
Retention is manual by design: the hash only grows when a record is quarantined, which is
exceptional, so an automated policy joins the deferred ledger only if volume ever appears.
