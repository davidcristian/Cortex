import { describe, expect, it } from "vitest";

import { chord, fieldKey } from "./fieldKeys";

/** One press, defaulting to the plain key everything below varies from. */
const press = (over: Partial<{ key: string; ctrlKey: boolean; metaKey: boolean }> = {}) => ({
  key: "n",
  ctrlKey: false,
  metaKey: false,
  ...over,
});

describe("chord", () => {
  it("is Ctrl on every platform and Cmd on the Mac, and nothing else", () => {
    expect(chord(press({ ctrlKey: true }))).toBe(true);
    expect(chord(press({ metaKey: true }))).toBe(true);
    expect(chord(press())).toBe(false);
    expect(chord(press({ key: "?" }))).toBe(false);
  });
});

describe("fieldKey", () => {
  it("cancels on Escape, the innermost thing closing first", () => {
    expect(fieldKey(press({ key: "Escape" }))).toBe("cancel");
    expect(fieldKey(press({ key: "Escape", ctrlKey: true }))).toBe("cancel");
  });

  it("holds a chord, which is what a field with no undo behind it does with one", () => {
    for (const key of ["n", "k", "ArrowUp", "ArrowDown", "j"]) {
      expect(fieldKey(press({ key, ctrlKey: true }))).toBe("hold");
      expect(fieldKey(press({ key, metaKey: true }))).toBe("hold");
    }
  });

  it("passes everything else on, `?` included, which is answered one layer up", () => {
    expect(fieldKey(press())).toBe("pass");
    expect(fieldKey(press({ key: "Enter" }))).toBe("pass");
    expect(fieldKey(press({ key: "?" }))).toBe("pass");
  });
});
