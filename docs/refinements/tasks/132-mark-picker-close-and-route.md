# The mark picker's click-away close and route in

**Status:** done 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0031](../../adr/ADR-0031-bubble-mark.md)

Both symptoms came from the missing settings surface, which is what the entry diagnosed. A
settings sheet shipped, holding the theme and the mark and opened from the hint strip or from the
mark itself, and `MarkPicker` was deleted rather than patched
([ADR-0032](../../adr/ADR-0032-preference-record.md)). Neither affordance had to be built: there
is no inline popover left to click away from, and the sheet is reachable from a chat that already
has messages.

The entry expected the `Ctrl+K` command palette to be the host. A sheet in the shortcut-sheet
family was the smaller step, and the palette can absorb it later without changing where the
choices live.

## History

- 2026-07-19: Filed with the bubble mark and shipped the same day.
