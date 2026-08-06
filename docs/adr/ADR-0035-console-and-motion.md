# ADR-0035: One console, and the motion a user's eye corrected

- **Status:** Accepted
- **Date:** 2026-07-20
- **Amends:** [ADR-0034](ADR-0034-panel-views.md) (decisions 1, 2, 5 and its first consequence),
  [ADR-0011](ADR-0011-body-v1.md) (the header's indicator row), and
  [ADR-0020](ADR-0020-reasoning-status.md) (what the settled Thoughts disclosure is built from)

## Context

Two things happened on the same day and they belong in one record, because the second is what the
first exposed.

The user answered the pitch that ends [ADR-0034](ADR-0034-panel-views.md) decision 8. Three
directions for the panel's non-chat faces had gone out as a live artifact; the plainest shipped and
two richer ones were left open (theme choices as thumbnails of the panel wearing them, and one
tabbed console instead of two destinations). The answer was **both at once**, which is decision 1
below and is a component change on plumbing that did not move, exactly as the deferral predicted.

Then the maintainer watched the running overlay, and named five things by hand:

- **"There is no animation when expanding thoughts."** The settled reasoning trace was a
  `<details>`, which reveals its content in one frame and cannot be talked into easing it.
- **The chat switcher's list flashed back** for a split second at the end of every close.
- **The scrollbars** "look absolutely terrible and disturb the look of the application and also
  push elements around."
- **Sending the first message shrank the panel.** The empty state is more content than the user
  bubble and the thinking bubble that replace it.
- **The connection dot belongs beside the "Recent chats" button**, not beside the title.

Each of those was traced at 60Hz before it was touched, and each trace turned up more than the
complaint it started from. [ADR-0034](ADR-0034-panel-views.md) decisions 2 and 5 were right about
where the panel belongs and wrong about three of the four mechanisms that put it there. Decisions 8
to 10 below are what a re-verification of decisions 2 to 7 turned up; decision 11, and the
paragraph that ends decision 8, came from a second re-verification of those. Both are cases where
the rule was right and the mechanism did not deliver it, and neither would have been found without
a trace, which is why every claim below carries the measurement it rests on.

## Decision

1. **The two other views became one console with a tab strip, so
   [ADR-0034](ADR-0034-panel-views.md) decision 1's three views are now two.** The pitch that ends
   that ADR's decision list (thumbnails of the panel wearing each theme; one tabbed console
   instead of two destinations) went to the user as a live artifact and came back as both at
   once: the swatch look, with the tab strip integrated. So `shortcuts` and `settings` are gone as
   separate destinations, and `chat` plus `console:appearance` / `console:shortcuts` are the
   panel's views. Six things follow, and each of them is why the merge is worth doing rather than
   a rename:

   - **Esc leaves in one press.** Two stacked flags meant two presses out of a settings view
     opened over a shortcut sheet, and the reducer had to say which sheet outranked which. One
     `consoleTab: "appearance" | "shortcuts" | null` cannot be in that state. The openers keep
     their own tab (the hint strip's sliders toggles appearance, the `?` and the `?` key toggle
     the shortcut list), the strip switches with an idempotent `openConsole`, and `closeConsole`
     is the one way out.
   - **Switching tabs is the morph that already existed.** The tab is part of the view NAME, so a
     switch resizes and re-centres through ADR-0034 decision 2's one movement and cross-fades
     through its decision 1's `.out` pane. Traced at 900x900: appearance is 411px (top 244,
     bottom 655) and the shortcut list 571px (top 164, bottom 735), and the switch moves both
     edges 80px in opposite directions over about 150ms, the paced duration for that distance,
     with the return trip landing back on 244/655 exactly. No second animation was written.
   - **A theme is chosen by looking at it.** Each tile is a miniature of the panel wearing that
     theme, drawn from that theme's own tokens (`components/ThemeMini.tsx`), and the Auto tile is
     the two themes `resolveTheme(null, …)` resolves to, split on the diagonal. Both rows are a
     map over their registry (`THEMES`, `MARKS`), so the plug-and-play property both modules claim
     survives this view: a fifth theme or mark appears here with no change to it. The marks are the
     real `BubbleMark` at 40px, not a CSS approximation, because the four styles differ by how they
     MOVE.
   - **The keycaps did not change.** The shortcut list is grouped now (Writing / Chats / The
     window), but each key is still its own `<b>` cap carrying the same outline glyph from
     `components/icons.tsx` that the hint strip draws, so `Ctrl` `N` still reads as two keys. The
     one difference is that `⇧` and `⏎` are now two caps rather than one, which is the same rule
     applied to the one row that broke it. **The hint strip came along**: it was the surface still
     drawing that chord as a single cap, which made the strip, not the list, the inconsistent one.
     Separating it costs 13px, taking the strip's content from 448px to 461px of a 558px row, so
     the wrap that dropped `Esc` from the strip is nowhere near.
   - **A tab-to-tab crossing holds the shared chrome still, and only one console is ever
     announced.** The header and the strip are the same elements in the same place in both panes,
     so the arriving pane's 7px rise and the leaving pane's 7px sink drew that chrome twice, 14px
     apart mid-fade (frozen at t=170ms in Chromium, the title and the strip visibly doubled). A
     crossing between two tabs now zeroes the distance and keeps every other timing: `.view.swap`
     sets `--rise: 0px`, which both `viewin` and `viewout` read, so the strip is pixel-identical in
     both panes at every frame of the switch (traced: 221/221 then 301/301 on the return) while the
     panel resizes under it. The distance is a variable rather than a second pair of keyframes
     because the flag is dropped the moment the crossing ends, and a second animation NAME is a
     second animation: the pane that had already arrived replayed its rise at 380ms, which the rAF
     trace caught as a 7px jump. Chat to console keeps the rise, sharing nothing with the chat.
     The leaving pane is also `aria-hidden` now, like the chat pane beside it, so the tree holds
     one "Console", one tab list and one tab panel instead of two of each while both are mounted.
     That only takes effect if focus leaves with the pane, since a browser refuses to hide the
     focused element's ancestor and Chromium says so in the console, so focus follows the
     selection onto the arriving pane's selected tab, and leaving the console returns it to the
     composer, which is where a summon puts it and where the draft still is. The rest of the tab
     list pattern (a roving `tabindex` and arrow keys along the strip) and a leaving pane that is
     untabbable as well as unannounced (which wants `inert`, and so React 19) are deferred and
     written down in [refinements/body-overlay.md](../refinements/body-overlay.md). **Both landed
     on 2026-08-03**, in the addendum below on the strip's keyboard, which also records that the
     React 19 half of that parenthesis was wrong: only the type is missing from React 18.
   - **The two state modules the merge lengthened were split rather than left over the cap.**
     `overlayState.ts` (394) handed the turn fold to `overlay/turnState.ts` and `useOverlay.ts`
     (321) handed the chat catalog to `overlay/useSessionCatalog.ts`, each re-entering through the
     module it left, so no call site moved and both are back under 300. `scripts/linecap.py` scans
     `.py` and `.rs` only, so this was never a machine failure; it is the cap's actual purpose,
     which is cognitive load, and it does not care which toolchain a file is in. One overlay source
     stays over (`bridge/demoBridge.ts`, 326): its split would produce a module no test imports,
     buying 49 lines for a new coverage exclusion, and widening that list is the worse trade. Both
     the split and that refusal are recorded in
     [refinements/body-overlay.md](../refinements/body-overlay.md).

2. **A view change centres; coming BACK to the chat restores.** ADR-0034 decision 2 re-centred
   every view change, the return trip included, so a look at settings moved the conversation to
   somewhere it had never been. The chat's pinned edge is now parked when it is left and handed
   back when it is returned to. Nothing about the chat changed while it was away, so nothing about
   it should move.

3. **Another chat is not another view.** The view name carried the session id, so the pencil and
   the switcher counted as view changes and re-centred. A new or different chat is the same view
   with other content in it: it resizes from the pinned edge like any other size change.

4. **The pinned edge is remembered unclamped; the ceiling applies only on the way out.** Growth
   past the ceiling used to write the clamped edge back into memory, so the shrink that followed
   started from the ceiling and landed somewhere new. Measured: one switcher open and close moved
   the panel's bottom edge from 656 to 774 and left it there. Keeping the want and the fit apart
   makes a grow-then-shrink round trip exactly reversible. It also means a shrink while clamped
   moves the bottom edge, which is the same statement as reversibility and not a second rule.
   **That last sentence stopped being true later the same evening** and is kept here because it is
   what this decision was reasoned from. The "way out" clamp it names, `max(0, min(pinned, 0.88v -
   h))`, was replaced by `max(0, pinned)` when the panel's second bound was deleted (the 2026-07-20
   "growth caps at the top" addendum, item 1): the ceiling applies to the HEIGHT, not to the edge, so
   nothing pulls the bottom edge back when a shrink gives it room. Reversibility survives untouched,
   the pinned edge still being remembered unclamped, and the cost this sentence priced for it is
   gone. Measured and closed 2026-08-06; see the clamped-shrink addendum below.

5. **The panel takes its bottom edge along with a roll, rather than after it.** ADR-0034
   decision 5 had the panel discover at `cortex:morphend` that it had outgrown its ceiling. That
   is one movement too late: opening the switcher on a panel already at its ceiling ran the top
   edge 12px off the top of the screen and then slid the whole panel back down, and closing it
   dipped the top edge 120px and brought it back. `data-morphing` now carries the height the section is rolling TO, so the
   panel can work out how tall it is about to be and slide over that same `MORPH_ROLL_MS`. Both
   directions hold the top edge still when the panel is settled as the roll begins. When it is
   not, the panel CARRIES its interrupted ease through the roll instead of cancelling it, from
   where the eye has the panel to where the roll will leave it, over the roll's own duration and
   curve: that is the section's own curve plus a residual that decays to nothing by the end.
   Cancelling it instead handed the used height straight back to layout, which is a teleport and
   not a movement; traced at 60Hz, acking a reminder and opening the switcher 40ms later dropped
   the top edge 61px in a single frame with nothing animating it. Composing the residual on top of
   the `auto` height would be neater and is not available: measured in Chrome, an additive `height`
   animation over an `auto` height is silently demoted to replacing it. The end event stays: the
   prediction is one section's word, and re-measuring is what keeps it honest, including when the
   panel was resized by something else (a token landing mid-roll) while its height was being driven.

6. **A closing roll holds its collapsed height until React removes it.** With the Web Animations
   default `fill: "none"` the section snapped back to full size the instant the roll ended and
   painted there until the unmount landed, which the user saw as the list flashing back for a
   split second. The opening direction deliberately does not fill: its end state is the natural
   height, and holding that would freeze the section at the content it opened with.

7. **A move is paced by its distance, not given a fixed time.** At a flat 380ms the panel never
   converged during a stream: every token re-renders it, each render cancels the running ease and
   starts a fresh one, and the panel trailed the text by a whole line for the length of a reply
   (traced: content in 22px steps, the top edge crawling 6px per 200ms behind it). The duration is
   now the distance the further-travelling edge covers at one constant pace, floored at 120ms and
   capped at 380ms, with the full duration earned at 240px: the longest move the panel makes is a
   full-height chat to the console, which at a 900px viewport slides its top edge 243px, and
   rounding the pace down is what lets that move actually reach the cap rather than stop just short
   of it.
   Measured over the same streamed reply, sampling every frame for how much of the history the
   panel had not grown to fit yet: mean 1.2px and peak 35px paced, against mean 13.8px and peak
   70px with every panel move forced back to a flat 380ms in the same build, and the text fully
   visible in 573 of 661 frames against 354. The ceiling is exported rather than restated, because
   the outgoing view's fade in `Panel` is timed to outlast every resize, which is to say timed to
   exactly that number.

   Pacing does not stop the restarting, and it was first written here as though it did ("a line of
   streamed growth settles at the floor, between one token and the next"), which measurement does
   not support: tokens land about every 55ms and the floor is 120ms, so each one still cancelled
   an ease that had covered less than half its distance. Instrumented on `.panel`, one reply
   started 26 animations, and a single 23px line ran `320->343` at t=4014, `335->343` at 4069,
   `340->343` at 4124 and `341->343` at 4179, settling 285ms after the words were on screen rather
   than the 120ms claimed. What makes the floor's promise true is decision 11.

8. **A summon centres on what the panel arrives with, not on what it was before.** The edge the
   session is pinned to used to be whatever the last measurement taken while the panel was CLOSED
   centred it on, and content routinely lands behind the summon: the reminder pull is latched on
   the same rising edge of visibility, so the stack rolls open 10ms later and the panel is 190px
   taller by the time anyone sees it. Treating that as growth pinned the panel to the centre of a
   height it never displayed, 109px above its own centre, where it then sat against its ceiling
   for the whole session and every later shrink slid the composer (measured: acking one reminder
   moved it 40px). So a summon owns the panel's geometry for the length of its own 0.44s transform
   transition: placements inside that window centre, the ride-along included, so a section rolling
   in behind a summon lands the panel centred in ONE movement rather than pinning it low and
   correcting afterwards. Anything that lands later is growth and pins, which is the rule again.
   The window is a duration and not a settled-size test on purpose: "the content stopped changing"
   is indistinguishable from a pause between tokens, and a test that cannot tell them apart would
   re-centre under the user's hand.

   **It ends the moment the user touches the panel**, however much of the window is left, because
   a duration alone cannot tell the panel's own content from a section the user just opened. A
   ride-along inside the window re-pins, and a section the user opens is a height they are about
   to hand back: traced at 60Hz, `Ctrl+K` 410ms into a summon wrote a pinned edge of 117px for the
   666px the panel would be with the list open, and closing the list left a 546px panel on that
   same edge, 60px below its own centre, for the rest of the session. Nothing washes a pinned edge
   out; a trip to the console and back parks the bad one and hands it straight back. So a
   `pointerdown`, a `keydown` or a bare `click` anywhere in the window ends the arrival, in the
   capture phase so that no handler in between can hide the user's hand by stopping the event.
   Input that lands while the panel is still SHUT is what summoned it (the orb click is a real
   press a beat before the panel appears) and is not a touch, which is checked against the panel's
   own open state rather than against a timestamp, there being no race in it either way. Measured
   after, as the panel's bottom edge down a 900px viewport, where a true centre is 722.9: a
   switcher round trip started 100, 300, 450, 600 or 1500ms after the panel appeared now settles
   at 723 to 725, where the first two settled at 730 and 783 before.

   Two costs, both measured rather than reasoned about. A token that arrives inside the window and
   is not preceded by any input still centres instead of growing upward, which is a few pixels
   while the panel is still scaling in. And a touch that lands mid-roll leaves the session pinned
   to the ride-along's PREDICTED centre rather than to the height the roll actually reached, since
   the placement that would have corrected it is no longer an arrival: 2.1px at a 900px viewport,
   which is the prediction's own error and is recorded in `docs/refinements/body-overlay.md`.

9. **Heights are read off the layout box, not the rendered one.** `getBoundingClientRect` reports
   the box after transforms, and the panel is scaled through every summon (`scale(0.92)` easing to
   1, past it, and back). Every geometry taken during one was ~8% short: at boot the panel read
   327.5px tall while its layout height was 356, and the reminder stack rolled to a target 8%
   short of its own content and snapped the last 16px on when the roll ended. `offsetHeight` is
   transform-free and still follows a running height animation, so the in-flight read that all of
   this is built on survives the change. The bottom edge is still read from the rect, which is
   exact even mid-summon: `transform-origin` is the panel's own bottom edge, so only the height
   above it is scaled.

10. **A prediction is capped at the height the panel is allowed to be.** The ride-along asks how
    tall the panel is about to be, and on a full-height panel the answer came back larger than the
    viewport allows: the arithmetic was asked where a 874px panel goes in a viewport that permits
    684, said the floor of the screen, and the panel's bottom edge ran 108px down and back up over
    the roll. The cap is `max-height`, which the panel already writes to itself.

11. **A render that does not redirect the panel resumes its move; only a new destination starts a
    new one.** Decision 7 shortened the ease and left the restarting in place, and the restarting
    is what a stream does to the panel: a token lands every ~55ms, each one re-renders, and each
    render pushed the landing another floor's worth into the future. So the panel now remembers
    where the animation in the air is going and when it is due, and a placement that lands on the
    same destination animates from where the eye is to that same place over the time that was LEFT
    of it. The clock is not restarted, so a line of growth lands 120ms after it appeared however
    many tokens arrive while it is landing. Measured over one reply, same instrumentation as
    decision 7: 14 panel animations instead of 26, the 23px line now `320->343` over 120ms at
    t=4010, `335->343` over 64ms at 4065 and `341->343` over 10ms at 4120, all three landing
    together at 4130. Traced at 60Hz over the same reply, every step of growth was caught within
    2px in 99-116ms (mean lag 1.57px, peak 35px for one frame of the largest step), and the panel
    stopped moving 133ms after the last word instead of 285ms. The comparison is only meaningful
    with the pacing: resuming a flat 380ms move would land the first token's ease 380ms late and
    every one after it in the same place, which is the defect decision 7 was for.

12. **The chat has a floor, and it is the invitation it replaces.** Everything from decision 2 on
    is about how the panel moves and not about when it should not, and the user found the case:
    sending the first message *shrank* the window. The empty state (the mark, "Ask me anything", two example
    chips) is 185px of content, and a user bubble with a thinking bubble under it is less, so the
    panel dutifully eased down at the exact moment the chat began. Traced at 60Hz on the body's
    720px window: 546px to 457px over 150ms, the top edge falling 89px. The chat's column of
    bubbles therefore carries a `min-height` of that same 185px, measured off the empty state
    rather than chosen, so the first exchange cannot leave the panel smaller than the invitation
    did. Re-traced after: first frame 546, minimum 546, maximum 547, no dip at any frame.

    **The floor is on the content, not on the scroll box, and its slack sits above the bubbles.**
    Both halves are the difference between a floor and a defect. A `min-height` on `.history`
    itself cannot yield, and there is a real configuration with no room for it: the switcher and
    the reminder stack both open at 720px leave the history 76px, where a box refusing to go below
    195px pushes the composer and the hint strip out past the panel's own clipped edge (built,
    measured, and looked at, before it was written the other way). Floored *content* scrolls
    instead, which is what the empty state already did when squeezed. And the reserved height goes
    above the bubbles (`justify-content: flex-end`) because the history follows the stream by
    scrolling to its own `scrollHeight`: reserved space *under* the last bubble is space the
    auto-scroll lands on, which in the squeezed case showed 18px of a thinking bubble above an
    otherwise blank history. Bottom-aligned, the newest bubble is the tail, the exchange sits
    against the composer the way a chat should, and the empty state stays centred because
    `margin: auto` outranks `justify-content`.

    **One number can only be the floor if the empty state is one height.** The example chips were
    allowed to wrap, which is the only part of that 185px that ever depended on how wide the panel
    is: swept across viewport widths, the two labels sit on one row down to a 526px panel and take a
    second row below it, where the invitation is 224px and the floor undershoots by 39px. That was
    filed as unreachable, the overlay window being fixed at 640x720 and unresizable, and the sweep
    is what showed how thin the margin actually is: the shipping window clears the wrap by 32px of
    label width, which is a font's worth of slack rather than a proof, and the engine that ships is
    WebView2 with Segoe UI rather than the Chromium this was measured on. The chips are therefore
    held to one row and shrink to an ellipsis instead of wrapping, which takes width out of the
    arithmetic entirely (measured 185px at every width from 700px down to 440px, with nothing
    overflowing the panel), and turns the failure mode from a panel that shrinks when the user
    first uses it into a label that is a few characters shorter.

13. **A turn completing is not allowed to resize the log either.** The floor covers the first send;
    a trace of the whole exchange found the other end. At a 900px viewport the panel grew all the
    way to 582px and then eased *down* 4.4px over about 130ms at the moment the answer settled.
    Neither the floor nor the geometry: it is the frame where the live thinking chip is dropped and
    the accumulated trace reappears as the collapsed "Thoughts" disclosure
    ([ADR-0020](ADR-0020-reasoning-status.md) addendum), 24px of chip replaced by 20px of
    disclosure. Those two are one row in two states rather than two elements that happen to follow
    each other, so both are now floored on a single token (`--trace-row`, 24px, which is the chip's
    own box) and the label is centred in it, and the swap happens in place. Measured as an A/B in
    one browser session, the old heights restored by an override and the new ones beside them: the
    descent went from 4.73px over 11 frames to 0.19px over two, and the panel now ends the turn at
    its maximum height instead of 4.4px under it.

    What is left is a snap of a third of a pixel, and re-verification gave it a mechanism rather
    than a shrug. `heightOf` reads `offsetHeight`, which is a whole number, so a move retargeted
    mid-flight by the next token opens its keyframes on the rounded height while the height on
    screen is fractional. Traced at 60Hz with `element.animate` instrumented (640x720, the reminder
    stack acked, one streamed reply), every down-step of the whole exchange falls on a frame
    carrying such a call, and each opens on exactly the rounded value: 363.188 to 363 against an
    opening keyframe of `363px`, 365.344 to 365 against `365px`, 386.328 to 386 against `386px`.
    Worst step measured anywhere is 0.39px, the panel is never below its pre-send height at any
    frame in any configuration, and the fix (reading the used height with its sub-pixels) is a
    harness change across every test that fakes `offsetHeight`, so it is filed in
    `docs/refinements/body-overlay.md` rather than taken.

14. **A roll says when it starts, because not every roll is a render.** ADR-0034 decision 5 gave
    the panel two ways to learn about a section: the attribute, found by the layout effect of
    whatever render opened the section, and the end event. Both assumed the panel re-renders when
    a section does,
    which was true while every section was part of the panel's own chrome and opened on overlay
    state. The user's "there is no animation when expanding thoughts" broke that assumption twice
    over. Rebuilding the trace's disclosure on `Collapse` (a button carrying `aria-expanded` over a
    rolling section, since `<details>` reveals its content in one frame and cannot be talked into
    animating it) put a rolling section inside a message, and a message's disclosure owns its open
    state locally: clicking it renders that message and nothing above it. Traced at 60Hz at a 900px
    viewport, the trace rolled open over its 300ms with the panel's `auto` height following it, and
    then the panel, hearing only the end and placing itself from the geometry it had remembered
    from before the roll, snapped back to its old height for a frame and eased 76px up and 43px
    down a second time. So `Collapse` now dispatches a bubbling `cortex:morphstart` as well, after
    the attribute is set. That ordering is the whole of what the panel depends on: the attribute is
    where the roll publishes the height it is going to, and a listener arriving before it finds
    nothing rolling at all (moved above the `setAttribute`, `Collapse.test.tsx`'s start-event test
    fails). Where the dispatch falls relative to the height animation is NOT part of the contract,
    and an earlier draft of this decision claimed it was, on the grounds that a listener should
    measure the section at the height the roll begins from. It cancels: the ride-along predicts the
    panel's coming height as what it is now, less what the section takes now, plus the target, so a
    listener before the animation reads 464 less 76 plus 76 and one after it reads 388 less 0 plus
    76, both 464. Measured both ways in Chromium at a 900px viewport, with the suite green either
    way and the two 60Hz traces of the panel frame for frame identical. The skip paths announce
    nothing, there being no roll to ride along with. The panel reads what it is placing FOR out of a
    ref assigned during the render rather than out of each handler's closure, because this event
    alone arrives from inside a layout effect, before any passive effect of that render has
    re-subscribed: the handler that hears a roll announced mid-commit is the PREVIOUS render's, so a
    closure over its props would place the panel for the render before the one on screen. The case
    that makes that reachable is one commit that both summons the panel and rolls a section, which
    `newChat` and `openSession` produce by setting `mode: "panel"` and `switcherOpen: false`
    together: Ctrl+N or a chat cycled to while the panel is minimized with the switcher list open.
    Reverting the ref to a closure and tracing that at 60Hz in a 900px viewport shows what is at
    stake: the list rolls shut over its full 300ms with the panel's bottom edge pinned where the
    minimized session left it, its top edge diving 63px and climbing back, and only once the roll
    has landed does the panel travel, snapping the composer 59px up the screen between 304ms and
    454ms. With the ref, the bottom edge eases 783 to 723 across the roll itself and the composer
    arrives with it, one movement landing at 354ms. Held by `usePanelMotion.test.ts`, which
    announces the roll from a layout effect declared ahead of the hook, that being a child effect's
    phase and order, and fails on the reverted hook by the same 100px the browser shows. Re-traced
    after: opening the trace is one movement (top 141 to 108, bottom 723 to 766, both monotonic,
    landing together at 340ms), closing is its exact reverse, and the switcher's own round trip is
    unchanged to the pixel.

15. **The history's scroll position has one user, so scroll anchoring is off in it.** Two things in
    this repo decide that number: `ChatView` holds the log at its tail while the reader is at the
    tail, and decision 14's roll deliberately leaves it alone so the row stays under the pointer
    that opened it. Chromium's scroll anchoring is a third, and the roll is the only mid-log resize
    in the overlay for it to react to, everything else in the history growing at the tail and the
    other two rolling sections living in the panel's chrome outside it. Where it did act, it acted
    badly: a roll measures its content at full height and then animates from zero, which the anchor
    reads as the log shrinking. Traced at 640x720 with the oldest reply's trace scrolled out of the
    window and opened by script, `scrollTop` fell 498 to 422 in a single frame and climbed back over
    the roll, the whole log lurching 76px down and creeping back up. Only a script reaches that: a
    pointer click on a row at mid window traced 19 for every frame of both directions, one straddling
    the top edge 71, and the newest reply's trace with the log parked at its tail 498, while focusing
    an offscreen row scrolls it into view first (498 to 0, the row visible before any activation), so
    neither hand nor keyboard can produce the condition. It is taken anyway, because on those paths
    the stillness is currently a property of which node the engine chose to anchor on rather than of
    anything written down, and the body ships on a WebView2 version this repo cannot trace.
    `overflow-anchor: none` on `.history` makes the traced lurch read 498 on every frame of both
    directions, and the log's own policy is untouched: a reader at the tail still follows a fresh
    reply (`scrollTop` 730 of a 730 maximum) and one scrolled up still holds place (120 before and
    after). What is given up is anchoring's genuine service in the closing direction, where it had
    been easing `scrollTop` down with the shrink (498 to 422 across the roll) to hold the visible
    content still. Without it, the content under a closing offscreen trace slides up by the height
    of it, which is exactly what the opening direction already does and the symmetric half of
    decision 14. Doing that deliberately, by animating the scroll on the roll's own clock, is the
    refinement already filed for the same box in `docs/refinements/body-overlay.md`.

