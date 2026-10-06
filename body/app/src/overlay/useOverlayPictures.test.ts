import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { NO_CLIPBOARD } from "../bridge/clipboard";
import type { HostClipboard, HostDrops } from "../bridge/types";
import { noteOf, waitingOf } from "./pictureState";
import type { ReadPicture } from "./pictures";
import { CLIPBOARD_UNREAD, DROP_UNREAD, useOverlay } from "./useOverlay";

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
      expect(noteOf(result.current.state.pictures, "s1")).toBe(
        "Only PNG, JPEG and WebP pictures can be attached.",
      ),
    );
  });

  it("attaches the host clipboard's picture for a paste the webview gave no file", async () => {
    const bridge = new FakeBridge();
    const clipboard: HostClipboard = {
      picture: () => Promise.resolve(new Blob(["x"], { type: "image/webp" })),
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader, clipboard));
    await act(async () => {
      result.current.pastePicture();
    });
    await vi.waitFor(() => expect(waitingOf(result.current.state.pictures, "s1")).toHaveLength(1));
    const [pasted] = waitingOf(result.current.state.pictures, "s1");
    expect(pasted!.preview).toBe("data:image/webp");
  });

  it("attaches nothing and says nothing when the host clipboard holds no picture", async () => {
    const bridge = new FakeBridge();
    const picture = vi.fn(() => Promise.resolve(null));
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader, { picture }));
    await act(async () => {
      result.current.pastePicture();
    });
    expect(picture).toHaveBeenCalledTimes(1);
    expect(waitingOf(result.current.state.pictures, "s1")).toEqual([]);
    expect(noteOf(result.current.state.pictures, "s1")).toBeNull();
  });

  it("says so when the host clipboard cannot be read", async () => {
    const bridge = new FakeBridge();
    const clipboard: HostClipboard = { picture: () => Promise.reject(new Error("over the limit")) };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1", reader, clipboard));
    await act(async () => {
      result.current.pastePicture();
    });
    await vi.waitFor(() =>
      expect(noteOf(result.current.state.pictures, "s1")).toBe(CLIPBOARD_UNREAD),
    );
    expect(waitingOf(result.current.state.pictures, "s1")).toEqual([]);
  });

  it("attaches every picture of the host's last native drop", async () => {
    const bridge = new FakeBridge();
    const drops: HostDrops = {
      listen: () => () => {},
      pictures: () =>
        Promise.resolve([
          new Blob(["x"], { type: "image/png" }),
          new Blob(["y"], { type: "image/jpeg" }),
        ]),
    };
    const { result } = renderHook(() =>
      useOverlay(bridge, () => "s1", reader, NO_CLIPBOARD, drops),
    );
    await act(async () => {
      result.current.dropPictures();
    });
    await vi.waitFor(() => expect(waitingOf(result.current.state.pictures, "s1")).toHaveLength(2));
    const waiting = waitingOf(result.current.state.pictures, "s1");
    const previews = waiting.map((picture) => picture.preview);
    expect(previews).toEqual(["data:image/png", "data:image/jpeg"]);
  });

  it("leaves the composer as it was when a native drop held no picture", async () => {
    const bridge = new FakeBridge();
    const pictures = vi.fn(() => Promise.resolve([]));
    const drops: HostDrops = { listen: () => () => {}, pictures };
    const { result } = renderHook(() =>
      useOverlay(bridge, () => "s1", reader, NO_CLIPBOARD, drops),
    );
    await act(async () => {
      result.current.attach([new Blob(["x"], { type: "text/plain" })]);
    });
    await vi.waitFor(() => expect(noteOf(result.current.state.pictures, "s1")).not.toBeNull());
    const note = noteOf(result.current.state.pictures, "s1");
    await act(async () => {
      result.current.dropPictures();
    });
    expect(pictures).toHaveBeenCalledTimes(1);
    expect(noteOf(result.current.state.pictures, "s1")).toBe(note);
    expect(waitingOf(result.current.state.pictures, "s1")).toEqual([]);
  });

  it("says so when the native drop's files cannot be read", async () => {
    const bridge = new FakeBridge();
    const drops: HostDrops = {
      listen: () => () => {},
      pictures: () => Promise.reject(new Error("no runtime")),
    };
    const { result } = renderHook(() =>
      useOverlay(bridge, () => "s1", reader, NO_CLIPBOARD, drops),
    );
    await act(async () => {
      result.current.dropPictures();
    });
    await vi.waitFor(() => expect(noteOf(result.current.state.pictures, "s1")).toBe(DROP_UNREAD));
  });
});
