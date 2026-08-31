import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ACTIVATE_EVENT, requestActivation, takePendingActivation } from "./activation";

// The module holds one flag for the whole app, so each test starts from a drained one.
beforeEach(() => {
  takePendingActivation();
});

afterEach(() => {
  takePendingActivation();
});

describe("activation", () => {
  it("has nothing pending until something asks", () => {
    expect(takePendingActivation()).toBe(false);
  });

  it("announces the request to whoever is already listening", () => {
    const heard = vi.fn();
    window.addEventListener(ACTIVATE_EVENT, heard);
    requestActivation();
    expect(heard).toHaveBeenCalledOnce();
    window.removeEventListener(ACTIVATE_EVENT, heard);
  });

  it("keeps the request for a listener that attaches afterwards", () => {
    // This is the case the module exists for: the browser self-summon and a cold-start hotkey
    // press both land before the app's passive effect has attached anything.
    requestActivation();
    expect(takePendingActivation()).toBe(true);
  });

  it("hands the request over exactly once, so a later listener does not replay it", () => {
    requestActivation();
    expect(takePendingActivation()).toBe(true);
    expect(takePendingActivation()).toBe(false);
  });

  it("collapses a burst into one outstanding request", () => {
    requestActivation();
    requestActivation();
    expect(takePendingActivation()).toBe(true);
    expect(takePendingActivation()).toBe(false);
  });
});