16. **The ceiling is a whole number of pixels, because the same number is written to the DOM and
    then predicted against.** `maxHeight` had one caller round it on the way out to `max-height` and
    another (`rideAlong`, capping its prediction) take it raw, which at 640x720 is 547 against
    547.2: the panel stood at one ceiling and was placed for another. A fifth of a pixel is nothing
    to animate, `MIN_DELTA_PX` being 2, so nothing ever eased it away, while the bottom edge IS
    written rounded and 86.6 and 86.4 round apart. Traced at 60Hz at
    640x720 with the reminder stack up, so the panel sat at its ceiling: every roll of a section
    inside it began with `bottom` stepping 87 to 86 in a single frame with nothing animating it, and
    stepped back the frame the roll ended. Both directions, a Thoughts trace and the chat switcher
    alike, since neither the section nor the view had anything to do with it. Rounding at the source
    settles both callers by construction and is what the ratio's own note asked for from the start
    (the ceiling is owned in `panelGeometry` rather than in CSS precisely so the two cannot drift),
    and it leaves the panel's box reading one value for every frame of every roll. This is NOT
    decision 13's leftover third of a pixel: that one is `offsetHeight` against a fractional used
    height while a stream retargets a move, it does not occur at the ceiling at all, and it stays
    filed. Pinned by "caps that prediction at the same whole-pixel ceiling the element was given"
    (`overlay/usePanelMotion.test.ts`), which reads 86 against the fractional ceiling and 87 against
    the rounded one, a viewport of 720 being the case a 1000px test viewport cannot see.

17. **Past one line the composer becomes two rows, because the send button's reserved column is
    only invisible on one of them.** The button is a flex sibling of the field, so it holds a 44px
    column down the WHOLE pill. On one line that reads as the field simply ending where the button
    begins. On several it reads as every wrapped line stopping short of the right edge for no
    visible reason, and at the field's 120px ceiling as a button floating alone at the bottom of a
    tall empty column. Past one line the pill restacks: the field spans it and the button drops to
    its own row beneath, still at the end. Measured at the panel's 560px the field goes from 475px
    to 519px wide, and the pill's two insets then agree at 16px a side, the far one being the
    field's 6px padding plus the 6px scrollbar gutter decision 22's rail reserves. **The button does
    not move.** Both layouts put it in the same corner of the same content box (`align-items:
    flex-end` down a row, `align-self: flex-end` at the end of a column) and the pill's bottom edge
    is pinned by the panel's own bottom anchor, so its rect is identical in both: traced character
    by character over two different lines of 91 and 92 characters, it read `[671,637,38,38]` in
    every one of the 183 samples, and each line's layout flipped exactly once. A rAF trace across
    the flipping character shows two distinct states and no third, so the restack lands in one
    frame.

    **Which layout to use is decided at one width, the inline one, whatever layout is on screen.**
    Asked at the width in use, the two layouts answer each other: a stacked field is 44px wider, so
    a draft that has just wrapped fits on one line again the moment the button leaves its side,
    which unstacks it, re-wraps it, and stacks it again. That band is measured, not theoretical:
    in Chromium at the panel's 560px a line of prose needs two lines inline and one stacked for
    five or six characters, and WHERE it starts is a property of the glyphs on the line rather than
    a constant. Two lines traced character by character, both at that width: one stacked at
    character 60 and showed its second line at 66, the other stacked at 62 and showed its second at
    67. Deciding at the inline width makes the layout a function of the text alone, so it cannot
    chase itself, and the band's cost becomes a pill that is one row roomier than its text needs
    for those few characters. **That cost is a resting state, not a flicker**, and it is worth
    saying plainly because it is the one thing here a user can sit and look at: a draft anywhere
    in that band (60 through 65 characters on the first line traced, 62 through 66 on the second)
    parks the pill stacked with a single visible line of text and an empty 38px row under it
    (`composer stacked`, field 34px, looked at). It is chosen anyway. The
    alternative is not a tighter pill, it is the original defect inside that same band, arriving and
    leaving under the hand. Deciding at the stacked width instead would put the original
    defect back inside the same band, which is the worse of the two. The one-line height is
    measured rather than assumed: a `rows={1}` textarea's auto height IS one row, so
    `scrollHeight > clientHeight` at `height: auto` asks the question with no font metric, line
    height or padding restated in TypeScript, and a long line that wrapped counts exactly like a
    typed newline. The pill's transition became named properties rather than `all` in the same
    change: the decision takes the class off and puts it back inside one layout effect, which an
    `all` transition read as a gap change starting over on every keystroke, wobbling the pill's top
    edge by about 2px per character until it was scoped to colour.

18. **The pill's growth is the log's loss, so the log holds its own tail across it, and the
    measurement that sizes the pill is not allowed to be observable.** Decision 17 made the
    composer up to 122px taller than it was, and the composer and the scrolling history are flex
    siblings in one column where the history is the child that yields. Every pixel the pill takes
    is a pixel of visible log, and the engine leaves `scrollTop` where it was rather than where the
    tail went, so the newest reply drifts out of view under a reader who is typing their answer to
    it. Measured at 640x720 with a two-turn chat and the panel at its ceiling: a wrapped draft left
    the log 52px past its tail (the last reply clipped mid-line, looked at) and a draft at the
    field's 120px ceiling 122px, which showed the middle of an old bubble and none of the reply.
    Two halves, and both were needed:

    - **The composer announces its own resize and the chat re-pins.** `Composer` measures the pill
      after every layout pass and calls `onResize` only when the height actually changed, and
      `ChatView` answers it with the same "scroll to the tail if the reader is at the tail" it
      already uses for a new message, reader override included. It is a callback and not a
      `ResizeObserver` on the log, because the log also resizes when a Thoughts trace rolls open,
      and decision 15 deliberately leaves `scrollTop` alone there so the row stays under the
      pointer that opened it. Naming the one cause keeps that decision intact. It is not a lift of
      the draft into `Panel` either: that would call the placement hook on every keystroke, which
      is the one thing decision 8 says must never re-centre the panel.
    - **The measurement pins the pill's floor while it runs.** Deciding the layout at the inline
      width means taking the class off, collapsing the field, reading, and putting it all back
      inside one layout effect. That is a real relayout of the whole panel, and an unpainted
      relayout costs nothing until one of them touches state that outlives the frame. This one
      does. At the ceiling the flex column is in deficit and every child gives up what it can; the
      pill keeps its height only because its automatic minimum IS that height, and dropping the
      class drops that minimum to a single row. Traced from inside the effect: the pill read 100px
      on entry, 75px with the class off, 100px again on exit, with the log 144, 169, 144 around it
      and its `scrollTop` clamped by Chromium to the 169px reading and never given back. So every
      keystroke AFTER the one that grew the pill walked the reply back off the edge, 25px at a
      time, and the first half above could not see it happen. `min-height` for the length of the
      measurement is the exact counter, since the automatic minimum is the thing that moves, and it
      cannot change the answer because the question is about the field's width.

    Verified at 640x720 with two turns and the panel at its ceiling: the log ends at its tail
    (offset 0) for a one-line draft, a pasted wrapped draft, a draft typed character by character
    past the wrap, a draft at the field's ceiling, and a cleared field. Before, the same five read
    0, 52, 52, 122, 0.

19. **When the column runs out, the draft's WINDOW pays, not the panel's edge.** Decision 18 spent
    the pill's growth out of the log, which works while the log has room to give. It runs out. At
    the body's own 640x720 window, with a new chat, the switcher open and the reminder stack up,
    the history is already down to its own padding (10px) and a draft pasted to the field's 120px
    ceiling had nowhere left to take from: the pill's bottom edge cleared the panel's clipped edge
    by 12.75px and the whole hint strip by 54.75px, so the writer lost the send button and every
    shortcut at once. This is decision 12's failure mode arriving by the other door, and the
    restack widened it: the same field height posed in the pre-restack inline layout (the button
    beside the field, no button row) leaves a 130px pill inside the panel with the hint strip
    clipped by 14.75px, so the restack turned "half the hint strip" into "the pill and all of it".
    All three measured in one browser session, the old rules injected back over the new ones in the
    same page.

    The draft's window is the right thing to spend, because it is the one box here that already
    scrolls: past 120px the field scrolls itself, so a shorter window shows fewer lines of the same
    text and loses nothing, where the alternative is chrome that is not on screen. Three
    declarations, and each one is load bearing:

    - **The stacked pill gets an explicit `min-height` of 84px, which REPLACES its automatic
      minimum** (a flex item's automatic minimum is its content, which is why it could not yield a
      pixel). 84px is one row of field plus the button's row, read off the boxes rather than
      asserted: 34px field + 38px button + 2px row gap + 8px padding + 2px border. It has to be
      exactly that and not a pixel more, since a floor above it shows up in decision 17's band as a
      taller resting pill (85px was tried first and did precisely that, and it moved the send
      button by 1px across the restack). And it has to exist: left free to shrink, the pill
      collapsed to 10px under a big enough deficit and spilled its own text 29px above itself and
      its button 69px below, which is worse than the clipping it replaces.
    - **The stacked field's `flex: none` becomes `flex: 0 1 auto`**, keeping the measured height as
      the basis (decision 17's reason for `none` was the basis, not the shrink) and giving back
      only the shrink. That is what makes the pill pay out of the field rather than out of the
      button's row: with the shrink left at 0 the pill shrank anyway, the field kept all 120px and
      hung 11px below the pill with the button 51px outside it.
    - **The history's shrink factor becomes an ordering, `flex: 1 100000 auto`.** Flexbox has no
      "shrink last", so the priority is spelled as a weight, and the weight has to be large because
      the alternative is a pill paying its share of every deficit at rest: at a factor of 1 the
      pill came out 42px under its own content (105.81px where its text wanted 148px) on the canned
      chat with the reminder stack up, a deficit the history could have covered alone. The share
      left to the pill is bounded by its base over the factor, under a five-hundredth of a pixel,
      and a sweep showed 1000 still costing 0.078px and 10000 costing 0.016px.

    **Wherever there is room, nothing moved.** Bit-identical at 640x720 with the old rules injected
    back over the new: empty and one-line 48px pill / 34px field, two lines 100/50, the field's
    ceiling with the switcher shut 170/120, and the canned chat at the panel's ceiling 148/98 with
    the history at 96.25px. In the squeezed case the pill lands at 114.25px with a 64.25px field
    scrolling inside it, and the hint strip clears the panel's edge by the same 1px it clears it by
    with no draft at all. **The yield is not a jump either**: rAF-traced across a switcher roll
    under a tall draft, the pill eases 148px to 114.25px over 55 frames on the roll's own clock and
    comes back 114.25px to 148px when it rolls shut, with the hint strip 1px inside the panel in
    every frame of both.

    What is left is a panel whose sections alone outrun it: the switcher's `40vh` and the reminder
    stack's `30vh` are 504px of a 547px panel at 720px, and once the pill is at its floor there is
    nothing else to give. Forced with a 300px ceiling, the pill floors at 84px with its text and
    its button inside it and the hint strip 34.75px out, so the degradation is bounded and it is
    the old one. Recorded in `docs/refinements/body-overlay.md`.

20. **A window that cuts a line fades it, and the writer's line is never the faded one.** Decision
    19 spends a deficit out of the draft's window, and the ceiling spends the same way: past 120px
    the field scrolls itself. Neither bound is a whole number of line boxes, so the edge line was
    sliced horizontally through its glyphs, and the slice is not exotic. Looked at twice at the
    body's 640x720: squeezed by an open switcher under a draft at the ceiling (a 64.25px field in a
    114.25px pill, whose fourth line is cut through its middle), and at the plain ceiling with no
    switcher at all, where a caret on the last line put Chromium's scroll at 17 of a possible 26 and
    the slice at the TOP edge instead. Both read as a rendering fault rather than as a window onto
    more text. Two declarations on `.field` answer it, and they are a pair:

    - **`mask-image` fades the field's own padding band at each end**, so a line the window cuts
      dissolves into the pill instead of being guillotined, and the fade says the true thing about
      why it is there. The band IS the padding, which is what makes it free: with the text inside
      its window those 9px hold nothing but padding, so there is nothing for the mask to act on.
      Diffed in Chromium against the same paint with the rules off, an empty pill is bit-identical
      and a one-line pill moves by at most 7 of 255 on 0.6% of its pixels, which is the composited
      layer's antialiasing rather than the fade.
    - **`scroll-padding-block` keeps the writer's line out of that band.** Chromium scrolls a caret
      flush to the edge it moved toward, so without it the line being typed is the line being
      faded. Declaring the field's own padding as its scroll padding moves the reading above to 26
      with the caret on the last line, and to 0 rather than 9 with the caret walked back to the
      first, so the caret's line always keeps its padding and the fade only ever eats text that is
      genuinely outside the window.

    The fade is about the scroll and not about the line it lands on, which is worth saying because
    it is visible: a line that happens to sit fully inside the window with more text below it is
    dimmed across its bottom band, looked at in both themes on the squeezed pill. That reads as
    "more below", which is exactly what is true there, where the same band on the last line of a
    draft that ends inside the window fades nothing at all.

    Quantizing the window instead was considered and measured away. Nothing in CSS snaps a flex
    shrink to a multiple of a line box, so it would have to be a `ResizeObserver` writing a
    line-multiple cap, and that observer fires on every frame of the switcher's roll, which decision
    19 traced easing the pill 148px to 114.25px over 55 frames: the field would step through it in
    16px jumps and take the send button with it. A fade costs no frame and no layout.

    **The line box is pinned in the same change** (`line-height: 16px`, which is what `normal`
    computes to for this stack). The 34px one-line field, decision 19's 84px floor and the fade band
    are all read off that 16px, and a host whose font stack falls back to other metrics would have
    moved all three at once. Pinning it moves nothing here: measured against the same page with the
    rules reverted, every box is identical in all four states (48/34 empty and one line, 100/50 two
    lines, 170/120 at the ceiling, 114.25/64.25 squeezed) and the send button is at the same place
    in every one.

21. **The measurement re-runs when the width moves, not only when the text does.** Decision 17's
    question is asked of the text AND of the width it is laid out at, and `Composer` only asked it
    on a keystroke, so a panel that narrowed under a standing draft kept both answers from the width
    it no longer has. Traced at 900x900: a one-line draft measured at 34px stayed at 34px with
    `scrollHeight` at 50 after the viewport went to 380px, which is a field scrolled inside a box
    sized for a line that no longer fits, in a pill still inline with a draft that now wraps; one
    further keystroke repaired it. The measurement moved into a `useCallback` that a `resize`
    listener calls as well, and the same trace now reads 100px/50px stacked the moment the viewport
    moves and 48/34 inline on the way back. The body's own window is fixed at 640x720 and cannot
    resize, so this is not reachable there today; the panel is `min(560px, 92vw)` and every other
    way that number can move (a zoom, a window allowed to resize, a second platform) arrives through
    the same event. The listener is removed on unmount, which is not hygiene: React nulls the two
    refs the measurement writes through, so a listener left behind throws on the first resize after
    the panel is gone (pinned by a test that fails with exactly that `TypeError` when the cleanup is
    dropped).

22. **A scrollbar is reserved chrome, and it never borrows the content's width.** Only `.history`
    was styled at all, and its 7px thumb took real layout width, so the log jumped sideways the
    first time a reply overflowed; the other six scroll regions wore the platform default. All
    seven now wear one quiet rail (`--rail`, 6px) and, more importantly, **reserve** it permanently
    (`scrollbar-gutter: stable`), so overflowing changes nothing about where content sits. Each
    container funds the rail out of its own inline-end padding, subtracted where there was enough
    to spare and added beside it where there was not, so no resting margin moved. This is
    `src/overlay.css` only: no behaviour and no component changed. The rule and its arithmetic live
    in [overlay-ux.md §2](../design/overlay-ux.md), and what a future eighth container has to do
    lives in [body-app.md](../modules/body-app.md).

    **Reserving a gutter answers one axis, so the other one is closed off instead.**
    `scrollbar-gutter: stable` reserves the inline-end band, which means a **horizontal** bar is
    never paid for: it takes its height out of the content box and pushes every child up, the same
    defect turned ninety degrees. `.history` had it. A bubble was the one scroll-container child in
    the file without `overflow-wrap: anywhere`, so a 64-char commit hash or a
    `gemma-3-12b-…-Q4_K_M.gguf` filename ran past its 82% max-width and grew the log a horizontal
    bar, costing 6px of log height and lifting every bubble by that much (measured at 900x900:
    `.history` `offsetHeight` 300 against `clientHeight` 294, `scrollWidth` 689 against
    `clientWidth` 552). The answer is not a second reserved gutter, which would be a permanently
    blank strip under every section for a bar that should not exist, but making sideways growth
    impossible: the bubble now breaks long tokens like its four siblings, the per-word streaming
    span (`.w`) moved from `white-space: pre` to `pre-wrap` so that break can reach the text inside
    an inline-block (measured: identical box for every one of 49 words of ordinary reply, so the
    reveal is untouched), and `.history` carries `overflow-x: clip` so content nobody has written
    yet cannot bring it back. After: `offsetHeight` equals `clientHeight` at 294, `scrollWidth`
    equals `clientWidth` at 552, on both the bare-text and the real per-word DOM.

23. **The connection dot opens the button cluster, and the title takes the row.** The link dot led
    the header from the day it landed ([ADR-0011](ADR-0011-body-v1.md) addendum, 2026-07-16); the
    user's direction is that it belongs beside the "Recent chats" button instead. The capture ring
    (ADR-0029) moved with it, because the two are **one row of state** rather than two ornaments:
    alone beside the title the ring would be the only mark there, appearing and vanishing with
    every capture, while at the head of the buttons the pair reads as "what the panel currently is"
    next to "what you can do to it". Neither indicator keeps an optical margin now that it sits
    mid-row, which supersedes ADR-0011's 2026-07-03 line about the title's 6px margin; both ride
    the header's own 10px gap. `components/ChatView.tsx` and the `.head` block of `src/overlay.css`
    carry it, and no component, state or accessible name changed.

    The title's inset is the part worth recording. It carries `margin-left: 14px`, so its first
    glyph sits **31px** from the panel's outer edge, against the 40px the old dot-first arrangement
    spent (1px border + 16px header padding + the dot's 6px margin + a 7px dot + the 10px gap) and
    the 17px the header's bare padding would give. 31px is what the 28px corner asks for twice
    over: the title's centre is already 31px below the top edge, so the text starts as far from the
    side of the panel as from the top of it, on the corner's own 45-degree diagonal; and 31px is
    where a switcher row's title already starts, with an assistant bubble's glyph at 32px and the
    composer's text at 33px (measured in Chromium at the panel's 560px), so the open chat's title
    shares a left edge with the list of the other chats that rolls open directly beneath it. The
    rule is scoped to `.head > .title:first-child`, since every other view's header opens with the
    back button, which supplies its own inset. Full arithmetic and the design rationale live in
    [overlay-ux.md §3](../design/overlay-ux.md) and [body-app.md](../modules/body-app.md).

## Consequences

- A console tab cannot be dismissed by clicking a backdrop, because there is no backdrop any more.
  That was already true of the two views this merge replaced
  ([ADR-0034](ADR-0034-panel-views.md)'s first consequence); what is new is that there is one thing
  to leave rather than two stacked, so Esc closes it in a single press and the header's chevron is
  the visible way back.
- **Three doors close the console and a fourth walks past it.** Esc, the chevron and `dismiss` all
  clear `consoleTab`; `newChat` does not, so Ctrl+N mints the session and empties the chat behind a
  console that stays on screen (measured at 900x900 after the merge, and true of the two sheets the
  merge replaced, neither of which `newChat` cleared either). The merge neither caused it nor fixed
  it, and which way it should go is a question for the user rather than a defect, so it is recorded
  in [refinements/body-overlay.md](../refinements/body-overlay.md).
- **The panel's geometry went from one hook to four modules beside it.** `overlay/panelGeometry.ts`
  is the pure arithmetic (the clamp, the centre, the whole-pixel ceiling and the pacing, no DOM in
  any of it), `overlay/panelMemory.ts` is what the panel remembers between placements and how it
  reads its own box, `overlay/panelRide.ts` is the slide alongside a section's roll, and
  `overlay/panelPlacement.ts` decides where the panel belongs. `usePanelMotion` is left with the one
  question of WHEN to place it. The same pressure split two state modules (decision 1's last
  bullet), which is the 300-line cap doing its actual job on a toolchain no scanner covers.
- **The panel listens for input it never reads.** Decision 8's touch is three capture-phase window
  listeners whose handler takes no argument and only notes that the user is there. They are the
  one thing in this hook that is not a render, and they are deliberately blunt: any press, any key,
  anywhere. Something finer (only the controls that resize the panel) would be a list to keep in
  step with the panel's chrome, and it would still be wrong about the composer, where typing is
  exactly the case that must not re-centre.
- **A shrink while the panel is against its ceiling moves the bottom edge, and the composer with
  it.** That is decision 4 restated rather than a second rule: an unclamped pinned edge is what
  makes the switcher's round trip reversible, and it is also what pulls the panel back toward that
  edge as soon as a shrink gives it room. Decision 8 is what keeps it rare, since a correctly
  pinned panel has to grow 615px at a 900px viewport before the ceiling binds at all: measured
  after it, acking a reminder, the pencil on a chat with a full reply in it, and a switcher round
  trip all move the composer 0px, where before decision 8 they moved it 40, 13 and 3. It still
  bites on a conversation tall enough to reach the ceiling, and the alternative (re-pinning to the
  clamped edge, and saving the pre-roll edge per section to hand back when it rolls shut) is a
  design the user has not been asked for. Recorded in `docs/refinements/body-overlay.md`.
  - **This consequence was already false when it was written, and its rarity number was wrong on
    top of that. Corrected 2026-08-06** (clamped-shrink addendum below). The edge clamp it depends
    on was deleted later the same evening by the "growth caps at the top" addendum's first item, so
    a clamped shrink moves nothing: the
    ceiling caps the height and the history gives the room up. And 615 is not a growth delta but the
    CEILING'S VALUE for a 546px panel centred at 900px, which has 69px of headroom, not 615. Real
    headroom is `0.88v - (v - h)/2 - h`, at 900px `342 - h/2`, so at most 342px for any panel and
    0px at `openHeight(900) = 684`. The 0px measurements after decision 8 are the only part of this
    bullet that still reads true, and they read true for the other reason.
- The hook is driven by renders and by the roll's end event and by nothing else, so a panel resized
  by neither keeps a placement computed for the height it used to have. The demo's canned chat
  settles 1.9px after its last render, which now reads as at most 1px of the centre it should have
  been given, the placement being centred rather than derived from the ceiling. Recorded in
  `docs/refinements/body-overlay.md`.
- **Decision 12's floor is a number in a stylesheet, so the empty state and the floor can drift
  apart.** Nothing checks that 185px is still what `.empty` renders to; a heavier mark or a third
  example chip makes the panel dip again by the difference, and a lighter one buys dead space.
  Width is no longer one of the inputs, since the chips are held to one row, so what remains is
  content and the engine: 185px was measured on Chromium under Linux and the body renders on
  WebView2 with Segoe UI, where a line box or a chip's padding could come out a pixel or two
  different. The cost of being wrong is a few pixels, the number is commented with the arithmetic
  it came from, and one structural test keeps the column the floor sits on from being refactored
  away. Measuring the rendered empty state once and publishing it as a custom property is the
  version that cannot drift, and it is the same probe decision 22's assumed rail width wants.
  Recorded in `docs/refinements/body-overlay.md`.
- **Decision 13 matches two heights by hand, which is the same kind of frozen number one level
  down.** `--trace-row` is the chip's box written out, so changing the chip's padding, border or
  font size grows the chip past the token and leaves the settled row short by the difference
  again. The token's comment says so, and `Message.test.tsx` pins the half a stylesheet cannot
  defend: that the two really are one row in two states, the disclosure standing exactly where the
  chip stood. The same startup probe would retire this one too, by reading the chip instead of
  restating it.
- **Decision 19's 84px pill floor is the third of those hand-measured numbers, and the least costly
  to get wrong.** It is one row of field plus the button's row, measured on Chromium under Linux,
  and the body renders on WebView2 with Segoe UI where a line box could come out a pixel different.
  Too high and a stacked draft in decision 17's band rests a pixel taller than its content (which
  is how 85px was caught, by the send button moving 1px across the restack); too low and a squeezed
  pill clips a pixel off its own single row, inside the field's own scroll box rather than over the
  panel. The startup probe that would publish the empty state's height would publish this one too.
- **A squeezed panel now shrinks the draft's visible window under the writer's hand.** That is
  decision 19's trade, taken deliberately: at the body's window with the switcher open and the
  reminder stack up, a draft at the field's ceiling shows a 64px window instead of 120px and the
  field scrolls to make up the difference, exactly as it already does past 120px. It is the
  exchange the history has been making all along, one step further down the column, and what was
  measured beside it is a send button and a hint strip off the bottom of the panel. Worth a
  user's eye, since they are the ones who can say whether a shorter draft window reads as tight
  or as broken.
- **A trace opening on a panel at its ceiling pushes the reply below the fold.** Decision 14's roll
  leaves the history's `scrollTop` alone, which keeps the row exactly under the pointer that clicked
  it and unfolds the trace beneath, where a disclosure belongs. While the panel can still grow,
  nothing scrolls at all. Where it cannot, the scroll box absorbs the growth and everything under
  the trace slides down by the height of it: measured at 640x720 with the reminder stack up, the
  disclosure's top edge held for every frame and the tail went 76px out of view, or the whole reply
  with a trace at its `28vh` cap. Following the tail instead is the wrong fix, since that scrolls
  the trace's own top edge away as it grows. The right one is a scroll animation sharing the roll's
  clock and curve, moving by as much of the growth as falls below the fold and no more, and it is
  recorded in `docs/refinements/body-overlay.md`.
- **The reserved slack sits above the bubbles, so a first send into an otherwise empty panel shows
  it.** With the reminder stack dismissed, the user bubble and the reply sit against the composer
  with roughly the empty state's height blank above them until the conversation grows into it. That
  is the deliberate cost of decision 12's alignment, not a side effect: the alternative puts the
  slack under the last bubble, where `scrollTop = scrollHeight` scrolls the newest bubble out of
  sight to reach it. Worth a user's eye rather than a fix, since the fix is the defect.
