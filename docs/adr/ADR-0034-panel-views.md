# ADR-0034: The panel's other faces are views it morphs into, not sheets laid over it

- **Status:** Accepted, amended by [ADR-0035](ADR-0035-console-and-motion.md)
- **Date:** 2026-07-19
- **Amends:** [ADR-0033](ADR-0033-panel-growth.md) (decisions 1, 5 and consequence 3)

> **What changed.** Decision 1's three views are two: `shortcuts` and `settings` became the tabs of
> one console ([ADR-0035](ADR-0035-console-and-motion.md) decision 1), which is also why Esc now
> leaves in a single press and why the first consequence below is about a view that no longer
> exists. Decision 2 re-centred every view change, the return trip included, and the chat's own
> edge is parked and handed back instead, unclamped, with another chat no longer counting as
> another view at all (ADR-0035 decisions 2 to 4); the flat duration those moves ran at became a
> pace (ADR-0035 decisions 7 and 11). Decision 5's `cortex:morphend` gained a sibling
> `cortex:morphstart` and a published target height, so the panel rides a roll instead of
> discovering it afterwards (ADR-0035 decisions 5, 6 and 14). Decisions 3, 4, 6, 7 and 8 stand and
> are why the rest works.

## Context

Three things went wrong at once with the panel's vertical behaviour, and they turned out to be one
problem seen from three sides.

1. **The panel stopped being centred.** ADR-0033 anchored it at `bottom: 15vh` so that growth
   pushed the top edge up and left the composer alone. That works during a conversation and is
   wrong at rest: an empty chat sat 84px below where the eye expects a summoned window, and it was
   never centred again for the rest of the session.

2. **The shortcut and settings sheets could not resize.** Both were `position: absolute; inset: 0`
   covers, so each inherited whatever height the chat underneath happened to have. The settings
   sheet has two rows in it. At 546px tall those two rows sat at the top of a mostly empty box with
   "Click outside or press Esc to close" stranded three hundred pixels below them.

3. **Closing a section snapped.** Removing the chat switcher deleted its rows in one frame,
   everything below them jumped up into the hole, and only then did the panel ease down after
   them. Two motions, in the wrong order. ADR-0033 recorded this as a known gap.

A fourth defect was found while measuring the first three: the growth hook treated any non-null
`Animation` as running, so after one ease finished it read the *new* height as "what is displayed",
found no delta, and skipped the animation entirely. Every second size change was therefore a jump.
Traced in a browser at 60Hz: opening the switcher jumped, closing it eased, opening it jumped.

## Decision

1. **The panel has views, and morphs between them.** `chat`, `shortcuts` and `settings` are three
   views of one window rather than a window with covers over it. Only the active view is in the
   layout flow, so it alone decides the height the panel is easing to. The settings view is now
   198px tall and the shortcuts view 391px, against 546px for the chat that opened them.

2. **A view change re-centres; growth inside a view goes upward.** These are the same measurement
   and live in one hook (`overlay/usePanelMotion.ts`), which owns both the panel's `bottom` and its
   `max-height` as inline styles. Opening a view, coming back from one, or switching chats resizes
   the panel and slides it back to true centre in a single animation of `height` and `bottom`
   together. A reply arriving or the switcher opening keeps the bottom edge pinned, so the composer
   never slides out from under the hand that just typed into it.

3. **The ceiling is derived from the max height, not chosen.** Growth pushes the top edge up until
   `12vh` of clear space is left above, and past that the panel grows downward instead. `12vh` is
   `(100 - 76) / 2`, so a panel at its 76vh maximum is *exactly* centred: a long conversation ends
   dead centre rather than jammed against the top edge. Because the two numbers must agree, both
   live in the hook and neither is in CSS.

4. **Sections roll open and shut themselves** (`components/Collapse.tsx`). The switcher list and the
   reminder stack animate their own height between nothing and their content, staying mounted
   through the close (an exit cannot be animated on an element React has already removed). The
   panel's `auto` height follows that roll frame by frame with no animation of its own, and since
   the panel is anchored by its bottom edge, nothing else on screen moves at all: the list rolls up
   and the panel's top edge comes down with it. Fading the section out instead was considered and
   does not work, because an invisible element still occupies its space and the snap simply happens
   later.

5. **A child animating the panel's height claims it, and hands it back** (`overlay/morph.ts` holds
   both halves of the contract). While `data-morphing` is set on any descendant, the panel leaves
   the height alone. When it clears, the section dispatches a bubbling `cortex:morphend`, which is
   the panel's only word that anything happened: a section rolling *open* changes no React state,
   so no render follows it and the panel would never learn it had grown. Without that event a
   switcher opened on a tall chat sat 39px from the top of the screen with 177px of space below it,
   having sailed past the ceiling of decision 3 unnoticed. Measured, not reasoned about.

   On that first placement after a roll, what is on screen is already the new height (the panel
   followed the roll frame by frame), so the geometry to animate *from* is that height at the old
   bottom edge, not the height the panel last remembered. Remembering the mid-roll height instead
   snapped the switcher back open for one frame; that frame was visible in a 60Hz trace before it
   was understood. What is left to animate is the slide off the ceiling, if there is one.

6. **The history takes the slack** (`.history { flex: 1 }`). Mid-resize the panel is taller than its
   content; without this the leftover height landed after the last child and jerked the composer
   and the hint strip up before easing them back. Measured: the composer moved 106px on a switcher
   close, then eased back over 300ms. It now does not move at all.

