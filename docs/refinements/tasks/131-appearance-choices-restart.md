# Appearance choices do not survive a restart

**Status:** done 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0031](../../adr/ADR-0031-bubble-mark.md)

The entry offered two options and declined to pick: `localStorage` in the webview, or a
preferences record the brain owns. The maintainer chose the record, so a `PreferenceStore` port
with a Redis adapter shipped, plus two RPCs on `BrainService` and `usePreferences` hydrating the
theme and mark at mount ([ADR-0032](../../adr/ADR-0032-preference-record.md)).

This was the overlay's first persistence of any kind, and the reason to prefer the record is that
it survives a reinstall and reaches surfaces other than the window that set it. One thing the
entry did not anticipate: the record arrives a round trip after mount, so hydration had to be
taught not to overwrite a choice made in that window, which is the feature's only race and has its
own test.

## History

- 2026-07-19: Filed with the bubble mark and shipped the same day.
