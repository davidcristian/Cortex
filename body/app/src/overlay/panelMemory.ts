// What the panel remembers about its own position between one placement and the next, and how it
// reads its own box. Shared by `panelPlacement` (where the panel belongs) and `panelRide` (the
// slide it makes alongside a section's roll), which are the only two things that write to it.

import type { Geometry } from "./panelGeometry";

/**
 * How long a summon owns the panel's geometry, matching `.panel`'s own 0.44s transform transition
 * in overlay.css. It ends early the moment the user touches the panel (see `touched`).
 *
 * Whatever lands inside that window belongs to the panel ARRIVING rather than to the session, so it
 * centres on it instead of growing upward from an edge pinned before it had its content. The
 * summon's reminder pull is the case that made this necessary: traced at 60Hz, the stack rolls open
 * 10ms behind the summon and settles 340ms later, and treating that as growth pinned the panel to
 * the centre of the 356px it had been before the reminders landed. It then spent the whole session
 * 109px above its own centre and hard against its ceiling, where every later shrink slid the
 * composer (measured: acking one reminder moved it 40px up the screen).
 *
 * That 40px is a reading from before the panel's second bound was deleted on 2026-07-20, and only
 * the composer half of it is stale: re-measured 2026-08-06, a shrink against the ceiling moves the
 * composer 0px whatever edge the session is pinned to, the ceiling now capping the HEIGHT. What the
 * window still earns is the first half, which is the whole reason it exists. A panel pinned to the
 * centre of a height its content is a beat away from having spends the session off its own centre,
 * and off centre is where it sits until the next summon.
 */
const ARRIVAL_MS = 440;

export interface Memory {
  /** The geometry currently on screen, or null before the first measurement. */
  shown: Geometry | null;
  /** The height the panel was last placed FOR: what its content asked of it, under the cap it was
   *  given. The watch on the panel's own box compares against this rather than against the box,
   *  because a move of the panel's own walks the box past it every frame while this stands still,
   *  and a render that resized the panel has already been answered by the placement that ran in it.
   *  0 before the first placement, which is always before the watch exists. */
  placedFor: number;
  running: Animation | null;
  /** Where `running` is taking the panel. Meaningless while `running` is null or finished. */
  aim: Geometry;
  /** When `running` is due to land, as `Date.now()`. A re-render that leaves the destination
   *  unchanged RESUMES the move over the time left of this rather than restarting its clock. */
  lands: number;
  /** The view the panel last settled into; anything else moves it. */
  view: string;
  /** Whether the panel was open at the last placement, so a summon can be seen arriving. */
  open: boolean;
  /** When the panel was last summoned, as `Date.now()`; 0 before the first one. */
  arrived: number;
  /** The bottom edge the panel is pinned to, UNCLAMPED: what it wants, not what fits. */
  pinned: number;
  /** The bottom edge last written to the DOM, which is `pinned` after the ceiling had its say. */
  applied: number;
  /** The chat's pinned edge, held while another view is on screen; null until it first leaves. */
  parked: number | null;
  /** The height a section inside is currently rolling to, or null when none is. */
  rolling: number | null;
  /** The height the panel is driving its own height to across the roll now running, or null in the
   *  usual case where the section owns the height and the panel's `auto` simply follows it. */
  carrying: number | null;
  /** Set while a child owned the last size change, and cleared by the first placement after it. */
  deferred: boolean;
}

/** A panel that has not been placed yet, seeded with the state it starts in: a panel that was
 *  already open on mount has not been summoned, and must not read as arriving. */
export function emptyMemory(open: boolean, view: string): Memory {
  return {
    shown: null,
    placedFor: 0,
    running: null,
    aim: { height: 0, bottom: 0 },
    lands: 0,
    view,
    open,
    arrived: 0,
    pinned: 0,
    applied: 0,
    parked: null,
    rolling: null,
    carrying: null,
    deferred: false,
  };
}

export interface Placement {
  readonly open: boolean;
  readonly view: string;
  /** Re-centre even though the view did not change (the viewport itself moved). */
  readonly recentre: boolean;
}

