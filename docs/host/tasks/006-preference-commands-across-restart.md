# The preference Tauri commands across a restart

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0032](../../adr/ADR-0032-preference-record.md)

**What only this proves.** That the two glue commands (`src-tauri/src/preferences.rs`) take the
settings record across the real IPC hop, and that the appearance the user picks is still there
after the app restarts. Everything either side of that hop is already proven: the brain half was
Docker-validated on 2026-07-19 against real Redis (written, both containers restarted, read back
intact, a cleared key still cleared), the Rust client is covered against a fake brain, and
`usePreferences` is covered at 100% including the hydrate-does-not-clobber race.

**Do.** Summon the overlay. Open **settings** from the sliders button in the hint strip (or by
clicking the mark on an empty chat). Pick a mark other than Mull and a theme other than the one
showing. Close the sheet, then quit the app and start it again.

**Pass.** The overlay comes back with the chosen mark and theme already applied, without a flash of
the defaults long enough to read. Picking **Auto** for the theme and restarting comes back
following the system scheme.

**Fail.** Defaults after a restart with a healthy brain means the read command or its hydration;
the choice not applying at all means the write command. The two are independent, so say which. A
brain that was down at launch is expected to show defaults: hydration runs once per mount, and that
limit is recorded in the ADR's consequences.

**Record it.** Edit [ADR-0032](../../adr/ADR-0032-preference-record.md) in place where the run
changes what it states; then delete this section.

## Notes

- Added 2026-07-19 with the preference record
  ([ADR-0032](../../adr/ADR-0032-preference-record.md)).
- The session doc numbers this check **4b**, the one number in the session that is not a plain
  integer: it was added after the rest and the existing numbering was left alone, since ADRs cite
  these checks by number.
- The host index's per-doc table row names this check and counts it in the session's eight, but the
  index's item list does not give it a line of its own.
- ADR-0032 has no host line naming this check, so the three-records rule the host index states is
  satisfied only by the session doc and the index table row.
