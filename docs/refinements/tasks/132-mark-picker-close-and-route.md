# The mark picker's click-away close and route in

**Status:** landed 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0031](../../adr/ADR-0031-bubble-mark.md)

**The entry's own diagnosis is what fixed it**
([ADR-0032](../../adr/ADR-0032-preference-record.md)):
both symptoms were the missing settings surface, so a settings sheet shipped (theme + mark,
opened from the hint strip or from the mark itself) and `MarkPicker` was deleted rather than
patched. Neither affordance needed to be built in the end. There is no inline popover left to
click away from, and the sheet is reachable from a chat that already has messages. The entry
guessed the `Ctrl+K` command palette would be the host; a sheet in the shortcut-sheet family
turned out to be the smaller step, and the palette can absorb it later without changing where
the choices live.

## Trail

- 2026-07-19: Filed with the bubble mark and landed the same day, both symptoms being the missing
  settings surface, so the sheet shipped and `MarkPicker` was deleted rather than patched.