- **Decision 22 buys stillness with two tradeoffs it does not solve**, both recorded in
  [refinements/body-overlay.md](../refinements/body-overlay.md). The rail's width is **assumed,
  not measured**: every container's padding arithmetic takes the reserved band to be `--rail`,
  which is true wherever `::-webkit-scrollbar` sets it. Chromium honours `scrollbar-width` **over**
  the pseudo-elements when both are set (measured: `thin` beside the 6px webkit rail reserves
  10px), so the standards path is fenced behind `@supports not selector(::-webkit-scrollbar)` and
  reaches only engines that have no pseudo-elements. On those the UA picks `thin`'s width, the
  subtractions do not balance, and the inline-end margin reads wider than the other side. Nothing
  shifts there either, which is the property that was asked for; exact symmetry is what is
  deferred, on an engine the body does not run on. And **the two 6px cards spend their whole inset
  on the rail**: the switcher and the reminder stack pad by exactly one rail, so their inline-end
  padding goes to zero and the reserved gutter becomes the inset. Their resting geometry is
  unchanged, and the cost is that a row's box reaches the reserved band, the painted thumb clearing
  the right-most child box by 1px. Only the box does: the hairline between two reminders is a
  border-top on a 12px-radius row, so it curves away and fades out nine columns clear of the thumb,
  and text and controls stay 9px to 11px clear on the rows' own padding. It bites if a row ever
  drops that padding, or if the maintainer reads the rail as touching the chrome.

## Addendum, 2026-07-20: four corrections from a maintainer pass

Each of these is small and each replaced something that had been reasoned about rather than looked
at, which is why they are recorded together.

1. **The console's header is one line: the way back, then the tab strip.** It had a title, a cross
   and a strip beneath them, which is three tellings of "you are in settings" stacked in a panel
   short enough that a row it does not need is a row you notice. The title went, the cross became
   the back chevron on the left, and the strip moved up beside it, centred by a spacer the width of
   that chevron. `components/PanelView.tsx` existed to hold the title-and-close chrome for two
   views; there is one view now and it owns its own header, so that file is gone.

2. **The chat title sits on the header's own 16px padding.** It had carried 14px more, argued from
   the panel's 28px corner and from a text rail the switcher rows share. Looked at rather than
   derived, 31px reads as a gap, not as balance. The right inset is the header's padding on the
   other side, so the two now match by construction.

3. **The mark is called the Bubble.** "Mark" named the implementation. What the user is choosing
   is a soap bubble, and the design language calls the whole identity bubbly
   ([overlay-ux.md](../design/overlay-ux.md) §1), so the setting is named after the thing on screen.
   The line under each group of tiles is centred under them too: it explains the group, and ranged
   left it read as a caption for the leftmost swatch.

4. **Dismissing leaves the console open; the next summon closes it.** Clearing the tab on dismiss
   changed the view in the same frame the panel started fading, so it morphed back to the chat under
   a window that was already going, which reads as the panel changing its mind on the way out.
   Traced at 60Hz: the live view now stays the console for the whole fade, opacity 1 to 0 over
   ~300ms, and the summon after it lands on the chat. The invariant the old code was protecting (a
   re-summon never opens onto stale settings) is unchanged; it is enforced on the way IN instead,
   which is the only side where it is observable.

## Addendum, 2026-07-20: growth caps at the top, and seven smaller corrections

1. **The panel grows upward or not at all.** It had two bounds, a flat maximum height and clear
   space kept at the top, and together they meant a panel that reached the top kept growing
   DOWNWARD to reach its height, walking the composer back down the screen. There is one bound now,
   the clear space, and it is applied to the HEIGHT: at the ceiling the panel stops getting taller
   and the history scrolls. Traced at 60Hz through a streamed reply: the bottom edge held one value
   for the entire stream, and the top edge stopped exactly on the 12% line.

   The cap depends on the bottom edge and the edge depends on the height, so both are decided in
   one pass: measure under the loosest cap either could allow (which is the tallest a CENTRED panel
   can be, `0.76v`, since that is what the ceiling permits once the centring is solved), work the
   edge out, then apply the real cap. Sizing the cap from the previous edge lags one render, and the
   lag was visible: a summon centred for the height it had at that instant, and the reminder stack
   landing after it grew upward from an edge chosen for a shorter panel, leaving the empty chat 82px
   below centre and scrolling at 520px where 604 would have fitted.

2. **No scrollbar for a size the panel is only passing through.** Mid-ease the panel is shorter than
   what it is easing to, so the history overflows for a few frames and flashes a thumb during every
   streamed line. The panel marks itself `data-resizing` while a move is in the air and the
   stylesheet hides the thumb for the duration. The thumb, not the overflow: `overflow: hidden`
   would also freeze `scrollTop`, which the auto-scroll writes to on every token.

3. **The reminder stack belongs to the empty chat.** It rolls away when the first message is sent or
   a chat is opened, through the same `Collapse` it arrived by.

4. **The chat title's two clearances are equal.** Measured rather than argued: on the header's bare
   padding the glyphs start 17px in and 27px down, so 10px of inset makes both 27px.

5. **The tab strip sits on the chevron's centre line.** It carried block margins from when it lived
   under a header rather than in one, and overriding only its inline sides left them: measured, the
   strip's centre was 4px above the chevron's.

6. **Shift is spelled out**, in the hint strip and the shortcut tab alike. Its glyph was the one
   modifier you had to recognise rather than read, sitting beside Ctrl and Alt as words. The drawn
   caps left are the keys with no name worth writing: return, and the two cycle arrows.

7. **The mark setting is the Iris**, after the rainbow in a soap film, which is both the thing being
   chosen and a word that sits beside Cortex. "Mark" named the implementation.

8. **The Auto tile is not captioned.** A line of prose under three pictures explaining the word on
   one of them is the picture explained to someone who has just looked at it.

## Addendum, 2026-07-20: four corrections from a second maintainer pass

1. **Two tabs share one height only while they are close, and the number saying so is
   `TAB_SPREAD_PX` in `components/ConsoleView.tsx`.** Both tabs are mounted and stacked in one grid
   cell, so the taller decides the panel's height and a tab switch resizes nothing. That was
   written as a rule with no number, on the grounds that the two tabs that ship are 12px apart
   (measured in Chromium at 640x720: the appearance tab wants 278px, the shortcut list 290px) and a
   window that jumps 12px and back reads as a flinch. It stops being right for a tab that is
   genuinely shorter, where the panel holds a band of empty space under the content and the window
   is lying about how much is in it. Past 15px the pane not on screen leaves the flow, the cell is
   left to the pane that is, and the panel morphs between the two heights as it does for any other
   size change inside a view.

   The two are measured rather than declared, in a pose the stack does not otherwise hold: a pane
   stretched to the cell reports the cell's height, which is the taller pane's, so unstretched is
   the only way the difference is visible at all. One synchronous read in a layout effect, which
   React runs before the panel's own, so the height the panel eases to is the one this decided.

2. **The chat's scroll position survives the console.** It did not, and
   [ADR-0034](ADR-0034-panel-views.md) decision 7 said it did; that decision now carries the
   correction and this is the fix. `ChatView` parks the position on every scroll of the reader's own
   and hands it back in a layout effect on the way in, so the return is painted with the
   conversation where the eye left it. A reader who was AT the tail comes back to the tail rather
   than to the line it used to be on, since a reply can land while the console is up.

   Scrolling that the layout does is not the reader's and is ignored while the console is up. The
   trip relays the history out twice, each time with a scroll event behind it, and either would
   otherwise park the log where the trip left it. The second would also re-pin it, a box with
   nothing to scroll reading as a box sitting at its own tail.

   *Corrected 2026-07-20:* one of those two relayouts is gone. The leaving view is bounded by the
   panel now (decision 3 of the addendum below), so the history keeps a real window for the whole
   morph and only the `display: none` at the end of it takes the position. The parking still does
   the work; there is simply less to defend against.

3. **The panel's own measurement no longer takes the log off the reader.** The panel measures itself
   by growing to the loosest cap any edge could allow and reading what it becomes (decision 1 of the
   addendum above). Every scroll box inside a taller panel is a taller box, and the engine answers a
   box that has outgrown its scroll range by clamping it, which putting the real cap back does not
   undo. Traced at 60Hz at 640x720 through a streamed reply, wheeling 60px up from the tail:
   `scrollTop` read 312, then 252 the frame the wheel landed, then 215 two frames later with nothing
   else touching it, 215 being the deepest a 390px window scrolls a 605px log. Every token did it
   again, which is what "the history will not let me scroll while a reply streams" was. The same
   clamp landed on every placement of any kind: opening the chat switcher moved a reader from 154 to
   73 and left them there.

   So `place` takes the scroll positions before it measures and hands them back after, on every path
   out. Traced again afterwards: a 60px wheel mid-reply holds at exactly where it landed for the
   rest of the reply, while the log grows from 605 to 694 underneath it.

   The suspect before tracing was the panel's height animation firing resize-induced scroll events
   that re-armed the auto-scroll's pin. It does not: the clamp lands 97px off the tail, which is
   past the 40px that counts as reading the tail, so the pin was never re-armed and the reader was
   simply moved. Recorded because the fix that hypothesis implies, treating only wheel and touch and
   key as intent, would have left the actual defect in place.

4. **A section's roll cannot overshoot the ceiling.** A roll is not a placement: the panel stands
   down and lets the section own the height, and nothing takes the measuring cap back off the
   element until the roll ends. So for the length of every roll the panel was licensed to grow to
   the loose cap. Traced at 60Hz at 640x720 with the panel already on its ceiling, opening the chat
   switcher: the panel jumped from 450 to the loose 547 with its top edge 11px off the top of the
   screen, held it for the whole 300ms roll, and the placement at the end put the real 450 back in a
   single frame. The real ceiling is written to the element for the duration instead, so the section
   rolls to its full height and the history gives the room up. Traced afterwards: the panel holds at
   450 with its top edge on the 86px line for every frame, the switcher rolls 0 to 120, and the
   history goes 293 to 173. Under the ceiling nothing changes: the same roll on a 353px panel grows
   it to 450 with the bottom edge pinned, which is decision 3 of this ADR working as it always did.

## Addendum, 2026-07-20: five more from the user watching the console open and shut

The first four are one fault each in the trip between the chat and the console, found by filming it
rather than by reasoning about it. None of them was introduced by the addendum above: the same
frames were captured against the commit before it, and they are identical.

1. **The console centres on itself.** `centringHeight` leaves a section marked `aside` out of the
   height the panel centres on, which is right for the chat, whose reminder stack arrives with the
   summon and can be two rows or five. It was subtracting that stack from the height of the view
   ARRIVING, because the chat is held in the DOM for one morph after it is left. Measured at 640x720
   entering the console over an empty chat with three reminders up: the console is 347px tall and
   was centred as though it were 155, which put it 96px above the middle of the screen. The ceiling
   is measured from the edge the panel sits on, so it was also capped at 351px where 448 would have
   fitted, and the console had four spare pixels in the whole view. Only an aside inside the view
   being placed counts now.

2. **The ceiling travels with the move.** `max-height` clamps an animated `height` exactly as it
   clamps a laid out one, and the ceiling belongs to the edge the panel is going to, so it was
   already the destination's while the panel was still the origin's size. Traced at 60Hz opening the
   console from a full-height chat: the ease was written 450 to 347, and the panel stood at 351 one
   frame after the click and eased the last 4px from there. The eye gets the whole shrink in a
   single frame followed by an animation of nothing, which is what "it pops and then animates" is.
   The cap is a keyframe now, from a value at or above the height it starts on, and both ends
   interpolate under one easing so the cap is never tighter than the height it is clamping.

3. **The leaving view is bounded by the panel.** It is lifted out of the flow so it cannot fight the
   arriving view for the height, and it was then laid out at its own natural height: with the
   session list open the chat's composer sat 388px down the panel at rest and 558px down one frame
   after the click, inside a panel 347px tall, so it was clipped away instantly while the rows above
   it faded for a quarter of a second. The maintainer read that as the chat bar being deleted rather than
   crossfaded. A `bottom` on the leaving view is the whole fix, and it also gives the history a real
   window for the length of the morph, which is one of the two things that used to take the log's
   scroll position.

4. **Focus does not scroll the panel.** The panel clips its overflow, which makes it a scroll
   container the user can never scroll and the engine can, and bringing a newly focused element
   into view is exactly when it does. Coming back from the console the panel is still the console's
   height and easing to the chat's, and the composer takes focus on that rising edge from below the
   panel's clipped edge. Traced at 60Hz at 640x720 with the session list open: `panel.scrollTop`
   went 0 to 139 in the frame focus landed and unwound over the ease, which is every row in the
   window lurching 139px up and creeping back. `preventScroll` on the focus, and it holds at 0 for
   every frame. The field is where the eye already is; it needs the caret, not bringing into view.

5. **The console's foot is 26px, not the header's 15.** *Superseded the next day: it is 16px, read
   off the side inset rather than judged. See the addendum below.* Matching the header's number is
   what made
   the two ends look wrong: the header spends its 15px above a 30px control with an inset glyph, so
   the ink starts about 25px down, while the same 15px at the foot sits directly under a card that
   runs the panel's full width, hard against a 28px corner radius. Measured, 17px of clearance at
   the top against 16px at the bottom, and the bottom was plainly the tighter. The two tabs still
   differ by the 12px one of them has spare, which is the cost of their shared height and is under
   the threshold that decides it.

**The maximum height did not change**, which the maintainer asked about after seeing the empty state
scroll with the session list open. `MIN_TOP_RATIO` and `maxHeight` are untouched, and the same
frames on the commit before this work read the same numbers: at 640x720 the panel is 450px with a
450px cap either way, and the empty state's history is 101px of a 195px column at rest and 10px of
it with the list open. That is the demo state genuinely not fitting: head 54, reminder stack 192,
session list 120, composer 48 and hints 33 come to 447 of the 450 available, so the history is left
with what is left, and the design's answer to a panel at its ceiling is that the history yields and
scrolls. What did change is that the panel no longer overshoots the ceiling while a section rolls,
so that squeeze is now visible during the roll rather than only after it.

## Addendum, 2026-07-20: the send button gets a hover, and it is the glyph that moves

Four were pitched to the user as a live page of the real button in its three states and both
themes: lift the cap 2px with a shadow, swell it to 1.12 on the spring, bloom its fill out of the
middle, or move the glyph and leave the cap alone. The maintainer picked the last, with two amendments,
and both amendments are the reason it is worth writing down.

1. **The glyph travels the way it means.** The arrow rises 3px over 0.28s on the spring the press
   already uses; the cap holds still and takes the same neutral fill it always had. It is the only
   one of the four that says something rather than acknowledging the pointer, and the only one that
   leaves the pill's geometry alone, which matters where the cap sits 4px from the panel's edge.

2. **A live button keeps its white glyph.** `.send.live` is white BECAUSE the cap under it is the
   accent gradient, and the hover was handing it back `--text`: near black in the light theme, on a
   magenta cap. The one state where hovering a button made it harder to read.

3. **The stop turns red, and it is the only hover in the overlay that changes hue.** Streaming, the
   button has swapped what it MEANS, not just what it does: everywhere else the send is how a turn
   begins and here it is how one is called off, and a grey that says "a button" does not carry that.
   Its square eases shut (0.84) rather than travelling, having no direction to go in.

   The red is `--halt`, which is not a new colour: it is what the trash on a chat row already wore
   as a literal, now named once and used by the two controls in the overlay that undo something in
   flight. It is the accent's own magenta walked to red (`--accent`'s middle stop is
   rgb(226, 75, 196); this is the same two channels) rather than a traffic light imported from
   nowhere, and it is read against the light panel as well as the dark one. This does not loosen
   the rule that colour is reserved for working affordances: a stop offered mid-turn, and a trash
   offered on hover, are working affordances at exactly the moment they are coloured, and neither
   is coloured at rest.

## Addendum, 2026-07-21: four the maintainer measured rather than described

1. **The console's foot is the console's sides.** Yesterday's addendum set it by eye twice, at the
   header's 15px (which measures 16 and reads tight) and then at 26 (which measures 27 and reads
   loose), and neither number was one anything else in the view agreed with. A card's left edge
   stands 17px from the panel's and its right edge stands 17px from the panel's, so its bottom edge
   does too: 16px of padding on `.rows` plus the panel's 1px border. Read off the other two rather
   than judged, and it follows them if they change. The lesson generalises past this rule, which is
   why it is written down: an inset that has a neighbour has an answer, not an opinion.

2. **The console keeps its tab on the way out.** `Panel` renders the console while it is leaving so
   it can fade, and read its tab from the reducer, which had already set it to null: the fallback
   was the FIRST tab, so leaving from the shortcut list drew the appearance tab over the list the
   user was looking at and took it away with the fade. The last tab shown is held in a ref for
   exactly that morph.

3. **Every keycap is at least as wide as the widest single key.** An outline arrow is 13px of
   drawing where an `N` is 8.2px and a `?` is 5.8px, so the six single keys measured 23, 20.2, 19.2
   and 17.8 and no two columns of them lined up. The floor is a minimum, so `Ctrl` at 31.6 and
   `Space` at 45.5 are untouched. A cap has to be a flex box for `min-width` to reach it, which is
   the one thing about the change that is not obvious from reading it.

4. **The empty state does not scroll.** It is a picture rather than a log, with no more of it
   further down, so a bar on it offers to reveal nothing and is only the panel admitting it could
   not fit its own welcome. `.log.bare` marks the case (no messages and no approval card), and there
   the column may be shorter than its content: it shrinks, centres, and clips, which is what leaves
   the history with nothing overflowing to offer a bar for. The clipping is symmetric because
   centring with negative free space overflows both ends alike, so the mark stays on the middle
   line. A log with a message in it is unchanged, bottom aligned and scrolling.

   Recorded because the obvious next move is a trap: dropping the empty state's 58px of block
   padding to buy room makes it worse. That padding is part of the height the panel sizes itself to,
   so the panel shortens and the history shortens with it, and the measurement says the content went
   185 to 127 while the window it had to fit went 101 to 72. Half a visible mark became a sliver of
   one, and it cost 29px of panel. What is left, when the room genuinely is not there, is a cropped
   picture: if that wants to become a mark that scales or chips that stand down, it is a change to
   what the empty state IS and belongs in the design doc first.

## Addendum, 2026-07-21: a theme is one frame, and four more the maintainer watched

1. **The overshoot came back at the end of the roll, by another route.** The addendum above put the
   real ceiling on the element for the length of a roll, and the roll then held it perfectly; the
   placement that runs when the roll ENDS was still reading the panel's height under the measuring
   cap. A panel standing at its 450px ceiling with the session list open measures 547 under that
   cap, so the ease was written 547 to 450: one frame of a 97px jump to a top edge 11px off the
   screen, then a slide back down, immediately after 21 frames of holding the ceiling exactly.

   It was invisible until the ceiling learned to ride along in the keyframes (decision 2 of that
   addendum), because the cap on the element had been clamping that ease flat. The fix is to read
   the height the eye actually has, which means reading it BEFORE the measuring cap goes on. Filmed
   again: the panel holds 450 with its top edge on the 86px line for every frame of the roll and of
   the placement that follows it, in both directions.

2. **A theme change happens in one frame.** *Superseded the same day: it CROSSES, over 400ms, with
   one transition on everything. The maintainer wanted the fade kept and the stragglers fixed, and turning
   every transition off fixed the stragglers by removing the fade. See the addendum below.*
   `applyTheme` sets `data-swapping`, writes the tokens,
   forces a style flush and clears it; `[data-swapping] *` turns every transition off. Without it
   the swap was a ragged 20 frames: the ground eased its own colour over 0.4s, most text sets a
   colour and transitions nothing so it changed in the frame of the click, and every control that
   eases colour for its hover crossed at its own 0.16s to 0.35s pace. What the maintainer noticed was the
   chat's title and the reminder lines lagging, which are the two things in the panel that INHERIT
   the ground's colour rather than setting their own, and so were the only text following the 0.4s.
   The forced flush is the load-bearing line: without it the attribute goes on and off inside one
   task and the browser never resolves style in between.

3. **A gradient is not a colour, and four rules asked for one.** `--accent` is a
   `linear-gradient`, so `color: var(--accent)` does not compute; a declaration that fails at
   computed-value time is not dropped but set to `unset`, which for an inherited property means
   `inherit`. The pinned row's pin has therefore always taken the ground's text colour rather than
   the accent, and being inherited is what made it jitter: the ground eased its colour across a
   theme change while the button ran its own 0.16s ease chasing it, sending the pin from the old
   text colour up past the new one and back down (traced at 60Hz: 25 to 242 over eleven frames, then
   165 in the next). It asks for `var(--text)` now, which is what it has always rendered as, and the
   pinned row's `border-left`, whose shorthand the same gradient invalidated whole, is gone rather
   than left reading as live. **Three more sites still ask for it**: the thinking chip's label, the
   rename box's border, and they are left alone deliberately, because giving them the accent they
   ask for is a visible change to surfaces nobody has complained about.

4. **The session row is title and preview, then right to left the time, the pin, the pencil, the
   trash.** The time takes the edge, being what the eye goes to when it is skimming for a chat, and
   it stands 11px inside the row's right edge because the title stands 11px inside its left. It
   moves out of the row's own button to get there, which costs a click target that was never an
   affordance: what selects a chat is its title, its preview, and the space between them.

5. **A keycap's height is floored with its width.** Both floors are what a glyph cap measures. Every
   cap in the hint strip was 15px or 17px tall depending only on whether its key happened to be
   drawn or written, so `Shift` and the return glyph beside it sat on different lines.

## Addendum, 2026-07-21 (later): the theme crosses, and a dismiss does not move

1. **A theme change is a crossing, not a snap.** The addendum above made every element take the new
   tokens in one frame, which fixed the raggedness by removing the fade. The fade was wanted; only
   the stragglers were not. So `data-swapping` now puts ONE transition on everything for the length
   of the crossing (`THEME_SWAP_MS`, written to the root as `--theme-swap` so the stylesheet reads
   the same number that holds the attribute on), instead of turning transitions off. Traced at 60Hz
   afterwards: the ground, the chat title, the session titles, the times, the previews, the hint
   strip and the pin all move together, frame for frame, on one curve.

   Two details are load-bearing. The attribute goes on BEFORE the tokens, because a transition is
   started from the after-change style, so the rule has to be in effect for the style that changes.
   And it comes off on a timer rather than a style flush, which is the opposite of what the snap
   needed: taken off in the same task there is nothing left to ease. The first application is not a
   crossing, or the overlay fades up into its own colours on boot.

2. **A dismiss is not a placement.** A closed panel re-centred itself so the next summon would start
   in the middle. That write landed in the frame of the dismiss, with the panel still at full size
   and fully opaque: traced at 640x720 with a conversation and the session list open, the window went
   from 450 tall at a 184px edge to 508 tall at a 106px edge in one frame, and only then began to
   shrink away. The panel now keeps the geometry it is standing in while it closes, and the summon
   centres for itself, which is what the arrival window has always done (`arriving` is true for the
   whole of it, and centring is one of the conditions it turns on). Re-measured: dismissing holds
   184px for every frame of the close, and the summon after it lands dead centre.

   A panel that has never been placed is the exception, since there is no geometry to keep, and the
   summon frame itself no longer animates its geometry: the pop owns that arrival, and the edge it
   arrives at is now genuinely new rather than one the dismiss left ready.

3. **The bell and the check are centred on a reminder card**, not hung from its first line. They are
   about the whole reminder rather than the sentence's opening, and a card is a line of text over a
   line of meta.

## Addendum, 2026-07-21 (later still): the switcher's time column is reserved

`.switcher-time` reserves 55px and right-aligns its text in it, so the column holds still while the
clock runs and down a list of chats of different ages. The number is a measurement, taken at the
size the column is actually drawn at, of everything `relativeTime` can say: `just now` 48.4,
`59m ago` 50.9 (the widest of the three bounded shapes), `23h ago` 47, and the day branch, which is
not bounded, at 47 for two digits and 54.3 for three. 55 therefore covers every value up to a chat
pinned for the better part of three years, and a fourth digit of days is left to push the column
rather than being paid for by every row above it.

Two things are easy to get wrong here and are written into the rule. The inset is a margin rather
than padding, because `box-sizing` is border-box in this stylesheet and padding would come out of
the 55 and reserve 44. And the text is right-aligned inside the box: left-aligned, a short value
hangs the reserve off its end and the alignment the reserve exists for is the thing it breaks.
`relativeTime.test.ts` asserts the four shapes as a range rather than as samples, so a fifth shape
is a failing test pointing at this number rather than a column that has quietly started moving.

The time also keeps 8px off the pin beside it. The row's own 2px gap is the spacing WITHIN the
cluster of three icon buttons, and a label that is not one of them wants its own.

## Addendum, 2026-08-03: a chat arriving takes the console with it

The deferral this closes was recorded on 2026-07-20 while verifying the console merge, and it was
recorded rather than fixed because the one line it needed had two defensible values and neither was
the agent's to choose. `newChat` cleared the switcher and any pending confirm but not `consoleTab`,
so pressing Ctrl+N while the console was up minted the session and emptied the chat *behind* it:
measured at 900x900, the console's live tabpanel stayed on screen while the title behind it had
gone back to "New chat". The
behaviour predates the console, the two sheets it replaced having been left standing by the same
arm, so the merge neither caused it nor hid it.

**The user's answer, given on 2026-08-03: Ctrl+N closes the console.** A keystroke aimed at the
conversation puts you in the conversation. The chat is cleared, the console tab goes with the chat
it was opened over, and the empty chat is what you are looking at.

The alternative was real and is worth keeping on the record, because it surprises the other way
round rather than not at all. The console is the one surface in the panel that is about the app
instead of the conversation, so closing it out from under someone who reached for a new chat while
reading the shortcut list takes away what they were reading. What settles it is that the arm was
already half-committed to the answer that shipped: it sets `mode: "panel"` for exactly the reason
the user gave, and a new chat that arrives somewhere the user cannot see is the weaker half of a
statement the arm was otherwise making in full.

Two consequences of the pick, both of which the deferral's "one line in one reducer arm" estimate
did not carry:

