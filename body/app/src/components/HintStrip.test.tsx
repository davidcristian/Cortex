import { render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { HINT_STRIP_PROPERTY } from "../overlay/measured";
import { laysEverything } from "../test-setup";
import { HintStrip } from "./HintStrip";

let restore: () => void = () => undefined;

afterEach(() => {
  restore();
  document.documentElement.style.removeProperty(HINT_STRIP_PROPERTY);
});

it("hands its own height to the panel's budget, so a wrapped strip is reserved in full", () => {
  restore = laysEverything(55);
  render(<HintStrip onToggleConsole={() => undefined} />);
  expect(document.documentElement.style.getPropertyValue(HINT_STRIP_PROPERTY)).toBe("55px");
});
