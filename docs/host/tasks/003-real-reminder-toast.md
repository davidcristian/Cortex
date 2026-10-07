# A real reminder toast

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Verified:** 2026-10-07

**What only this proves.** That WinRT toasts render at all for an unpackaged app's
`AppUserModelID`, and that the inert-text and escaping rules covered in CI survive the real
notification service. Everything above that OS call ran on the Linux shell on 2026-10-07: the
ticker firing a reminder the cortex set, the brain dialing the shell's `BodyService.Notify` from a
container, `LinuxNotify` delivering it escaped to a notification server on the session bus, the
ack on delivery, and no card afterwards
([readings](../../readings/body-actions-linux.md#reminder-pushes)). The port and the inert-text
rule are tested in `body_core`, and `WindowsNotify` renders a WinRT toast. What is left is a
person's look at a real toast, per [runbooks/scheduling.md](../../runbooks/scheduling.md). The
Consequences of [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) state the same thing and
link the host index this item is listed in.

**Do.** [runbooks/scheduling.md](../../runbooks/scheduling.md), "The Windows half", four steps.
In short: *"remind me to stretch in one minute"*, then a second reminder whose text contains
`<b>bold</b> & "quotes"`.

**Pass.** A toast appears with the reminder text; summoning the overlay afterwards shows **no** card
for it, because a shown toast is delivery and the ticker acknowledged it. The hostile-markup
reminder appears with those characters literal.

**Fail.** No toast at all is most likely the app identity rather than the code: a
`npm run tauri dev` run has no Start Menu shortcut and so no registered `AppUserModelID`. The
runbook gives the borrowable PowerShell id for `CORTEX_TOAST_APP_ID` to confirm that diagnosis. A
toast that never appears **only for the markup reminder** is the sharp failure: the escaping broke
and the payload did not parse. Clicking a toast doing nothing is expected, not a failure, since
toast activation routing is a recorded deferral.

**Record it.** Edit [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md) in place where its
Consequences name the real toast; then delete this section.

## Notes

- The session doc numbers this check **2**; ADR-0066 links the section that lists it.
- It needs a fired reminder, so seed one before starting. The reminder pull surface check pairs
  with this one and uses the same seed.
- This is the second of the two checks the brain dials the body for, so it needs the extra
  prerequisites the host index lists for that direction: `CORTEX_BODY_ADDR=0.0.0.0:23151`, the
  brain brought up with `-f docker/docker-compose.body.yml`, and a Windows firewall allowance for
  that port.

## History

- 2026-10-07: screened for what runs off Windows and ran it on the Linux shell against the cortex
  on the card. A typed "remind me to stretch in one minute" and a reminder whose text is markup
  were each pushed once through `LinuxNotify`, escaped for a server listing `body-markup`, and
  acked, so the overlay's empty chat showed no card; with the notification server stopped, a third
  stayed deliverable and showed its card
  ([readings](../../readings/body-actions-linux.md#reminder-pushes)). This narrows the item to
  WinRT rendering the toast, the `AppUserModelID` and the toast XML's escaping.
