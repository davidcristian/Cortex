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
    const { container, rerender } = render(<Announcer notice={null} />);
    const idle = read(container);
    expect(idle.region.getAttribute("role")).toBe("status");
    expect(idle.text).toBe("");
    expect(idle.said).toBeNull();

    rerender(<Announcer notice={{ text: "Switched to Everything about cats.", count: 1 }} />);
    const spoken = read(container);
    expect(spoken.region).toBe(idle.region);
    expect(spoken.text).toBe("Switched to Everything about cats.");
  });

  it("reads whatever the notice holds, a list change included", () => {
    const { container } = render(
      <Announcer notice={{ text: "Chat deleted. 1 chat left. Switched to New chat.", count: 4 }} />,
    );
    expect(read(container).text).toBe("Chat deleted. 1 chat left. Switched to New chat.");
  });

  it("makes a second announcement with the same words a second mutation", () => {
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
    const { container, rerender } = render(
      <Announcer notice={{ text: "Switched to Cats.", count: 1 }} />,
    );
    expect(read(container).text).toBe("Switched to Cats.");
    rerender(<Announcer notice={null} />);
    expect(read(container).text).toBe("");
  });
});