1. **`openSession` had the identical hole, and it is reachable by keyboard.** The entry named only
   `newChat`, and its own reasoning applies unchanged to loading a stored chat, which is the same
   event from the user's side: another conversation arriving on the panel. The switcher row that
   normally starts one is not reachable while the console is up (the chat view is `display: none`
   behind it), but Ctrl+Up and Ctrl+Down are global keys handled in `Overlay.tsx` and cycle straight
   through `openSession`, so a cycled chat loaded behind the console exactly the way a new one did.
   Both arms now clear the tab, so the rule is "a conversation arriving on the panel brings the chat
   with it" rather than a special case for one keystroke. The keyboard is the whole of the reachable
   surface here, which is worth saying because it bounds the defect: the header's pencil and the
   switcher's rows are the pointer doors into these two arms and neither can be clicked while the
   console is up, so what was measured is exactly what a user could hit.
2. **The other two chat swaps deliberately keep the console, and now say why.** `deleteSession`
   resets the panel to a fresh chat in place, and it keeps the tab for the same reason it already
   keeps the switcher open: a delete is fired from a switcher row, so the user is managing chats
   rather than asking for one, and the surface they are working in survives the write. That row is
   its only caller, so it is unreachable from the console besides. `adoptSession` is a
   cold-start background restore that must take nothing off the panel, and it cannot meet an open
   console anyway, since reaching the console means summoning the panel and a summon sets `touched`,
   which is the flag adoption gives way to.

This is the opposite call from `dismiss`, and for the opposite reason, so the maintainer-pass
addendum above that gave the dismiss its rule is worth reading beside this one. A dismiss leaves the
console standing because the panel is on its way out and
morphing back to the chat under a fading window read as the window changing its mind; the summon
after it is what clears the tab. Here the panel stays on screen, so the morph back to the chat is
the movement the keystroke asked for rather than one the window makes on its own way out. Both
halves are pinned in
`overlay/overlayState.test.ts`: one case walks both tabs through both arriving doors, and a second
pins the delete and the adoption as leaving the console where it was, so a later "consistency" edit
to those two has to argue with a test rather than pass silently.

Measured in Chromium at 900x900, the viewport the deferral was written against, by driving the real
overlay over the demo bridge and reading which view is in the layout flow. Before, with both clears
removed: the console is the live view, Ctrl+N leaves it the live view with its strip still selected
on Face, and Ctrl+Down loads "Summarize my unread email" with its two bubbles underneath while the
console stays up (the hint strip's own buttons are not clickable in that state either, which is the
`display: none` on the view being covered, and is why the keyboard is the whole reachable surface).
After: the same two presses each leave the chat as the live view with no tab strip mounted at all,
the first on the empty state and the second on the loaded conversation. One naming note for anyone
reading the deferral beside this: the tabs were labelled Appearance and Shortcuts when it was
written and are labelled Face and Chords now, the reducer keys being unchanged.

## Addendum, 2026-08-03: a reminder leaves on its own clock, and its ack does not wait for it

Decision 4 gave every section its own roll, and the deferral filed against it on 2026-07-19 said
that a row inside one of those sections still went in a frame: `Collapse` wrapped the whole
reminder stack, so acking one reminder of three deleted that row while the panel eased smoothly
around the hole. **Read against the code on 2026-08-03, half of that had already been fixed and
the entry was never closed.** The stack has wrapped each row in its own `Collapse` since the
settings-tab slice of 2026-07-20, and the roll it produces is the right one: traced at 60Hz, the
acked row's height ran 57.25px to 0 over the roll and its neighbour travelled the same distance in
the same frames. What the entry described as the whole defect was therefore already gone; what was
left underneath it was worse than the entry claimed, and is what this addendum is about.

**The way that first version held the row was to hold the ACK.** Pressing the check put the
reminder id into a local `going` list, started the roll, and called `onDismiss` from a
`setTimeout(MORPH_ROLL_MS)`. So the row on screen and the list upstream disagreed for 300ms, and
everything else followed from that. A `useEffect` cleanup cleared the pending timers on unmount,
which is correct for a timer and fatal for an ack: the stack is keyed to the chat it belongs to
(`ChatView`), so minting a new chat or opening the one a reminder points at remounts it, and inside
those 300ms the ack was cancelled and never sent. Measured in Chromium at 900x900 over the demo
bridge, acking the middle of three reminders and pressing Ctrl+N 100ms later left all three cards on
screen, and a fresh summon, which re-reads the brain, listed all three again. The gesture had done
nothing at all. The same list also never forgot an id, so a reminder that came back (which is
exactly what a lost ack leaves behind, ADR-0025 preferring a repeated reminder to a lost one) was
rendered into a `Collapse` that was already shut and stayed invisible for the life of the panel.

### The decision

**A leaving row is held by the view, not by the removal.** The ack goes upstream in the frame the
check is pressed, the reducer drops the reminder immediately as it always did (ADR-0025's optimistic
dismissal), and the row is kept on screen afterwards by a new hook,
`overlay/usePresence.ts`, which renders a list that outlives the caller's. An item that leaves the
caller's list stays in the rendered one, marked `leaving`, at the index it held, carrying the last
version of itself that was on screen, until its exit says it is over. Nothing the user asks for
waits on an animation, and an unmount mid-exit can lose nothing, because there is nothing in flight
to lose.

**The exit's clock is the roll's, and there is only one of it.** The hook holds no timer and does
not know how long an exit takes. `Collapse` gained one optional prop, `onClosed`, called when a
CLOSING roll has finished, and that call is the only thing that ends a hold. So the timing and the
easing of a leaving row are not a new decision at all: they are `MORPH_ROLL_MS` and `EASING` from
`overlay/morph.ts`, the same 300ms and the same curve the panel and every other section already
share. A second clock beside them is the thing this deliberately does not add.

**The order inside `Collapse.finish` is a contract.** `onClosed` is called after the
`cortex:morphend` dispatch, because the panel re-measures on that event and the row must still be
part of what it measures. React's batching would hold the caller's removal until after `finish`
returns in either order; the order is there to say which of the two is allowed to depend on the
other, and a test asserts the sequence rather than the outcome.

**The layout collapses through the roll and not around it.** A held row is a real row of zero
height at the end, so its neighbours close the gap by travelling over the roll's own curve, the
panel's `auto` height follows the section frame by frame exactly as decision 4 set up, and the
release itself moves nothing: by the time the hook drops the row, the row is 0px tall and its
`Collapse` has already told the panel the roll is over.

### What it measures

Chromium over the demo bridge, three due reminders on an empty chat, traced per animation frame.

- **640x720, the body's own window, acking the middle of three.** The panel is at its 450px
  ceiling here, so the history absorbs the whole change: panel top 86, bottom 536, height 450 on
  every frame of the exit, and the first row's top edge holds at 148 for every frame too. The acked
  row runs 58.25px to 0 (first sub-pixel movement one frame after the click, zero 317ms later, which
  is the 300ms roll plus the frame it starts on) and the row below it travels 263.5 to 205.25 across
  the same frames. The slot leaves the DOM one frame after the height reaches zero and nothing moves
  when it does.
- **900x900, where the panel is not clamped, same gesture.** The history yields 26.75px of the
  58.25 first, so the panel's top edge is still for the opening 167ms, then eases 108 to 138.5 and
  stops. It is monotonic, the largest single frame is 6.75px, and there is no step at the release:
  the panel reads 487.5 on the frame before and every frame after.
- **Two acks 120ms apart at 900x900**, which is the case the old timer made ambiguous. Each row
  runs its own roll on its own clock (57.25 to 0 across t=42 to t=359, released at 375.8; 58.25 to 0
  across t=209 to t=525.8, released at 559.1). The row between them never changes height and only
  travels. The panel's top edge is monotonic through both, 108 to 196.75, largest single frame
  9.22px, with no backward step anywhere.
- **The last reminder, where the row's roll and the stack's own wrapper roll run together.** They
  share the clock and the curve, so the two read as one movement: the panel eases 429.25 to 352
  monotonically at both viewports, and the card chrome the empty stack still measures (14px of
  padding and border) leaves with no panel movement at all, being inside a wrapper the panel is
  already measuring at zero.
- **The ack, measured the way it was lost.** Acking the middle reminder and pressing Ctrl+N 100ms
  later now leaves two cards on screen, and a fresh summon lists two. Before, it left three and
  listed three.
- **One pixel is spent, and only when the row leaving is the top one.** The hairline sits between
  two rows, so the row under a departing first row loses the line above it in the frame that empty
  slot is removed: at 900x900 the panel's last step is 137.5 to 138.5 and the stack's 130.5 to
  129.5, one frame after a 300ms roll that has already landed. It is kept because it is the truth
  (a line between two rows, one of which has gone) and because the alternative rule, a border
  bottom on every row but the last, only moves the same pixel to the case where the BOTTOM row is
  acked. Acking a middle row spends nothing either way, and it is the case the earlier traces are
  taken from.

### Two repairs that came with it

Wrapping each row in a `Collapse` had put a `<div>` between the stack's `<ul>` and its `<li>`
children, and both consequences were live and unnoticed until this pass measured them.

1. **The stack was no longer a list.** Its `<ul>` had three `<div>` children, so the
   `aria-label="Due reminders"` sat on a list whose items were not items. The row's `<li>` now sits
   OUTSIDE the roll, as `.reminder-slot`, with the wrapper and the row's own box inside it.
2. **The hairline between two reminders had been switched off.** It is drawn by
   `.reminder + .reminder`, an adjacent-sibling rule, and two rows in two wrappers are not
   siblings. Computed `border-top-width` read 0px on all three rows. The rule now reads down from
   the slot (`.reminder-slot + .reminder-slot .reminder`), which keeps the border inside the
   wrapper that clips it, so a row rolling shut takes its own hairline with it and the row left at
   the top of the stack loses the one above it in the frame that slot leaves. The stack measures
   187.75px where it measured 185.75px, which is the two restored hairlines and the whole of the
   difference. Decision 22's reserved-rail note measures that hairline down to the pixel its
   corner curve fades on, and it is not wrong: it was taken 39 minutes before the wrapper landed,
   which is how long the measurement was true for.

### One lesson worth the space

The hook's first shape remembered what it had just rendered by writing a ref during the render. It
passed every test written against it and dropped the row on the first frame in a real browser, which
is the very defect it exists to prevent, one layer down. The cause is `StrictMode`, which the
overlay runs under (`main.tsx`) and which invokes a render twice: the second pass read back what the
first had written and concluded that nothing had left. The memory is written from a layout effect
now, so a render is a pure function of the props, the state and the last commit, and every case in
`overlay/usePresence.test.tsx` renders under `StrictMode` so that it stays that way. The general
form: a hook that derives from "what I rendered last time" has to mean the last COMMIT, and only an
effect knows which render that was.

### What this does not do

The hook is written to be shared and only the reminder stack is wired to it. *Wired to the switcher
later the same day; see the addendum below.* The switcher's rows
have the same shape of exit (a deleted chat leaves the list the moment the write lands) and would
want the same treatment, but they need their own DOM restructure, their own hover and pinned rules
re-checked against the wrapper, and their own frame trace, so they are a second surface rather than
a free line. That is recorded as a deferral in
[docs/refinements/body-overlay.md](../refinements/body-overlay.md).

## Addendum, 2026-08-03: the panel watches its own box, and an arrival counts the same aside a placement counts

Decision 14 gave a roll its own two events because a roll is not always a render the panel sees.
Three deferrals filed on 2026-07-20 said the same thing about content. `usePanelMotion` places the
panel on renders of `Panel`, on both ends of a roll and on a window resize, and anything that
resizes the panel outside those leaves the last placement standing. The composer is the largest and
most frequent case: the draft lives in `Composer`'s own state, so a field growing a line re-renders
nothing above it and the panel's `auto` height simply follows in the frame the character lands,
bottom edge pinned, with no ease at all.

### What the watch answers, and what it refuses

**The panel observes its own box (`overlay/panelWatch.ts`) and drives the same placement the roll's
end event drives.** All of the design is in what it refuses to answer, because every placement
resizes the element being watched. Traced at 900x900 over the demo, a single `ResizeObserver` on the
panel delivered 19 notifications across the reminder stack's 300ms roll and 18 more across one 380ms
move of the panel's own, one per frame of each.

1. **A roll owns the height.** While a section inside is animating its own height, the panel's
   `auto` height follows it frame by frame, and the ride-along has already taken the bottom edge to
   where the roll will leave it. Placing on those frames is the panel's arithmetic against a height
   that is mid-animation by construction.
2. **A move of the panel's own owns the height too.** The panel's ease is a height animation on this
   same element. Answering its frames feeds the observer its own output: each one would cancel the
   running ease to measure the natural box and start another, sixty times a second, which is the
   mid-stream retarget already filed as a refinement arriving once per frame instead of once per
   token. Measured over one scripted reply, three runs each side, the panel is given 2 to 3
   animations both before this change and after it.
3. **A reading with nothing behind it is answered with nothing.** The watch remembers the height it
   last looked at, not the height the panel was placed at, since a roll and an ease both walk the
   box past it every frame and the only question each time is whether anything has moved.
4. **The watch is lifted for the frame the panel writes in.** Placing is itself a resize of the
   observed element, the ease starting at the height the panel had rather than the one that was
   reported. An observer whose callback resizes its own target is the one case the specification's
   depth rule cannot deliver, the re-gathered observation being no deeper than the broadcast that
   caused it, so the notification is dropped and the page is told through the "loop completed with
   undelivered notifications" error. Measured over the demo, that was one error event per keystroke
   that grew the pill. Dropping the observation before placing and taking it up again on the next
   frame leaves nothing to re-gather: the same trace now reports zero.

**The ease is not a frame late for any of this**, which is worth stating because it looks as though
it should be. `requestAnimationFrame` runs before the resize observer steps, so a trace taken there
reads the frame's layout before the placement has had its say. Traced at 640x720 over a Shift+Enter
that restacks the pill, a rAF probe reads the panel at 404 for the frame the character landed and a
second observer reading the same frame after the placement reads 352 with one animation attached.
The frame paints the height the panel had and eases from it. Nothing jumps and comes back.

### What it measures

Chromium over the demo bridge, per animation frame.

- **The composer's four growth steps at 640x720 with the reminder stack acked**, each of which was
  one unpainted frame before and is now a paced ease. A further line on an already stacked pill runs
  the panel's top edge 148, 147.13, 143.11, 137.64, 134.61, 133.03, 132.28, 132.02, 132, where it
  was 148 to 132 between two consecutive samples with no third state between them. The character
  that restacks a one-line draft runs 184, 182.02, 172.98, 160.75, 153.86, 150.33, 148.61, 148.02,
  148 against a single 36px step. A Shift+Enter that restacks and adds a line at once runs 184,
  181.14, 168.08, 150.41, 140.5, 135.34, 132.88, 132.03, 132 against a single 52px step, largest
  frame 17.67px. A paste that fills the field to its 120px ceiling runs 184, 180.98, 168.19, 141.92,
  118.2, 103.77, 95.05, 89.92, 87.14, 86.06, 86 against a single 98px step, largest frame 26.27px.
  The paste is 98px rather than the 122px the deferral published because the panel is on its own
  ceiling at that size and the history absorbs the other 24.
- **A resize with no render and no roll behind it at all**, which is the general case the composer
  is one instance of: 40px of content appended straight into the log from the console, where React
  never hears about it. Before, the panel's top edge went 368.13 to 328.13 in one frame. After, it
  runs 368.13, 365.77, 355.66, 342.16, 334.52, 330.59, 328.67, 328.02, 328.13 over about 120ms.

### The end of a roll is not a resize, so `cortex:morphend` stays

The deferral that asked for the observer expected it to retire the end event. It cannot, and the
reason is visible in the same trace: **a roll ends without changing the panel's size at all.** An
opening roll fills nothing, so its final value is the section's natural height and the element is
already there when the animation stops; a closing roll fills forwards at zero and the section that
is then unmounted was already contributing nothing. Instrumented at 900x900 across the reminder
stack's roll, the last notification lands at t=456 with the panel at 518 and `cortex:morphend`
fires at t=471 with no notification anywhere near it, the next one arriving 2.3 seconds later when
a conversation is loaded. Nothing but that event tells the panel a roll is over, which is what
decision 5 already says about re-measuring keeping a prediction honest, and it is now also what
tells the watch that the height is the panel's own again.

### An arrival counts the aside the way a placement counts it

Decision 8 says a summon owns the panel's geometry until the user touches it, and a deferral filed
against it measured 2.1px of error left behind when a touch lands mid-roll: the ride-along pins the
edge from a prediction, and the placement at the end of the roll, which is what would have corrected
it, is no longer an arrival. **Read against the code and the browser on 2026-08-03, the prediction
is exact and the error was somewhere else entirely, and it is 97px rather than 2.1.**

The prediction cannot be wrong in the way the deferral assumed, because the rolling section's
current height cancels out of it: the panel will be as tall as it is now, less what the section
takes now, plus what it is about to take, and the roll is announced at its start where those two
readings are taken in the same frame. What the ride-along got wrong was the aside. `centringHeight`
leaves the reminder stack out of the height the panel centres on, so that the chat centres on itself
and the stack grows it upward, and the ride-along asked a different question: whether the section
that is ROLLING is the aside. A stack that is merely standing in the panel while something else
rolls was therefore counted into the arrival's centring and out of the placement's. Measured at
900x1000 over the demo, Ctrl+N with the switcher list open, which summons the panel and rolls that
list shut in one commit while the stack stands: the summon pinned the edge at 227 and the placement
at the end of the roll re-centred to 324, so the panel's bottom edge travelled 97px down the
viewport across the roll and came back at the end of it, and a key pressed inside the arrival
window, which is exactly what stops that placement re-centring, left the session pinned 97px low
for the rest of it.

**The ride-along now counts its prediction through `centringHeight` itself**, the same function the
placement counts its measurement with, and the two agree by construction rather than by argument.
The aside's height is taken as the height it will have when everything settles, which is the height
it is rolling to while it rolls and the height it has otherwise, so the one function serves both
callers. It is bounded at `openHeight` BEFORE the aside comes off, because that is the order the
measurement happens in: `place` reads the element under the loose cap and takes the aside off what
it read. Bounded afterwards, the ride-along stood a whole aside above the placement that followed it
on any panel whose content outgrows that cap, which is a second beat on the summon rather than a
wrong edge for the session.

After: the panel's bottom edge holds at 676 for every frame of that roll and settles at 676 whether
the user touches the panel mid-roll or not, at both 900x900 (edge 274, the panel on its ceiling) and
900x1000 (edge 324). The aside's own roll behind a summon is unchanged, since for that case the two
spellings were always the same number.

Three functions moved with this, without changing: `centringHeight`, `tabSlack` and `holdScroll` are
now `overlay/panelParts.ts`, the probes a placement makes into the panel's own tree, so that
`panelRide` can ask the same questions without importing the module that imports it, and
`arrivalBottom` is now in `overlay/panelGeometry.ts` with the rest of the pure arithmetic.
`panelPlacement.ts` is 295 lines where it was 371.

### What this does not do

The watch answers a resize that arrives while the panel is settled. One that arrives while the
panel's own ease is in the air is deliberately ignored until that ease lands, and **the cost is
latency rather than a jump**, which is worth measuring rather than assuming. Traced at 900x1000 with
200px of content injected into the log and 40px more injected 100ms into the resulting ease: the
first move runs the panel's top edge 368 to 168 over about 316ms with the second growth invisible
throughout, because the running height animation overrides the box the growth would have changed.
The frame the animation hands the element back reads 168, the frame after reads 165.83, and the
residue then eases 40px to 128 over about 120ms, monotonic, with no step anywhere. So the second
growth waits, at most the 380ms ceiling of decision 7 and in practice much less, and then arrives
the way every other growth does. It is recorded as a deferral in
[docs/refinements/body-overlay.md](../refinements/body-overlay.md), because waiting is still not
following, and the obvious alternative, retargeting the move in flight on every frame of it, is the
harm decision 11 and the mid-stream-retarget deferral are both about.

## Addendum, 2026-08-03: the panel's height is a budget, and the sections spend what is left

Decision 19 taught the composer to yield before the panel's edge does, and named what it left
behind: two sections whose own caps are each written as though that section were alone with the
panel. The chat switcher may take `40vh` and the reminder stack `30vh`, and neither number has ever
had anything to do with how tall the panel actually is. **Measured before anything was changed, the
deferral that recorded this understated it in three ways**, so the corrections come first.

### What the measurement found

At the body's own 640x720 window, in Chromium, driving the overlay's demo bridge:

- **It is not a corner reachable only with both sections full.** On the demo's own seed, two chats
  and three reminders, pressing the switcher button once put the hint strip **29.75px past the
  panel's clipped edge** and moved the composer 30.75px down the screen to get there. The deferral
  had that case inside the panel with a pixel to spare, and its 547px panel is where the arithmetic
  went: 547 is `openHeight(720)`, the ceiling of a panel pinned 86px off the bottom of the screen,
  and this state does not pin it there. Measured on the same seed the panel stands 450px tall on a
  184px edge, and on a widened one 436px on a 198px edge, so the entry weighed the sections against
  about a section more panel than they actually have.
- **It is not bounded at the hint strip.** With both sections at their caps and an EMPTY composer,
  the composer sat **204px** past the panel's clipped edge and the hint strip **246px** past it, so
  the send button and every shortcut were off screen at once, with no draft involved. With a draft
  at the field's ceiling those became 240px and 282px. Focusing the field then scrolled the panel's
  own `overflow: hidden` box by 247px to bring the caret into view, which took the header off the
  top of the panel.
- **It gets worse on a bigger screen, not better.** The caps are viewport fractions and the panel's
  ceiling is not: at 640x1400 the two sections want 980px of a 708px panel, and the hint strip
  measured **450px** past the edge; at 640x1000, 322px.

**It is a pair and not a family**, which is the other thing worth checking rather than assuming.
The stylesheet holds four `vh` caps, and the other two (`.thoughts-body` at `28vh`,
`.confirm-draft` at `42vh`) sit inside the scrolling history, which is the child that yields.
Measured with the switcher at its budgeted 227px and an approval card's draft at its full 302.39px
inside a 46px history: the hint strip still cleared the panel's edge by 1px and the composer by
43px. A box inside a scroller cannot reach the panel's edge, so those two numbers are not part of
this and are left alone.

### The decision

**The panel's ceiling is published, and the two sections are written as shares of what is left of
it.** `overlay/panelBudget.ts` writes `--ceiling` beside every layout write of the panel's
`max-height`, because `max-height` is the one thing a descendant cannot read, and overlay.css does
the rest. The arithmetic lives in the cascade rather than in the placement code for one reason: a
section and the panel cannot then hold different opinions of the same height, there being one
number and no second source to drift from it.

- **The composer and the hint strip cannot lose, because they are never in the budget.**
  `--reserved` is the column's own furniture, taken off the ceiling before either section sees any
  of it: the panel's hairline (2px), the header (54px), the history's own padding (10px), the
  composer's margins (11px and 9px) around its floor, and the hint strip (33px). The floor itself is
  `--pill-floor`, declared once and enforced on `.composer.stacked`, so decision 19's 84px and the
  reservation of it are the same 84px by construction.
- **The order of yielding is now three deep and unchanged at the top.** The history yields first and
  by a long way (its shrink weight, decision 19), the sections yield after it, and the composer
  yields last and only down to its floor, spending its draft's window rather than the panel's edge.
  Only the history's padding is reserved, because the conversation is the thing that is supposed to
  give room up.
- **Between the two sections it is a ratio, not an order.** With both in the tree the budget splits
  four sevenths to the switcher and three to the stack, which is the 40 and the 30 they are already
  written in, read as shares. Neither wins outright on purpose: both boxes already scroll, so a
  shorter window shows fewer rows of the same list and loses nothing, which is exactly the argument
  decision 19 used for spending the draft's window. A winner-takes-the-budget rule would leave the
  loser showing nothing, and a stack of fired reminders that silently is not there is worse than one
  that is two rows shorter. A ratio also needs no memory of which section arrived first, so the
  panel reads the same whichever order the user opened them in.
- **A section alone with the panel still gets the whole budget.** The share is taken back only by a
  rule that asks whether the OTHER section is in the tree, so the ordinary case, a reminder stack on
  an empty chat with nothing else open, is bit-identical to what it was: 216px of stack, the hint
  strip clearing the edge by the same 1px.

### What it measures

At 640x720 with the seed widened to twelve chats and eleven reminders, so both sections are
genuinely at their caps. Every number is the box's distance past the panel's clipped edge, so
negative is inside:

| State | Hint strip, before | after | Composer, before | after |
| --- | --- | --- | --- | --- |
| Reminder stack alone | -1 | -1 | -43 | -43 |
| Switcher alone | 24 | -1 | -18 | -43 |
| Switcher alone, draft at the field's ceiling | 60 | -1 | 18 | -43 |
| Both sections | 246 | -1 | 204 | -43 |
| Both sections, draft at the field's ceiling | 282 | -1 | 240 | -43 |

The history is 46px where it was 10 in the two cases with no draft, and the panel's own height and
pinned edge are unchanged in all five (436px at a 198px edge). At 640x1400, 640x1000 and 640x900
with both sections open the hint strip reads -1 where it read 450, 322 and 290. The console view is
untouched, having no sections at all.

**Mutated three ways, each restored after.** Dropping the published property from `capTo` reddens
`panelBudget.test.ts` and the placement test that asserts the ceiling is published at all three of
the caps a placement writes. Putting the section caps back to the bare `vh` returns the harm
exactly: 246px and 204px with both sections open, 35px and -7px with the tall draft, which is the
shape the deferral recorded from its forced 300px ceiling. Taking `var(--pill-floor)` out of
`--reserved` alone puts the hint strip 46.98px out with an empty composer and 81.98px out with a
full one, which is the one mutation that proves the reservation, and not merely the cap, is what
keeps the composer on screen.

**The CSS half of this is not expressible in jsdom**, which has no layout and no `:has()`, so the
browser numbers above are the evidence for it rather than a test that would only be asserting its
own harness. What is tested in the toolchain is the seam: that a cap and the number the sections
spend are written together and cannot come apart.

### What this does not do

Three things, each recorded as a deferral.

The budget bounds a section's content, not its own frame. Each section is a bordered, padded card
that cannot be shorter than 14px whatever the cap says, plus 6px of air beneath it, so with both
open below roughly 260px of viewport there is nothing left to give: measured at 640x240, where the
budget floors at zero, the hint strip is 34px past the edge. At 640x300 it is inside. The body's
window is 720px tall and no smaller.

