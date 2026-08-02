import { afterEach, describe, expect, it } from "vitest";

import { resized } from "../test-setup";
import {
  CHAT_FLOOR_PROPERTY,
  TRACE_ROW_PROPERTY,
  chatFloorRef,
  publishHeight,
  traceRowRef,
} from "./measured";

/** An element whose laid-out height jsdom would otherwise report as 0 for everything. */
function tall(height: number): HTMLElement {
  const element = document.createElement("div");
  Object.defineProperty(element, "offsetHeight", { configurable: true, value: height });
  document.body.append(element);
  return element;
}

/** What the browser does when the box changes under a laid-out element. */
function grewTo(element: HTMLElement, height: number): number {
  Object.defineProperty(element, "offsetHeight", { configurable: true, value: height });
  return resized(element);
}

const standing = (property: string) =>
  document.documentElement.style.getPropertyValue(property);

afterEach(() => {
  document.documentElement.style.removeProperty(CHAT_FLOOR_PROPERTY);
  document.documentElement.style.removeProperty(TRACE_ROW_PROPERTY);
  document.body.innerHTML = "";
});

describe("publishHeight", () => {
  it("publishes the height it measured, not the number the stylesheet started with", () => {
    // The whole point of the module: an empty state that grew a line has to move the floor with
    // it. A probe that published the frozen 185 would pass every structural test and drift exactly
    // as the constant did.
    publishHeight(CHAT_FLOOR_PROPERTY, tall(207));
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("207px");
  });

  it("republishes when the same element is measured again at a new height", () => {
    // The empty state mounts once per empty chat, so this is the ordinary path rather than a
    // corner: a second chat, a changed mark, a reload after an edit. Measuring twice must land on
    // the second reading and not latch the first.
    const element = tall(185);
    publishHeight(CHAT_FLOOR_PROPERTY, element);
    Object.defineProperty(element, "offsetHeight", { configurable: true, value: 224 });
    publishHeight(CHAT_FLOOR_PROPERTY, element);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("224px");
  });

  it("leaves the standing value alone when the element has no layout to report", () => {
    // jsdom, a `display: none` ancestor, and a node that is not in a document all read 0. A zero
    // floor would collapse the log the constant exists to hold up, so the stylesheet's own
    // declaration has to survive the reading.
    publishHeight(CHAT_FLOOR_PROPERTY, tall(185));
    publishHeight(CHAT_FLOOR_PROPERTY, document.createElement("div"));
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("leaves the standing value alone when the element is on its way out", () => {
    // React calls a ref with null at unmount. The empty state unmounts precisely when the first
    // message arrives, which is the frame the floor is first load-bearing, so forgetting the
    // number there would be worse than never having taken it.
    publishHeight(CHAT_FLOOR_PROPERTY, tall(185));
    publishHeight(CHAT_FLOOR_PROPERTY, null);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("names the two properties overlay.css reads, which is the whole of the coupling", () => {
    // Vitest runs with CSS processing off, so the stylesheet's bytes cannot be read from inside
    // this toolchain and nothing machine-checks that these still agree with the rules that spend
    // them. Pinning the literals is what a rename has to walk past, the same arrangement
    // `--ceiling` and `data-resizing` already have.
    expect(CHAT_FLOOR_PROPERTY).toBe("--chat-floor");
    expect(TRACE_ROW_PROPERTY).toBe("--trace-row");
  });
});

describe("the refs the components attach", () => {
  it("sends the empty state to the floor and a chip to the trace row, never the other way", () => {
    chatFloorRef(tall(185));
    traceRowRef(tall(24));
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("185px");
    expect(standing(TRACE_ROW_PROPERTY)).toBe("24px");
  });

  it("reads each chip once, because a turn can have two of them up at once", () => {
    // A tool chip and a status chip are the same box and can be on screen together, so one watch
    // per property could not hold them: a shared ref callback is told an element is leaving but
    // never which one, and the tool chip's departure would stand the status chip's watch down.
    // Each is read instead, which says the same thing and leaves nothing behind.
    const tool = tall(24);
    const status = tall(24);
    traceRowRef(tool);
    traceRowRef(status);
    expect(standing(TRACE_ROW_PROPERTY)).toBe("24px");
    expect(grewTo(tool, 99) + grewTo(status, 99)).toBe(0);
    expect(standing(TRACE_ROW_PROPERTY)).toBe("24px");
  });

  it("does nothing at all on unmount, whichever ref it is", () => {
    chatFloorRef(null);
    traceRowRef(null);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("");
    expect(standing(TRACE_ROW_PROPERTY)).toBe("");
  });

  it("follows the box after the frame it was attached in", () => {
    // The reading taken as the element is attached is not the last word on it. Measured at boot in
    // Chromium, the empty state is 183px in that frame and 185px two frames later, because the
    // example chips' row comes out 29px before the system font stack resolves and 31px after. A
    // probe that read once would freeze a number that is wrong by the difference.
    const element = tall(183);
    chatFloorRef(element);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("183px");
    expect(grewTo(element, 185)).toBe(1);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("stops following an element it has let go of", () => {
    // React hands the ref the next element before it hands over null when a component re-keys, and
    // the empty state is keyed to its chat. An observer left behind on the old node would go on
    // publishing a box nobody is looking at.
    const gone = tall(185);
    chatFloorRef(gone);
    chatFloorRef(tall(207));
    expect(grewTo(gone, 400)).toBe(0);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("207px");
  });

  it("stops following on unmount too", () => {
    const element = tall(185);
    chatFloorRef(element);
    chatFloorRef(null);
    expect(grewTo(element, 400)).toBe(0);
    expect(standing(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });
});
