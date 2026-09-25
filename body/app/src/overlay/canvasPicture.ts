import { type ReadPicture, fitted } from "./pictures";

// The thumbnail's long edge: twice the composer's 44px tile, for a sharp one on a 2x display.
const THUMB_EDGE = 88;

function draw(bitmap: ImageBitmap, width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (context === null) {
    throw new Error("no 2d canvas");
  }
  context.drawImage(bitmap, 0, 0, width, height);
  return canvas;
}

function encoded(canvas: HTMLCanvasElement, mimeType: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("encode failed"))), mimeType);
  });
}

/** The real `PictureReader`: the webview decodes the file, and a canvas downscales it to
 *  `DEFAULT_MAX_EDGE` and encodes it again, as JPEG for a JPEG and as PNG otherwise. Excluded from
 *  coverage, since jsdom has no canvas; the headless overlay runs it. */
export async function readWithCanvas(file: Blob): Promise<ReadPicture> {
  const bitmap = await createImageBitmap(file);
  try {
    const { width, height } = fitted(bitmap.width, bitmap.height);
    const mimeType = file.type === "image/jpeg" ? "image/jpeg" : "image/png";
    const blob = await encoded(draw(bitmap, width, height), mimeType);
    const scale = Math.min(1, THUMB_EDGE / Math.max(width, height));
    const thumb = draw(bitmap, Math.ceil(width * scale), Math.ceil(height * scale));
    const data = new Uint8Array(await blob.arrayBuffer());
    return { image: { data, mimeType, width, height }, preview: thumb.toDataURL("image/png") };
  } finally {
    bitmap.close();
  }
}
