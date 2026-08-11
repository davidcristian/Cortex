# Appearance choices do not survive a restart

**Status:** landed 2026-07-19
**Area:** body-overlay
**Origin:** [ADR-0031](../../adr/ADR-0031-bubble-mark.md)

**By the option this entry called the more expensive one**
([ADR-0032](../../adr/ADR-0032-preference-record.md)).
The entry recorded two choices and declined to pick: `localStorage` in the
webview, or a preferences record the brain owns. The maintainer chose the brain's record, so what
shipped is a `PreferenceStore` port with a Redis adapter, two RPCs on `BrainService`, and
`usePreferences` hydrating the theme and mark at mount. The entry's framing held up: this was
the overlay's first persistence of any kind, and the reason to prefer the record was exactly
what the entry said, that it survives a reinstall and reaches surfaces other than the window
that set it. One thing the entry did not anticipate: because the record arrives a round trip
after mount, hydration had to be taught not to overwrite a choice made in that window, which is
the feature's only real race and now has its own test.

## Trail

- 2026-07-19: Filed with the bubble mark and landed the same day on the maintainer's choice of the
  brain's preferences record over `localStorage`, as a `PreferenceStore` port with a Redis adapter,
  two RPCs on `BrainService`, and `usePreferences` hydrating the theme and mark at mount.