The room a section hands back arrives in one frame. A section rolling shut is in the tree until
React removes it, so the other holds its share for the length of that roll and takes the whole
budget in the frame the roll's end hands it over. Traced at 640x720 acking a full stack with the
switcher open: the panel's own box never moves at all (one distinct height across the trace, largest
single-frame step of its top edge 0px) and the switcher steps 127.14 to 227 in a single frame,
revealing two more rows.

Nothing machine-checks the two halves of `--ceiling`. `CEILING_PROPERTY` in TypeScript and
`var(--ceiling, 100vh)` in the stylesheet are one seam with no gate across it, and a rename on
either side falls back to the viewport silently, which is the neighbourless cap again with every
test green. The literal is pinned in `panelBudget.test.ts` so a rename has to walk past it, which is
the same arrangement `data-resizing` already has with the rule that hides the history's thumb, and
the real answer is a scan that reads both trees.

## Addendum, 2026-08-03: the floor under a chat is measured off the thing it copies

Decision 12 gave `.log` a floor so that sending the first message does not shrink the panel, and
sized it by measuring the empty state in a browser and writing the number into the stylesheet. The
deferral that recorded this asked for the number to be read off the empty state instead, and named
two more frozen numbers the same probe would retire. **Read against the tree before anything was
built, one of the three was not there at all, and its absence was a live defect**, so the audit
comes first.

### What the three constants actually were

- **The chat floor's 185px was gone.** `.log`'s `min-height` was deleted on 2026-07-20 by the
  settings-tab slice, about forty minutes after the deferral describing it was written, on the
  reasoning that the reminder stack now rolls away on the first message so the shrink is deliberate.
  That is true of a chat with reminders due and false of every other chat. Nothing re-read the entry
  for fourteen days, so this backlog carried a refinement about tuning a constant that had been
  deleted, over a defect nobody was looking at.
- **`--trace-row`'s 24px had not drifted.** Measured mid-turn in Chromium, the live activity chip's
  laid-out box is exactly 24.000px and the settled disclosure's own box is 20px, floored to 24 by the
  token, which is what decision 13 shipped. The chip's own `min-height` was restating its natural
  height back at itself, a no-op that read as a constraint.
- **`--rail`'s 6px is what the engine that ships reserves.** Measured on the two unbordered scroll
  boxes, `.history` and `.field` both reserve exactly 6px (`offsetWidth - clientWidth`). The recipe
  the deferral and the stylesheet comment both name needs one correction before anyone uses it: on a
  bordered box it over-reads by the border, `.reminders` answering 8px for a 6px rail inside two 1px
  edges.

### What the missing floor cost

Traced at 60Hz over the demo bridge, on an empty chat with the reminder stack acked, which is every
chat a user has no reminders due on. At 900x900 and at 640x720 alike, sending the first message took
the panel from 352px to **262px** and back to 297px as the reply began, an excursion of 90px whose
whole travel is the panel's top edge: the composer's own top reads 535 (and 445) for every frame of
it, the panel being pinned at its bottom edge. The panel then climbed past its starting height as
the answer arrived. So the first thing a user does in a new chat dropped the conversation 90px and
then walked it back up, which is the complaint decision 12 exists to answer, arriving through a
deletion rather than through a drift.

### The decision

**`.log` floors on `--chat-floor`, and `overlay/measured.ts` publishes that property from the empty
state's own box.** The same module publishes `--trace-row` from the live chip's box, and `.chip`'s
own floor is gone, so the chip is the row and the disclosure matches it rather than both restating a
constant.

- **The probe renders nothing.** A hidden copy of the empty state would reproduce the defect being
  fixed one layer down, the copy drifting from the real thing with nobody looking at the copy. Both
  elements are already in the tree exactly when their numbers are knowable, and each leaves exactly
  when its number starts to matter: the empty state stands for the whole life of an empty chat and
  is replaced by the first message, and the live chip stands for the whole of a turn's deliberation
  and is replaced by the disclosure that has to be as tall as it.
- **It is therefore not a startup probe, and no startup would be early enough.** Measured at boot,
  the first reading of the empty state is 183px against the 185px it settles at two frames later,
  because the example chips' row comes out 29px before the system font stack resolves and 31px
  after. So the empty state is a reading plus a watch, the shape `PanelEdge` already uses for its
  own box: once as React attaches the element, so the number is never missing, and again whenever
  the box actually changes. A chip is one reading, and the difference is reasoned rather than
  incidental: a chip cannot be on screen before the user has typed, so it is never measured through
  the settling the empty state sits in, and a tool chip and a status chip can be up at once, which
  one watch could not hold honestly, a shared ref callback being told that an element is leaving but
  never which one. Both chips are the same box, so a reading apiece says the same thing.
- **Neither watch can feed itself**, which is the care `panelWatch` documents. `--chat-floor` is
  spent by `.log`, and while the empty state is up the log carries `.log.bare`, whose own
  `min-height: 0` outranks it. `--trace-row` is spent by a disclosure that is never on screen beside
  the chip that publishes it. A reading changes nothing about the element it was taken from, so
  there is no resize for the panel's own watch to answer either.
- **Both readings are `offsetHeight`,** for the reason `panelMemory` gives: it ignores transforms,
  and both boxes are measured while one is running. The panel is scaled through a summon, and a chip
  arrives under a 300ms `confirmin` that translates and scales it, whose rect reads 23.883 against a
  laid-out 24.
- **When it cannot measure, the stylesheet's own value stands.** An element with no layout reports
  0 and publishes nothing, and an element that never mounts publishes nothing either: a chat
  restored with messages in it never shows the empty state, and a reply that did not reason never
  shows a chip. So `--chat-floor: 185px` and `--trace-row: 24px` stay declared on `:root` as
  documented fallbacks rather than being deleted, and the failure mode is exactly the behaviour that
  shipped before rather than a zero-height floor.

### The thumb the removal was right about

Restoring the floor brings back the defect the deletion cited, and it is real: a column taller than
the box it scrolls in overflows, so with the reminder stack still rolling away the history is handed
its share a frame at a time under a log already standing at the floor. Measured at 640x720, that is
**8 frames** with a thumb on screen, against the seven the removal reported.

The rule that hides the history's thumb while the panel is `[data-resizing]` already says why this
is wrong: the thumb is reporting a size the box is passing through rather than one it has. That rule
now covers the reminder stack's roll as well, and it names the **aside** rather than any rolling
section, which is a narrowing the browser argued for. The general version blinks a thumb that was
already on screen: measured on a history scrolling 845px inside 293px, one switcher round trip hid
it for 38 frames, to save 8 frames it should never have had. The stack is safe because of when it is
allowed to roll at all, being open only on a chat with no messages, so it can shut only as the first
message lands (this case) or as the last reminder is acked on an empty chat, where the log is
`.log.bare` and clips rather than scrolling. In neither is there an honest thumb to lose.

### What it measures

Panel height at rest on an empty chat, and again once the first message has landed, over the demo
bridge. The empty states are untouched; every case that used to fall now holds.

| State | Panel before | after |
| --- | --- | --- |
| 640x720, empty chat, reminder stack up | 450 | 450 |
| 640x720, first message sent, stack rolling away | 297.47 | 352 |
| 640x720, empty chat, stack acked | 352 | 352 |
| 640x720, first message sent, no stack | 297.47 | 352 |
| 900x900, empty chat, reminder stack up | 518 | 518 |
| 900x900, first message sent, stack rolling away | 297.47 | 352 |
| 900x900, empty chat, stack acked | 352 | 352 |
| 900x900, first message sent, no stack | 297.47 | 352 |

Frame by frame through the send with no stack, the panel now holds one height (352) from the
keystroke to the reply's first growth, where it ran 352, 348.67, 333.94, 306.81, 286.13, 274.30,
267.48, 263.78, 262.19 and back before. The published floor reads 183px in the frame the empty state
is attached and 185px once the font stack resolves, and the chip publishes 24px.

**The point of the change is what happens to an edit.** Lengthening the invitation by one wrapped
line takes the empty state to 201px: the measured floor follows it, and the panel stands at 368px
before the send and 368px after it. With the floor frozen at 185px under that same edit, the panel
stands at 368px before the send and **352px** after it, a 16px dip that is exactly the drift the
deferral predicted. The invitation was restored afterwards.

**Mutated three ways, each restored after.** Publishing the frozen `185px` instead of the measured
height reddens five tests across the module and both components. Dropping the ref from the empty
state reddens the Panel suite's floor test, and dropping it from a chip reddens the Message suite's.
The browser is the evidence for the CSS half, which jsdom has no layout to hold an opinion about.

### What this does not do

**The rail entry does not move, and a probe would not move it.** Measuring the rail is dead for want
of a consumer rather than for want of a measurement: no non-Chromium engine runs the overlay, and on
the engine that does the number is circular, since `::-webkit-scrollbar { width: var(--rail) }` sets
the width the probe would read back. Publishing a measured `--rail` on Chromium writes 6px over 6px,
and on a hypothetical Firefox it would have to be a second property rather than the same one, or the
webkit rule would consume its own output. The entry keeps its status, with its recipe corrected for
the border.

**Nothing machine-checks the two new properties**, which is the same TypeScript-into-CSS seam
`--ceiling` and `data-resizing` already have, and joins that deferral rather than opening one. The
literals are pinned in `measured.test.ts` so a rename has to walk past them.

## Addendum, 2026-08-03: the strip gets its keyboard, and what is hidden is untabbable

Decision 1 gave the console a tab strip with the right roles and half the pattern. It carried
`role="tablist"`, a `role="tab"` per face and `aria-selected` on the one showing, and it made focus
travel with the view, which is the half that makes the leaving pane's `aria-hidden` take effect at
all. The other half was deferred: a roving `tabindex` and arrow keys along the strip, and a pane on
its way out that is untabbable as well as unannounced. Both are closed here. The deferral put the
second half behind React 19, and that turned out to be wrong; the measurement is below.

### What the keyboard actually did, before

Driven in Chromium at 900x900 over the demo bridge, with real key presses rather than synthetic
events, reading `document.activeElement` after each one.

- **The strip was two stops, not one.** Both faces had no `tabindex` attribute at all, so both were
  in the page's tab order, and Tab from Face landed on Chords rather than leaving the strip.
- **Every key the pattern asks for did nothing.** ArrowRight, ArrowRight, ArrowLeft, Home and End
  in sequence left focus on Face and the selection on Face, five presses with no effect of any kind.
- **A pane on its way out was reachable.** Leaving the console for the chat and pressing Tab inside
  the 380ms fade landed on the back chevron, then Face, then Chords, all three inside `.view.out`
  and all three under its `aria-hidden="true"`, before the walk reached the body and wrapped into
  the chat. Three stops in a pane the user had already left.
- **Switching tabs was worse, because it also dropped focus.** The two panes cross-fade over 200ms
  and the stylesheet takes the leaving one out of the tab order with `visibility: hidden` on a delay
  that waits for the fade. Tab pressed inside that window walked six stops through the tab being
  left (Auto, Midnight, Daylight, Mull, Muse, Hunch, every one of them under the pane's own
  `aria-hidden`), and then `visibility` landed on the element that had focus and the keyboard was on
  the body.
- **A dismissed panel was a whole invisible panel of stops.** The panel is never unmounted, and
  closed it is `opacity: 0` with `pointer-events: none` and nothing at all taking it out of the tab
  order. Esc to the orb and six presses of Tab reached the two reminder rows' open and dismiss
  buttons, three times round, inside `aria-hidden="true"`.

### The React 19 claim was wrong, and this is how

The deferral said the leaving pane wants `inert` "which React types only from 19 (this tree is on
18, and setting the attribute by hand around a subtree React owns is the kind of thing that reads as
a bug later)". Only the first clause is true, and it is about types rather than about React. Probed
against the tree's own react-dom 18.3.1, on the server renderer and on the client:

| written | rendered | warning |
| --- | --- | --- |
| `inert={true}` | `<div></div>` | yes, "Received `true` for a non-boolean attribute" |
| `inert=""` | `<div inert=""></div>` | none |
| `inert="inert"` | `<div inert="inert"></div>` | none |
| `inert={undefined}` | `<div></div>` (removed again) | none |

React 18 has no entry for `inert` in its prop tables, so it falls through to the custom-attribute
path, which writes a string value straight to the DOM and drops a boolean one. An empty string is
how HTML spells a boolean attribute that is present, so the string form is not a workaround for the
real thing: it is the real thing, written the way the platform writes it, by React, through JSX,
with nothing set by hand around a subtree React owns. What React 18 genuinely lacks is the type,
which `@types/react` 18.3.31 confirms by not mentioning `inert` anywhere. One module augmentation in
`overlay/withdrawn.ts` adds it, narrowed to the empty string so no call site can write the form
React 18 drops. Upgrading React was neither needed nor attempted.

This is the third entry in a row whose cost estimate was wrong about itself, and it is worth naming
the shape: the estimate reasoned from a version number to a capability. The capability was one
`renderToStaticMarkup` call away from being checked.

### The decision

**One rule for what is hidden, one map for what the keys do.**

1. **`aria-hidden` and `inert` are written together, by one function, in every place the overlay
   holds something mounted that is not on screen.** `overlay/withdrawn.ts` exports `withdrawn(away)`
   returning the pair, and the three places spread it: the panel while it is dismissed, the view
   being left for the length of its morph, and the tab not showing inside the console. The two
   attributes are not two spellings of one idea, which is why the pairing is the rule rather than a
   convenience. `aria-hidden` hides a subtree from assistive technology and leaves the tab order
   alone, and a browser refuses it over an ancestor of the focused element, so it needs the app to
   move focus first before it does anything at all. `inert` takes the subtree out of the tab order,
   out of the pointer's reach and out of the accessibility tree, and it blurs whatever inside it had
   focus rather than asking to be helped. `aria-hidden` stays beside it because it is what every
   reader already understands, and it stays written in both directions, an explicit
   `aria-hidden="false"` on the live view being a useful thing for the tree to say. `inert` is
   written in one direction only: its absence is its false, and `inert="false"` would be an inert
   element.
2. **The strip is one stop in the tab order, and the stop is the tab that is up.** A roving
   `tabindex`, 0 on the selected face and -1 on the others. With selection following focus this
   needs no memory of its own, because the tab that has focus and the tab that is selected are the
   same tab: `aria-selected` and `tabIndex` are two readings of one fact rather than two pieces of
   state that could disagree.
3. **Selection follows focus.** One arrow press both moves the keyboard and changes the view. The
   practice recommends automatic activation wherever showing a panel costs nothing, and here it
   costs nothing twice over: both panes are already mounted and stacked in one grid cell, so there
   is no load and no latency, and at the shipping spread of 12px they share a height
   (`TAB_SPREAD_PX`), so the panel does not even resize. Manual activation would make the keyboard
   pay two keystrokes for what one click already does, on the surface whose entire content is
   reversible preferences, and it would need a second piece of state (the focused tab, separate from
   the selected one) to hold the gap between them. If a future face is far enough from its
   neighbours to put the panel back into a morph on every arrow, this is the decision to revisit,
   and `TAB_SPREAD_PX` is the number that would say so.
4. **The arrows wrap, Home and End do not.** Wrapping is what the practice recommends, and on a
   strip of two it is what makes the arrows worth pressing: stopping at the ends would leave
   ArrowRight a no-op half the time, which reads as a broken key rather than as a strip that has an
   end. Home and End are absolute by their own meaning, so there is nothing for them to wrap around;
   End on the last tab is the last tab, and it asks for the tab already up, which `openConsole` has
   always treated as the no-op it is.
5. **The strip answers Left and Right and not Up and Down.** It is a horizontal strip, which is the
   practice's own condition for that, and the overlay spends Ctrl with the vertical arrows on
   cycling chats. A strip that also answered them would put two meanings on one gesture, told apart
   only by a modifier. The four keys it does answer are `preventDefault`ed, because the panel clips
   its overflow and Home, End and the arrows scroll a clipped box the user cannot scroll back.
   Everything else passes through untouched, which is what keeps Esc, Ctrl+K and the rest reaching
   the window listener in `Overlay.tsx` from a focused tab.
6. **Focus follows the selection at every switch, not only on the way in.** The `autoFocus` that
   decision 1 put on the arriving pane's selected tab is now an explicit layout effect on the tab
   that is up. On the way in it does exactly what `autoFocus` did. It also covers the switches,
   which `autoFocus` never did because the console pane is not remounted when the tab changes, and
   there are three of those. The arrows land there already, so it is a no-op for them; a click
   arrives with focus on the button the pointer pressed, so it is a no-op for that too. The third is
   the one it repairs: `?` is a global key that toggles the shortcut tab from anywhere, so it can
   change the tab while the keyboard is down among the theme tiles, and that pane is about to go
   inert underneath it. It focuses with `preventScroll`, for the reason the composer's focus already
   gives at length: the panel is a scroll container the user cannot scroll and the engine can, and
   bringing a newly focused element into view is exactly when it does.

One piece of the ROLES came with the keys, the strip's roles having otherwise been complete since
decision 1: each face now carries `aria-controls` naming the pane it opens, over an id minted by
`useId` rather than written by hand. The two already read alike, the pane taking its accessible name
from the same label as its tab, but a reader offering "move to the panel" needs the pointer rather
than the coincidence, and a duplicated id is what a test now reddens on.

The keys live in `overlay/tabStrip.ts` as one pure map, `nextTab(key, tabs, from)`, generic over
what a tab is and returning the tab rather than its index. That is where the wrap lives, so what the
strip does with a key is one function to read and one function to change, and a second strip would
be a call rather than a copy. It answers `null` for a strip with nothing on it, which is the only
edge in the arithmetic and is pinned as such.

### What it measures

Same window, same bridge, same key presses, after.

- **The strip is one stop.** Face is `tabindex="0"` and Chords `tabindex="-1"`, and they swap with
  the selection. Tab from the selected face leaves the strip entirely; the whole console is two
  stops now (the back chevron and the one live face, plus whatever the live pane holds) where the
  walk used to include both faces and the hidden pane's tiles.
- **Every key works, and moves the view with it.** ArrowRight put focus and `aria-selected` on
  Chords with `tabindex` following; a second ArrowRight wrapped back to Face; ArrowLeft went to
  Chords and again to Face; Home landed on Face and End on Chords, each with the selection and the
  roving index in the same place as the focus.
- **The leaving view is unreachable.** `.view.out` now carries `inert`, and the eight Tab presses
  after leaving the console for the chat land on Send, Settings, Shortcuts, the body, and then
  Recent chats, Toggle theme, New chat and Dismiss: eight stops, all in the live chat, zero in the
  pane on its way out, against three in it before.
- **The 200ms tab crossing is unreachable too.** Switching tabs without moving focus and then
  pressing Tab eight times inside the fade gives zero stops in the leaving pane, against six before,
  and focus is never dropped to the body by a `visibility` flip landing on it.
- **A dismissed panel takes nothing with it.** Six presses of Tab after Esc land on the body six
  times, against six buttons inside the invisible panel before.
- **The `?` key no longer loses the keyboard.** With focus on the Auto theme tile, pressing `?`
  used to leave focus on the body once the fade finished. It now lands on the Chords tab, 40ms after
  the press and still there 440ms later.

**Mutated six ways, each restored after.** Removing the roving `tabindex` reddens the one-stop test
and the arrow test. Taking `onKeyDown` off the strip reddens four. Making the arrows stop at the
ends instead of wrapping reddens two in the pure map's suite and one in the view's. Making
`withdrawn` return `aria-hidden` alone, which is exactly the state this addendum found, reddens five
across three suites. Dropping the `preventDefault` reddens the test that asserts which keys the
strip claims. Dropping the focus effect reddens three in the console's suite and one in the panel's.

### What this does not do

**The chat switcher is mis-roled, and that is a new deferral rather than part of this.** Its `<ul>`
carries `role="listbox"` while its rows are `<li>` elements holding four ordinary buttons each and
no `role="option"` anywhere, so its children do not satisfy the role its container claims; measured
in the same session, one open switcher offered eight tab stops across two rows. That is not the
defect this addendum fixes. The strip was correctly roled and keyboard-incomplete, and completing it
is additive; the switcher's roles and its interaction model disagree with each other, and settling
that means choosing between two shapes (make the rows options and give the list one stop with
`aria-activedescendant`, or drop the listbox role and let it be the list of composite rows it
already behaves like) and reconciling whichever wins with Ctrl+Up and Ctrl+Down, which cycle
sessions without moving focus at all. It is recorded in
[refinements/body-overlay.md](../refinements/body-overlay.md).

**A section rolling shut stays tabbable, and deliberately.** `.collapse` hides its overflow while
its height animates to zero, and clipped content keeps its place in the tab order. It
is also still in the accessibility tree, with no `aria-hidden` on it, so both channels agree, which
is the standard this addendum is applying rather than a violation of it. A section rolling shut is
still on screen and still shrinking; it is not a pane that has been left.

**The reminder stack is a list of rows with buttons and needs nothing.** Its `<ul>` claims no role
its children have to satisfy, and tabbing through the rows is the correct pattern for it.

**A tabpanel holding no focusable element does not take a tab stop of its own.** The practice asks
for `tabindex="0"` on such a panel so a keyboard user can reach its content, and exactly one of the
two qualifies: Chords is a static list of keycaps with nothing focusable in it, while Face is a wall
of buttons. Adding it would put a stop on the panel that shows no focus ring and does nothing on the
sighted keyboard path, to reach a list that scrolls nowhere and that a reader already reaches by its
own name and through the `aria-controls` above. The trigger to revisit is a panel that scrolls, or
one whose content a keyboard user needs to reach with no control inside it, at which point the rule
is per panel (does this one hold anything focusable) rather than per strip.

## Addendum, 2026-08-03: the switcher's rows leave the same way, and reordering is what they add

The addendum above built `overlay/usePresence.ts` generic and wired only the reminder stack to it,
recording the switcher's rows as a deferral that called itself mostly a wiring change. The wiring is
about half of it. The hook needed one real change, the markup needed a restructure the reminder
stack's did not, and a leaving row needed to stop being clickable.

**What the switcher did before.** Traced at 900x900 over the demo bridge, deleting the middle of
three chats: the row and its 50px went between one frame and the next, `list=164` at t=21 and
`list=114` at t=37.7, with the row below jumping from y=270 to y=220 in that same frame. The panel
does not move at all here (518 tall, composer top 535, on every frame), because the history absorbs
the change, so that one snap was the entire visible event.

### The decision

**The rows render from `usePresence`, and the row is what is held.** Exactly as the reminder stack
does: the delete goes to the brain in the frame the confirm is pressed, `deleteSession` drops the
chat from `state.sessions` when the write lands, and the row stays on screen inside its own
`Collapse` until that roll reports itself over through `onClosed`. The clock and the curve are
`MORPH_ROLL_MS` and `EASING`, as everywhere else.

**A leaving row goes back UNDER the row it was under, not at the index it held.** This is the one
change to the hook, and it is the switcher's own requirement. The reminder stack only ever loses
rows, so its order is one-directional and a remembered index and a remembered neighbour agree on
every frame of it. The switcher re-lists after every write and lists pinned chats first and then by
recency, so a pin, a finished turn, or a plain summon refresh can reorder the list underneath a row
that is still rolling out. `Leaving` therefore carries the key of the row above it as well as the
index, and `merge` puts it back after that key when the key is still on screen. The index survives
as the fallback, for a neighbour that has been released first or that a whole re-listing dropped,
and it still clamps to the end of the list so a row released out of order takes its slot with it.
The anchor is read off what was on SCREEN rather than off the caller's list, so it can be another
leaving row, and the ascending sort in `merge` guarantees that anchor is already back in place when
the row that hangs from it looks for it.

**The `<li>` carries nothing but its place in the list.** `.switcher-slot` sits outside the roll and
`.switcher-row` inside it, which is the reminder stack's arrangement and the first of its two
reasons: a list whose items are wrapper `<div>`s is not a list to a screen reader. Its second
reason does not apply, the switcher drawing no rule between rows, so there is no adjacent-sibling
hairline here to switch off. A third reason the reminder stack did not have does apply, and it is
the load-bearing one: `min-height: 50px` is what keeps a row the same height whether it is showing a
title over a preview, a rename box, or a delete confirm, and left on the outside of the roll it is
also a floor the roll cannot get under.

**A leaving row is withdrawn for the length of its exit.** `withdrawn(leaving)` from
`overlay/withdrawn.ts` puts `aria-hidden` and `inert` on the slot. A row held on screen after its
chat is gone is otherwise 300ms in which its title still opens a deleted chat, its trash still asks
to delete one that no longer exists, and the tab order still walks all four of its buttons. This is
new exposure that the exit itself creates, so the exit closes it.

**And the demo bridge deletes for real now.** It was the one catalog write left as a no-op over its
held list while rename and pin both stuck, which made this exit unmeasurable by hand: the reducer
dropped the row, the refresh immediately behind it listed the chat again, and the row that had just
begun rolling out came straight back. The demo also seeds a third chat, because only a middle row
shows both halves of the motion at once.

### What it measures

Chromium over the demo bridge, three chats, the switcher open, traced per animation frame.

- **900x900, deleting the middle row.** The row runs 50.00px to 0.00 from t=53.4 to t=353.4, which
  is the 300ms roll and the frame it starts on. The row below travels 269.63 to 220.00 across those
  same frames; the row above holds at 170.00 on every one of them. The card runs 164 to 114. The
  panel is 518 tall with its top at 108 and its composer at 535 on every frame of the exit, so
  nothing outside the list moves at all. The slot leaves the DOM at t=386.8 and the card reads 114
  on the frame before and the frame after, which is a released row costing nothing.
- **640x720, the body's own window, same gesture.** The list is at its cap here (135.14px of a
  162px content), so the card holds 135.14 for the first 155ms and only starts shrinking once the
  content falls under the cap, reaching 114 at the end. The rows inside travel throughout. Panel 450
  and composer 445 on every frame. A capped, scrolling switcher rolls a row out inside its own
  scroll box and the panel never hears about it.
- **A pin landing 120ms into a delete, at 900x900.** At t=137.8 the list re-groups: the pinned chat
  takes the top, the previously pinned one takes second, and the rolling row (20.48px at that
  instant) travels from y=220 to y=270 with the row it sat under. The card's height eases straight
  through the reorder, 141.13 to 134.48 to 129.23, with no discontinuity. Under the index rule the
  same trace leaves the rolling row at y=220 and walks its former neighbour down past it to
  y=240.47, so the closing gap ends up between two rows it was never between and one of them
  crosses it.
