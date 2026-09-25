import { describe, expect, it } from "vitest";

import type { AttachedImage } from "../bridge/types";
import {
  MAX_ATTACHED_IMAGES,
  MAX_IMAGE_BYTES,
  type Picture,
  type ReadPicture,
  addPictures,
  fitted,
  isReadable,
  pictureProblem,
  readPictures,
} from "./pictures";

const image = (over: Partial<AttachedImage> = {}): AttachedImage => ({
  data: new Uint8Array([1, 2]),
  mimeType: "image/png",
  width: 10,
  height: 10,
  ...over,
});
const picture = (id: string): Picture => ({ id, image: image(), preview: `data:${id}` });
const file = (type: string, name = type) => new Blob([name], { type });

describe("fitted", () => {
  it("keeps a picture already within the long edge", () => {
    expect(fitted(1600, 900)).toEqual({ width: 1600, height: 900 });
  });

  it("scales the long edge to 1600 on either axis", () => {
    expect(fitted(3200, 1800)).toEqual({ width: 1600, height: 900 });
    expect(fitted(1000, 4000)).toEqual({ width: 400, height: 1600 });
  });

  it("never rounds a thin side down to nothing", () => {
    expect(fitted(20_000, 1)).toEqual({ width: 1600, height: 1 });
  });
});

describe("isReadable", () => {
  it("accepts the three types the brain accepts and nothing else", () => {
    expect(["image/png", "image/jpeg", "image/webp"].map(isReadable)).toEqual([true, true, true]);
    expect(isReadable("image/gif")).toBe(false);
  });
});

describe("pictureProblem", () => {
  it("passes a picture at the byte cap and at the side limits", () => {
    const full = new Uint8Array(MAX_IMAGE_BYTES);
    expect(pictureProblem(image({ data: full, width: 1, height: 8192 }))).toBeNull();
  });

  it("names a picture over the byte cap", () => {
    const over = new Uint8Array(MAX_IMAGE_BYTES + 1);
    expect(pictureProblem(image({ data: over }))).toMatch(/over 6 MiB/u);
  });

  it("names a side outside 1 to 8192", () => {
    expect(pictureProblem(image({ width: 0 }))).toMatch(/size could not be read/u);
    expect(pictureProblem(image({ height: 8193 }))).toMatch(/size could not be read/u);
  });
});

describe("addPictures", () => {
  it("adds every picture while there is room", () => {
    const added = addPictures([picture("a")], [picture("b")]);
    expect(added.pictures.map((p) => p.id)).toEqual(["a", "b"]);
    expect(added.overflow).toBeNull();
  });

  it("stops at the limit and says why", () => {
    const five = ["a", "b", "c", "d", "e"].map(picture);
    const added = addPictures(five.slice(0, 3), five.slice(3));
    expect(added.pictures).toHaveLength(MAX_ATTACHED_IMAGES);
    expect(added.overflow).toBe("A message holds at most 4 pictures.");
  });

  it("adds nothing to a composer already full", () => {
    const full = ["a", "b", "c", "d", "e"].map(picture);
    expect(addPictures(full, [picture("f")]).pictures.map((p) => p.id)).toEqual(
      full.map((p) => p.id),
    );
  });
});

describe("readPictures", () => {
  const read = (from: Blob): Promise<ReadPicture> =>
    from.size === 3
      ? Promise.reject(new Error("broken"))
      : Promise.resolve({ image: image({ mimeType: from.type }), preview: "data:x" });

  it("reads every readable file and names no problem", async () => {
    const result = await readPictures([file("image/png"), file("image/webp")], read);
    expect(result.read.map((p) => p.image.mimeType)).toEqual(["image/png", "image/webp"]);
    expect(result.problem).toBeNull();
  });

  it("skips a file of another type and says which types are read", async () => {
    const result = await readPictures([file("image/gif"), file("image/png")], read);
    expect(result.read).toHaveLength(1);
    expect(result.problem).toBe("Only PNG, JPEG and WebP pictures can be attached.");
  });

  it("names a file the reader could not decode, and keeps the rest", async () => {
    const result = await readPictures([file("image/png", "bad"), file("image/jpeg")], read);
    expect(result.read.map((p) => p.image.mimeType)).toEqual(["image/jpeg"]);
    expect(result.problem).toBe("That picture could not be read.");
  });

  it("leaves out a picture the brain would refuse", async () => {
    const huge = () =>
      Promise.resolve({ image: image({ width: 9000 }), preview: "data:x" } as ReadPicture);
    const result = await readPictures([file("image/png")], huge);
    expect(result.read).toEqual([]);
    expect(result.problem).toMatch(/size could not be read/u);
  });
});
