import { describe, expect, it } from "vitest";

import { formatDraftValue } from "./draftValue";

describe("formatDraftValue", () => {
  it("leaves a string exactly as it is, newlines included", () => {
    expect(formatDraftValue("# Week 30\n- one")).toBe("# Week 30\n- one");
  });

  it("renders scalars and null as their text", () => {
    expect(formatDraftValue(3)).toBe("3");
    expect(formatDraftValue(true)).toBe("true");
    expect(formatDraftValue(null)).toBe("null");
  });

  it("renders an object as key: value lines", () => {
    expect(formatDraftValue({ filename: "notes.md", subtype: "markdown" })).toBe(
      "filename: notes.md\nsubtype: markdown",
    );
  });

  it("gives a multi-line value its own line, so the payload reads as itself", () => {
    expect(formatDraftValue({ filename: "notes.md", content: "one\ntwo" })).toBe(
      "filename: notes.md\ncontent:\none\ntwo",
    );
  });

  it("separates array items with a blank line", () => {
    expect(formatDraftValue([{ filename: "a.md" }, { filename: "b.md" }])).toBe(
      "filename: a.md\n\nfilename: b.md",
    );
  });

  it("renders an array of scalars without inventing structure", () => {
    expect(formatDraftValue(["a", "b"])).toBe("a\n\nb");
  });

  it("recurses through nesting, which is how an attachment list reads", () => {
    expect(
      formatDraftValue({
        to: "ada@example.com",
        attachments: [{ filename: "notes.md", content: "# Week 30\n- one" }],
      }),
    ).toBe("to: ada@example.com\nattachments:\nfilename: notes.md\ncontent:\n# Week 30\n- one");
  });
});
