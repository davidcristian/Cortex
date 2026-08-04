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
    // A live region has to be present BEFORE the change it reports, so an empty one is the
    // resting state rather than an absent one. Reddens if the region is only rendered with a
    // notice in hand, which is the arrangement that announces nothing at all.
    const { container, rerender } = render(<Announcer notice={null} />);
    const idle = read(container);
    expect(idle.region.getAttribute("role")).toBe("status");
    expect(idle.text).toBe("");
    expect(idle.said).toBeNull();

    rerender(<Announcer notice={{ title: "Everything about cats", count: 1 }} />);
    const spoken = read(container);
    // The same node, with words in it now: the region itself never remounts.
    expect(spoken.region).toBe(idle.region);
    // A sentence and not a bare title, which would name a thing without saying what happened.
    expect(spoken.text).toBe("Switched to Everything about cats");
  });

  it("makes a second arrival under the same title a second mutation", () => {
    // Two chats can carry one title, and text replaced by identical text is not a change a
    // reader is told about. The count is what replaces the node instead of leaving it, so the
    // region mutates on every arrival. Reddens if `Announcer` stops keying on the count: React
    // then reuses the node and the second swap is silent.
    const { container, rerender } = render(<Announcer notice={{ title: "New chat", count: 1 }} />);
    const first = read(container);
    rerender(<Announcer notice={{ title: "New chat", count: 2 }} />);
    const second = read(container);
    expect(second.text).toBe("Switched to New chat");
    expect(second.said).not.toBe(first.said);
    expect(second.region).toBe(first.region);
  });

  it("takes its words back down when a swap speaks for itself", () => {
    // A switcher row clears the notice, and the region must not keep reading the last chat
    // switched to: what stands in it is only ever the last thing that was actually announced.
    const { container, rerender } = render(<Announcer notice={{ title: "Cats", count: 1 }} />);
    expect(read(container).text).toBe("Switched to Cats");
    rerender(<Announcer notice={null} />);
    expect(read(container).text).toBe("");
  });
});
