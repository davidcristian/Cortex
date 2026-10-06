import { describe, expect, it } from "vitest";

import { NO_CLIPBOARD, pictureBlob } from "./clipboard";

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
