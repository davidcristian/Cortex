# The console tab strip's missing keyboard half

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The strip carries `role="tablist"` with a
`role="tab"` per face and `aria-selected` on the one showing, and focus travels with the view:
the arriving pane's selected tab takes it (`components/ConsoleView.tsx`), and leaving the console
hands it back to the composer, whose `active` prop is "the panel is open AND no console tab is
up" (`components/ChatView.tsx`). That handoff is load-bearing rather than polish, because a
browser refuses to hide the focused element's ancestor from assistive tech, so without it the
`aria-hidden` on the pane being left is ignored and the tree holds two consoles for the length of
a morph (Chromium says so in the console, and the AX tree over CDP showed both before the handoff
landed and one after). Two pieces of the pattern are deferred. The strip has no roving `tabindex`
and no arrow-key navigation, so both tabs are in the tab order and Left/Right do nothing, where
the ARIA practice is one stop for the whole strip and arrows to move along it. And a pane on its
way out is `aria-hidden` but still focusable, so a Tab pressed during the 380ms of a crossing can
land in it; the sanctioned fix is `inert`, which React types only from 19 (this tree is on 18,
and setting the attribute by hand around a subtree React owns is the kind of thing that reads as
a bug later). Deferred because neither is reachable with a pointer, both are invisible outside
that 380ms window, and the half that changes what is ANNOUNCED, which is the half a screen reader
actually reports, is done.
**BOTH halves LANDED 2026-08-03
([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)), and the entry's blocker was not
real.** The strip is one stop in the tab order now, carried by a roving `tabIndex` that is 0 on the
selected face and -1 on the others and needs no state of its own, because selection follows focus
and the tab that has focus is the tab that is selected. `overlay/tabStrip.ts` is the pure map of
the keys: the arrows step along the strip and wrap at both ends, Home and End go to the ends and
do not wrap, the vertical arrows are left alone (Ctrl with those cycles chats), and the four it
answers are `preventDefault`ed because the panel clips its overflow. Selection follows focus rather
than waiting for Enter, which the practice recommends wherever showing a panel costs nothing and
which this console can afford twice over: both panes are already mounted, and at the shipping 12px
spread they share a height, so an arrow changes the content and not the panel's size. The leaving
pane is `inert` as well as `aria-hidden`, from one function (`overlay/withdrawn.ts`) used in all
three places the overlay holds something mounted that is not on screen, the third being the panel
itself while dismissed. **The React 19 blocker evaporated on contact.** Only the TYPE is missing:
probed against the tree's own react-dom 18.3.1 on both renderers, `inert=""` renders
`<div inert="">` with no warning and `inert={undefined}` removes it again, while `inert={true}` is
the form React 18 drops. An empty string is how HTML spells a present boolean attribute, so the
string form is what the platform means rather than a workaround, and it is written by React
through JSX with nothing set by hand; one module augmentation adds the type, narrowed to `""` so no
call site can write the form React 18 drops. Nothing was upgraded. The entry also undersold the
reach in two ways. The 380ms morph was not the only window: switching tabs cross-fades the two
panes over 200ms, and Tab pressed inside THAT window walked six stops through the tab being left
and then lost focus to the body when `visibility: hidden` landed on the focused element. And the
dismissed panel had the same defect one level up, `aria-hidden` over an `opacity: 0` panel that is
never unmounted, where six presses of Tab reached the reminder rows' buttons three times round.
Measured in Chromium at 900x900 before and after: the strip went from two tab stops to one, five
arrow and Home/End presses from doing nothing at all to moving focus and the selection together,
the leaving view from three reachable stops to zero, the tab crossing from six to zero, and the
dismissed panel from six to zero. The `?` key, which can change the tab from anywhere, used to
drop focus to the body when it fired from inside a pane; focus follows the selection at every
switch now, so it lands on the arriving tab. What this consciously did not do is the chat
switcher, whose `role="listbox"` disagrees with its own rows; that is the new entry below.

## Trail

- 2026-07-20: Opened when the two settings views became one console.
- 2026-08-03: Both halves closed, and the area's count held because the pass that landed them opened
  the chat switcher's role mismatch. What the entry got wrong is a species this backlog had not
  recorded before: it reasoned from a version number to a capability, and the capability was one
  `renderToStaticMarkup` call away from being checked.