- **Deleting the chat the panel is showing.** The reducer resets the panel to a fresh empty chat in
  the same commit that drops the row, and the reminder stack is keyed to the session so it remounts
  with it. The top row still runs 50.00 to 0.00 over 300ms with both rows below travelling in step,
  and the panel holds 518 with the composer at 535 on every frame.
- **Deleting the LAST chat**, which is the one case with a rough edge. The row rolls out cleanly and
  the panel follows the last 11px of it, since the history has nothing left to give (top 108 to 119
  from t=189.7, monotonic, largest single frame 2.86px, composer still at 535). Then the empty line
  arrives in one frame at t=356.7, taking the card 14 to 53. The panel does NOT snap back with it:
  it eases 119 to 108 over the following 117ms, monotonic, largest single frame 2.77px. The trace's
  own reading of 108 in the frame the line lands is the artefact this ADR's watch addendum already
  documents (`requestAnimationFrame` runs before the placement's own frame, so a probe there reads
  the natural box with no animation attached, which a re-run confirmed: the animation first appears
  one frame later, starting at 118.41). So the one-frame event is the line appearing inside the
  card, and it is recorded as a deferral rather than smoothed, for the reason under it.

### The mutation proof

Three, each restored afterwards.

1. **Placing a leaving row by index alone** reddens exactly two tests, the reorder case in
   `overlay/usePresence.test.tsx` and the one in `components/SessionList.test.tsx`, and nothing
   else. The browser trace of the same mutation is the y=240.47 counterfactual above.
2. **Rendering `sessions` instead of `stack.entries`** reddens six in the switcher's suite: the
   held row, the withdrawal, the reorder, the whole re-listing, two exits at once, and the empty
   line waiting.
3. **Putting `min-height: 50px` back on `.switcher-slot`** passes every test, because jsdom has no
   layout, and the browser shows the defect immediately: the row stands at 50.00 for the whole
   300ms roll and then vanishes in one frame, 164 to 114 at t=370.4. That is the old snap arriving
   300ms late, and it is why the split is in the CSS comment as well as here.

### What this does not do

**The switcher's empty line still arrives in one frame.** Deleting the last chat rolls that row out
and then puts "no other chats yet" up in the frame after, costing the panel the 11px correction
measured above. Rolling the line in as well was considered and is worse in the other direction: a
first chat arriving into an empty list would then add the new row's 50px instantly and only
afterwards roll the 39px line away, an overshoot larger than the snap it removes. One flag cannot
make both directions smooth, so the line is left instant and the case is filed in
[refinements/body-overlay.md](../refinements/body-overlay.md). Answered later the same day by the
addendum below, which found that it is not one flag: the direction that must be instant is a plain
unmount, and the line now grows in over the leaving row's own roll.

**The reorder itself is not animated.** A pin regrouping the list moves every row it touches in one
frame, exactly as it did before this, and what changed is only that a row on its way out travels
with them instead of being left behind. Animating the reorder is a different mechanism (every row's
position read before the commit and played back after it, the pattern usually called FLIP) and a
different decision, filed with the line above. Landed later the same day by the addendum below, as
`overlay/useTravel.ts`, with the leaving row on the survivors' clock.

**The `role="listbox"` question is untouched.** The switcher still puts that role on its `<ul>` over
rows of ordinary buttons with no `role="option"`, which the addendum above opened as its own
deferral, and this change is deliberately neutral to it: whichever shape wins, the role belongs on
the `<li>`, which is where it would have gone before and where it still goes. The one thing added to
those elements is `aria-hidden="false"` on a row that is not leaving, which is the default state
written out and is harmless under either answer. Answered later the same day by the addendum below,
which took the role off and left the `<li>` carrying its own implicit one.

**And the rows still have no ENTER animation.** A chat arriving in the list appears in the frame the
refresh lands, which is what it did before. The asymmetry is on purpose and is the same one the
reminder stack has: a removal is a gap that has to close before the eye can follow it, while an
arrival is already where it belongs.

## Addendum, 2026-08-03: the switcher is a list of rows, and a row says which chat is open

The addendum above opened the switcher's role as a deferral with two shapes and left the choice to
the user. The user chose: **drop the listbox role.** The switcher announces the list of composite
rows it already behaves like, every per-row button stays individually reachable, `Ctrl+↑` and
`Ctrl+↓` keep cycling chats exactly as they did, and no `aria-activedescendant` or `role="option"`
went in.

### What the role actually cost

The deferral said a listbox was announced whose required children were missing. Read out of
Chromium's accessibility tree at 900x900, it was worse than that, because a `<li>` inside a listbox
is not a listitem either. The container came through as `listbox "Recent chats"` over three children
of role `none`, each holding its four buttons directly, so the rows had no boundary a reader could
count by: a listbox with no options in it and twelve loose buttons inside.

### The decision

`role="listbox"` comes off the `<ul>` in `body/app/src/components/SessionList.tsx` and nothing
replaces it. The `aria-label` stays and now names a list rather than a listbox, and the implicit
list and listitem roles come back on their own, so no role is written on the `<li>` at all. That is
the reminder stack's arrangement exactly, a named `<ul>` with no role and rows of ordinary buttons
under it, which is what the two lists should have had in common from the start.

One thing had to be added rather than removed. Which chat is open was carried by the `.current`
background tint and by nothing else, and this answer drops the one ARIA shape that could have
carried it, since `aria-selected` needs the listbox. The row's own button therefore takes
`aria-current`, written `true` on the open row and `false` on the others, which is the pin toggle's
`aria-pressed` idiom one row over. The value is `true` rather than one of the tokens because a chat
is none of the enumerated kinds: not a page, a step, a location, a date or a time.

`Ctrl+↑` and `Ctrl+↓` needed no reconciliation in the end. They are an application-wide cycle, not
movement inside a list, and with the listbox gone the markup no longer promises otherwise.

### What it measures

Chromium at 900x900, on the demo's own seed, before and after:

- **The tree.** `listbox "Recent chats"` over three `none` children becomes `list "Recent chats"`
  over three `listitem`s, each holding the row's four buttons.
- **The tab order is untouched.** Twelve stops inside the switcher both times, four to a row, in
  the same order, with the whole cycle at 24. The deferral's "eight tab stops across two rows" was
  right for the list it measured and is eight no longer, the demo having seeded a third chat when
  the row exit landed; four to a row is the figure that carries.
- **The open chat says so.** Nothing is current at boot, the demo restoring a chat that is not in
  the seeded list. Clicking the second row and reopening the switcher reads
  `Everything about model swaps=true` with the other two rows `false`, and a `Ctrl+↓` press lands
  the same `true` on the chat it cycled to.

Two notes for whoever measures next. jsdom does not reproduce the row finding at all, since
`dom-accessibility-api` maps `<li>` to `listitem` whatever an ancestor claims, so the browser is the
only place the `none` rows are visible and the Vitest suite pins what it can see: no listbox in the
tree, a named list, a listitem per row, four buttons each at `tabIndex` 0, and `aria-current` true
on the open row and false on the rest. And `aria-current` cannot be read back from CDP, whose
accessibility domain has no `current` among its property names, so it was verified per row in the
live DOM beside the roles that did come out of the tree.

### The mutation proof

Putting `role="listbox"` back reddens the new test at its first assertion, and taking the
`aria-current` line off reddens it at its last. Both were checked in place and restored.

### What this does not do

**The swap itself is still silent, and that is a new deferral.** Leaving the cycle keys alone leaves
them announcing nothing: a press replaces the whole conversation with focus where it was, and the
page's only live region is the link indicator reading the brain's health. Measured at 900x900, two
presses walk the header title through three chats while focus stays on the header's chats button,
and the first press closes the switcher under it. The listbox shape would have answered this by
moving focus, so the rejected shape takes the answer with it; what fits this one is a polite live
region naming the chat that arrived. Recorded in
[refinements/body-overlay.md](../refinements/body-overlay.md) and on its index.

**The header's chats button still shares the list's accessible name.** Both are "Recent chats",
read in the same pass and left alone: they announce with different roles, so the button and the list
are told apart in speech by what follows the name.

## Addendum, 2026-08-03: the empty line is not a row, and a row that stays travels

The row-exit addendum above closed with two motions left instant on purpose, filed as one deferral:
the switcher's empty line arriving in the frame after the last row's roll, and a reorder moving
every row it touches in a single frame. They are answered here, one by a decision about what an
empty list is, the other by the mechanism the deferral named.

**What the two actually did.** Traced at 900x900 over the demo bridge, per animation frame.
Deleting the last chat rolled the row out over 300ms (card 64 to 14, largest single frame 7.47px)
and then put the line up in the next frame, card 14 to 53, with the panel easing its top 119 to 108
over the 117ms after that. Pinning the third of three chats moved every row in the frame the
re-listing committed: the pinned chat 270 to 170, the two above it 50px each, all in one 16.7ms
step. The deferral's numbers were right, its reading of the panel was right, and the shape of the
fix it proposed for the first one was not.

### The decision

**The empty line waits for the row it replaces and yields to the row that replaces it.** The line is
not a row. It is what the list says when it has nothing to say, so it has no claim on the eye and no
right to keep a chat waiting. That gives the two directions different rules, which is what the
deferral asked for, and they turn out not to need a flag between them:

- *Emptying.* The line is asked of `sessions` rather than of the rendered rows, so it goes up in the
  same commit that starts the last row's exit, and `Collapse`'s new `enter` prop grows it from
  nothing over that row's own roll. The two are on screen together for those 300ms, the row
  shrinking to zero while the line grows to 39, and the card eases from a row's height to a line's
  instead of collapsing to 14 and snapping 39px back up.
- *Filling.* The line is unmounted in the frame a chat arrives. There is no roll to run, because the
  thing the eye is going to is the row, and a line rolling away underneath it would add the row's
  50px at once and take the line's 39 off over the following 300ms, which is an overshoot bigger
  than the step it removes. This is the direction the deferral correctly refused to smooth.

The order in the markup is load-bearing: the line renders BELOW the rows, so the first
`data-morphing` in the tree during those 300ms is the leaving row's, and the ride-along
(`panelRide.ts`) reads the target the card is actually going to rather than the line's.

**`enter` is read once, at mount.** A section mounted with the view it belongs to is already there
and animates only what happens to it afterwards, which is why the switcher's list rolls open when
the panel opens it and not when it is built. Something mounted INTO a list already on screen has
arrived, and only that case wants the roll. Opening the switcher on a list that is already empty
therefore shows the line at its full height with nothing animating, which is what keeps the
section's own roll measuring a card of 53 rather than one growing out of nothing.

**A row the list MOVES travels there, through `overlay/useTravel.ts`.** The mechanism is the one the
deferral named: read where each row is, let the commit put it where it belongs, and hand the
difference back as a `translateY` that decays to nothing over `MORPH_ROLL_MS` and `EASING`. Three
things about it are worth writing down.

*A transform cannot fight the panel.* Layout is final in the frame a travel starts, so the card's
height never changes, the panel's `auto` height has nothing to follow, and the `ResizeObserver` the
panel keeps on its own box has no resize to answer. Measured across a reorder, the card holds 164 on
every frame and its `scrollHeight` holds 162 against a 162 client box, so the rows moving through
each other never even reach for a scrollbar.

*A row is remembered by its element, not by a key.* React moves the DOM node a keyed row owns rather
than rebuilding it, which is what makes a reorder a reorder, so the element is the identity and a
`WeakMap` needs no cleanup. A row that was rebuilt is correctly a row with nowhere to travel from.

*Where a row WAS is not where the last commit left it, and this is the finding the deferral did not
have.* A roll moves rows by layout, frame by frame, with no commit anywhere in it: over a deleted
row's 300ms exit its neighbours below travel 50px, and the next commit is the release, once the roll
has already taken them there. Read against the previous commit, that is a 50px jump to answer, and
the answer is a travel back down a distance the row had just covered, which is a worse defect than
the one being fixed. So while a roll is in flight inside the list the record is refreshed every
frame and nothing is played from it: the frame loop only remembers, and only a commit may animate.
That is also what puts a regrouping that lands mid-roll on honest numbers, the leaving row included,
since every row is measured from where it was in the previous frame.

*An interrupted travel is composed, not cancelled.* A second regrouping mid-travel finds a row
visually between two places and structurally at the second, so cancelling would drop whatever of the
first travel was still in the air. Every travel is `composite: "add"` instead, each a translation
decaying to zero, so the offsets sum to the gap the eye has and the row lands where layout already
put it.

**And the demo bridge can make a chat arrive.** `converse` remembers the chat it was called for,
titled by `deriveTitle`, which is the brain's own rule applied locally, so a turn in a fresh chat
puts a row in the list on the refresh that follows it. The demo's list could only ever shrink
before, which left the filling direction of the empty line unmeasurable by hand: the same gap the
delete had before the row exit landed, found the same way and closed the same way.

### What it measures

Chromium over the demo bridge, per animation frame, before and after.

- **The last chat deleted, 900x900.** Before: the card ran 64 to 14 over the roll's own 300ms and
  then 14 to 53 in one frame, with the panel's top walking 108 to 119 over the roll and easing
  118.41 back to 108 over the 117ms after the line landed. After: the card runs 64 to 53 over 283.9ms, largest single
  frame 1.66px, and the panel's top holds 108 with its height at 518 on every frame of it. The
  39px frame is gone and so is the correction that followed it.
- **The same gesture at 640x720**, where the panel is on its ceiling: card 64 to 53 over 283.5ms,
  largest single frame 1.66px, panel top 86 and height 450 on every frame.
- **A chat arriving into an empty list, 900x900.** Card 53 to 64 in one frame, before and after
  alike. That step is the difference between a line's height and a row's, and it is kept
  deliberately (below).
- **The switcher reopened on an empty list.** The card reads 53 from the first frame, with no roll
  inside the section's own.
- **A pin regrouping three chats, 900x900.** Before: the pinned chat 270 to 170 and the two above it
  50px each, all in one frame. After: 270 to 170 over 300.3ms with a largest single frame of
  15.04px, the other two 50px each with a largest single frame of 7.52px, and the card at 164
  throughout.
- **Two pins 90ms apart.** The second travel starts while the first is in the air: every row moves
  continuously, largest single frame 14.76px, and all three settle at their new places by t=415.1
  against a second regrouping that committed at t=101.9, which is that travel's own 300ms and no
  more. Nothing is left stranded. A row whose first travel was carrying it somewhere else does pass
  its new place and come back (the chat pinned first runs to 201.2 on its way to 220), which is what
  composing two eases looks like and is continuous throughout.
- **A pin landing 120ms into a delete's roll.** The regrouping frame moves nothing (the rows swap in
  the DOM and their transforms hold them where the roll had them), the two survivors then travel to
  their new places at a largest single frame of 7.79px while the roll continues underneath, and the
  release commit at the end of the exit costs nothing: the row below reads 185.27 on the frame
  before it and 181.24 on the frame after, which is the roll's own pace.

### The mutation proof

Eight, each restored afterwards, each reddening only what it should.

1. **The line waits for the rendered rows again** (its old condition): one test fails, the empty
   line growing into the gap.
2. **The line mounts without `enter`**: the same test fails, at the roll rather than at the timing.
3. **`Collapse` ignores `enter` on mount**: one test fails, in its own suite.
4. **Travels replace rather than add**: two fail, the interruption and the terms of the animation.
5. **The frame loop is never started**: three fail, including the release-commit case, which is the
   regression this loop exists to prevent.
6. **Reduced motion is ignored**: one fails.
7. **A pending frame is never cancelled**: one fails.
8. **The list is never asked to travel**: one fails, the switcher's own wiring.

### What this does not do

**A chat arriving into an empty list still steps the card 11px in one frame.** That is a line's 39px
being replaced by a row's 50, and smoothing it needs the arriving row to roll in, which no row in
the overlay does. The asymmetry is the one the row-exit addendum already recorded and defended: a
removal is a gap that has to close before the eye can follow it, an arrival is already where it
belongs. It is three and a half times smaller than the 39px frame it replaces and it happens in the
direction the eye is already looking. Trigger for revisiting it: the maintainer catching that frame,
or a list in the overlay wanting arrivals to roll.

**A row that leaves and comes back mid-roll takes the line with it abruptly.** A failed delete lists
the chat again, the row's `Collapse` reopens from where it had rolled to, and the empty line, being
unmounted the moment `sessions` is non-empty again, goes in that frame rather than rolling back out.
Nothing else was worth the second mechanism: the case is a lost write, the line is at most 39px, and
the row coming back is what the eye follows.

**The travel is the switcher's alone.** The reminder stack only ever loses rows, so it has nothing
to travel, and `useTravel` is written against a selector and a ref rather than against the switcher
so that the second list to want it wires it in one line.

## Addendum, 2026-08-03: the log rides a roll, and anchoring's good half comes back as code

Decision 14 taught a Thoughts trace to roll open in place. Decision 15 took Chromium's scroll
anchoring out of the history, because the position already had two deciders and did not need a
third. Both left the same thing behind: at the panel's ceiling there is no room for the panel to
absorb a trace, so the growth goes into the log's scroll range instead and the end of the reply
slides out under the composer, and nothing in the overlay answered it. This closes the refinement
filed for it in [body-overlay.md](../refinements/body-overlay.md).

1. **The rule is the tail pin, held across a roll.** Whether the reader is at the tail is the claim
   the log already keeps and already restores (`overlay/useLogScroll.ts`), and the reader at the
   tail is the one this happens to. So while they are there, `overlay/logRide.ts` holds the same
   distance from the end of the content for every frame of the roll, and the growth comes out of
   the scroll rather than out of the reply. A reader who has scrolled up is left alone, which is
   the disclosure's own default and the right one for them: a section growing pushes only what is
   BELOW it, and what is below it is not where they are reading. Traced at 60Hz at 640x720 on a
   history full enough to hold the panel at its ceiling, before: the trace was 76px, the
   disclosure's top edge held at 262.41px for every frame, and the distance from the log's bottom
   edge to the end of the reply went 3px to 79px. After: that distance reads 3px on every frame of
   both directions, `scrollTop` runs 408 to 484 and back, the largest single frame is 12px, and the
   movement spans t=44ms to t=311ms, which is the roll's own 300ms and no second beat after it.

2. **One rule, both directions, and the closing one is what decision 15 gave up.** Closing is the
   same sentence and lands back on the pixel the opening started from. It is also the service
   anchoring had been performing: with a trace scrolled off the top of the window, anchoring eased
   `scrollTop` down with the shrink so the visible content never moved, which decision 15 recorded
   as its one good half (498 to 422 in that trace) and gave up to be rid of the bad one. Traced on
   the same path now, deliberately: `scrollTop` eases 487 to 411 across the shrink and the oldest
   visible bubble holds its place to under a pixel for every frame. `overflow-anchor: none` stays,
   and it is now a line that gives up nothing: the engine's compensation was a guess about which
   node to hold, and this is the log's own policy applied on the roll's own frames.

3. **There is no clock here and no curve.** The scroll is recomputed from the box on every frame of
   the roll, and the box is being resized by the roll's own height animation, so the scroll inherits
   the roll's timing by construction rather than by agreeing with it. Neither `MORPH_ROLL_MS` nor
   `EASING` is read in the file, which is the strongest form of sharing them, and `Collapse.tsx` is
   untouched. The filed entry expected the opposite, asking for "a scroll animation alongside
   `Collapse`'s height animation" on the grounds that `Collapse` "owns the only clock either could
   share". A second animation would have had to predict how much of the growth the panel was about
   to absorb; reading the box each frame needs no prediction at all, and answers the panel's own
   ride-along and its ceiling by measuring what they did rather than by modelling them.

4. **Below the ceiling nothing scrolls, because nothing needs to.** The panel grows by exactly what
   the trace takes and the history grows with it, so the scroll range never changes and the ride's
   arithmetic returns the position the box is already at. Traced at 900x900 on a one-turn chat: the
   panel goes 390.97 to 466.97 and `scrollTop` reads 0 on every frame of both directions. This is
   the case a fix that assumed the trace's whole height would have got wrong.

5. **The cap is that the reader keeps what they opened.** Holding the tail through a trace taller
   than the window would scroll the trace's own top edge off the screen and leave the reader on its
   bottom half, so the ride stops at the frame the section's top edge reaches the top of the window.
   Traced at 640x600, where that edge sits 58px down a 206px window: the ride spends exactly those
   58px, stops at t=181ms with the whole trace in view from its first line, and lets the last 21px
   of the growth go into the scroll as before. The cap is measured on the rolling section rather
   than on the block around it, which costs the "Thoughts" control a row of visibility in that one
   case and buys a rule that does not depend on how much markup sits between the section and the
   box. A section already above the window caps the ride where it stands, since scrolling further
   down would carry the reader away from the thing they opened.

6. **The reader outranks the ride.** Every frame compares the box against what the ride last wrote,
   and anything else that moved it, the wheel or the tail pin answering a reply that landed
   mid-roll, ends the ride on the spot. Traced at 640x720 with an 80px wheel at t=190ms: the ride
   stood down in the frame it landed and `scrollTop` read the reader's number for every frame after
   it. The comparison is against the last written position clamped to the range the box has NOW,
   because a closing roll shortens the content under a position the engine then clamps for itself,
   which is the box moving and not the reader.

7. **The claim is measured, not remembered, and that was a real defect on the way.** The log's own
   copy of "the reader is at the tail" is refreshed from scroll events, and a roll is precisely the
   thing that falsifies it without one. Built on the remembered answer, the ride at 640x460 (a 121px
   history with the disclosure above the window) did nothing on the way open, correctly capped, and
   then eased the log 76px on the way shut on a claim that had been false since the open: a round
   trip that had been exactly reversible left the reader 76px off where they started. Read off the
   box on the roll's own first frame, which is the one moment in a roll where the log is still the
   size it was, both directions answer for the state they are actually in.

8. **Under `prefers-reduced-motion` the log holds still.** A roll under it is not a motion at all:
   `Collapse` commits the end state and announces no start, so the ride is never reached and the
   disclosure behaves as it did before it learned to roll. Traced at 640x720: the trace appears in
   one frame, the distance from the end goes 0 to 76 and back to 0, and `scrollTop` never moves.
   `Collapse.test.tsx` now asserts the silence, since the log's behaviour hangs off it.

### What the filed entry got wrong about its own setup

Its measurement said "at 640x720 with the reminder stack up, so the panel was already at its 547px
ceiling". Neither half reproduces. The stack is gated on an empty log and rolls away on the first
message, so a full history never has it up; and the ceiling at that viewport reads 450px now, the
panel's budget having moved it since. What does reproduce is everything the entry was actually
about, on a history long enough to hold the panel at its ceiling without help: the 76px trace, the
disclosure's top edge unmoved for every frame, and the 3px to 79px tail. The condition that matters
was never the stack; it is the panel having nothing left to give.

### What this opens

**The panel's own chrome shrinks the log the same way, and the log does not answer that either.**
The switcher list and the reminder stack roll in the panel's chrome, outside the history, and at the
ceiling their growth comes out of the history's window rather than out of the panel. Measured at
640x720 on the same full history: opening the chat switcher takes the history's window 293px to
73px with `scrollTop` left at 408, so the reader's distance from the end of the reply goes 3px to
223px in one roll. It is the same defect with the other cause, the window shrinking rather than the
content growing, and the same arithmetic would answer it; what it needs is to hear a roll that
happens outside the box, which means the panel and not the log dispatching to the ride, plus its own
measurements across the summon, a new chat and a reminder ack, where the panel is doing plenty of
moving on its own account. It is exactly reversible (closing the switcher reads 3px again) and the
reader can scroll, so it is filed rather than bundled
([body-overlay.md](../refinements/body-overlay.md)).

## Addendum, 2026-08-04: a chat swap says which chat arrived, unless its door already said it

The switcher-role addendum above left the cycle keys exactly as they were and opened one deferral
on its way out: the swap they perform is silent. This closes it. The overlay gains **one polite
live region**, at its root and never inside the panel, and the rule for who writes to it is about
the **gesture** rather than the transition: a swap speaks when the control that fired it named no
chat, and stays quiet when that control's own accessible name is the title arriving.

### What was measured before

Chromium at 900x900, on the demo's own seed, with the reminder stack and the switcher as they boot:

- **The keys.** Focus put on the header's chats button (by opening the switcher with it), then two
  presses of `Ctrl+↓` walk the header title "New chat" to "Summarize my unread email" to
  "Everything about model swaps". The first press closes the switcher out from under the reader,
  `aria-expanded` going true to false, and `document.activeElement` is the chats button throughout.
  Nothing on the page says any of it.
- **The other doors, which the entry did not have.** `Ctrl+N` has the identical shape: the title
  goes back to "New chat", focus does not move, nothing is announced. A reminder card's "open chat"
  loads its origin chat ("Everything about model swaps") and says nothing. Deleting the chat that is
  open resets the panel to a fresh one, also silently. So the doors are seven and not the two the
  entry named.
- **The page's live regions.** One `role="status"`, the connection dot, reading
  "Brain ready: cortex-orchestrator demo".

### What the deferral got right and what it got wrong

Right, and reproduced exactly: the mechanism (`Overlay.tsx` calling `cyclePrev`/`cycleNext` from a
window keydown), the three titles in that order, focus never moving, the switcher closing on the
first press, and the answer itself, a polite live region naming the chat that arrived rather than
the focus move the rejected listbox shape would have brought.

Wrong in four places, each of which changed the shape of the fix:

1. **"The page's only live region" is true of the page as measured and not of the overlay.** Two
   more carry a role and mount conditionally: the capture ring (`role="status"`, up only while the
   assistant has asked for the screen during a turn) and an errored reply's bubble
   (`role="alert"`). Neither is ever about a chat, so the conclusion survives, but a reader
   counting regions from that sentence would come up one short of what the tree can hold.
2. **"`state.title` already holds it" is true only after the swap, and reading it before is a
   bug.** A history load can fail, and its `.catch` deliberately leaves the current chat in place,
   so a notice raised at the keypress would name a chat that never arrived. What is announced is
   the title the reducer arm computes, off the same `headerTitle` call the header takes, so the
   region and the header cannot disagree about which chat is on screen for the same reason the
   header and the switcher row cannot.
3. **The decision cannot live in the reducer arm, because one arm serves two doors.**
   `openSession` is the switcher row AND the cycle keys; `newChat` is the pencil AND `Ctrl+N`. The
   flag therefore travels with the action from the door that raised it, which is the only shape
   that can deliver the entry's own "so a reader is not read back a title it just clicked": a rule
   written into either arm would have to answer for both of that arm's doors at once.
