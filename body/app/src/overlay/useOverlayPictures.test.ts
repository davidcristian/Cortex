import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { waitingOf } from "./pictureState";
import type { ReadPicture } from "./pictures";
import { useOverlay } from "./useOverlay";

const reader = (from: Blob): Promise<ReadPicture> =>
  Promise.resolve({
    image: { data: new Uint8Array([7]), mimeType: from.type, width: 8, height: 6 },
    preview: `data:${from.type}`,
  });

describe("useOverlay with pictures", () => {
  it("reads attached files into the composer and sends them with the next turn", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader));
    await act(async () => {
      result.current.attach([new Blob(["x"], { type: "image/jpeg" })]);
    });
    await vi.waitFor(() => expect(waitingOf(result.current.state.pictures, "s1")).toHaveLength(1));
    const waiting = waitingOf(result.current.state.pictures, "s1");
    expect(waiting.map((picture) => picture.preview)).toEqual(["data:image/jpeg"]);
    act(() => result.current.submit("what is this"));
    expect(bridge.attached).toEqual([[waiting[0]!.image]]);
    expect(waitingOf(result.current.state.pictures, "s1")).toEqual([]);
  });

  it("removes a waiting picture, so the turn goes without it", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader));
    await act(async () => {
      result.current.attach([new Blob(["x"], { type: "image/png" })]);
    });
    await vi.waitFor(() => expect(waitingOf(result.current.state.pictures, "s1")).toHaveLength(1));
    const [only] = waitingOf(result.current.state.pictures, "s1");
    act(() => result.current.detach(only!.id));
    act(() => result.current.submit("and now"));
    expect(bridge.attached).toEqual([[]]);
  });

  it("says why a file was not attached", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader));
    await act(async () => {
      result.current.attach([new Blob(["x"], { type: "text/plain" })]);
    });
    await vi.waitFor(() =>
      expect(result.current.state.pictures.note).toBe(
        "Only PNG, JPEG and WebP pictures can be attached.",
      ),
    );
  });
});