/**
 * How tall the element is, in layout pixels, sub-pixels included.
 *
 * `getBoundingClientRect` is the wrong tool for this one number: it reports the box AFTER
 * transforms, and the panel is scaled through the whole summon (`scale(0.92)` easing to 1, with a
 * spring that overshoots past it). Measured at boot: the panel read 327.5px tall while its layout
 * height was 356, so every geometry taken during a summon was ~8% short, the edge the session ends
 * up pinned to included.
 *
 * The used height off the computed style passes that same check and keeps the fraction the box
 * actually has. Measured in Chromium on a 356.281px box with a 1px border: `offsetHeight` reads 356
 * whether or not the box is scaled, the rect reads 356.266 plain and 327.764 under `scale(0.92)`,
 * and this reads 356.266 under both. It follows a running height animation the same way (an element
 * easing 400 to 500 reports the in-flight 409.984 and its natural height again once cancelled),
 * which is what makes it safe to read mid-move.
 *
 * The whole pixel `offsetHeight` gave instead is what made a move retargeted mid-stream open its
 * keyframes below the height the eye had, so the panel stepped back by the remainder for a frame
 * ([ADR-0035](../../../../docs/adr/ADR-0035-console-and-motion.md), the fractional-height addendum).
 *
 * It reports the BORDER box, this app setting `box-sizing: border-box` on everything, so it is the
 * same box `offsetHeight` reported. An element with no layout box (jsdom, a `display: none`
 * ancestor, a node outside a document) has no used value to give and reports 0 here, which is what
 * `measured.ts` reads as "nothing to publish".
 */
export function heightOf(element: HTMLElement): number {
  const used = Number.parseFloat(getComputedStyle(element).height);
  return Number.isNaN(used) ? 0 : used;
}

/**
 * How tall the element would be right now if nothing were animating it, read WITHOUT cancelling
 * the move in the air.
 *
 * A height animation overrides the used height, so while the panel's own ease runs, content that
 * grows inside it changes nothing the box can show: the panel's watch cannot tell its own ease
 * walking the box from a resize it should answer, and it used to answer neither until the ease
 * landed. An `!important` inline declaration outranks the animation origin in the cascade, so
 * handing the height back to layout for the length of one read asks the element the question the
 * animation is hiding. Measured in Chromium at 900x1400, 60px appended into the log and 40px more
 * two frames into the resulting ease: the box read 567.906 for both frames while this read 616.75
 * and then 667.75, which is the growth arriving. Nothing paints in between (the override is gone
 * before the frame ends), and the read costs no notification of its own: instrumented over the
 * demo, the observer's "loop completed with undelivered notifications" error fired zero times.
 *
 * The element's own cap is re-asserted for the same read, because a move carries its ceiling in the
 * keyframes (`panelGeometry.frame`) and that riding cap would otherwise clamp the answer to a
 * different number every frame. Under the cap the placement actually wrote, the answer is exactly
 * what a placement would measure: stable while the content is, and only content moves it.
 */
export function naturalHeightOf(element: HTMLElement): number {
  const style = element.style;
  const height = style.getPropertyValue("height");
  const priority = style.getPropertyPriority("height");
  const cap = style.getPropertyValue("max-height");
  style.setProperty("height", "auto", "important");
  style.setProperty("max-height", cap, "important");
  const natural = heightOf(element);
  style.setProperty("height", height, priority);
  style.setProperty("max-height", cap);
  return natural;
}

/** Where the element is right now, mid-animation: what the eye actually sees. The bottom edge is
 *  read from the rect, which is exact even mid-summon, the panel's `transform-origin` being its own
 *  bottom edge; only the height above it is scaled. */
export function measure(element: HTMLElement, viewport: number): Geometry {
  return { height: heightOf(element), bottom: viewport - element.getBoundingClientRect().bottom };
}

/** Whether the panel is still arriving from a summon, and so centres on whatever it is now. */
export function arriving(memory: Memory, at: Placement): boolean {
  return at.open && Date.now() - memory.arrived < ARRIVAL_MS;
}

/**
 * The user reached for the panel, which ends the summon's ownership of its geometry however much
 * of the window is left: what changes from here is the session's, and the session GROWS from its
 * pinned edge rather than re-centring.
 *
 * Without this, a section the user rolled open inside the window re-pinned the panel to the centre
 * of a height that section was about to hand back. Traced at 60Hz in a 900px viewport: opening the
 * chat switcher 410ms after the summon wrote a pinned edge of 117px for the 666px the panel would
 * be with the list open, and closing the list left the 546px panel sitting on that same 117px, 60px
 * below its own centre, where it stayed for the rest of the session. Nothing washes a pinned edge
 * out: a trip to the console and back parks the bad edge and hands it straight back.
 *
 * Input that lands while the panel is still SHUT is what summoned it (the orb click is a real
 * pointerdown a beat before the panel appears), so it is not a touch. The arrival that follows it is
 * exactly the case the window exists for.
 */
export function touched(memory: Memory): void {
  if (memory.open) {
    memory.arrived = 0;
  }
}
