import { describe, expect, it, vi } from "vitest";

import { NO_CLIPBOARD, NO_DROPS, pictureBlob, pictureBlobs } from "./clipboard";

// jsdom's Blob has no `arrayBuffer`, so the bytes are read the way a page without it would.
function bytesOf(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.readAsArrayBuffer(blob);
  });
}

describe("pictureBlob", () => {
  it("makes a blob of the picture's type from its base64 bytes", async () => {
    const blob = pictureBlob({ dataBase64: "iVBORw==", mimeType: "image/png" });
    expect(blob?.type).toBe("image/png");
    expect(await bytesOf(blob!)).toEqual(
      new Uint8Array([0x89, 0x50, 0x4e, 0x47]),
    );
  });

  it("answers null when the clipboard holds no picture", () => {
    expect(pictureBlob(null)).toBeNull();
  });
});

describe("NO_CLIPBOARD", () => {
  it("never holds a picture", async () => {
    await expect(NO_CLIPBOARD.picture()).resolves.toBeNull();
  });
});

describe("pictureBlobs", () => {
  it("makes one blob of each picture's type, in order", async () => {
    const blobs = pictureBlobs([
      { dataBase64: "/9j/", mimeType: "image/jpeg" },
      { dataBase64: "UklG", mimeType: "image/webp" },
    ]);
    expect(blobs.map((blob) => blob.type)).toEqual(["image/jpeg", "image/webp"]);
    expect(await bytesOf(blobs[1]!)).toEqual(new Uint8Array([0x52, 0x49, 0x46]));
  });
});

describe("NO_DROPS", () => {
  it("never calls back and never holds a picture", async () => {
    const onDrop = vi.fn();
    NO_DROPS.listen(onDrop)();
    expect(onDrop).not.toHaveBeenCalled();
    await expect(NO_DROPS.pictures()).resolves.toEqual([]);
  });
});
