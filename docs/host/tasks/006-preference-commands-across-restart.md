# The preference Tauri commands across a restart

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0032](../../adr/ADR-0032-preference-record.md)

Added 2026-07-19 with the preference record
([ADR-0032](../../adr/ADR-0032-preference-record.md)).

**What only this proves.** That the two ungated glue commands (`src-tauri/src/preferences.rs`)
carry the settings record across the real IPC hop, and that the appearance the user picks is
still there after the app restarts. Everything either side of that hop is already proven:
the brain half was Docker-validated on 2026-07-19 against real Redis (written, both containers
restarted, read back intact, a cleared key still cleared), the Rust client is covered against a
fake brain, and `usePreferences` is gated at 100% including the hydrate-does-not-clobber race.

**Do.** Summon the overlay. Open **settings** from the sliders button in the hint strip (or by
clicking the mark on an empty chat). Pick a mark other than Mull and a theme other than the one
showing. Close the sheet, then quit the app and start it again.

**Pass.** The overlay comes back with the chosen mark and theme already applied, without a flash
of the defaults long enough to read. Picking **Auto** for the theme and restarting comes back
following the system scheme.

**Fail.** Defaults after a restart with a healthy brain means the read command or its hydration;
the choice not applying at all means the write command. The two are independent, so say which.
A brain that was down at launch is expected to show defaults: hydration is once per mount, and
that limit is recorded in the ADR's consequences.

**Record it.** A dated addendum to [ADR-0032](../../adr/ADR-0032-preference-record.md); then delete
this section.

## Notes

- The sitting doc numbers this check **4b**, which is the one number in the sitting that is not a
  plain integer: it was added after the rest and the existing numbering was left untouched, since
  ADRs cite these checks by number.
- The host index's per-doc table row names this check ("the preference commands and the appearance
  surviving a restart") and counts it in the sitting's eight, but the index's roll call under
  "Every item, one line each" does not list it, and its own heading there says seven checks share
  the bring-up. This item has no line of its own in that roll call.
- ADR-0032 carries no host line naming this check, so the three-records rule the host index states
  is satisfied only by the sitting doc and the index table row.
