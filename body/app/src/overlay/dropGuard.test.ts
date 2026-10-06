import { afterEach, describe, expect, it } from "vitest";

import config from "../../src-tauri/tauri.conf.json";
import { guardDrops } from "./dropGuard";

function drag(kind: string, types: readonly string[] | null): Event {
  const event = new Event(kind, { cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: types === null ? null : { types } });
  window.dispatchEvent(event);
  return event;
}

let undo = () => {};

afterEach(() => undo());

describe("guardDrops", () => {
  it.each(["dragenter", "dragover", "drop"])("cancels a %s holding a file or an address", (kind) => {
    undo = guardDrops(window);
    expect(drag(kind, ["Files"]).defaultPrevented).toBe(true);
    expect(drag(kind, ["text/uri-list", "text/html"]).defaultPrevented).toBe(true);
  });

  it("leaves a plain text drag and a drag with no data to the webview", () => {
    undo = guardDrops(window);
    expect(drag("drop", ["text/plain", "text/html"]).defaultPrevented).toBe(false);
    expect(drag("dragover", null).defaultPrevented).toBe(false);
  });

  it("stops cancelling once undone", () => {
    guardDrops(window)();
    for (const kind of ["dragenter", "dragover", "drop"]) {
      expect(drag(kind, ["Files"]).defaultPrevented).toBe(false);
    }
  });

  it("matches a window config that leaves every drop to the page", () => {
    expect(config.app.windows.map((entry) => entry.dragDropEnabled)).toEqual([false]);
  });
});
