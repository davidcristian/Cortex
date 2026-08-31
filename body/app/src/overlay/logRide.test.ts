import { afterEach, describe, expect, it, vi } from "vitest";

import { rideTail } from "./logRide";

/** The log's own threshold, which `rideTail` is handed rather than reading. */
const WITHIN = 40;

/** jsdom has neither layout nor a frame clock, so the test is the layout: one mutable record of
 *  how tall the box's content is, how much of it shows, where it is scrolled to, and where the
 *  rolling section's top edge is in that content. */
interface Layout {
  content: number;
  window: number;
  top: number;
  /** The section's top edge, in content coordinates. */
  at: number;
}

/** Where the rolling section stands. */
type Where = "in" | "chrome";

function stage(layout: Layout, where: Where = "in") {
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
  if (where === "in") {
    box.append(section);
    document.body.append(box);
  } else {
    document.body.append(section, box);
  }
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
  section.getBoundingClientRect = () => rect(where === "in" ? layout.at - box.scrollTop : layout.at);
  return {
    box,
    section,
    cancelled,
    /** Where the log is, as the eye has it: how far the content's end is below the window. */
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
    const layout: Layout = { content: 704, window: 293, top: 100, at: 300 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    expect(log.frames()).toBe(1);
    expect(log.top()).toBe(100);
  });

  it("stops where the rolling section's own top edge reaches the top of the window", () => {
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
    const layout: Layout = { content: 704, window: 121, top: 580, at: 530 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 780;
    log.tick();
    expect(log.top()).toBe(580);
  });

  it("holds the tail through a roll in the chrome, which takes the window and not the content", () => {
    const layout: Layout = { content: 469, window: 293, top: 173, at: -118 };
    const log = stage(layout, "chrome");
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    expect(log.tail()).toBe(3);
    for (const shrunk of [254, 192, 122, 90, 73]) {
      layout.window = shrunk;
      log.tick();
      expect(log.tail()).toBe(3);
    }
    expect(log.top()).toBe(393);
  });

  it("gives a chrome roll's room back on the way shut, landing on the pixel it started from", () => {
    const layout: Layout = { content: 469, window: 73, top: 393, at: -118 };
    const log = stage(layout, "chrome");
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    for (const grown of [122, 192, 254, 293]) {
      layout.window = grown;
      log.tick();
      expect(log.tail()).toBe(3);
    }
    expect(log.top()).toBe(173);
  });

  it("does not read a chrome section's own top edge as room the reader has to keep", () => {
    const layout: Layout = { content: 469, window: 293, top: 173, at: -118 };
    const log = stage(layout, "chrome");
    expect(log.section.getBoundingClientRect().top - log.box.getBoundingClientRect().top).toBe(-118);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.window = 73;
    log.tick();
    expect(log.top()).toBe(393);
  });

  it("hands the scroll straight back to a reader who takes it mid-roll", () => {
    const layout: Layout = { content: 704, window: 293, top: 408, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 739;
    log.tick();
    expect(log.top()).toBe(443);
    layout.top = 363;
    layout.content = 780;
    log.tick();
    expect(log.top()).toBe(363);
    expect(log.frames()).toBe(3);
  });

  it("does not mistake the engine's own clamp for the reader taking the scroll", () => {
    const layout: Layout = { content: 780, window: 293, top: 484, at: 529 };
    const log = stage(layout);
    rideTail(log.box, log.section, WITHIN);
    log.tick();
    layout.content = 704;
    expect(log.top()).toBe(411);
    log.tick();
    expect(log.top()).toBe(408);
  });

  it("settles on the height the roll ended at before it stops following", () => {
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
