import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Announcer } from "./Announcer";

/** The region, which is always in the tree, and the element inside it holding what it says. */
const read = (container: HTMLElement) => {
  const region = container.querySelector(".announcer");
  if (region === null) {
    throw new Error("the live region is not in the tree");
  }
  return { region, said: region.firstElementChild, text: region.textContent };
};

describe("Announcer", () => {
  it("stands in the tree with nothing to say, and is polite when it has something", () => {
    // A live region has to be present before the change it reports, so the resting state is an
    // empty region rather than no region. This test fails if the region is only rendered once a
    // notice exists, which is the arrangement that announces nothing at all.
    const { container, rerender } = render(<Announcer notice={null} />);
    const idle = read(container);
    expect(idle.region.getAttribute("role")).toBe("status");
    expect(idle.text).toBe("");
    expect(idle.said).toBeNull();

    rerender(<Announcer notice={{ text: "Switched to Everything about cats.", count: 1 }} />);
    const spoken = read(container);
    // The same node with words in it now, since the region itself never remounts.
    expect(spoken.region).toBe(idle.region);
    // Rendered as given. The sentence is built in `notice.ts`, which keeps everything the region
    // may carry in one file. This test fails if this component starts composing text again.
    expect(spoken.text).toBe("Switched to Everything about cats.");
  });

  it("reads whatever the notice holds, a list change included", () => {
    // The region reports what happened to the panel rather than only which conversation arrived,
    // so a delete that also swaps states both in one sentence instead of needing a second region.
    // This test fails if this component ever puts a fixed prefix back in front.
    const { container } = render(
      <Announcer notice={{ text: "Chat deleted. 1 chat left. Switched to New chat.", count: 4 }} />,
    );
    expect(read(container).text).toBe("Chat deleted. 1 chat left. Switched to New chat.");
  });

  it("makes a second announcement with the same words a second mutation", () => {
    // Two chats can carry one title, and two deletes can leave the same number of rows, and text
    // replaced by identical text is not announced. Keying on the count replaces the node instead of
    // reusing it, so the region mutates on every notice. This test fails if `Announcer` stops keying
    // on the count, since React then reuses the node and the second notice is silent.
    const { container, rerender } = render(
      <Announcer notice={{ text: "Switched to New chat.", count: 1 }} />,
    );
    const first = read(container);
    rerender(<Announcer notice={{ text: "Switched to New chat.", count: 2 }} />);
    const second = read(container);
    expect(second.text).toBe("Switched to New chat.");
    expect(second.said).not.toBe(first.said);
    expect(second.region).toBe(first.region);
  });

  it("takes its words back down when a swap speaks for itself", () => {
    // A switcher row clears the notice, and the region must not keep the last chat switched to, so
    // it holds only what was actually announced.
    const { container, rerender } = render(
      <Announcer notice={{ text: "Switched to Cats.", count: 1 }} />,
    );
    expect(read(container).text).toBe("Switched to Cats.");
    rerender(<Announcer notice={null} />);
    expect(read(container).text).toBe("");
  });
});
