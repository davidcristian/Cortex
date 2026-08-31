# ADR-0034: The panel's other screens are views it morphs into, not sheets laid over it

**Status:** Accepted (2026-07-21), amended by [ADR-0035](ADR-0035-console-and-motion.md)

## Context

Three things went wrong at once with the panel's vertical behaviour, and they turned out to be one
problem seen from three sides.

1. **The panel stopped being centred.** [ADR-0033](ADR-0033-panel-growth.md) anchored it at
   `bottom: 15vh` so that growth pushed the top edge up and left the composer alone. That works
   during a conversation and is wrong at rest: an empty chat sat 84 px below where the eye expects
   a summoned window, and it was never centred again for the rest of the session.

2. **The shortcut and settings sheets could not resize.** Both were `position: absolute; inset: 0`
   covers, so each inherited whatever height the chat underneath happened to have. The settings
   sheet had two rows in it, and at 546 px tall those two rows sat at the top of a mostly empty box
   with its closing hint stranded three hundred pixels below them.

3. **Closing a section snapped.** Removing the chat switcher deleted its rows in one frame,
   everything below them jumped up into the hole, and only then did the panel ease down after
   them. Two motions, in the wrong order.

A fourth defect was found while measuring the first three: the growth hook treated any non-null
`Animation` as running, so after one ease finished it read the *new* height as "what is
displayed", found no difference, and skipped the animation entirely. Every second size change was
therefore a jump.

## Decision

