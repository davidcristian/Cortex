# Runbook: scheduling and reminders

The brain can hold durable schedules in Redis and fire them. It offers five cortex-only tools
(`schedule_task`, `list_scheduled`, `cancel_scheduled`, `snooze_scheduled`, `edit_scheduled`), a
`ScheduleTicker` that fires what is due, and reminder delivery by pull over `ListDueReminders` and
`AckReminder`, or by push over `BodyService.Notify` when the body is wired. `snooze_scheduled`
postpones the next fire by `for_seconds` from now, moving only the next occurrence of a recurring
item and keeping the series on its original cadence; `edit_scheduled` changes an item's text or
recurrence in place without moving its next due time. Decisions:
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md) and [ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md).
CI covers everything but bring-up, the Docker checks below and the Windows half.

## Bring-up

Scheduling is off by default (`CORTEX_SCHEDULE_BACKEND=none`): no store, no built-in tools, no
ticker, and the pull RPCs answer benignly empty. Turn it on with the base compose file, which
passes the variable through:

```
CORTEX_SCHEDULE_BACKEND=redis docker compose --project-directory . \
  -f docker/docker-compose.yml up -d --build
```

Schedules live in the same append-only, named-volume Redis as sessions. The settings, all
`CORTEX_SCHEDULE_*`: `POLL_S` (pass interval, default 5), `LEASE_S` (default 300, to be kept above
the slowest expected task fire, since a task that outruns its lease is claimed again and runs
twice, which is the at-least-once trade), `CLAIM_LIMIT` (batch cap per pass, default 8),
`MAX_ACTIVE` (the `schedule_task` creation bound, default 32) and `TZ` (the IANA zone
model-facing times render in, default `UTC`).

### Display timezone

`CORTEX_SCHEDULE_TZ` (an IANA key such as `Europe/Bucharest`) sets the zone `schedule_task`,
`list_scheduled` and `snooze_scheduled` render in, and the zone an `at` without an offset is read
as. It is display only: stored due times stay UTC instants, so changing it re-renders existing
items and moves nothing.

```
CORTEX_SCHEDULE_BACKEND=redis CORTEX_SCHEDULE_TZ=Europe/Bucharest docker compose \
  --project-directory . -f docker/docker-compose.yml up -d --build
```

An unknown key fails the brain at startup with a `ValidationError` naming it, by design, since a
silent fallback would render every time in the wrong zone. Check `docker compose logs brain` for
`unknown timezone` if the container will not come up after changing it. An `at` that has an
explicit offset is always honoured; a bare wall time reads as this zone, and the two daylight
saving irregularities resolve with `fold=0`, so an ambiguous hour takes the earlier offset and a
skipped one fires just past the gap.

### Recurrence: an interval, or a wall-clock rule

There are two shapes and an item takes exactly one.

- `every_seconds` is a fixed interval. It is the right shape for "every 90 minutes"; across a
  daylight saving transition it keeps its interval, so its wall-clock time shifts.
- `at_time` (`HH:MM`, in `CORTEX_SCHEDULE_TZ`) with an optional day selector is a wall-clock rule.
  It is the right shape for "every weekday at 09:00": it keeps the clock time across a daylight
  saving transition, where a 86400-second interval would drift an hour. The first fire is computed
  from the rule, so `at_time` replaces `at` and `in_seconds` rather than accompanying them. The
  selector is at most one of:
  - `on_days` (`["mon","tue",...]`, omitted means every day), the weekly window.
  - `on_month_days` (`[1, 15]`, integers `1..31`), the monthly one. A day a short month lacks
    fires on that month's last day rather than skipping the month, so `[31]` is how to say "the
    last day of every month" and `[30, 31]` fires once in February.
  - `on_dates` (`["12-25", "01-01"]`, `MM-DD` strings with no year), the yearly one. Use it for
    anniversaries and renewals, where an interval of 365 days drifts a day every leap year.
    `02-29` is accepted and fires on the 28th in a common year, while a date no year contains
    (`02-30`) and a full ISO date (`2026-12-25`, whose year would have to be silently dropped) are
    both refused with a correction.

  Giving more than one selector in a single call is refused: a rule holds exactly one.

  An optional `in_zone` (an IANA key such as `"America/New_York"`) names the zone the `at_time`
  wall clock is in, for a reminder that should fire on another zone's clock, say 09:00 New York
  time while the deployment renders Bucharest. Omit it to use `CORTEX_SCHEDULE_TZ`. It is
  meaningful only with `at_time`, since an interval has no wall clock to place, and an unknown key
  comes back as a correction. A per-zone item lists and confirms its due time in its own zone.

