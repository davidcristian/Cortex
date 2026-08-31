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
    // Shift is how a `?` is typed, so it is not a chord.
    expect(chord(press({ key: "?" }))).toBe(false);
  });
});

describe("fieldKey", () => {
  it("cancels on Escape, the innermost thing closing first", () => {
    expect(fieldKey(press({ key: "Escape" }))).toBe("cancel");
    // Asked before the modifier, so a reader reaching for the way out gets it however they hold it.
    expect(fieldKey(press({ key: "Escape", ctrlKey: true }))).toBe("cancel");
  });

  it("holds a chord, which is what a field with no undo behind it does with one", () => {
    // The four the overlay binds today, plus one it does not: the answer is about the modifier, so
    // the next chord the overlay grows is held on the day it is bound rather than the day after.
    for (const key of ["n", "k", "ArrowUp", "ArrowDown", "j"]) {
      expect(fieldKey(press({ key, ctrlKey: true }))).toBe("hold");
      expect(fieldKey(press({ key, metaKey: true }))).toBe("hold");
    }
  });

  it("passes everything else on, `?` included, which is answered one layer up", () => {
    expect(fieldKey(press())).toBe("pass");
    expect(fieldKey(press({ key: "Enter" }))).toBe("pass");
    // The console's key is guarded by element type in the overlay's own handler, so a field that
    // held it here would be duplicating a rule rather than composing with it.
    expect(fieldKey(press({ key: "?" }))).toBe("pass");
  });
});
