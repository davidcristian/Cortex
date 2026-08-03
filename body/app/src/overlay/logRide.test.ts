import { afterEach, describe, expect, it, vi } from "vitest";

import { rideTail } from "./logRide";

/** The log's own pin threshold, which the ride is handed rather than reading. */
const WITHIN = 40;

/**
 * jsdom has neither layout nor a frame clock, so the test IS the layout: one mutable record standing
 * for how tall the box's content is, how much of it shows, where it is scrolled to, and where the
 * rolling section's top edge sits in that content.
 *
 * A roll is the test moving `content` between frames, and a roll the panel is still absorbing moves
 * `window` with it, which is exactly what the section's height animation does to a real box. The
 * scroll position is faithful in the one way the ride depends on: the engine clamps it to the range
 * the box has, on the way in AND on the way out, so a closing roll shortens the content under a
 * position that then reads back as something else.
 */
interface Layout {
  content: number;
  window: number;
  top: number;
  /** The section's top edge, in content coordinates. */
  at: number;
}

function stage(layout: Layout) {
  const frames: FrameRequestCallback[] = [];
  const cancelled: number[] = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  vi.stubGlobal("cancelAnimationFrame", (handle: number) => cancelled.push(handle));
  const range = () => Math.max(layout.content - layout.window, 0);
  const box = document.createElement("div");
  const section = document.createElement("div");
  section.setAttribute("data-morphing", "76");
  box.append(section);
  document.body.append(box);
  Object.defineProperty(box, "scrollHeight", { get: () => layout.content });
  Object.defineProperty(box, "clientHeight", { get: () => layout.window });
  Object.defineProperty(box, "scrollTop", {
    get: () => Math.min(Math.max(layout.top, 0), range()),
    set: (value: number) => {
      layout.top = Math.min(Math.max(value, 0), range());
    },
  });
  const rect = (top: number) => ({ top }) as DOMRect;
  box.getBoundingClientRect = () => rect(0);
  section.getBoundingClientRect = () => rect(layout.at - box.scrollTop);
  return {
    box,
    section,
    cancelled,
    /** Where the log sits, as the eye has it: how far the end of the content is below the window. */
    tail: () => range() - box.scrollTop,
    top: () => box.scrollTop,
    frames: () => frames.length,
    tick: () => frames[frames.length - 1]?.(0),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

describe("rideTail", () => {
  it("holds the reader's distance from the end of the log for every frame of the roll", () => {
    // A full history at 640x720 with the panel on its ceiling: the window cannot grow, so every
    // pixel the trace takes is a pixel of the reply pushed under the composer.
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    expect(log.tail()).toBe(3);
    for (const content of [717, 739, 757, 771, 780]) {
      layout.content = content;
      log.tick();
      expect(log.tail()).toBe(3);
    }
    // 76px of growth, and the reader is exactly where they were relative to the end of the reply.
    expect(log.top()).toBe(484);
  });

  it("gives the growth back on the way shut, landing on the pixel it started from", () => {
    const layout: Layout = { content: 780, window: 293, top: 484, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    for (const content of [757, 727, 704]) {
      layout.content = content;
      log.tick();
      expect(log.tail()).toBe(3);
    }
    expect(log.top()).toBe(408);
  });

  it("scrolls nothing at all while the panel is still absorbing the growth", () => {
    // Below the ceiling the panel grows by what the trace takes and the window grows with it, so the
    // scroll range never changes and there is nothing for the ride to do. Traced at 900x900: the
    // panel went 390.97 to 466.97 and `scrollTop` read 0 on every frame of both directions.
    const layout: Layout = { content: 234, window: 234, top: 0, at: 100 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    for (const grown of [247, 287, 310]) {
      layout.content = grown;
      layout.window = grown;
      log.tick();
      expect(log.top()).toBe(0);
    }
  });

  it("leaves a reader who has scrolled up exactly where they are", () => {
    // A section growing pushes only what is below it, so nothing this reader is looking at moves,
    // and the row stays under the pointer that opened it, which is what a disclosure is meant to do.
    const layout: Layout = { content: 704, window: 293, top: 100, at: 300 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    // One frame asked for and answered, and no second one: the ride stood down on the reading.
    expect(log.frames()).toBe(1);
    expect(log.top()).toBe(100);
  });

  it("stops where the rolling section's own top edge reaches the top of the window", () => {
    // Following the tail past this point scrolls the trace off the top and leaves the reader on its
    // bottom half. Traced at 640x600, where the trace's top edge sits 58px down a 206px window: the
    // ride spends those 58px and the last 21px of the growth goes into the scroll as before.
    const layout: Layout = { content: 704, window: 293, top: 408, at: 438 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 780;
    log.tick();
    expect(log.top()).toBe(438);
    expect(log.tail()).toBe(49);
  });

  it("caps a section already above the window where it stands, rather than chasing it", () => {
    // The reader is not looking at it, so scrolling further down would only carry them away from the
    // thing they opened. Traced at 640x460, where the history is 121px and the disclosure sits 50px
    // above its top edge.
    const layout: Layout = { content: 704, window: 121, top: 580, at: 530 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 780;
    log.tick();
    expect(log.top()).toBe(580);
  });

  it("hands the scroll straight back to a reader who takes it mid-roll", () => {
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 739;
    log.tick();
    expect(log.top()).toBe(443);
    // The wheel, 80px up the log. Traced in Chromium at 640x720: the ride stood down in the frame it
    // landed and `scrollTop` read the reader's number for every frame after it.
    layout.top = 363;
    layout.content = 780;
    log.tick();
    expect(log.top()).toBe(363);
    expect(log.frames()).toBe(3);
  });

  it("does not mistake the engine's own clamp for the reader taking the scroll", () => {
    // A closing roll shortens the content under a position the engine then clamps for itself, which
    // is the box moving and not the reader. Compared raw, the ride would give up on its own shrink.
    const layout: Layout = { content: 780, window: 293, top: 484, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 704;
    expect(log.top()).toBe(411); // the engine got there first
    log.tick();
    expect(log.top()).toBe(408);
  });

  it("settles on the height the roll ended at before it stops following", () => {
    // `Collapse` clears the attribute before it says the roll ended, so the frame that finds the
    // roll over is still the frame that has to land the scroll on the finished layout.
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 780;
    log.section.removeAttribute("data-morphing");
    log.tick();
    expect(log.top()).toBe(484);
    expect(log.frames()).toBe(2);
  });

  it("stops following a section that leaves the tree mid-roll", () => {
    // A chat switched while a trace rolls unmounts the whole message with the attribute still on it,
    // and a loop reading a detached tree would never stop.
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    expect(log.frames()).toBe(2);
    log.section.remove();
    log.tick();
    expect(log.frames()).toBe(2);
  });

  it("gives up the frame it is holding when the ride is called off, once", () => {
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    const off = rideTail(log.box, log.section, WITHIN);
    off();
    expect(log.cancelled).toEqual([1]);
    off();
    expect(log.cancelled).toEqual([1]);
  });

  it("has nothing to call off once the roll has ended on its own", () => {
    const layout: Layout = { content: 704, window: 293, top: 100, at: 300 };
    const log = stage(layout);
    const off = rideTail(log.box, log.section, WITHIN);
    log.tick();
    off();
    expect(log.cancelled).toEqual([]);
  });
});