4. **A title said twice is not said twice.** A live region reports a mutation, not a value, so text
   replaced by identical text announces nothing. Two chats can easily share a title (the same
   question asked twice, or two runs of "New chat"), so the notice carries a count and the region's
   child is keyed on it.

### The decision

`overlay/notice.ts` holds a `Notice` (`title` plus `count`) and `speak`, which is the whole of the
new state. `OverlayState` gains `notice: Notice | null`, the `openSession` and `newChat` actions
gain an `announce` flag, and `components/Announcer.tsx` renders the region. Seven doors, and the
rule is read off the gesture rather than off the transition:

| Door | Speaks | Why |
| --- | --- | --- |
| `Ctrl+↑` / `Ctrl+↓` | yes | A keystroke names no chat and moves no focus. |
| `Ctrl+N` | yes | The same, for the fresh chat it mints. |
| A reminder's "open chat" | yes | The control is named for the act, not for the chat. |
| The fresh chat after deleting the open one | yes | Its only door is `Confirm delete <title>`, which names the chat LEAVING. |
| A switcher row | no | The row's accessible name IS the arriving title. |
| The header's pencil | no | Labelled "New chat", which is what arrives. |
| Cold-start adoption | no | No gesture to answer, and it runs only while `touched` is false, which every speaking door sets, so it can never land over something said. |

A silent swap **clears** the notice rather than leaving it: a removal is not announced under the
default `aria-relevant`, so nothing is read, and the region is left holding only what was actually
last said. The delete fallback needs no flag, having the one door.

The region sits at the overlay's root and not in the panel, which is load-bearing. A dismissed
panel is `aria-hidden` and `inert` (`overlay/withdrawn.ts`) and the cycle keys are global, so a
press can put the panel on screen and swap the chat in one commit; a region inside it would be
entering the accessibility tree in the same frame as the words it wants read. What it says is a
sentence, `Switched to <title>`, because a bare title arriving out of nowhere names a thing without
saying what happened to it.

### What it measures

Chromium at 900x900, same seed, after:

- **The region is there before it is needed.** At boot the tree holds two `status` nodes, the new
  one empty and the connection dot named as before, both `live: polite`, `atomic: true`,
  `relevant: additions text`. Its box is 1x1 and it is not inside `.panel`.
- **The keys speak.** The same two presses now put "Switched to Summarize my unread email" and then
  "Switched to Everything about model swaps" in the region, each naming the title the header carries
  in the same frame. `Ctrl+N` reads "Switched to New chat". A reminder's "open chat" reads "Switched to
  Everything about model swaps". Deleting the open chat reads "Switched to New chat".
- **The named doors stay quiet.** A switcher row click and the header's pencil each leave the region
  empty, and a `MutationObserver` over it records only the removal of what stood there.
- **One title, twice, is two announcements.** Two `Ctrl+N` presses in a row record three mutations:
  an addition, then a removal, then an addition of the identical string. Without the keyed child
  the second press mutates nothing at all.

### The mutation proof

Seven mutations, each reddening exactly one test and no other, checked in place and restored:
dropping the `key` on the region's child (the same-title test), pinning `speak`'s count at 1 (the
counting test), making `openSession` ignore its flag (the door test), flipping the switcher row to
announce (Panel's switcher test), flipping the reminder's control to silent (Panel's reminder
test), giving `Ctrl+N` the pencil's rule (Overlay's door test), and dropping the notice from the
delete fallback (the delete test). Moving the `Announcer` under the panel reddens the placement
test on the `inert` subtree, which is the assertion that keeps it out.

### What this does not do

**Focus is still exactly where the gesture left it, and for three doors that is now the body.**
Measured at 900x900: clicking a switcher row keeps focus on the row for its 300ms roll and then
loses it to `<body>` when `Collapse` unmounts the row; a reminder's "open chat" loses it in the same
way, the stack rolling away as the history fills; and confirming a delete loses it with the row.
The live region reads regardless of focus, so nothing here depends on it, but a reader is left with
no place in the panel to continue from. It is a focus question rather than an announcement one, it
predates this work, and it is filed as its own deferral
([refinements/body-overlay.md](../refinements/body-overlay.md)).