7. **The chat view is never unmounted**, only taken out of the flow. A half-typed draft and the
   composer's focus survive a trip to settings and back on that alone.

   *Corrected 2026-07-20:* the history's scroll position was claimed here too, and did not survive.
   Being taken out of the flow cost it once and `display: none` cost it again: unbounded by the
   panel, the history's window became its whole content, and a box with nothing left to scroll is
   clamped to zero by the engine. Traced at 60Hz at 640x720 with the log a third of the way up, 154
   of 463 became 0 against a 463px window in the frame the class changed. The leaving view is
   bounded by the panel now, so only the unrendering is left, and the position is parked and handed
   back in `overlay/useLogScroll.ts` before the return is painted. It survives because a view does
   that, not because the view is never unmounted (ADR-0035, the two addenda on the user's console
   passes).

8. **The views are rows, and the baseline is the plainest of three directions pitched.** Both are a
   titled list: what it is on the left, what it can be on the right, hairlines between, and one way
   back. The two views differ only in what the right-hand side holds, which is why a keycap and a
   theme picker sit at the same rhythm. Colour stays reserved for working affordances, so nothing
   here is accented. Two richer directions (theme choices as thumbnails of the panel wearing them;
   one tabbed console instead of two destinations) were pitched to the user as a live artifact and
   were open, and either is inner markup on this same plumbing. The maintainer picked **both**, and
   [ADR-0035](ADR-0035-console-and-motion.md) decision 1 is what was built: this decision's two
   views are one console now, and its rows are the shortcut tab's rows.

## Consequences

- A settings view cannot be dismissed by clicking a backdrop, because there is no backdrop any
  more. Esc still closes it, and the header's chevron is the visible way back. This is a better
  affordance than the old one and it is also a behaviour change.
- The morph animates `height` and `bottom`, both of which drive layout, so this is the one place in
  the overlay that deliberately animates layout-affecting properties. It is bounded: one element,
  one animation, at most one per render.
- A single reminder leaving the stack still vanishes in one frame rather than rolling up, since
  `Collapse` wraps the stack and not each row. The history absorbs the slack (decision 6), so what
  is left is one row's worth of instant. Recorded in `docs/refinements/body-overlay.md`.
  **Closed 2026-08-03** ([ADR-0035 addendum](ADR-0035-console-and-motion.md)), and this bullet was
  out of date within a day: the stack wrapped each row from 2026-07-20 and the roll was already
  right. What that first version actually cost was the ack, which it delayed behind a 300ms timer
  an unmount could cancel. `overlay/usePresence.ts` holds the removed ROW instead, until that row's
  own `Collapse` reports its roll over, and the ack leaves in the frame the check is pressed. The
  switcher's rows are the same shape of exit and are not wired to the hook yet, which is the
  deferral that replaces this one in the same area doc.
- Two views' worth of chrome collapsed into `components/PanelView.tsx`, and `Panel` became a router
  over `components/ChatView.tsx` and the two views, which is what kept every file under the cap.

## Addendum (2026-07-21): the console stands on the chat's edge

Living with the motion, the user reversed one half of the morph: entering the console, or
switching between its tabs, no longer slides the panel to the true middle of the screen. It
resizes in place instead, standing on the bottom edge the chat is standing on, the way growth
inside a view does, so the eye tracks one thing changing (the height) rather than two. Coming
back to the chat is unchanged, and now trivially so, the edge never having moved.

The slide itself was not deleted: `panelPlacement.ts` keeps it behind `VIEW_CHANGE_RECENTRES`,
a defaulted argument of `place`, with both settings under test (the flipped-switch tests drive
`place` directly, including the parked-edge restore and the ceiling-along-the-move clamp that
only a rising bottom edge can exercise). Flipping the constant restores this decision's
original motion in full.

## Addendum (2026-07-21, later): which edge a view resizes from, and where the console arrives

The standing edge above answered where the console *opens*; living with it surfaced the other
half of the question, which is what happens once you are in it. Two rules now, and one principle
under them: **the edge nearest the hand is the edge that holds still.**

- **A resize inside any view but the chat holds that view's TOP edge**, so the growth happens at
  the bottom. The console's chrome is its back button and its tab strip, both at the top, and a
  tab change must not slide the strip out from under the cursor that just clicked it. The chat is
  the same principle at its other end: its composer is the thing at the edge the hand is on, so
  it keeps its bottom pinned and grows upward (ADR-0033).
- **A view with more than one shape arrives at the top its TALLEST shape would take.** The console
  publishes how far the tab on screen falls short of its tallest (`TAB_SLACK_ATTRIBUTE`, written
  by `ConsoleView` from the two pane heights it already measures for `TAB_SPREAD_PX`) and the
  placement hangs the arriving shape from that top. Without it the strip sat at two heights
  depending on which button opened the console, since the hint strip's sliders lands on the taller
  tab and its `?` on the shorter one, and the maintainer caught it: "the window position is lower when
  opening the shortcuts view vs the settings view".

The arrival is computed in full rather than as an adjustment to the edge, because the tallest
shape may not fit above that edge at all, in which case its top is the clear space kept at the
screen's top instead. The first cut added the slack to the edge and let the top-holding rule
correct it on the next render, which put the console through two eases, the second sliding its
bottom down 44px after it had apparently arrived. Traced at 60Hz over all three transitions
afterwards (chat to either tab, and between tabs), the top holds at one pixel value for every
frame of every one.
