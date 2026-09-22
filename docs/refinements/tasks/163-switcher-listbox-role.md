# The chat switcher's disputed listbox role

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

`SessionList.tsx` put `role="listbox"` on its `<ul>`, but its children were `<li>` elements holding
four ordinary buttons each (the row, then hoist, rename and delete) with no `role="option"` anywhere.
A listbox was announced whose required children were missing. The choice was between making the
rows options with `aria-activedescendant`, which leaves nowhere for the three per-row buttons, and
removing the role.

The maintainer chose to remove the role, so the switcher announces the list of composite rows it
already behaved like. The `aria-label` stays, all four buttons per row keep their own tab stops,
and `Ctrl+↑` and `Ctrl+↓` are untouched.

The role cost more than the role. A `<li>` inside a listbox is not a listitem, so the rows were
announced as nothing at all: in Chromium's accessibility tree the container read `listbox "Recent
chats"` over three children of role `none`, each holding its four buttons directly. With the role
off, the same tree reads `list "Recent chats"` over three `listitem`s, with nothing written on the
`<li>` to get them back.

Which chat is open was shown only by a background tint, and `aria-selected` needs the listbox, so
the row's own button now has `aria-current`, `true` on the open row and `false` on the others.

Notes for whoever measures next. jsdom does not reproduce the finding, because
`dom-accessibility-api` maps `<li>` to `listitem` whatever an ancestor claims, so the Vitest suite
asserts what it can see and the browser is where the `none` rows are visible. `aria-current` cannot
be read back over CDP either; it was verified per row in the live DOM.

## History

- 2026-08-03: Opened by the pass that gave the console's tab strip its keyboard navigation, which
  checked the overlay's other lists.
- 2026-08-03: Closed the same day on the maintainer's answer. The entry was right that this was a
  decision rather than a defect list, and it understated the defect twice: in what a `<li>` inside a
  listbox is announced as, and in the channel its "nothing else changes" missed.
