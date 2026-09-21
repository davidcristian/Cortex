// What the panel remembers about its own position between one placement and the next, and how it
// reads its own box. Written only by `panelPlacement` and `panelRoll`.

import type { Geometry } from "./panelGeometry";

/** How long a summon owns the panel's geometry, matching `.panel`'s own 0.44s transform transition
 *  in overlay.css, and ended early by `touched`. Whatever happens inside it belongs to the panel
 *  arriving: the summon's reminder stack, for one, settles 340ms after the summon. */
const ARRIVAL_MS = 440;

export interface Memory {
  /** The geometry currently on screen, or null before the first measurement. */
  shown: Geometry | null;
  /** The height the panel was last placed for: what its content asked of it, under the cap it was
   *  given. The watch compares against this rather than against the box, because a move of the
   *  panel's own walks the box past it every frame while this stands still. */
  placedFor: number;
  running: Animation | null;
  /** Where `running` is taking the panel. Meaningless while `running` is null or finished. */
  aim: Geometry;
  /** When `running` is due to arrive, as `Date.now()`. A re-render that leaves the destination
   *  unchanged resumes the move over the time left of this rather than restarting its clock. */
  lands: number;
  /** The view the panel last settled into; anything else moves it. */
  view: string;
  /** Whether the panel was open at the last placement, so a summon can be seen arriving. */
  open: boolean;
  /** When the panel was last summoned, as `Date.now()`; 0 before the first one. */
  arrived: number;
  /** The bottom edge the panel is held to, unclamped: what it asks for, not what fits. */
  pinned: number;
  /** The bottom edge last written to the DOM, which is `pinned` after the ceiling has its say. */
  applied: number;
  /** The chat's own edge, kept while another view is on screen; null until it first leaves. */
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

/** How tall the element is, in layout pixels, sub-pixels included. `getBoundingClientRect` reports
 *  the box after transforms and the panel is scaled through a summon, where it read 327.5px against
 *  a layout height of 356. An element with no layout box reports 0. */
export function heightOf(element: HTMLElement): number {
  const used = Number.parseFloat(getComputedStyle(element).height);
  return Number.isNaN(used) ? 0 : used;
}

/** How tall the element would be right now if nothing were animating it, read without cancelling
 *  the move in the air. A height animation overrides the used height, so an `!important` inline
 *  declaration hands the height back to layout, along with the cap the placement wrote. */
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

/** Where the element is right now, mid-animation: what the eye actually sees. The bottom edge
 *  comes from the rect, which is exact even mid-summon, the panel's `transform-origin` being its
 *  own bottom edge; only the height above it is scaled. */
export function measure(element: HTMLElement, viewport: number): Geometry {
  return { height: heightOf(element), bottom: viewport - element.getBoundingClientRect().bottom };
}

/** Whether the panel is still arriving from a summon, and so centres on whatever it is now. */
export function arriving(memory: Memory, at: Placement): boolean {
  return at.open && Date.now() - memory.arrived < ARRIVAL_MS;
}

/** The user reached for the panel, which ends the summon's ownership of its geometry: what changes
 *  from here grows from the edge the panel is held to rather than re-centring. Input that arrives
 *  while the panel is still shut is what summoned it, so it does not count. */
export function touched(memory: Memory): void {
  if (memory.open) {
    memory.arrived = 0;
  }
}
