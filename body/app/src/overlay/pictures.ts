import type { AttachedImage } from "../bridge/types";

export const MAX_ATTACHED_IMAGES = 4;
export const MAX_IMAGE_BYTES = 6 * 1024 * 1024;
export const DEFAULT_MAX_EDGE = 1600;
const MAX_SIDE_PX = 8192;

/** The `failed` code the brain ends a turn with when an attached picture fails its checks. */
export const ATTACHMENT_REFUSED = "attachment_refused";

const READABLE = new Set(["image/png", "image/jpeg", "image/webp"]);

/** One picture waiting in the composer, with the address its thumbnail is drawn from. */
export interface Picture {
  readonly id: string;
  readonly image: AttachedImage;
  readonly preview: string;
}

/** A picture read from a file, before the composer gives it an id. */
export type ReadPicture = Omit<Picture, "id">;

/** Decodes a file, downscales it and encodes it again; rejects when the file cannot be read. */
export type PictureReader = (file: Blob) => Promise<ReadPicture>;

/** Whether the webview can read a file of this type and the brain accepts it. */
export function isReadable(type: string): boolean {
  return READABLE.has(type);
}

/** The size a picture is drawn at: its own, or scaled so its long edge is `DEFAULT_MAX_EDGE`. */
export function fitted(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, DEFAULT_MAX_EDGE / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

/** Why the brain would refuse `image`, as the composer says it, or null when it would not. */
export function pictureProblem(image: AttachedImage): string | null {
  if (image.data.length > MAX_IMAGE_BYTES) {
    const cap = MAX_IMAGE_BYTES / 1024 / 1024;
    return `That picture is over ${cap} MiB even after shrinking, so it was not attached.`;
  }
  const sides = [image.width, image.height];
  if (sides.some((side) => side < 1 || side > MAX_SIDE_PX)) {
    return "That picture's size could not be read, so it was not attached.";
  }
  return null;
}

/** `waiting` with `incoming` added, up to the limit, and the note to show when any was left out. */
export function addPictures(
  waiting: readonly Picture[],
  incoming: readonly Picture[],
): { pictures: readonly Picture[]; overflow: string | null } {
  const room = MAX_ATTACHED_IMAGES - waiting.length;
  const overflow =
    incoming.length > room ? `A message holds at most ${MAX_ATTACHED_IMAGES} pictures.` : null;
  return { pictures: [...waiting, ...incoming.slice(0, Math.max(0, room))], overflow };
}

/** Reads every file `reader` can, and names the last problem met, if any. */
export async function readPictures(
  files: readonly Blob[],
  reader: PictureReader,
): Promise<{ read: readonly ReadPicture[]; problem: string | null }> {
  let problem = files.every((file) => isReadable(file.type))
    ? null
    : "Only PNG, JPEG and WebP pictures can be attached.";
  const results = await Promise.allSettled(
    files.filter((file) => isReadable(file.type)).map(reader),
  );
  const read: ReadPicture[] = [];
  for (const result of results) {
    const found =
      result.status === "rejected"
        ? "That picture could not be read."
        : pictureProblem(result.value.image);
    if (found === null && result.status === "fulfilled") {
      read.push(result.value);
    }
    problem = found ?? problem;
  }
  return { read, problem };
}
