import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Message as MessageModel } from "../overlay/overlayState";
import { CHUNK_LETTERS } from "../whisper/front";
import { WhisperBubble } from "./WhisperBubble";

const msg = (over: Partial<MessageModel>): MessageModel => ({
  id: "m",
  role: "assistant",
  content: "",
  streaming: false,
  tool: null,
  status: null,
  statusState: null,
  thoughts: "",
  error: null,
  ...over,
});

const grow = (): void => undefined;

// The clock is its own tested module; here the frames are swallowed so a live bubble holds its
// breath and what is under test is the DOM the component lays for the clock to drive.
beforeEach(() => {
  vi.spyOn(window, "requestAnimationFrame").mockReturnValue(1);
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("WhisperBubble", () => {
  it("renders history as one plain bubble with none of the machinery", () => {
    const { container } = render(
      <WhisperBubble message={msg({ content: "loaded reply" })} onGrow={grow} />,
    );
    const bubble = container.querySelector(".bubble");
    expect(bubble?.className).toBe("bubble b-ai");
    expect(bubble?.textContent).toBe("loaded reply");
    expect(container.querySelector(".wtxt")).toBeNull();
    expect(container.querySelector(".mist")).toBeNull();
  });

  it("breathes before the first token: the mist, a posed pill, and Thinking for the reader", () => {
    const { container } = render(
      <WhisperBubble message={msg({ streaming: true })} onGrow={grow} />,
    );
    const bubble = container.querySelector(".bubble");
    expect(bubble?.className).toBe("bubble b-ai whisper w-breath");
    expect(container.querySelector(".mist i")).not.toBeNull();
    expect(container.querySelector(".ch")).toBeNull();
    expect(container.querySelector(".sr-copy")?.textContent).toBe("Thinking");
  });

  it("lays words as letter boxes, gaps verbatim, presentation hidden behind the copy", () => {
    const { container } = render(
      <WhisperBubble message={msg({ streaming: true, content: "hi\nthere " })} onGrow={grow} />,
    );
    expect(container.querySelectorAll(".wd")).toHaveLength(2);
    expect(container.querySelectorAll(".ch")).toHaveLength(7);
    expect(container.querySelector(".wtxt")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".wtxt")?.textContent).toBe("hi\nthere ");
    expect(container.querySelector(".sr-copy")?.textContent).toBe("hi\nthere ");
  });

  it("chunks a giant streamed token into boxes the bubble can break between", () => {
    const hash = "a".repeat(CHUNK_LETTERS + 4);
    const { container } = render(
      <WhisperBubble message={msg({ streaming: true, content: hash })} onGrow={grow} />,
    );
    expect(container.querySelectorAll(".wd")).toHaveLength(2);
  });

  it("keeps its letter DOM once the turn settles: the latch, not the message, decides", () => {
    const { container, rerender } = render(
      <WhisperBubble message={msg({ streaming: true, content: "one two" })} onGrow={grow} />,
    );
    rerender(<WhisperBubble message={msg({ content: "one two done" })} onGrow={grow} />);
    expect(container.querySelector(".wtxt")).not.toBeNull();
    expect(container.querySelectorAll(".wd")).toHaveLength(3);
  });

  it("derives its phases with no frames at all under reduced motion", () => {
    const media = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      ...media(query),
      matches: true,
    })) as typeof window.matchMedia;
    try {
      const { container, rerender } = render(
        <WhisperBubble message={msg({ streaming: true })} onGrow={grow} />,
      );
      expect(window.requestAnimationFrame).not.toHaveBeenCalled();
      expect(container.querySelector(".bubble")?.className).toContain("w-breath");
      rerender(<WhisperBubble message={msg({ streaming: true, content: "hi " })} onGrow={grow} />);
      expect(container.querySelector(".bubble")?.className).toContain("w-talking");
      rerender(<WhisperBubble message={msg({ content: "hi there" })} onGrow={grow} />);
      expect(container.querySelector(".bubble")?.className).toContain("w-settled");
    } finally {
      window.matchMedia = media;
    }
  });
});
