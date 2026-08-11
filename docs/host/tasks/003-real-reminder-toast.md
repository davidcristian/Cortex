# A real reminder toast

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

**What only this proves.** That WinRT toasts render at all for an unpackaged app's
`AppUserModelID`, and that the CI-gated inert-text and escaping rules survive the real notification
service. Everything except "does it appear and read well" is already gated in `body_core`.

Kept verbatim from [refinements/scheduling.md](../../refinements/index.md#scheduling), where this lived
inside the landed `Notify` entry:

> Remaining, and unchanged from what this slice always owed: the **Host-Windows** look at a real
> toast (runbook [scheduling.md](../../runbooks/scheduling.md)).

The sentence below was that slice's status in a planning doc, preserved here when it was slimmed
on 2026-07-19; [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)'s own 2026-07-19 addendum states
the live version of it and points back at this item by number:

> the port plus the inert-text rule are gated in `body_core`, `WindowsNotify` renders a WinRT
> toast, and only the user's look at a real toast is left.

**Do.** [runbooks/scheduling.md](../../runbooks/scheduling.md), "Host-only half on Windows", four steps.
In short: *"remind me to stretch in one minute"*, then a second reminder whose text contains
`<b>bold</b> & "quotes"`.

**Pass.** A toast appears carrying the reminder text; summoning the overlay afterwards shows **no**
card for it, because a shown toast is delivery and the ticker acked it. The hostile-markup reminder
appears with those characters literal.

**Fail.** No toast at all is most likely the app identity, not the code: a `npm run tauri dev` run
carries no Start Menu shortcut and so no registered `AppUserModelID`. The runbook gives the
borrowable PowerShell id for `CORTEX_TOAST_APP_ID` to confirm that diagnosis. A toast that never
appears **only for the markup reminder** is the sharp failure: the escaping broke and the payload
did not parse. Clicking a toast doing nothing is expected, not a failure (toast activation routing
is a recorded deferral).

**Record it.** A dated addendum to [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md), whose
host line names the native toast; then delete this section.

## Notes

- The sitting doc numbers this check **2**, and ADR-0025 cites it by that number.
- The host index's roll call adds that it needs a fired reminder, so seed one before starting. The
  reminder pull surface check pairs with this one and uses the same seed.
- This is the second of the two checks the brain dials the body for, so it needs the extra
  prerequisites the host index lists for that direction: `CORTEX_BODY_ADDR=0.0.0.0:50151`, the
  brain brought up with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance for
  that port.