A calendar occurrence inside a spring-forward gap fires just past the gap, late and never
skipped; one in a fall-back repeat fires once, on the earlier of the two readings, in whichever
zone governs the rule. Because a rule names a wall time rather than an instant, **changing
`CORTEX_SCHEDULE_TZ` moves existing calendar schedules that did not name their own `in_zone`** to
the new zone's 09:00, while a rule that named an `in_zone`, and every interval and one-shot item,
only re-render. That is deliberate: a zone-less 09:00 reminder moves with the deployment's zone,
and one with a zone stays at the wall time it was set to.

`edit_scheduled` changes recurrence in place in either direction: `at_time` (with an optional
`on_days`, `on_month_days` or `on_dates`, so a rule can also switch between weekly, monthly and
yearly, plus an optional `in_zone`) sets or retimes a rule, `every_seconds` replaces one with an
interval, and `every_seconds: 0` stops it repeating. The two forms are mutually exclusive in one
call. Retiming a rule moves the next fire to that rule's own next occurrence and reports it,
unlike an interval change, which leaves the next fire alone and takes effect from the one after
it. A fired but undelivered reminder retimed this way fires fresh rather than re-delivering the
stale one.

With subagents wired (`CORTEX_SUBAGENTS_BACKEND=llamacpp`) the tool also offers `kind: "task"`,
an autonomous subagent run per fire, dispatched through the ticker's own audited
`spawn_subagents` path with `confirmer=None`, so tools that need approval stay unreachable and a
task created on a tainted turn is refused outright. That dispatch writes one audit line with
`item_id`, which is how `docker compose logs brain | grep item_id=` answers "what fired, and what
did it do?" for a dispatch that runs with no user present. A finished task's outcome, not the
instruction that produced it, is delivered as a notification under a `Cortex task` title and, if
the push fails, waits in the store for the overlay's next pull, so a one-shot task's result
survives its fire and a task that finishes while the body is down is recovered.