**Nobody has heard it.** What is proved here is the accessibility tree and the DOM mutations, which
is the standard every other accessibility pass in this ADR applied (the tab strip, `withdrawn`, the
switcher's role), and it is what this machine can prove. Whether a given screen reader re-speaks an
identical string is its own decision; a listen would ride the standing Windows bring-up
([host/windows-desktop.md](../host/windows-desktop.md)) rather than open a sitting of its own.

**Nothing else announces.** A turn's reply, a tool chip, a reminder arriving and the switcher's own
open and close are all still silent, deliberately: this region exists for the one thing that
replaces the whole panel without moving anything.

## Addendum, 2026-08-04: the log rides a roll in the chrome as well as one inside it

The log-ride addendum above closed the trace's half of one defect and filed the other: a section
rolling in the panel's chrome takes the log's window away exactly as a trace takes its content, and
the ride never heard those rolls. This closes the filed entry
([body-overlay.md](../refinements/body-overlay.md)). It is one line of subscription and one rule
about the cap, and both of the entry's guesses about the shape of it were wrong in ways worth
recording.

### What was measured before

Chromium at 640x720, the body's own window, on a history long enough to hold the panel at its 450px
ceiling (four turns of the demo's canned reply, log content 469px in a 293px window, the reader 3px
off the end of the last reply).

- **Opening the chat switcher takes the window 293px to 73px with `scrollTop` left at 173**, so the
  distance from the log's bottom edge to the end of the reply runs 3px to 223px across the roll,
  which is the whole answer gone under the composer. Closing reads 3px again, so it is exactly
  reversible, which is why it was filed rather than bundled.
- **The start event never reaches the box.** Listeners on the history, on its column and on the
  panel, with the switcher opened: the column and the panel hear it, the history hears nothing. The
  chrome's sections are siblings of the box, so a bubbling event from one goes up past the log.
- **The panel does not move at all in that trace** (top edge 86, height 450 on every frame), which
  is what the ceiling means: there is nothing left for it to absorb the growth with.

### What the entry got right, and the two things it got wrong

Right, and reproduced: the numbers above, the diagnosis (the ride is subscribed to a box their start
event never reaches), and that the ride is already written against a box and a section rather than
against the history, so no second mechanism was needed.

Wrong in two places, one of them the whole cost of the entry:

1. **"The same arithmetic answers it" is false, and the wiring alone changes nothing.** The ride's
   cap keeps the rolling section's own top edge on screen, and it is expressed as the room between
   that edge and the box's. For a section in the chrome that room is NEGATIVE for every frame of the
   roll, its top edge being above the box; the floor that stops the ride chasing a section already
   above the window turns that into no room at all, and the cap freezes the ride at the position it
   started from. Measured with the subscription landed and the cap left as it was: the window ran
   293px to 73px and `scrollTop` read 173 on every frame, byte for byte the trace with nothing
   listening. The rule the fix adds is one line, `box.contains(section)`, and it says what the cap
   was always about: only a section INSIDE the box is something the reader can be carried away from.
   A switcher list stays where the panel put it whatever the log does underneath.
2. **The reminder stack cannot cost a reader anything, so the pair is really one section and a
   family.** The stack is gated on an empty log (`ChatView` opens it only while `messages.length ===
   0`), which is the same gate the previous addendum caught this entry's predecessor on. Measured on
   the boot state: acking one of three reminders grows the history 99px to 158px with the log's
   content at 99px, so `scrollTop` and the tail read 0 on all 21 painted frames. What the entry did
   not name is the family that DOES reach it: every row inside those two lists rolls through the
   same component (`overlay/usePresence.ts`, a row leaving; the switcher's empty line arriving), and
   a row leaving the open switcher moves the log exactly as the list itself does.

### The decision

**The log listens on the column, and the roll's own element is the event's target.** `Panel` holds a
ref for the chat's `.view` and hands it to `ChatView`, which hands it to `useLogScroll`; the
subscription moves from the box to that column. One listener hears both kinds, a roll inside the log
bubbling through the box on its way there, so there is one doorbell and not two. The section is read
off `event.target` rather than searched for by attribute, which is what keeps two rolls in the same
frame apart (a switcher row leaving under an empty line arriving is the reachable pair) and which
the roll contract already licenses: `morph.ts` says the element that announces is the element that
was marked, and both dispatchers do exactly that.

**The cap is only ever about a section inside the box**, per the correction above. Outside it, the
ride holds the tail and nothing bounds it but the box's own range.

The console's column is deliberately a different element, so a roll in there is not the chat log's
business, and the panel itself was not used for the same reason.

### What it measures

Chromium at 640x720 unless stated, per painted frame. The readings are taken in a `ResizeObserver`
callback rather than in a `requestAnimationFrame` one, because the observer step runs after every
rAF callback and therefore reads the frame the ride has already written into; a rAF probe registered
before the ride reads that frame's new geometry against the ride's previous write and reports a lag
that never paints, peaking at 36px on the way open, which is one frame of the roll's growth plus the
3px being held.

- **The entry's case.** Opening the switcher on the full history: the distance from the end of the
  reply reads 3px on all 19 painted frames and `scrollTop` runs 173 to 393; closing it runs 393 back
  to 173 with the same 3px throughout, so the round trip lands on the pixel it started from. No
  frame moves it more than 34px, and the movement takes about 270ms of the roll's own 300ms, with
  nothing after it.
- **A row leaving the open list.** Deleting a chat with the switcher up: the window grows 170px to
  220px, `scrollTop` eases 299 to 249, and the tail holds at 0 for all 19 frames.
- **A summon, with the roll landing inside its arrival window.** Dismissed on a full history, then
  summoned and the switcher opened 100ms later, which is the case where the panel is placing itself
  and the ride-along is driving the bottom edge: the tail holds at 0 for all 19 painted frames while
  the panel's top edge travels 129.76 to 85.54 and the window 390px to 170px, `scrollTop` easing 79
  to 299. The ride and the panel's own motion do not fight, because the ride reads the box each
  frame rather than predicting where it will be.
- **A new chat.** `Ctrl+N` with the switcher open on a full history, which empties the log and rolls
  the list shut in one commit: the log has nothing left to hold, `scrollTop` and the tail read 0 on
  every frame, and the panel eases its top edge 86.5 to 145.5 undisturbed.
- **A reminder ack.** The third of the three cases the entry asked for, and a no-op for the reason
  above: 0 and 0 on every frame.
- **Below the ceiling.** A one-turn chat, where opening the switcher takes the panel from 352px to
  its ceiling first: the tail reads 0 throughout and `scrollTop` runs 0 to 72 and back to 0 as the
  log yields the last of it, with no step anywhere.
- **A reader who has scrolled up is left alone.** With the log parked at `scrollTop` 40 and the
  switcher closing under them: `scrollTop` reads 40 on every frame while the window grows 220px to
  390px. Nothing they are reading moves, which is the same rule the trace's half of this already
  applied.

### The mutation proof

Three mutations, each reddening exactly the tests that carry the claim, checked in place and
restored: taking the `box.contains` rule out again freezes the ride at its opening position (both
new ride tests and the panel's wiring test), taking the ref off the panel's chat column leaves the
log listening to nothing (the panel's wiring test alone), and putting the subscription back on the
box reddens four (the chrome test, the two-rolls test, the unmounted-column test and the panel's
wiring test) while leaving the inside-the-log ride green, which is the shape that says the two kinds
of roll are one mechanism.

### What this does not do

**Nothing new is bounded by the section's own top edge outside the box.** A chrome section tall
enough to leave the log a single line still leaves it that line, since the ride only ever holds the
tail; what stops that from being a problem is the panel's height budget (the addendum above where
the sections spend what the column's furniture leaves), which is what keeps the composer and the
hint strip on screen in the first place.

**The console's own column is not wired, and has nothing to wire.** No section in it rolls today,
and a log is not what it holds.

## Addendum, 2026-08-06: the clamped shrink was answered on the day it was asked

A deferred entry held that decision 4 forced a choice: an unclamped pinned edge buys a switcher
round trip that is exactly reversible, and pays for it by sliding the composer whenever a shrink
gives a clamped panel room. Two designs were written up, the user was asked twice (2026-07-20 and
2026-08-04) and picked neither, and the entry sat for seventeen days as the one item in the backlog
whose whole remaining cost was a decision.

There was no choice. HEAD delivers both halves, and has since 20:57 on 2026-07-20, thirty two
minutes after the entry was written into the console-and-motion commit at 20:25 the same evening.
The "growth caps at the top" addendum above, item 1, is what did it: the second bound came off, and
with it the clamp on the pinned EDGE.

### What changed underneath the entry

`clamped(pinned, viewport, height)` was `max(0, min(pinned, 0.88v - h))`. That `min` is the whole of
the entry's argument: it walks the bottom edge down as the panel grows past its ceiling, and lets it
walk back up as soon as a shrink gives room, which is the composer moving. It is now
`clamped(pinned) = max(0, pinned)` in `overlay/panelGeometry.ts`, a no-op for any chat, whose pinned
edge is `centred(...)` and therefore at least `0.12v`. The ceiling moved onto the height as
`maxHeight(viewport, bottom)`, so a panel at its ceiling stops getting taller and the history
scrolls. `overlay/panelPlacement.ts` still spends the clamp on the way out and still never folds it
into `memory.pinned`, so reversibility is untouched. Nothing was traded; a bound was deleted.

### What was measured, and how it was made to fail first

Driven by hand in headless Chromium against the demo bridge, per painted frame, reading the
composer's own bounding box rather than inferring its position from the panel's edge.

At 640x720 the three reminders on the empty chat put the panel against its ceiling on arrival, and
the panel is asked rather than assumed: `offsetHeight` 450, `max-height` 450, and the `--ceiling`
the panel publishes for itself 450, against `round(0.88 x 720 - 184) = 450`. Top edge 86, bottom
edge 184px, composer top 445. At 900x900 the same three readings are 518 at a 274px edge.

1. **Acking one reminder**, which gives back 58px of real content (the stack reads 188 then 130 and
   the history's box grows 99 to 158 taking the room up): the panel holds 450 tall at a 184px edge
   for all 75 frames and the composer reads 445 on every one of them. Travel 0px.
2. **A switcher round trip while clamped**: the list opens 135px inside the panel and rolls the
   stack to 100, then both come back at 0 and 188. The panel reads 450 at 184px before, during and
   after, and the composer 445 throughout. Reversible and immobile at once, which the entry says is
   impossible.
3. **Acking all three**, which takes the panel clean off its ceiling: the TOP edge moves 86 to 184
   and the height 450 to 352, while the bottom edge holds 536 and the composer holds 445 on every
   frame. The shrink is taken entirely at the top, which is decision 4's rule 3 running in reverse.
4. **The same three at 900x900**, where the panel also arrives clamped (518 tall at a 274px edge):
   the ack drops the top edge 108 to 138.5 with the composer at 535 on all 76 frames, and the round
   trip returns the panel to the identical 274px edge with the composer at 535 throughout.

**The arm was reddened before it was trusted.** The deleted clamp was put back at the one line that
spends it, `edge = max(0, min(wanted, 0.88v - height))`, which is the old `clamped` verbatim. The
panel then arrives 546 tall at an 88px edge with the composer at 541, and acking one reminder
settles it at 483: a 58px move, through a 96px excursion (541 down to 445 across the roll, back up
to 483), with the edge walking 88 to 184 to 146. That is the entry's defect, reproduced on demand.
The change was reverted and every green reading above was re-taken afterwards.

### The rarity number was wrong, and it made waiting look cheap

"A correctly pinned panel has to grow 615px at a 900px viewport before the ceiling binds at all"
reads 615 as a growth delta. It is the ceiling's VALUE for a 546px panel centred at 900px:
`maxHeight` allows `0.88v - b`, a centred panel of height h sits at `b = (v - h)/2`, so its ceiling
is `0.88v - (v - h)/2` and its headroom is that less h, which at 900px is `342 - h/2`. For the 546px
panel that is 69px, not 615. Headroom is at most 342px for any panel at all, and exactly 0 at
`openHeight(900) = 684`, which is where the two curves meet by construction. Measured live at 900px,
the demo's own arriving chat has 0px of headroom and stands on its ceiling before the user has
touched anything. The ceiling is common, not rare. What is gone is the consequence.

### What this says about the backlog rather than about the panel

The entry was restated twice from its own text and never re-derived from the tree, and two sittings
in `docs/refinements/index.md` measured its answer and filed it as a null result: on 2026-08-03 the
panel-watch pass recorded "the composer holds its bottom edge at 493 through an ack and a switcher
round trip either way", and the chat-floor pass the same day recorded the composer holding still
"through an ack, a switcher round trip and the pencil at both viewports". 493 is this panel's
composer bottom at 640x720. Both were asking whether their own change had moved the composer, which
is narrower than asking whether anything still did. The index's opening warning, that an entry's own
cost estimate is a hypothesis, now carries the harder form beside it: an entry's account of the code
is a hypothesis too, and a much more expensive one, because it reads as a description of the tree.

### What this does not do

**Decision 4 is not reversed.** The pinned edge is still remembered unclamped and the clamp is still
spent on the way out, which is still what makes the round trip reversible. Only the sentence pricing
that reversibility is retired, the price having been deleted.

**The alternative design is not adopted, and should not be.** Re-pinning to the clamped edge and
saving a pre-roll edge per section buys nothing HEAD does not already have, and costs the panel
parked on whatever low edge its tallest moment left it with. It is recorded as history, not as a
standing option.

## Addendum, 2026-08-06: the caret follows the conversation

The live-region addendum above put a chat swap into speech and left focus exactly where the gesture
had made it, filing the rest as its own deferral: three of the doors into a swap sit inside sections
the swap takes away, so the control that fired it stops existing and the browser falls back to
`<body>`, outside the panel and one Tab from the top of the page. This closes that. **Focus goes to
the composer**, which is the user's answer, taken plainly over the two alternatives on 2026-08-06.

### What was measured before

Chromium at 900x900 against the demo bridge, `document.activeElement` read before each gesture and
at 0, 60, 150, 290, 320 and 700ms after it.

- **A switcher row** keeps focus for its whole roll, reading the row at every sample through 320ms
  and `BODY` by 700, which is `Collapse` unmounting the row when the roll ends. This is the door the
  entry described, and the only one of its three that behaves the way it said.
- **A reminder card's "open chat"** reads `BODY` at 0ms. The stack does not roll away as the entry
  had it: that `Collapse` is keyed on the session id, so a swap remounts it outright and the control
  is gone in the commit itself.
- **A delete confirm on the open chat** also reads `BODY` at 0ms, by a third mechanism again. The
  row leaving is `withdrawn` the moment `sessions` drops it, and `inert` blurs what it contains, so
  the control is blurred before any roll has started.
- **The doors are more than three.** `Ctrl+N` pressed with focus on a switcher row holds the row to
  290ms and reads `BODY` at 320, so the defect belongs to where the gesture was made rather than to
  which control made it. The cycle keys are the same shape into the same arm and were not measured
  separately from a row, `Ctrl+N` being the one traced.
- **The doors that keep focus** are the ones whose control survives: `Ctrl+↓` from the header's chats
  button leaves focus there through the swap, the pencil keeps it, and cold-start adoption has the
  composer already, the browser build self-summoning into it.

### The decision

Three candidates were put to the user: the composer, the header's chats button (which keeps a reader
who is browsing chats where they were browsing), and a split where a delete keeps focus in the
switcher that deliberately stays open behind it. The answer was the composer, for all of them,
because it is where a summon already lands and it puts the reader in the conversation that arrived.

`OverlayState` gains `arrival: number`, a count raised by every arm that replaces the conversation,
and the composer's existing focus effect reads it: the `active: boolean` prop became
`arrival: number | null`, null while the panel is shut or the console is over the chat, and the
field takes focus on every change. One prop rather than two: it is one idea, which conversation the
field is sitting in, and `ChatView` stands at 299 lines against a 300-line cap, so a second would
have left it exactly on that cap with nothing spare for whoever reads it next.

**Unlike the notice, no flag travels with the action.** That rule is about the gesture, so one arm
serving two doors had to be told which one rang; this rule is about the transition, every door on an
arm wants the same landing, and each arm therefore answers for all of its own doors. Cold-start
adoption is excluded by being its own arm, which is also the only correct answer: the panel it would
be moving focus inside is shut, and shut it is `inert`.

**A count and not the session id.** Re-selecting the chat already open is a real gesture, the row is
a plain button on every row, and it still takes that row away with the closing list; the id would
not move and the caret would be lost. A count is also what makes two arrivals under one title two
events, which is the notice's lesson applied to the same problem one field over.

**At the arrival and not at the end of the roll.** The swap is one commit, so focus leaves the doomed
control before its section starts rolling, rather than riding 300ms on an element that is on its way
out; two of the three doors have already been blurred by then anyway, so "the end of the roll" would
mean 300ms parked on `<body>` for them.

| Door | Focus before | Focus after |
| --- | --- | --- |
| A switcher row | the row, then `<body>` | the composer, from 0ms |
| A reminder's "open chat" | `<body>` at once | the composer, from 0ms |
| A delete confirm on the open chat | `<body>` at once | the composer, from 0ms |
| `Ctrl+N` from inside the switcher | the row, then `<body>` | the composer, from 0ms |
| `Ctrl+↑` / `Ctrl+↓` from the chats button | the chats button | the composer, from 0ms |
| The header's pencil | the pencil | the composer, from 0ms |
| Cold-start adoption | wherever it was, the browser build's self-summon having put it in the composer | untouched, this being the one swap that is not counted |

### What it measures

Chromium at 900x900, same seed, after: every door in the table reads `TEXTAREA [Message]` at 0ms and
at every sample through 700ms, with the arriving title in the header and the live region saying what
it said before.

**The panel does not notice.** The switcher's roll under a row press is frame for frame what it was:
43 painted frames, the panel's top edge 108 to 273.19 and its height 518 to 352.81 in both traces,
eleven of fifteen sampled frames identical to the hundredth of a pixel and the other four apart by
at most 0.06, the largest single top step 25.42 before and 25.56 after, and the log's `scrollTop`
identical throughout. That is `focus({ preventScroll: true })` doing the job it was already in this
component for.

### The mutation proof

Two mutations, each reddening a different pair of tests, checked in place and restored. Pinning the
three arms at `arrival: state.arrival` (the swap stops counting) reddens the reducer's arrival test
and the App-level door test, and leaves the composer's own test green, which is the split the
contract wants. Giving the effect the old rising edge, `[arrival !== null]`, reddens the composer's
test and the App-level one, and leaves the reducer green.

### What this does not do

**The same rows still drop focus when nothing swaps.** Pressing Rename, committing a rename,
pressing Delete, confirming the delete of a chat that is not the open one, and acking a reminder
each take the pressed control away without replacing the conversation, so `arrival` never hears
about them and each reads `<body>` afterwards (the ack after its roll, the rest at once). They want
answers of their own shape rather than the composer, and are filed as one deferral
([refinements/body-overlay.md](../refinements/body-overlay.md)).

**A draft still belongs to no chat.** The field is never unmounted, so its text survives a swap:
"half a question" typed into one chat is still there, caret at 15, after `Ctrl+↓` loads another. That
was always so and cost nothing while focus was landing on `<body>`; now the caret is put in that
field by the swap, so it is the first thing a reader meets in the conversation that arrived. Filed
beside the entry above, with the two shapes it could take.

**The switcher is still open behind a delete.** The split answer that would have kept focus in it
was declined with the rest, so a reader who deletes the open chat lands in the composer of the fresh
one with the list still up. Getting back to it is a walk rather than a step: three presses of
Shift+Tab from the field reach the empty chat's own two example prompts and then its mark button,
with the reminder stack and the rows above those, which is the tab order the panel has always had
and is the cost the user accepted in taking the one rule.

## Addendum, 2026-08-06: the panel measures itself in the pixels it actually has

Two deferrals on the panel's own motion were one piece of work, and this closes both. The panel
measured itself with `offsetHeight`, a whole number, so every move retargeted mid-stream opened its
keyframes below the height the eye had; and its watch on its own box refused a reading while its own
ease was running, because a running height animation overrides the box, so a resize that landed
inside a move waited that move out. Fixing the second alone would have put the first back sixty
times a second, which is why the pair was filed as one.

**The panel now reads its used height off the computed style, and its watch asks what the panel
WOULD be rather than what the box says.**

### What was measured before

Chromium at 60Hz against the demo bridge, `Element.prototype.animate` instrumented to record every
opening keyframe, `offsetHeight` instrumented at the getter to record every read beside the
fractional height at that instant, and frames sampled from a `ResizeObserver` registered after the
panel's own, since `requestAnimationFrame` runs before the observer step and reads the layout the
placement has not had its say on yet.

- **The rounding is live.** At 900x1000 with the reminder stack acked, over one streamed reply: 310
  of 330 readings of the panel's `offsetHeight` threw a sub-pixel away, worst 0.484px. All three of
  the panel's moves opened on a whole number, and the painted top edge stepped back 0.281px at the
  frame a retarget opened at 459 against a panel standing at 459.281.
- **At the shipping window there is nothing to see**, as the entry said: at 640x720 with the stack
  up the panel makes no moves of its own at all, being pinned at its ceiling.
- **The wait is live too, and it is longer than latency alone.** At 900x1000 on an empty chat, 150px
  appended straight into the log and 40px more 100ms into the resulting 255ms ease: the second
  growth was invisible from t=160 to t=333, the frame that handed the element back read 514, the
  frame after read 516.31, and the residue eased to 556 over 120ms, settled at t=465.
- **A second rounding of the same shape was found beside it.** The bottom edge was written rounded
  while the keyframe went to the fraction: measured at 901x1001, a whole ease painted a 324.5px edge
  and the frame that took the animation away handed back the 325px inline value. Half a pixel, on a
  bordered and shadowed edge, at the end of every move whose pinned edge is fractional.

### The decision

**The height is the used value off the computed style.** It keeps the fraction and it passes the
check `offsetHeight` was chosen for: measured on a 356.281px box with a 1px border, `offsetHeight`
reads 356 scaled or not, the rect reads 356.266 plain and 327.764 under `scale(0.92)`, and the used
height reads 356.266 under both. Live, at 900x900: 120ms into a summon the panel's rect reads 511.626
while its used height reads 518, and the session is pinned to the same 274px edge on every summon.

**The watch probes what the panel would be, by handing the box back to layout for one read.** An
`!important` inline declaration outranks the animation origin in the cascade, so `height: auto`
important, with the element's own cap re-asserted beside it, answers the question the animation is
hiding. At 900x1400, 60px appended and 40px more two frames into the ease: the box read 567.906 for
both frames while the probe read 616.75 and then 667.75. Nothing paints in between and no observer
notification comes of it, the box being back before the frame ends.

**The alternative was measured rather than argued.** Taking the guard off and letting every
notification place, which is the shape the watch's own doc rejected in prose, runs 24 animations for
one 150px growth instead of 2: the ease restarts its own curve every frame, so the panel crawled 33px
in the first 233ms and then dumped 40.83px in a single frame at the end, against a largest single
frame of 26.25px with the probe.

**The watch measures against the height the panel was placed FOR** (`Memory.placedFor`), not against
the height it last looked at. A render that grows the panel is answered by the placement inside that
render, and that placement resizes the element the watch is on; measured against a remembered
reading, the notification one frame later reads as growth and places a second time. That doubled
every move over one reply, 6 animations for 3 growths, each pair 3ms and 0.015px apart.

### What it measures now

Same instruments, same windows. At 900x1000 over one streamed reply: the panel's `offsetHeight` is
read zero times, none of the four openings is a whole number, and the worst backward step is 0.015px,
which is Chromium's own 1/64px grid and the floor of what can be represented. At 900x1000 with the
40px landing inside the ease: it is answered one frame later by a retarget opening at 449.016, and
the panel is settled at t=339 rather than t=465, the 188ms of nothing gone. At 901x1001 the inline
edge and the keyframe are the same 324.5px and nothing steps. Across a new chat, the stack acked row
by row, the switcher open and shut, a draft that wraps and a streamed reply, at 900x1000 and 640x720
alike, the observer's "loop completed with undelivered notifications" error fires zero times.

### The falsification proof

Four reverts, each checked in place and restored, each reddening the tests that name it. Rounding
the used height again reddens the sub-pixel keyframe test alone. Writing the bottom edge rounded
again reddens that test and the whole-pixel-ceiling test. Putting the guard back so the watch waits
the move out reddens the join test and the sub-pixel one. Measuring against the height last looked at
rather than the height placed for reddens both watch-settling tests.

### What this does not do

**A section's own roll still measures its target with `offsetHeight`.** `Collapse` reads the whole
number, publishes it as the height it is rolling to, and an opening roll does not fill, so the
section hands itself back to its own layout at the end. Measured at 900x1000 over the demo: the
reminder stack's aside is 193.75px against a 194px target and a Thoughts trace is 57.25px against 57,
so a roll ends 0.25px away from where it was going and steps there. The panel's ride-along adds that
rounded target to fractional heights, which puts its prediction the same 0.25px out, far under the
2px below which nothing is animated at all. It is deferred because the reading is one line and the
harness around it is not: the roll stand-in every per-row exit is asserted through is shared by three
test files. Filed with the numbers in
[refinements/body-overlay.md](../refinements/body-overlay.md), and **landed hours later the same
day**: the addendum below has the trace and the harness change.

**The other boxes that measure themselves are unchanged too.** The console's tab slack, the panel
edge's canvas and the composer's pill each read `offsetHeight` for their own purposes; only the tab
slack reaches the panel's arithmetic, and it does so through the same 2px floor.

## Addendum, 2026-08-06: a draft belongs to the conversation it was typed into

The caret addendum above filed one thing it had made visible: the composer's field is never
unmounted, so its text is the overlay's and not any chat's, and now that a swap puts the caret in
that field, the first thing a reader meets in the arriving conversation is a sentence they started
somewhere else. **The user's answer is a draft per chat**, taken over clearing on swap on
2026-08-06, because a half-typed question is work and swapping away is not a decision to discard it.

### What was measured before

Chromium at 900x900 against the demo bridge, "half a question" typed into the field and then every
door into a swap fired. The entry's claim held exactly and at every door, not only the one it named:
the value and the caret came through `Ctrl+↓`, a switcher row, `Ctrl+N`, the header's pencil, a
delete confirm on the open chat, and a reminder card's open control, all reading
`{"value":"half a question","caret":15}` afterwards, with the arriving chat's title in the header.

One detail in the entry is worth correcting rather than repeating: **"caret at 15" is the end of the
draft**, `"half a question"` being fifteen characters, so the entry was recording where the caret
already was and not a caret preserved mid-sentence. Both are true at HEAD, as it happens; a caret
parked at offset 2 also survived a swap unchanged.

Cold-start adoption could not be reproduced in the browser at all, and for a reason worth writing
down: the browser build self-summons on load, `open` sets `touched`, and adoption is guarded on
`touched`, so the adopt attempt is always refused before a field exists to type into. It is covered
in the reducer instead.

### The decision

**`OverlayState` gains `drafts`, unsent composer text keyed by session id, and the composer becomes
a controlled field over the entry for the chat on screen** (`overlay/drafts.ts`,
`components/Composer.tsx`). A swap hands the arriving conversation its own text in the very commit
that swaps the transcript, so no arm parks anything, no effect runs in between, and there is no frame
that could paint the wrong conversation's sentence.

**In the body's own reducer rather than behind a store port, argued rather than assumed.** The repo's
hard rule is that state survives a model swap, meaning no conversation state, task state or working
memory inside a model-server process or a model's KV cache. This is in the body, which a model swap
cannot reach, so that rule is satisfied by construction and Redis would not make it more so. The
separate question a store would answer is survival of a body RESTART, and a draft does not earn it:
it is text nobody has sent, nothing but the field it was typed in can read it, and no surface
anywhere promises it is kept, which is what makes an undurable draft honest rather than a lie. It is
the same category as the switcher being open, the console's tab, the log's scroll position and a
switcher row's own half-typed rename, all of which die with the process today. What durability would
cost is a proto message, a brain-side arm, an adapter, a contract test and an eviction policy, spent
per keystroke over gRPC, for a sentence a restart loses.

**In the reducer rather than in the component, which is what keeps that cheap to revisit.** Two
things the composer cannot see need the map: the delete cascade has to take a deleted chat's draft
with it, and a swap has to hand over the arriving text synchronously. If a draft ever must survive a
restart it hydrates and persists exactly where `messages` does, with no component to reach into.

**An empty field is stored as nothing.** `parkDraft` with `""` drops the entry, which is the whole
of the eviction policy: a map keyed by chat that stored `""` would grow an entry per conversation
ever visited and never lose one, where this holds only chats with a sentence waiting in them, and
each leaves again when its text is sent, when its chat is deleted, or when the field is emptied by
hand. A draft for a chat outside the loaded switcher window needs nothing special, being keyed by id
rather than by list membership.

**Sending a text empties the field that held it**, asked of the text and not of the door
(`turnState.submit`). The composer sends its own draft, so the draft goes; an example prompt on the
empty state sends the chip's words, so a half-typed question sitting in the field beside it is not
thrown away by a button pressed for something else. A send the reducer refuses (a blank field, a turn
already streaming) spends nothing, where the field used to blank itself regardless.

**Typing now counts as touching the overlay.** `touched` has always documented itself as covering
typing and could not, nothing having dispatched on a keystroke; the draft action sets it, which
closes the one path where a cold-start restore could take away the conversation a half-typed line was
written in.

| Door | The draft it leaves | The field it arrives on |
| --- | --- | --- |
| A switcher row | parked under the chat being left | that chat's own text, or empty |
| `Ctrl+↑` / `Ctrl+↓` | parked under the chat being left | that chat's own text, or empty |
| `Ctrl+N` and the header's pencil | parked under the chat being left | empty, a fresh id holding nothing |
| A reminder card's open control | parked under the chat being left | that chat's own text, or empty |
| A delete confirm on the open chat | dropped with the conversation it described | empty |
| A delete of any other chat | that chat's draft dropped; the open chat's untouched | unchanged, no swap |
| Cold-start adoption | never runs once anything is typed (`touched`) | unchanged |
| A trip to the console and back | nothing, no swap and no unmount | the same text, as before |

### The caret

**A restored draft is offered at its end**, not at the offset it was left at. Coming back to a
half-typed thought is coming back to finish it, so the caret is where the next character goes. It is
also the field's own answer rather than machinery: assigning a textarea's value puts the selection
after the last character, a swap is exactly what assigns it (the text differs), and a keystroke is
exactly what does not, which is the same mechanism saying both halves. Measured in Chromium at
900x900 and 640x720: a draft left with the caret at offset 2, swapped away and reopened from a
switcher row, comes back at 15; and typing an `X` at offset 4 of a standing draft leaves the caret at
5, in place, rather than throwing the writer to the end.

### What it measures

**Every door, at 900x900**, after: a sentence typed in one chat is gone from the field the moment
another conversation arrives and is waiting under the chat it was written in when any door goes back;
`Ctrl+N` and the pencil arrive empty and leave both sentences behind them; a delete of the open chat
arrives empty; a reminder's open control behaves as the row does; a trip to the console and back is
unchanged, which it always was; a send empties the field and an example chip does not.

**The panel does not jump, which is the hazard a taller composer carries.** The swap alone was
traced per animation frame with the switcher already open and settled, at both viewports, against a
swap into a chat holding nothing:

- **900x900.** Into a chat with no draft, the panel eases its top edge 108 to 273.19 over 18 frames,
  largest step 25.56px. Into the chat holding a draft at the field's ceiling (a 148px pill against
  48), 108 to 174 over 12 frames, largest step 14.25px. **Zero direction reversals in either**, which
  is the reading that matters: a jump-and-come-back is a reversal. The draft-laden swap is the
  smaller and smoother of the two, the panel easing once to a height that already has the draft in
  it.
- **640x720.** Into a chat with no draft, 86 to 183.19 over 14 frames, largest step 22.53px. Into the
  chat with the draft, **one frame and no movement at all**: the panel is at its ceiling and stays
  there.
- **The pill is never painted at its unmeasured height.** It reads 148 in the first traced frame of
  the swap and every frame after, never 48 and then 148. A parent's layout effect runs after its
  children's, so the composer has measured and sized itself before `usePanelMotion` places the panel
  in the same commit, and the panel's watch then finds the height it just placed for and says nothing
  ([`overlay/panelWatch.ts`](../../body/app/src/overlay/panelWatch.ts)).

### The falsification proof

Seven mutations, each checked in place and restored, each reddening tests that name it and leaving
the rest green. Reading the field off the last text typed anywhere rather than off the chat on screen
reddens the App-level door test alone, which is the wiring that test exists for. Dropping the delete
cascade's `dropDraft` reddens the delete test. Never spending a sent draft reddens the reducer's send
test and the App-level one; always spending it reddens the send test on the example-chip half.
Storing `""` as an entry reddens the eviction test. Taking `touched` off the draft arm reddens the
adoption test. Carrying the outgoing draft into a freshly minted chat reddens the new-chat test and
the App-level one.

### What this does not do

**A draft does not survive a restart of the body**, by the argument above rather than by omission. If
that is ever wanted it is a store-backed hydrate and persist at the reducer, where `messages` already
is, plus an eviction policy the in-memory map does not need.

**The word stays overloaded.** An approval's `argumentsJson` is "the draft" in the confirmer's
vocabulary (`components/draftValue.ts`) and a switcher row's in-progress label is a `draft` local.
Both are unrelated to the composer's, which is what every doc in the overlay already calls a draft, so
inventing a third word would have cost more than the collision does.

**`ChatView` was split to make room for this**, the file having stood at 299 lines against a 300-line
cap. The hint strip under the composer is its own component now (`components/HintStrip.tsx`), which
is a split by responsibility rather than by line count: it is the row of keyboard affordances plus
the two doors into the console, and it takes no state. `newChat` moved from the reducer's switch into
`overlay/sessionState.ts` beside `openSession`, `adoptSession` and `deleteSession` for the same
reason and with the same test: all four are conversation-swap arms answering the same three questions
(what is announced, that the caret follows, and what becomes of the draft), and reading one is now
reading the others.

## Addendum, 2026-08-06: the caret stays in the list

The addendum above sends the caret to the composer whenever a conversation arrives, and said plainly
what it did not do: the same rows drop focus for the gestures that swap nothing. This closes that.
**A list that reshapes under the hand keeps the caret**, by a rule with three clauses and one clock
(`overlay/rowCaret.ts`).

### What was measured before

Chromium at 900x900 against the demo bridge, `document.activeElement` read before each gesture and at
0, 60, 150, 290, 320 and 700ms after it. **The entry filed five gestures and there are thirteen**,
which is the sibling entry's lesson repeating: doors are counted by reading the component, not by
remembering the last bug report.

| Gesture | Before | Mechanism | After |
| --- | --- | --- | --- |
| Rename opens | the pencil | the pencil is unmounted by the shape change (`pencilInDom` 3 → 2, no slot `inert`) | `<body>` at 0ms |
| Rename commits, the save button | the editor | the editor is unmounted with the form | `<body>` at 0ms |
| Rename commits, Enter in the field | the editor | the same | `<body>` at 0ms |
| Rename cancels, Escape | the editor | the same, **and Escape reaches the window listener and dismisses the panel** | `<body>` at 0ms, panel gone |
| Delete opens | the trash | the trash is unmounted by the shape change | `<body>` at 0ms |
| Delete cancels | the confirm's cancel | the confirm is unmounted by the shape change | `<body>` at 0ms |
| Delete confirms, another chat | the confirm's yes | unmounted (`confirmInDom` 0 at 0ms) inside a slot that is also `inert` in the same commit | `<body>` at 0ms |
| Delete confirms, the last row | the confirm's yes | the same | `<body>` at 0ms |
| Delete confirms, the only row | the confirm's yes | the same | `<body>` at 0ms |
| Delete confirms, the OPEN chat | the confirm's yes | the same, but a fresh chat arrives | the composer, already answered |
| A reminder's ack | the ack | held for the whole roll (the ack at 0, 150 and 320ms), then `Collapse` unmounts the row | `<body>` at 350ms |
| A reminder's ack, the last one | the ack | the same, and the section leaves with the row | `<body>` at 350ms |
| Pin / unpin | the toggle | nothing: the button survives the regroup it causes | the toggle, at every sample to 700ms |

Two of those rows are findings rather than measurements of the filed defect. **Escape cancelling a
rename also ended the session**: the editor's handler closes the editor and the press carries on to
the window listener that dismisses the panel, so the panel read `panel edge-live` (no `open`) 400ms
later. And **`?` typed into that editor opened the console**: the global handler's guard named the
composer's textarea alone, so typing "why?" left `why` in the field and the settings pane on screen.
Both were reachable before this and neither was reachable *by accident* before this, the caret never
having been put in that editor by anything but a click.

### The rule

**A row that changes SHAPE hands the caret to the control its new shape puts in the place of the one
that left.** A rename opens on its editor, with the title it is standing in for selected; a rename
closes, either way, on the pencil that opened it, whose label now reads the name just given. A delete
opens on the confirm's **cancel** and never on its trash, and closes on the trash that asked.

**A row that LEAVES hands it to the same control in the row that inherits its place**, the row below
where there is one and the row above for the last row. Same control, not the row's first: the reader
was deleting chats, and landing on the next row's trash makes deleting several one gesture repeated
rather than a walk back into the list between each. This is the composite-row reading of the standard
list-deletion pattern, and it is the reading this list needs: the switcher's rows are four buttons
each and were deliberately taken out of `listbox` for that reason (the accessibility addendum above),
so "focus the next option" has no referent here and "the same column, one row down" does.

**A list with no row left hands it to its anchor**, a control outside the list that the view holds
(`ChatView`). The two lists get different anchors because what the reader is left with differs. Delete
the last other chat and the switcher is still open in front of you saying it holds nothing, so the
caret goes to the header's chats button, which opened the list and is what closes it again. Ack the
last reminder and the stack goes with it, delivery being over, so the caret goes to the composer's
field. That second one lands where the arrival rule lands and is not the arrival rule: nothing
arrived, and the argument is that the only thing left on the panel is the conversation underneath.

**And the pin toggle is answered by saying nothing about it.** It is the one row gesture whose
control survives, so a rule for it would be a rule that moves a caret already in the right place.

#### Why the cancel and not the confirm

Measured, rather than argued from the practice. With focus on the confirm's yes, one further Enter
deleted the chat (three rows to two); with focus on its cancel, the same press put the row back
(two rows to three). The reader arrives at that confirm having just pressed a key to open it, and the
confirm exists precisely so that one stray press cannot delete a chat, so landing on the destructive
half would make the second press of a key somebody is already holding the whole of the decision. The
pointer has no such hazard: the confirm's yes sits at x=633 against the trash's 528, and what lands
under the trash's own centre after the shape change is the confirm's text.

#### And Escape closes the innermost thing

Both of the row's overlays now keep a cancelling Escape to themselves (`event.stopPropagation()`),
which is the rule the console already followed one layer up. The console can do it from the overlay's
own handler because the overlay holds its state; the editor's and the confirm's live in the row, so
the row is what says the press was answered. The `?` guard is asked of `HTMLInputElement` as well as
`HTMLTextAreaElement`, so a third field anywhere in the overlay is covered on the day it is added.
Modified chords are deliberately untouched: `Ctrl+N`, `Ctrl+K` and the cycle keys still reach the
overlay from inside an editor, a modified chord not being a character somebody is typing.

### At the commit, not at the end of the roll

The same call the arrival rule made, and here it has a second argument of its own: **the control being
aimed at has been on screen all along.** The heir of a deleted row never left, and a row changing shape
mounts its new controls in the very commit the old ones go, so there is nothing to wait for. Waiting
would mean the caret parked somewhere for 300ms, and the measurements above say it would be two
different somewheres: a switcher row is unmounted and `inert` at once, so the caret would spend the
roll on `<body>`, while an acked reminder's button survives its whole roll, so the caret would ride an
element animating to nothing. One clock answers both and it is the earliest one.

**The panel does not notice.** Traced at 60Hz at 900x900. A confirmed delete: 60 frames, the panel's
box unchanged at top 108 and height 518 throughout (the switcher's row exit never moved the panel,
which is why the snap it replaced was the whole of what the eye saw), `panel.scrollTop` and the log's
`scrollTop` both 0 at every frame. An ack with two reminders left: top 108 to 138.5 and height 518 to
487.5 over 14 distinct boxes, largest single top step 6.14, both scroll positions 0 throughout. The
last ack, where the section leaves and the caret crosses to the composer: top 196.75 to 274, height
429.25 to 352 over 20 distinct boxes, largest step 11.57, both scroll positions 0. And the arrival
rule's own trace is unmoved: a switcher row press still runs the panel 108 to 274 with a largest top
step of 25.58 against the 25.56 recorded when that rule landed. `focus({ preventScroll: true })`
throughout, which is why every `scrollTop` above is a zero.

### How it is built

`overlay/rowCaret.ts` is the whole of it: `heir(keys, gone)` (pure, the row that inherits a place),
`caretKey(role, id)` (the name of one control, passing a null id through so a call site stays one
expression), and `useRowCaret(list, anchor)`, which returns the function a gesture calls to name where
the caret should be once its change is on screen. The move happens in a layout effect, before paint.

**Named rather than held as a ref**, because the control being aimed at usually does not exist when
the gesture fires. The rows write `data-caret` and the list looks one up inside its own container,
which is `useTravel`'s arrangement (one container ref plus a selector) applied to focus instead of to
position. The lookup matches on the dataset rather than folding the id into the selector, so an id
with a quote in it is a key that misses rather than a selector that throws.

**Asking is what schedules the move**, through a counter the hook bumps, rather than the caller's own
state change happening to. Every gesture that calls it does change what its list renders, so the render
comes anyway and this costs no commit (one handler is one batch); what it buys is a hook that is true
on its own terms rather than one that works because of its callers. It was written the other way first
and the hook's own tests were the thing that caught it: a stage that only set a ref never re-rendered,
so nothing focused.

**A field the caret lands in is selected**, which is only ever the rename editor: a list sends the
caret into a field to have that field replaced. Bare focus leaves the caret at the end instead
(measured: offset 28 of "Everything about model swaps"), so the reader would have to select the name
by hand before saying a new one, and selection also makes one Backspace the empty submit that clears a
custom title back to the derived one. Deliberately not applied to the anchor, which is a landing place
the list fell back to rather than a control it chose, and whose one instance is a sentence somebody is
writing.

**`SessionList` was split to make room**, the row's three shapes moving to `components/SessionRow.tsx`.
A split by responsibility: the list is the rows plus their exits, their anchor and their caret, and the
row is what one of them looks like. The state stays in the list, so at most one row renames and at most
one asks about a delete, as before.

**`Reminders` withdraws a leaving row**, which is the switcher's existing rule arriving one component
over and is what the caret rule needs: with the caret moved on at the commit, an acked row's two
controls stayed live and tabbable for the whole roll, so Shift+Tab walked back into a reminder that had
been answered and was rolling away.

**The composer's field ref moved up to `ChatView`.** The view that already decides where the caret goes
is the view that holds the handle to its home, and the reminder stack needs it as an anchor. Nothing in
the composer changed but where the ref comes from.

### The mutation proof

Thirteen mutations, each applied in place, run, and restored. Every one reddened at least one test and
none reddened everything: dropping the editor's caret, aiming the confirm at its destructive half,
narrowing `heir` to the row below, deleting the open-chat guard, dropping the field's `select()`,
dropping the anchor fallback, dropping either Escape's `stopPropagation`, widening the `?` guard back,
dropping the reminder row's withdrawal, dropping the ack's caret, and blanking the caret for a closing
editor, a cancelled confirm and a confirmed delete. The one that spread furthest was the confirm's
target, which reddened three tests across two files including the App-level door; the one that spread
least was the open-chat guard, which reddened exactly the test that says the swap rule owns that door.

### What this does not do

**A modified chord still reaches the overlay from inside an editor.** `Ctrl+N` pressed while renaming
mints a new chat and takes the switcher with it, discarding the edit in progress. That is arguably
right, a chord being a deliberate act rather than a character, and it is not measured either way here.
Recorded in [refinements/body-overlay.md](../refinements/body-overlay.md).

**Nothing announces where the caret went.** Every landing above puts focus on a control whose
accessible name says what it is ("Delete Reminders and recurrence", "Cancel delete", the pencil naming
the new title), which is the reason no live region was added, but the *list's* own change (a row is
gone, one row remains) is still silent. The swap rule's live region says which chat arrived; there is
no equivalent for a list that shrank. Recorded beside the entry above.

## Addendum, 2026-08-06: a section rolls to the height it actually stands on

The addendum above left one reading behind, on the element one layer down, and this closes it.
`Collapse` measured the height it rolls to with `offsetHeight`, a whole number, while the panel now
reads its own box with the used height off the computed style. Two roundings of one number, on the
two sides of a contract whose whole purpose is that both sides agree.

### What was measured before

Headless Chromium at 900x1000 over the demo, `Element.prototype.animate` hooked before the app
loaded so the summon's own rolls are in the trace, and every painted frame sampled for each
section's used height beside the panel's.

- **Both numbers the entry published reproduced exactly at HEAD.** The reminder stack's aside stands
  at 193.75px with an `offsetHeight` of 194, and a section at 57.25 against 57 is there beside it.
  That second one is a reminder ROW rather than a Thoughts trace: a trace at this viewport measures
  76 flat, so the entry had the right number on the wrong element.
- **The step is real in both directions.** The summon's roll of the aside opened `0px` to `194px`
  and the finish handed the section back to its own layout at 193.75. The closing roll then opened
  at 194 while the eye had 193.75, which is a 0.25px step up in a single frame, and the panel's
  `auto` height took it along (545.75 to 546 at the same frame).
- **The ride-along inherited it exactly as the entry said.** Its prediction is the panel's natural
  height less the section's plus the roll's target, so with a rounded target it read 546 for a roll
  that left the panel at 545.75.

### The decision

**The roll measures with `heightOf`, the same used height the panel reads its own box with.** The
check that chose `offsetHeight` for this element still has to pass, and it does: a section lives
inside a panel that is scaled through the whole summon, and the used height ignores that transform
where the rect does not (356.266 under `scale(0.92)`, where the rect reads 327.764). What it adds is
the sub-pixel, which is the entire defect. The mid-roll read of where the section had got to moves
with it, so a reopen carries on from the fraction it was painted at rather than from a rounded one.

**The published target carries the fraction too.** `data-morphing` is the number the panel predicts
from, and it now reads `193.75`; the prediction is arithmetic over three fractional heights and
lands on the height the panel actually takes.

### What it measures now

Same instrument, same window. The aside rolls `0px` to `193.75px`, the ride-along's prediction is
545.75 against a settled 545.75, and the step at every roll boundary in the trace is 0.000px. That
is under the 0.015px the panel's own change reached, and for a different reason: 0.015 was
Chromium's 1/64px grid showing through a real conversion, while this is two sides of one contract
reading one number, with nothing left to disagree about.

### The harness, which was the entry's stated cost

Every fake of a rolling section's height now says it through the computed style, so no test asserts
on a number production does not read. `stubRoll` in `body/app/src/test-setup.ts` (shared by
`Reminders.test.tsx`, `SessionList.test.tsx` and `Panel.test.tsx`) hands its height to
`laysEverything`, which was widened to take an answer that can change under the test, and
`Collapse.test.tsx`'s own stand-in does the same so that a roll interrupted mid-flight still reads
where it had got to. That is the whole of the "three test files sharing one prototype-wide fake"
the entry priced, and it landed as one helper rather than a rewrite per file, exactly as the
panel's did.

**Falsified both ways.** Reading `offsetHeight` again reddens eleven `Collapse` cases plus the
per-row exits in `Reminders.test.tsx` and `SessionList.test.tsx`, which is the harness proving it is
bound to production. Rounding the used height instead reddens exactly one case, the new one that
rolls a section standing on a sub-pixel and asserts the keyframes and the published target both
carry it.

### What this does not do

**The whisper's bubble still publishes a rounded target.** `useWhisperClock` announces
`String(Math.round(tH))` while writing its own box to a tenth of a pixel, so the ride-along adds a
whole number to fractional heights for the length of a streamed reply. It is the same shape as the
defect above and is read from the code rather than measured: the bubble is never handed back to
layout the way a section is, so the visible symptom may not exist. Filed unmeasured in
[refinements/body-overlay.md](../refinements/body-overlay.md), where the first move is a live trace
and not a change.
