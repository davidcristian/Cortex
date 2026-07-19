# Scheduling & reminders

These deferrals originate at [ADR-0025](../adr/ADR-0025-scheduling-reminders.md), the Slice 9.5 scheduling and reminders decision, joined by [ADR-0027](../adr/ADR-0027-turn-provenance.md) for the `TurnStamp` turn-provenance seam. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** toast activation routing, `SubagentTask` session attribution, `ToolInvocation` audit-line stamp, Postgres durable twin, cron expressions, automated dead-letter retention, push retry policy (sharpened to fix-when-it-bites), task/reminder distinction on the pull surface

**Scheduling & reminders in Slice 9.5 ([ADR-0025](../adr/ADR-0025-scheduling-reminders.md)):** each
behind the unchanged `ScheduleStore`/`BodyGateway`/seam shapes.
- **The Rust `BrainTransport` reminder methods landed 2026-07-14 ([ADR-0025 transport
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** `list_due_reminders` / `ack_reminder`
  (+ the `DueReminder` core mirror) behind the committed proto shapes, translated in a new
  `body/crates/rpc/src/reminders.rs` beside the session reads, with the retry split the
  entry predicted (list retried as idempotent, ack forwarded). The reason for that split
  sharpened in the writing: a repeated ack is harmless *brain*-side, but a retry after a
  **lost reply** answers `acked=false` for a reminder the same call cleared, so the caller
  reads "nothing to ack"; the test is whether a repeat can change the answer, not whether
  the call is a write. CI-gated at 100% and mutation-proven (retry present, retry absent,
  row mapping, ack answer; each reverted individually turns a distinct test red). Remaining
  of the in-slice remainder: the overlay's reminders-on-open surface (fetch on open, badge
  tainted, ack on dismiss), now unblocked, and the body-side `Notify` OS trait + the Tauri
  toast rendering reminder text inert (host-validated). The brain treats the interim
  `Unimplemented` as any push failure, so pull already delivers end to end.
- **The overlay's reminders-on-open surface landed 2026-07-14 ([ADR-0025 overlay
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The second of the three in-slice
  remainders, and the one that gives the two pull RPCs a consumer: the `BrainBridge` port
  grows `listDueReminders`/`ackReminder` (+ a `DueReminder` mirror), `src-tauri/src/reminders.rs`
  implements them over the same resilient transport as the session reads, and a card stack
  renders above the history. The fetch is latched on the **rising edge of visibility**, not on
  mount: the body sits resident in the tray, so a mount-time read would deliver into a window
  nobody is watching and the ack-on-dismiss contract would be describing a card that was never
  seen; the latch re-arms on hide (one read per summon) and absorbs StrictMode's double-fired
  effect, which the tests assert under a real `<StrictMode>` wrapper since that is how
  `main.tsx` renders. Dismissal is **optimistic and the ack is never retried**, which is the
  layer that pays for the transport addendum's split: recovery is a re-read on the next open,
  so a lost reply can never be misread as a stale dismissal. Two properties are written down
  because they are invisible in the diff that would break them: reminder text is the one string
  the overlay shows that **no output guardrail inspected** (ADR-0015 filters streamed replies,
  not store rows), so nothing in the card may ever become a link, and a recurring card says
  `repeats` because acking clears the occurrence while the series re-arms, so an unmarked card
  would make dismissal read as cancellation. CI-gated at 100% over the fake bridge with ten
  guards mutation-proven (the visibility check, the re-arm, the latch, the optimistic dispatch,
  the failed-pull no-op, the wholesale replace, the dismissal filter, both badges, and the
  stack's placement outside the scrolling history; each reverted individually turns a distinct
  test red). Remaining of the in-slice remainder: only the body-side `Notify` OS trait + the
  Tauri toast (host-validated). Remaining behind this surface: **overlay badge/UX polish for
  tainted reminders** (the ADR-0025 deferral, now that a real badge exists to polish).
- **The reminder card's origin chat landed 2026-07-14 ([ADR-0025 origin
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** "Open the conversation this came from",
  which this entry correctly predicted needed no wire change: `session_id` has ridden every
  `DueReminder` since the seam was designed, and the overlay already loads a chat on demand,
  so the card gained a control and nothing else did (no proto field, no transport method, no
  reducer action, no brain change). It reuses `Panel`'s existing `onSelectSession`
  (`useOverlay.openSession`), so a reminder and the switcher load a chat by one path with one
  set of semantics, and no new prop crosses `Overlay` → `Panel`. Three decisions are worth
  more than the diff. The control is a **sibling of the reminder text, never the text
  itself**: making the card body clickable is the switcher's own shape and is the one thing
  this surface may not do, because reminder text is the string no output guardrail inspected,
  so an attacker who lands a reminder writes the label on whatever control it becomes.
  **Opening is not acking**, since an ack destroys the reminder and navigation does not, so a
  mis-click on the way to the context may not clear what it came to explain. And the control
  is **absent, not disabled**, both for a session-less row (`""`) and for a card whose origin
  is already on screen, where opening would change nothing while cancelling the turn running
  in that chat. CI-gated at 100% with four guards mutation-proven, and browser-validated in
  headless Chromium against the demo bridge in both themes (the adopted chat's own card offers
  no control, clicking one swaps title and history while all three cards stay, and the
  now-current chat's cards drop their controls in the same render). The pass also settled the
  resting treatment, the same correction the taint badge needed: at the meta row's `--dim` the
  label read as more metadata, so it rests at `--muted` and grows the switcher's pill on hover.
- **Overlay badge/UX polish for tainted reminders closed 2026-07-16 as satisfied, with no code
  change ([ADR-0025 badge addendum](../adr/ADR-0025-scheduling-reminders.md)).** The deferral was
  recorded before any badge existed, and by the time one did the overlay surface and its browser
  pass had already paid for the polish it names, so it was re-read against the tree rather than
  acted on. Each property it asks for holds in `body/app/src/components/Reminders.tsx`: a
  `tainted` row carries the fixed app-authored label `untrusted source` in the meta row beside
  the `repeats` tag, every field is a plain text node with nothing linkified, and the one control
  on the card keeps its own fixed label and sits beside the reminder text instead of becoming it.
  The badge's *treatment* is the specific thing "polish" would have meant here, and the overlay
  addendum's browser pass had already corrected it: a dashed neutral pill read as a third tag, so
  it took the error bubble's tint at a lower alpha while keeping the dashed border, which is why
  the signal does not rest on hue (`overlay.css`, `.reminder-tag.untrusted`). The gated tests
  assert behaviour rather than styling, including a hostile-text case proving the card renders an
  anchor tag as visible text and contains no anchor element. Nothing under the card changed after
  it shipped: every later overlay edit landed on the confirm card, the draft value, the reducer,
  or the demo bridge's confirm fixture, none of them on the reminder component, its styling, or
  its row type. **Two landings the same day were checked for whether they reopen it, and neither
  does.** The native toast badges a tainted reminder with its own fixed body-authored
  attribution, so push delivery is not an unbadged back door around the card that pull delivery
  badges. Structured provenance widened the *turn* stamp, not the stored item: `ScheduledItem`
  still keeps the taint bit and no sources and `DueReminder` carries no source field, so naming
  *which* source tainted a reminder is not available to display here; that is the separately
  recorded **provenance across the stores** entry ([untrusted-content.md](untrusted-content.md))
  and would be a store plus proto change rather than overlay work. What would reopen this: a
  named defect in the rendered card, most plausibly from the host Windows pass on the real
  overlay, which is the one look no gate reaches.
- **The body-side `Notify` OS trait + Tauri toast landed 2026-07-16 ([ADR-0025 notify
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The last of the three in-slice
  remainders, so push delivery exists end to end: the ticker's `notify` call reaches a real
  handler instead of the shape-now `Unimplemented`. `body_core::os::notify` holds the port
  (`Notify::show(&Notification) -> Result<bool, NotifyError>`, `Send + Sync` like
  `AudioControl`, in its own submodule because `os.rs` was at the line cap), `os_linux`/
  `os_macos` get the stubs behind the coverage escape hatch, `os_windows` gets the real
  `WindowsNotify` (a `ToastGeneric` WinRT toast), and `body_rpc`'s server takes the second
  backend generic the ADR predicted. **Three corrections to that ADR's own framing, each found
  by reading the code:** (1) it placed the Windows implementation in the **Tauri shell**, but
  the shell's own contract is that it holds no branchy decision, and `os_windows` already is
  the per-platform backend home and already `cfg(windows)`, so the backend lands there and the
  shell keeps only which backend to build and from which env var; (2) `VolumeService` could not
  keep its name once the server answered two unrelated capabilities, so it is
  `OsService<A: AudioControl, N: Notify>` (a rename, no behavior change); (3) the ADR-0023
  `unsafe` authorization widened by one line, still COM only and still `os_windows` only,
  because WinRT projections are safe but activating a WinRT factory needs a COM-initialized
  thread the tokio workers do not have. The load-bearing decision is **where the inert-text rule
  lives**: the ADR phrased it as an instruction to the Windows file, which would have rested the
  whole data-not-instructions posture on the one file no gate ever sees, so `Notification::new`
  applies it in the pure core instead (control characters replaced by spaces, never dropped, so
  words cannot fuse; each line bounded at 200 characters with a trailing ellipsis, so an
  oversized payload degrades a reminder rather than losing it, the same bias as the
  daylight-saving fold and the month-length clamp). **Escaping split off from sanitizing** once
  the two were examined: a toast template is XML, but a future Linux backend renders through
  markup-limited text where a pre-escaped string would show the entity literally, and a backend
  that escapes for itself would double-escape, so `escape_xml` is a gated helper the renderer
  calls rather than something the value bakes in. `shown=false` turned out to be a real answer
  rather than a dead wire field, because `ToastNotifier.Setting` reports *before* showing that
  notifications are off for this app, user, or policy, which is a decline and not a failure; the
  brain treats it exactly like an error either way, so the split buys only honest logs. The
  taint badge is a fixed body-authored `from an untrusted source` line, for the reason the
  overlay's card already learned (whoever writes the reminder must never write the label that
  describes it). CI-gated at 100% line+region+branch with nine guards mutation-proven (the
  control-character replacement, the length bound, the truncation mark, the taint-conditional
  attribution, the ampersand escape, the declined verdict, the unavailable status mapping, and
  the title/body and taint mapping into the value), plus a compile-only cross-check: both
  `os_windows` and the ungated Tauri shell were type-checked and clippy-checked against the real
  `windows` crate for the `x86_64-pc-windows-msvc` target from Linux. Remaining, and unchanged
  from what this slice always owed: the **Host-Windows** look at a real toast (runbook
  [scheduling.md](../runbooks/scheduling.md)), which **moved to
  [docs/host/windows-desktop.md](../host/windows-desktop.md) on 2026-07-19** with that sentence
  kept verbatim, joined there by the pull surface's own user check, which until that day had no
  line in any backlog although ADR-0025's host line and the runbook both named it. Neither was
  ever counted in this area, so no
  count moves. Newly deferred behind it: **toast activation
  routing** (its own entry below). Unblocked by it, and still deferred on their own merits: the
  **task-outcome delivery notification** and the **push retry policy**.
- **Toast activation routing.** A shown toast is inert: clicking it does nothing, while the
  overlay's reminder card offers "open the conversation this came from". Closing that asymmetry
  is **not behind an unchanged seam**, which is why it is recorded rather than folded in:
  `NotifyRequest` carries `title`/`body`/`reminder_id`/`tainted` and **no `session_id`** (unlike
  `DueReminder`, which has carried one since the seam was designed), so the body cannot resolve
  the origin chat at all today. It also needs an activation channel from the toast back into the
  running app, and for an unpackaged Win32 app that means a registered COM activator, which is
  more Windows plumbing than the delivery it improves. Wait for a second consumer of toast
  interaction (snooze-from-the-toast would be the other one) before spending it.
- **Toast activation routing sharpened 2026-07-16 as dead until a second consumer of toast
  interaction, the two-part design recorded ([ADR-0025 toast-activation
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** Read against the tree, the `session_id`
  the obvious fix wants on `NotifyRequest` has no reader but a host-side Windows one, so adding
  it now would be the dead wire this sweep declined five times the same day (blended relevance,
  `GetVolume`, the structured redaction event, occurrence history, the per-error-code retry table),
  on the same "no consumer" test. **The push path is fire and forget, confirmed end to end.**
  `_deliver` reads only the `shown` verdict (`ticker.py`), `GrpcBodyGateway.notify` returns only
  `reply.shown` (`gateway.py`), the body's `OsService.notify` builds a `body_core::Notification`,
  calls `Notify::show`, and discards all but `shown` (`body/crates/rpc/src/server.rs`), and
  `WindowsNotify.show` renders a fire-and-forget `ToastGeneric` toast with nothing read back
  (`body/crates/os_windows/src/notify.rs`); the Linux and macOS backends are `unimplemented!()`.
  The overlay never sees the call at all: it is a `BrainService` client, while `Notify` is a
  `BodyService` RPC the body serves, so no `notify` reference exists anywhere under `body/app/src`.
  The only reader of any toast payload beyond `shown` is the host-side `toast_xml`
  (`cfg(windows)`, never measured in CI), and the only thing that could act on a clicked toast is a
  COM activator that does not exist. **The two-part design, so the next pass re-derives nothing.**
  Part one, the seam prerequisite: a `session_id` on `NotifyRequest` (a new proto field
  regenerated into both stubs), set by the ticker's `_deliver` for both kinds (a reminder and a
  task each carry the origin `item.session_id`; a session-less item carries `""`, the `DueReminder`
  convention, and its toast is simply not routable), plumbed through `BodyGateway.notify` and its
  adapter into `Notification`, and embedded by `toast_xml` as the toast's top-level `launch`
  argument so a click's activation payload names the origin chat. Part two, the host-side
  activator: a registered COM `INotificationActivationCallback` for the unpackaged app's
  `AppUserModelID`, plus an activation channel from the Tauri shell into the running overlay, so a
  clicked toast invokes the app, reads the `launch` `session_id` back, and routes the overlay to
  that chat through the same `onSelectSession`/`openSession` the reminder card's origin-chat control
  already uses. **Why part one does not land alone.** Its last mile (the `launch` attribute in
  `toast_xml`) is itself host-side `cfg(windows)` and uncovered, so the field cannot be plumbed
  end to end in the CI-gated half; and the activation payload should be designed with its reader,
  since the entry's own named second consumer, snooze-from-the-toast, wants toast action buttons
  carrying their own arguments rather than a bare top-level `session_id`, so committing the wire
  shape now risks being wrong when the activator arrives. **Trigger:** a second consumer of toast
  interaction (snooze-from-the-toast) that shares the COM plumbing's cost, at which point the proto
  field and the toast launch payload are designed together with the activator that reads them, as
  one piece. This is the same `NotifyRequest` `session_id` the out-of-window authoritative title
  entry ([session-read-seam.md](session-read-seam.md)) names as one of its own reopen paths.
- **Session attribution landed 2026-07-13 ([ADR-0027](../adr/ADR-0027-turn-provenance.md)).**
  The dispatcher's per-call stamp widened from the lone taint bool to a frozen `TurnStamp`
  (`session_id` + `tainted`), built fresh per dispatch from the engine-threaded
  `ToolLoopContext.session_id` (the ticker stamps the fired item's stored provenance; a
  subagent stamps no session, having none). `schedule_task` fills
  `ScheduledItem.session_id` from it, so a created item attributes to its origin chat; the
  ticker's fire re-stamps the stored provenance onto its spawn dispatch (honest but
  unconsumed today: `spawn_subagents` reads only the taint bit). The stamp is the designed
  convergence seam for the ADR-0013/0019 structured-provenance deferrals: source URI/sender
  fields join the same object (still deferred there), never a new parallel channel.
  Remaining behind the same seam (ADR-0027 deferred): **`SubagentTask` session attribution**
  once a subagent-reachable consumer exists, and the **audit line** (`ToolInvocation`)
  gaining the stamp when an audit consumer wants per-session queries.
- **The Postgres durable twin** behind the unchanged port, when per-provenance queries or
  retention policies earn it (Redis AOF on a named volume is the sessions-grade v1 tier).
- **The display-timezone knob landed 2026-07-14 ([ADR-0025 display
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** `CORTEX_SCHEDULE_TZ` (an IANA key,
  default `UTC`, passed through by `docker/docker-compose.yml` so it is not inert in the
  container) is the zone `schedule_task` / `list_scheduled` / `snooze_scheduled` render in and
  the zone an offset-less `at` is read as. A pure `DisplayZone(name, tz)` in the core carries
  `render` + `resolve`; the IANA lookup stays at the composition root, so the core never
  imports `zoneinfo`, and an unknown key fails the process at **boot** rather than at the first
  listing. The two hardcoded `(UTC)` spec strings now name the configured zone, since correct
  numbers under a false label would be worse than no knob. Two things implementation corrected
  in this entry's own framing: reading a naive `at` as zone-local is a **deliberate behavior
  change** (v1 rejected it, which was right only while everything rendered UTC), and rendering
  needed a normalization hop through UTC, because `astimezone` returns `self` when the input
  already carries the target zone and so printed a *nonexistent* wall time for a spring-forward
  gap while the same instant read back from the store printed the canonical one. Display only:
  stored `due_at`/`anchor` stay UTC instants, no record or codec changed, no migration.
  Remaining:
- **Calendar recurrence landed 2026-07-14 ([ADR-0025 calendar
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The recurrence half of the original
  entry, and the cost this entry predicted was right: a new recurrence *shape*, not a knob.
  A pure `CalendarRule(hour, minute, days)` in the new `cortex_core/schedule_calendar.py`
  sits **beside** `ScheduledItem.every` (at most one of the two, enforced in `__post_init__`),
  `next_calendar_due` walks the rule's own weekdays resolving each candidate through the
  existing `DisplayZone.resolve`, and one new `next_occurrence(item, now, zone)` is the single
  entry point the ticker calls. Model-facing, that is `at_time: "09:00"` plus optional
  `on_days: ["mon", ...]`, mutually exclusive with `at`/`in_seconds`/`every_seconds`, with the
  first fire **derived from the rule** so no two-field consistency invariant reaches the model.
  Cron was rejected (a parser dependency, and a syntax a small model gets subtly wrong in ways
  that still validate). The DST policy the entry asked for is **inherited rather than
  invented**: a gap occurrence fires just past the gap (late, never skipped) and a fall-back
  repeat fires once, exactly as a naive `at` already resolved. Two corrections to this entry's
  own framing: the `anchor` field is **not** the home for the grid origin, because a rule *is*
  its own grid, so a snoozed calendar item needs no anchor and the snooze machinery was
  untouched; and the store needed no change at all, only the codec (an additive `rule` key read
  with `.get`, the `anchor` precedent, no version bump, no migration). The ticker takes the
  configured zone on `TickerSettings` rather than a seventh constructor argument. CI-gated at
  100% with all seven new guards mutation-proven, DST cases against real `ZoneInfo` zones on
  both sides of UTC; the contract suite covers the new field on fake and fakeredis alike, and
  because the codec changed, two real-stack runs back it: the live-Redis contract leg (itself
  mutation-proven to exercise the new key) and an end-to-end pass inside `cortex-brain:latest`
  that created "every weekday at 09:00" in `Europe/Bucharest`, fired it, and re-armed on the
  same wall-clock hour.
  It also forced the `cortex_core/__init__.py` barrel split (see [tools-mcp.md](tools-mcp.md)) and split
  `schedule_verb_args.py` out of `schedule_args.py` at the cap. The day-of-month and yearly
  halves both landed, in their own entries below; the **per-rule timezone** landed 2026-07-15
  (its own entry below). Remaining: **cron expressions** if a rule this shape cannot express
  ever turns up.
- **A per-rule timezone landed 2026-07-15 ([ADR-0025 per-rule
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The calendar addendum recorded this as the
  additive extension it turned out to be: `CalendarRule` gains an optional `zone: DisplayZone |
  None`, so a rule fires at its own wall clock (`in_zone: "America/New_York"`) regardless of
  `CORTEX_SCHEDULE_TZ`, while a zone-less rule still follows the deployment zone (the "your 09:00
  follows you" default, byte-for-byte unchanged and no migration, since a zone-less rule writes
  no `zone` key). The cost the calendar addendum's one-line note understated is the **resolver
  seam**: a per-rule zone is an *open* set, so unlike the single deployment zone it cannot be
  pre-resolved once at boot, and a `ZoneResolver` port (UTC-only default in the core, the
  `zoneinfo`-backed `ZoneInfoResolver` injected at the root) is needed wherever a name becomes a
  zone. It reaches exactly three boundaries: creation and edit parsing (a bad `in_zone` is a
  model correction), and the codec's decode, which **self-resolves** the stored name so the
  `RedisScheduleStore` and its five `decode` call sites stayed untouched (threading a resolver
  through would have pushed `schedules.py` past the 300-line cap). An unresolvable *stored* zone
  is a corrupt record (fail loud, only reachable via a tz-database change, never model input),
  and a per-zone item renders its `due_at` in its own zone so the shown wall time matches the
  rule. Two ruff ceilings fell out (`PLR0911`/`PLR0913`), resolved by extracting a shared
  `parse_calendar_rule` (which also deduped creation/edit rule parsing) and bundling the zone
  config into a `ZoneContext`, the `TickerSettings` precedent. CI-gated at 100% with the two new
  guards mutation-proven (rule-zone ignored, unresolvable-zone silently substituted; each turns a
  distinct test red), the codec round-trip run on fake + fakeredis + the live-Redis contract leg.
  Remaining: a **per-rule DST-policy override** is not owed (the fold policy is inherited), so
  only **cron expressions** stay open, as every calendar entry left them.
- **Setting and retiming a rule via `edit_scheduled` landed 2026-07-14 ([ADR-0025 rule-edit
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** `at_time`/`on_days` join the edit verb, so
  a rule can be authored on any item and retimed in place instead of cancelled and recreated;
  the reverse direction (rule to interval, or `0` to stop) already shipped. Behind the unchanged
  `ScheduleStore` port with no codec, record, or migration change. Three corrections to this
  entry's own framing, each found by reading the code rather than the entry: (1) it is **not**
  just "a `ScheduleEdit` that carries the third case", because a rule is its own grid, so setting
  one must **re-derive `due_at`**, bending the edit verb's deliberate "the next due time is never
  moved" rule for the one shape whose invariant requires it (an interval, anchored on `due_at`,
  is untouched). (2) The derivation needs a clock and a zone that `apply_edit` and both stores
  deliberately lack, so the rule and its first occurrence ride the edit as one frozen
  `RuleChange`, derived at the verb the way creation already derives its own first fire; binding
  the pair is also what keeps `due_at` from becoming the general knob this verb refused. (3) A
  naive `ZADD` of the moved due time would have been a **live defect**: a fired-but-undelivered
  reminder is `DONE`, `DONE` items are never on the due index today, and `ack` leans on that by
  deleting a `DONE` record without a `zrem`, so the item would have re-entered the claim path
  (whose staleness re-check only guards `PENDING`) and fired twice. `apply_snooze` already
  answered exactly this, so the rule branch borrows its behavior and its write set rather than
  inventing one. `schedule.py` hit the 300-line cap and split, keeping the value types and the
  recurrence math while `schedule_transitions.py` took the pure transitions both stores apply.
  CI-gated at 100% with all ten new guards mutation-proven (each reverted individually turns the
  new tests red), across the pure transitions, the verb's parse matrix, and the store contract
  suite on fake and fakeredis alike. No codec change, so no live-Redis run is owed beyond the
  contract suite's own leg.
- **Monthly day-of-month rules landed 2026-07-14 ([ADR-0025 monthly
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The calendar rule named a wall time and a
  set of **weekdays**, so its search was bounded to one week and "on the 1st of every month" had
  no expression but a 30 day interval, which is the drift the rule shape exists to avoid. The
  day set became a closed union (`DaySelector = Weekdays | MonthDays`) on `CalendarRule.on`,
  model-facing as an `on_month_days` list of integers on both `schedule_task` and
  `edit_scheduled`, refused alongside `on_days`. The cheaper-looking `month_days` field beside
  the existing `days` was rejected because it makes a monthly rule carry a weekday set it
  ignores (the type stating a falsehood, and "exactly one selector" demoted from a shape to a
  cross-field check); the union is also where a **yearly** variant joins. **A day the month
  lacks clamps to that month's last day rather than skipping the month**, which is not a new
  policy but the one daylight saving already set here (an irregularity moves an occurrence and
  never deletes one), decided on asymmetric failure modes: skipping means a monthly reminder
  silently never fires in up to five months of the year. Two properties fell out rather than
  being designed: `[31]` **is** "the last day of every month", so no separate last-day selector
  is owed, and days that clamp together fire once, since the walk works in resolved dates. The
  walk stays total by construction rather than by a cap (each selector answers
  `walk(start) -> (candidates, wrapped)`, the fallback being later than any instant `start`
  names), so `next_calendar_due` keeps one body and no unreachable branch. The codec
  distinguishes the selectors by **which key is present** (`days` versus `month_days`), so
  records predating this decode as weekly and a weekly rule still encodes byte-identically; no
  version bump, no migration. `schedule_day_args.py` split out of `schedule_args.py` at the
  300-line cap, shared by creation and the edit verb. CI-gated at 100% with the new guards
  mutation-proven, DST and local-date cases on both sides of UTC, and the codec's
  backward-compatible read tested against a hand-written pre-addendum record.
- **Yearly rules landed 2026-07-14 ([ADR-0025 yearly
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** The union's designed third variant, and
  the last cycle a wall-clock rule can name. An annual occurrence (a birthday, a renewal, a tax
  date) had no expression but a 365 day interval, which is the worst case the rule shape
  exists for: it drifts a full day every leap year and never self-corrects, so the reminder
  walks off its own date within a decade. `YearDays(days: frozenset[MonthDay])` joins
  `DaySelector`, model-facing as `on_dates: ["12-25"]` on both `schedule_task` and
  `edit_scheduled`. **Three corrections to the monthly addendum's own framing, each found by
  writing the code:** (1) it predicted "a `YearDays` variant naming a month alongside its
  days", and a single month with a day set cannot say "25 December and 1 January", which is the
  commoner annual shape, so it holds a set of `MonthDay(month, day)` pairs whose natural sort is
  chronological-within-the-year (the walk and the codec both lean on that rather than
  re-deriving it); (2) the field is **`on_dates`, not `on_year_days`**, despite the symmetry
  with its two siblings, because "year day" already means the ordinal 1..366 and a small model
  reading it that way writes `[359]` for Christmas, which validates as nothing; (3) the
  advertisement, not just the parsing, had to be shared: both verbs carried their own copy of
  the selector JSON schema, so a third selector would have been a third divergence between two
  descriptions of one vocabulary, and `day_selector_properties()` now lives in
  `schedule_day_args.py` beside the parser that reads it (`at_time` stays per-caller, its
  meaning genuinely differing between creation and edit). Two policies are **inherited rather
  than invented**: 29 February clamps to the 28th in a common year (the monthly clamp, which is
  daylight saving's "an irregularity moves an occurrence and never deletes one"; skipping would
  fire it in one year of four), and the walk stays total by the same `(candidates, wrapped)`
  contract, its fallback being next year's earliest date. A full ISO date is **refused rather
  than truncated**, matching `at_time`'s refusal of a seconds field, since dropping the year
  silently would answer a different question than the model asked; an unpadded `1-5` is accepted,
  because leniency there is unambiguous and drops nothing. The codec takes a third present-key
  variant (`year_dates`, as `[month, day]` pairs), so both older variants still encode
  byte-identically and no version bump or migration is owed. `schedule_calendar.py` hit the
  300-line cap and split, keeping the rule and the occurrence math while `schedule_selectors.py`
  took the three selectors, which is the union's own responsibility line. CI-gated at 100% line
  and branch with the new guards mutation-proven, DST and local-date cases on both sides of UTC,
  a four-occurrence no-drift property across the 2028 leap year, and the codec's
  backward-compatible read tested against hand-written pre-addendum records for **both** older
  variants (the yearly key must fall through, not shadow). **Two things the mutation pass
  corrected that the 100% gate did not**, both worth reusing: the `>= start` filter inside
  `walk` is an optimization rather than the strictness guard, in the **existing monthly**
  selector as much as the new one (removing either leaves the suite green, since
  `next_calendar_due`'s `instant > after` is the real test), so it is documented as a narrowing
  and deliberately not claimed as proven; and the first attempt to mutate the full-ISO-date
  refusal (widening the digit bound to `\d{1,4}`) stayed green because what refuses
  `2026-12-25` is the single-hyphen *shape*, not the digit count, which `MonthDay`'s own
  validation would catch anyway. Mutating toward the failure the guard exists to prevent (a
  regex that truncates a leading year) is what proved it. Remaining: nothing by symmetry. A
  fourth variant would be a different kind of thing (an nth-weekday rule, "the second Tuesday").
- **Occurrence history.** Coalesced single-slot deliverability keeps no per-fire records,
  and terminal cleanup deletes a one-shot task's outcome with its record; a history table
  would also cover unseen-toast recovery.
- **Occurrence history closed 2026-07-16 as declined, no consumer reads a fired occurrence
  ([ADR-0025 occurrence-history addendum](../adr/ADR-0025-scheduling-reminders.md)).** The entry
  above reads true against the tree: the store keeps no per-fire record, verified live against the
  compose Redis. A fired reminder sets the single `deliverable_since` slot (cleared at `ack`,
  overwritten if it re-fires before the ack, so coalesced); a task overwrites the single
  `last_outcome`; a terminal one-shot is deleted at `finish` (`next_due=None`, not deliverable) and
  takes its outcome with it; and a one-shot reminder the body reports `shown` is `ack`ed by the
  ticker at once, so `RedisScheduleStore.ack` deletes its DONE record. The live pass showed each:
  after a one-shot fired and was acked there were **zero `cortex:*` keys left**, a recurring item
  survived the fire with `deliverable_since=None`/`last_outcome=None` (no trace it had fired), and a
  one-shot task's `ran: 3 emails` outcome was gone with its record. So the unseen-toast gap the
  entry names is real: a one-shot reminder firing to an empty room is delivered by a toast nobody
  saw and then vanishes, and the next overlay open reads nothing back. **What closed it is that
  nothing reads a fired occurrence.** The seam exposes only `ListDueReminders` (which maps the
  `deliverable()` awaiting-ack slot) and `AckReminder` (`proto/body.proto`); `Reminders.tsx`
  renders that slot and acking removes a row by contract, so it cannot double as a history view
  without breaking the ack it is. `list_scheduled` reads `last_outcome`, but only the single last
  line of a still-active item, never a series. A recovery surface (a "recently fired"/"you missed
  these" view), the entry's own consumer, does not exist, and building it is a full stack: a new
  store read the in-memory fake must also answer, a growth or retention policy on an otherwise
  unbounded write-only log, a new `BrainService` RPC, a `BrainTransport`/`BrainBridge` method with
  its Rust and Tauri adapters, and a new overlay component. The origin ADR rejected per-occurrence
  records for exactly this ("duplicate fires nobody reads at personal scale"), so building the
  record blind now would ship the growth policy it warned against with nothing to shape it. **Store
  note:** a real durable history wants queries and retention, which is the deferred **Postgres
  durable twin** rather than the Redis this would grow unbounded, so the two reopen together. Moves
  to the backlog's dead-until-a-consumer list; it **reopens** the first time a surface reads a fired
  occurrence, arriving then as the record and that surface designed as one piece, not a log built
  ahead of its reader.
- **Snooze landed 2026-07-12 ([ADR-0025 snooze addendum](../adr/ADR-0025-scheduling-reminders.md)).**
  A new fenced `ScheduleStore.snooze(item_id, until)` transition (WATCH-fenced like
  finish/release/ack, contract-tested across fake + fakeredis + the live suite) plus the
  fourth cortex-only built-in `snooze_scheduled(id, for_seconds)` (in `schedule_verbs.py`,
  the line-cap split that took `cancel_scheduled` along). It shipped one-shots only (a snoozed
  recurring item would silently re-anchor its series), with the recurring case recorded as a
  remainder; that **anchor-preserving occurrence snooze landed 2026-07-13** (its own entry
  below). A fired-but-undelivered reminder re-arms (fires fresh, never re-delivers stale).
- **Dead-letter inspection landed 2026-07-12 ([ADR-0025 dead-letter addendum](../adr/ADR-0025-scheduling-reminders.md)).**
  `RedisScheduleStore.dead_letters()`/`purge_dead_letter()`, adapter-only by design (the
  quarantine is a codec mechanic the fake can never produce; a port method would force a
  vacuous fake), operator-facing and never a model tool (the raw bytes are the content the
  codec refused); runbook recipe + redis-cli equivalents in scheduling.md. Automated
  retention stays deferred until quarantine volume ever exists.
- **Edit verbs landed 2026-07-13 ([ADR-0025 edit addendum](../adr/ADR-0025-scheduling-reminders.md)).**
  Retext / re-recur without cancel-and-recreate: one new fenced `ScheduleStore.edit(item_id, edit)`
  transition (a bare watched `SET`, since only the record changes and `due_at` stays put so the
  indexes need no write) plus the fifth cortex-only built-in `edit_scheduled(id, text?, every_seconds?)`,
  replaying the snooze slice. A `ScheduleEdit` value applied by one pure `apply_edit` both stores
  share; `every_seconds` is three-valued (a bounded interval sets, `0` stops, omission leaves), and
  re-recur changes only future re-arms because the next occurrence never moves. The load-bearing
  nuance the deferral named holds: unlike cancel/snooze the editing turn's taint **ORs onto the item,
  never clears it** (so the listing badges it and re-taints), and a **task** cannot be edited on a
  tainted turn at all (the creation-side refusal), while a reminder edit under taint is allowed.
  Contract-tested across fake + fakeredis + the live Redis suite (retext, set/clear recurrence, taint
  monotonicity, FIRING/unknown refusal, the WATCH-fence race) at 100%.
- **Anchor-preserving occurrence snooze landed 2026-07-13 ([ADR-0025 occurrence-snooze
  addendum](../adr/ADR-0025-scheduling-reminders.md)).** `snooze` now works on recurring items:
  `ScheduledItem` gains an optional `anchor` (the recurrence grid origin, separate from `due_at`
  the next fire; the separate-anchor field the edit verb deliberately did not add), one pure
  `apply_snooze` both stores share pins it to the pre-snooze `due_at` on a recurring item's
  first snooze, and the ticker re-arms from `recurrence_base(item)` so a snoozed series returns
  to `origin + k*every` rather than drifting to `until + every`. The stores drop only the
  recurring refusal (FIRING/unknown still answer `False`, fence untouched); `anchor` rides the
  durable record as a forward-compatible additive key (no version bump, `decode` reads it with
  `.get`); snooze still carries no taint gate (it injects no content). Contract-tested across
  fake + fakeredis + the live Redis suite, plus pure `apply_snooze`/`recurrence_base` units, the
  tool test, and a ticker test proving the anchor-grid re-arm, at 100%.
- **The remaining scheduling deferrals** stay: **task-outcome delivery** as a notification and a
  **push retry policy** beyond next-poll-pull (both were blocked on the body half of this slice
  and are unblocked since the toast landed, since the `Notify` port a task outcome would reuse
  now has a real backend). The overlay badge/UX polish for tainted reminders that this line used
  to name closed as satisfied on 2026-07-16 (its own entry above).
- **Task-outcome delivery landed 2026-07-16, and the push retry policy sharpened behind it
  ([ADR-0025 task-outcome addendum](../adr/ADR-0025-scheduling-reminders.md)).** The entry above
  read true against the tree, and it decomposed into one thing to build and one to sharpen.
  **What a finished task delivered before:** the ticker's `_fire_task` finished with
  `deliverable=False`, so the outcome went only to the single `last_outcome` slot, read by nothing
  but `list_scheduled` (`schedule_tools.py`), and a one-shot task was deleted at `finish` (terminal
  cleanup) taking its outcome with it, the gap the declined occurrence-history entry named. Nothing
  proactively told the user their scheduled task had run. **What the reminder path already
  provided:** `_fire_reminder` finishes `deliverable=True` then pushes over `BodyGateway.notify`,
  acking on a shown toast (so pull will not re-show) and staying deliverable on a declined/failed
  push (so the pull path delivers), and the deliverable/ack machinery is **kind-agnostic** end to
  end, `ScheduleStore.deliverable()` and the Redis `DELIVERABLE_KEY` index filter nothing by kind,
  and `list_due_reminders`/`Reminders.tsx` render whatever `DueReminder`s the store yields. So a
  task outcome could reuse the whole ladder with **no store, no proto, and no overlay change**.
  **What landed:** `_fire_task` now finishes `deliverable=True` and calls the shared `_deliver`
  (renamed from `_push`, generalized to a title+body) with the *outcome* under a `TASK_TITLE`
  toast, never the standing instruction; `reminder_to_proto` maps a task's `last_outcome` into
  `DueReminder.text` so the pull recovery shows the result, not the instruction. A one-shot task's
  outcome now survives its fire (DONE-while-deliverable until acked), closing the one-shot half of
  the occurrence-history gap for tasks. **Double-delivery is prevented by the same ack the reminder
  path uses, not a resend timer:** a shown push acks (pull will not re-show), a failed push stays
  deliverable (pull shows once, dismissal acks), so exactly one of push and pull ever clears the
  slot; mutation-proven (dropping the task delivery reddens the delivery tests, dropping the ack
  reddens the acked-not-deliverable tests, dropping the outcome mapping reddens the pull test).
  Live against the compose Redis a one-shot task fired, pushed, acked, and left no `cortex:*` key,
  while a body-down fire left the outcome on the deliverable index for pull. **The push retry
  policy is deferred, sharpened, and moved to fix-when-it-bites:** the safe retry today *is* the
  deliverable-until-acked pull, and a proactive re-push beyond it double-delivers, because
  `NotifyRequest.reminder_id` is the item id, stable across a recurring item's re-fires, so the
  body cannot tell a retry of fire N from the legitimate fire N+1, and the `BodyGatewayError` a
  down body raises is indistinguishable from a shown-toast-with-a-lost-reply (the same lost-reply
  idempotency hole the ack-retry split and the `converse` reconnect sharpen turned on). A
  genuinely-safe re-push needs a **per-fire delivery id** the body dedups on, which is exactly the
  per-occurrence record the occurrence-history entry declined for want of a consumer, so the two
  reopen together. Its trigger: a body that reconnects between a failed push and the next overlay
  open often enough that an outcome stuck-until-open is a real gap, built then with the per-fire id.
- **A task/reminder distinction on the pull surface (opened 2026-07-16 behind the landing).** A
  fired task now rides the same `DueReminder`/`Reminders.tsx` card as a reminder, undistinguished:
  `DueReminder` carries no `kind`, the overlay labels the stack "Due reminders" with a bell icon,
  and the same taint/inert-text posture holds (a task outcome is a store row no output guardrail
  saw, badged if tainted, nothing linkified), so the reuse is safe but a task outcome reads as a
  reminder. Telling them apart wants a `kind` (or a distinct field) on `DueReminder` plus overlay
  rendering, a proto + four-tree + overlay change. Deferred until the surface must distinguish them
  (a different icon, a "task ran" label, a task-only action), not built speculatively.