1. **The panel has views, and morphs between them.** The chat and the console
   ([ADR-0035](ADR-0035-console-and-motion.md) decision 1, whose two tabs replaced the first
   version's separate shortcut and settings views) are views of one window rather than a window
   with covers over it. Only the active view is in the layout flow, so it alone determines the
   height the panel is easing to.

2. **One module owns the panel's edge and height, and the edge nearest the hand stays put.**
   `overlay/panelPlacement.ts`, driven by `overlay/usePanelMotion.ts`, owns both the panel's
   `bottom` and its `max-height` as inline styles, and `overlay/panelPin.ts` holds the rule for
   which edge stays put:
   - **Growth inside the chat keeps the bottom edge fixed**, so the composer never slides out
     from under the hand that just typed into it. A reply arriving, the switcher opening and a new
     chat emptying the panel are all growth inside the chat.
   - **Entering the console, or switching its tabs, resizes in place** on the bottom edge the chat
     currently sits on, so the eye follows one thing changing (the height) rather than two. Coming
     back to the chat restores the edge it was left at (ADR-0035 decision 2).
   - **A resize inside any view but the chat keeps that view's top edge**, so the growth happens
     at the bottom. The console's chrome is its back button and its tab strip, both at the top,
     and a tab change must not slide the strip out from under the cursor that just clicked it.
   - **A view with more than one size arrives at the top its tallest size would take.**
     `ConsoleView` publishes how far the tab on screen falls short of its tallest
     (`TAB_SLACK_ATTRIBUTE`, from the two pane heights it already measures for `TAB_SPREAD_PX`),
     and the placement hangs the arriving tab from that top, so the strip sits at one height
     whichever button opened the console. The arrival is computed in full rather than as an
     adjustment to the edge, because the tallest size may not fit above that edge at all, in
     which case its top is the clear space kept at the screen's top; adjusting the edge and
     letting the top-keeping rule correct it put the console through two eases.

   The first version slid the panel to the true centre on every view change. The maintainer,
   having lived with it, chose the kept edge; the slide stays one flag away behind
   `VIEW_CHANGE_RECENTRES` (`overlay/panelPin.ts`), a defaulted argument of `place`, with both
   settings under test, including the stored-edge restore and the ceiling clamp that only a rising
   bottom edge exercises.

3. **The ceiling is derived from the max height, not chosen.** Growth pushes the top edge up until
   12% of the viewport is left clear above (`MIN_TOP_RATIO` in `overlay/panelGeometry.ts`), and
   past that the panel grows downward instead. The loosest cap, `openHeight`, is 76% of the
   viewport, `(100 - 76) / 2` being that same 12%, so a panel at its maximum is *exactly* centred:
   a long conversation ends dead centre rather than jammed against the top edge. Because the two
   numbers must agree, both live in code and neither is in CSS
   ([ADR-0035](ADR-0035-console-and-motion.md) decision 27).

4. **Sections roll open and shut themselves** (`components/Collapse.tsx`). The switcher list and
   the reminder stack animate their own height between nothing and their content, staying mounted
   through the close (an exit cannot be animated on an element React has already removed). The
   panel follows that roll, and since the panel is anchored by its bottom edge, nothing else on
   screen moves: the list rolls up and the panel's top edge comes down with it. Fading the section
   out instead was considered and does not work, because an invisible element still occupies its
   space and the snap simply happens later.

5. **A child animating the panel's height takes control of it, and hands it back**
   (`overlay/morph.ts` holds both halves of the contract). While `data-morphing` is set on any
   descendant, the panel leaves the height alone. When it clears, the section dispatches a bubbling
   `cortex:morphend`: a section rolling *open* changes no React state, so no render follows it and
   nothing else would tell the panel it had grown. Without that event a switcher opened on a tall
   chat sat 39 px from the top of the screen with 177 px of space below it, having grown past the
   ceiling of decision 3 without the panel measuring again. A `cortex:morphstart` and the published
   target height let the panel follow the roll rather than discover it afterwards
   ([ADR-0035](ADR-0035-console-and-motion.md) decisions 5 and 14).

   On the first placement after a roll, what is on screen is already the new height, so the
   geometry to animate *from* is that height at the old bottom edge, not the height the panel had
   last recorded. Animating from that stored height snapped the switcher back open for one frame,
   visible in a 60 Hz trace.

6. **The history takes the leftover space** (`.history { flex: 1 }`). Mid-resize the panel is
   taller than its content; without this the leftover height ended up after the last child and
   jerked the composer and the hint strip up before easing them back. Measured: the composer moved
   106 px on a switcher close, then eased back over 300 ms. It now does not move at all.

7. **The chat view is never unmounted**, only taken out of the flow. A half-typed draft and the
   composer's focus survive a trip to the console and back on that alone. The history's scroll
   position does not: out of the flow and under `display: none` the history has nothing left to
   scroll and the engine clamps it to zero. It is stored and restored in
   `overlay/useLogScroll.ts` before the return is painted
   ([ADR-0035](ADR-0035-console-and-motion.md) decision 30).

8. **The views are rows.** A view is a titled list: what it is on the left, what it can be on the
   right, hairlines between, and one way back, so a keycap and a theme chooser sit at the same
   rhythm. Colour stays reserved for controls the user acts on, so nothing here is accented. Two
   richer directions were presented as a live artifact (theme choices as thumbnails of the panel
   rendered in each theme, and one tabbed console instead of two destinations); the maintainer
   chose both, and [ADR-0035](ADR-0035-console-and-motion.md) decision 1 is what was built.

## Consequences

- The console cannot be dismissed by clicking a backdrop, because there is no backdrop any more.
  Esc closes it, and the header's chevron is the visible way back.
- The morph animates `height` and `bottom`, both of which drive layout, so this is the one place in
  the overlay that deliberately animates layout-affecting properties. It is bounded: one element,
  one animation, at most one per render.
- `Panel` is a router over `components/ChatView.tsx` and `components/ConsoleView.tsx`, which is what
  keeps every file under the line cap.

## Alternatives rejected

- **Sheets laid over the chat**: a cover inherits the chat's height (Context 2).
- **Sliding to the true centre on every view change**: two things move at once; kept behind
  `VIEW_CHANGE_RECENTRES` (decision 2).
- **Fading a closing section out**: it still occupies its space until it is removed (decision 4).

## Related

- Code: `body/app/src/overlay/panelPlacement.ts`, `panelPin.ts`, `panelGeometry.ts`, `morph.ts`,
  `usePanelMotion.ts`, `components/Collapse.tsx`, `components/ConsoleView.tsx`.
- Design: [overlay-ux.md](../design/overlay-ux.md).
- ADRs: [ADR-0033](ADR-0033-panel-growth.md) (how the height changes),
  [ADR-0035](ADR-0035-console-and-motion.md) (the console and the motion rules).
