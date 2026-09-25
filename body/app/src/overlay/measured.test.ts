import { afterEach, describe, expect, it } from "vitest";

import { lays, resized } from "../test-setup";
import {
  CHAT_FLOOR_PROPERTY,
  HINT_STRIP_PROPERTY,
  TRACE_ROW_PROPERTY,
  chatFloorRef,
  hintStripRef,
  publishHeight,
  traceRowRef,
} from "./measured";

/** An element whose laid-out height jsdom would otherwise report as nothing at all. */
function tall(height: number): HTMLElement {
  const element = document.createElement("div");
  lays(element, height);
  document.body.append(element);
  return element;
}

/** What the browser does when the box changes under a laid-out element. */
function grewTo(element: HTMLElement, height: number): number {
  lays(element, height);
  return resized(element);
}

const current = (property: string) =>
  document.documentElement.style.getPropertyValue(property);

afterEach(() => {
  document.documentElement.style.removeProperty(CHAT_FLOOR_PROPERTY);
  document.documentElement.style.removeProperty(TRACE_ROW_PROPERTY);
  document.documentElement.style.removeProperty(HINT_STRIP_PROPERTY);
  document.body.innerHTML = "";
});

describe("publishHeight", () => {
  it("publishes the height it measured, not the number the stylesheet started with", () => {
    publishHeight(CHAT_FLOOR_PROPERTY, tall(207));
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("207px");
  });

  it("republishes when the same element is measured again at a new height", () => {
    const element = tall(185);
    publishHeight(CHAT_FLOOR_PROPERTY, element);
    lays(element, 224);
    publishHeight(CHAT_FLOOR_PROPERTY, element);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("224px");
  });

  it("leaves the current value alone when the element has no layout to report", () => {
    publishHeight(CHAT_FLOOR_PROPERTY, tall(185));
    publishHeight(CHAT_FLOOR_PROPERTY, document.createElement("div"));
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("leaves the current value alone when the element is on its way out", () => {
    publishHeight(CHAT_FLOOR_PROPERTY, tall(185));
    publishHeight(CHAT_FLOOR_PROPERTY, null);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("names the two properties overlay.css reads, which is the whole of the coupling", () => {
    expect(CHAT_FLOOR_PROPERTY).toBe("--chat-floor");
    expect(TRACE_ROW_PROPERTY).toBe("--trace-row");
    expect(HINT_STRIP_PROPERTY).toBe("--hint-strip");
  });
});

describe("the refs the components attach", () => {
  it("sends the empty state to the floor and a chip to the trace row, never the other way", () => {
    chatFloorRef(tall(185));
    traceRowRef(tall(24));
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("185px");
    expect(current(TRACE_ROW_PROPERTY)).toBe("24px");
  });

  it("reads each chip once, because a turn can have two of them up at once", () => {
    const tool = tall(24);
    const status = tall(24);
    traceRowRef(tool);
    traceRowRef(status);
    expect(current(TRACE_ROW_PROPERTY)).toBe("24px");
    expect(grewTo(tool, 99) + grewTo(status, 99)).toBe(0);
    expect(current(TRACE_ROW_PROPERTY)).toBe("24px");
  });

  it("republishes the hint strip when a narrow panel wraps it onto a second row", () => {
    const strip = tall(33);
    hintStripRef(strip);
    expect(current(HINT_STRIP_PROPERTY)).toBe("33px");
    expect(grewTo(strip, 55)).toBe(1);
    expect(current(HINT_STRIP_PROPERTY)).toBe("55px");
    hintStripRef(null);
  });

  it("does nothing at all on unmount, whichever ref it is", () => {
    chatFloorRef(null);
    traceRowRef(null);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("");
    expect(current(TRACE_ROW_PROPERTY)).toBe("");
  });

  it("follows the box after the frame it was attached in", () => {
    const element = tall(183);
    chatFloorRef(element);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("183px");
    expect(grewTo(element, 185)).toBe(1);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });

  it("stops following an element it has let go of", () => {
    const gone = tall(185);
    chatFloorRef(gone);
    chatFloorRef(tall(207));
    expect(grewTo(gone, 400)).toBe(0);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("207px");
  });

  it("stops following on unmount too", () => {
    const element = tall(185);
    chatFloorRef(element);
    chatFloorRef(null);
    expect(grewTo(element, 400)).toBe(0);
    expect(current(CHAT_FLOOR_PROPERTY)).toBe("185px");
  });
});