With the body wired (`CORTEX_BODY_BACKEND=grpc`) fired reminders and task outcomes both attempt a
native-toast push. A toast the host shows counts as delivery, so the ticker acks the item at once
and the overlay will not show it again; a declined or failed push leaves it deliverable and the
pull path delivers. There is no proactive re-push beyond that next pull, because a re-push without
a per-fire delivery id would double-deliver
([docs/refinements/index.md#scheduling](../refinements/index.md#scheduling)). Turning the backend
off strands stored deliverables until it is re-enabled: the records persist, but nothing lists or
fires them.

## The Docker checks, validated 2026-07-08

Both live checks run against the real containers and need no GPU:

```
cd brain && uv run pytest -m integration --no-cov \
  packages/session/tests/test_schedule_live.py \
  packages/orchestrator/tests/test_schedule_live_seam.py
```

`test_schedule_live.py` replays the full fenced-protocol contract suite against live Redis. It
skips if real schedules exist, because the checks assert exact global views and claim whatever is
due, and would otherwise disturb a live deployment's items. `test_schedule_live_seam.py` proves
the loop end to end: it seeds a due reminder into the store, waits for the brain's ticker to fire
it, reads it back over `ListDueReminders`, acks it over `AckReminder` (a second ack does nothing)
and cleans up. `just seam-health` confirms the rewired turn path still converses; it needs the
brain served with a token and the same value in its own environment, and fails to start without
one ([local-dev-wsl.md](local-dev-wsl.md) says why).

## The Windows half

What these close and where to record them:
[docs/host/index.md#windows-desktop](../host/index.md#windows-desktop).

**The native toast**, the push half, is the `body_core::os::Notify` port with a real
`WindowsNotify` WinRT backend. The inert-text rule, the untrusted-source attribution line and the
XML escaping are all covered by CI in the core, so what is genuinely host-side is whether a toast
appears and reads well.

1. Run the body with the brain wired for push, as in [body-volume.md](body-volume.md):
   `CORTEX_BODY_ADDR=0.0.0.0:50151` plus the shared `CORTEX_SEAM_TOKEN`, and the brain up with
   `-f docker/docker-compose.body.yml` so `CORTEX_BODY_BACKEND=grpc`.
2. In a chat, say "remind me to stretch in one minute". When it fires, a toast should appear with
   the reminder text, and summoning the overlay afterwards should show no card for it, because a
   shown toast is delivery and the ticker acked it.
3. Check the hostile case with a reminder whose text is markup, such as one containing
   `<b>bold</b> & "quotes"`. It must appear as those literal characters. A toast that never
   appears for such a reminder means the escaping failed and the payload would not parse.
4. **If no toast ever appears**, the likely cause is the app identity rather than the code.
   Windows attributes a toast to an `AppUserModelID` that an installed Start Menu shortcut must
   have, and a `npm run tauri dev` run has none. Set `CORTEX_TOAST_APP_ID` to an already
   registered identity to confirm (PowerShell's,
   `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`, is the usual
   borrowed one), or test from an installed build, whose shortcut has `dev.cortex.body`, the
   default.

Clicking the toast does nothing, by design for now
([docs/refinements/index.md#scheduling](../refinements/index.md#scheduling)).

**The overlay reminder surface**, the pull half, is covered by CI over the fake bridge, so what
remains is looking at it on the real hotkey path: summon the overlay with something due and the
card stack sits above the history, each card with its text, how long ago it fired, `repeats` on a
recurring series, and a dashed, faintly red-tinted `untrusted source` badge when `tainted`.
Dismissing with the check button acks it. Both themes and the eleven-card scroll case were checked
in headless Chromium against the demo bridge, so what is genuinely host-side is whether the stack
reads well over the live window and whether killing the brain mid-session leaves the cards in
place, which it should, since a failed pull dispatches nothing.

## Troubleshooting

- **A reminder never fires.** Is the backend on? `docker logs cortex-brain-1` is where the ticker
  logs pass failures. Is the item still PENDING? Ask `list_scheduled` in a chat, or run
  `redis-cli zrange cortex:schedules:due 0 -1` on loopback.
- **A fire repeats.** Expected after a crash or a task outrunning `CORTEX_SCHEDULE_LEASE_S`, which
  is at-least-once by design; the fencing token keeps the duplicate's late finish from overwriting
  state. Raise the lease if tasks legitimately run long.
- **A corrupt record.** The claim path quarantines it to the `cortex:schedules:dead` hash, loudly,
  and the pass continues. See below.

## Dead-letter quarantine

A record that fails to decode on the claim path is quarantined, with the item id as the field and
the raw bytes as the value, so one corrupt record costs the pass one item instead of failing it.
Two log lines say it happened, each naming the item as a field rather than in prose, so one id
finds both the traceback and the move:

```bash
docker compose --project-directory . -f docker/docker-compose.yml logs brain \
  | grep "quarantining a corrupt schedule record"
# ERROR:cortex_session.schedule_claims:quarantining a corrupt schedule record \
#   dead_key=cortex:schedules:dead item_id=<id>
```

Inspection is operator-side only and never a model tool, because the bytes are exactly the corrupt
or hostile content the codec refused:

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

`redis-cli hgetall cortex:schedules:dead` is the raw equivalent. Drop one entry for good with
`store.purge_dead_letter(item_id)` or `redis-cli hdel cortex:schedules:dead <id>`. Retention is
manual by decision: the hash gains one field per corrupt item id and the same transaction drops
that id from every live index, so it cannot grow on its own, and the raw bytes are the only record
that a record ever corrupted.
