import { fromBase64 } from "./base64";
import type { HostClipboard, HostDrops } from "./types";

/** The shell's `clipboard_picture` answer (matches `WirePicture` in clipboard.rs). */
export interface WirePicture {
  readonly dataBase64: string;
  readonly mimeType: string;
}

function blobOf(wire: WirePicture): Blob {
  return new Blob([fromBase64(wire.dataBase64)], { type: wire.mimeType });
}

/** The picture a `clipboard_picture` answer holds, or null when it holds none. */
export function pictureBlob(wire: WirePicture | null): Blob | null {
  return wire === null ? null : blobOf(wire);
}

/** The pictures a `dropped_pictures` answer holds. */
export function pictureBlobs(wires: readonly WirePicture[]): Blob[] {
  return wires.map(blobOf);
}

/** A clipboard with nothing on it, for the browser build, where the page reads a paste itself. */
export const NO_CLIPBOARD: HostClipboard = { picture: () => Promise.resolve(null) };

/** No native drops, for the browser build and WebView2, where the page reads a drop itself. */
export const NO_DROPS: HostDrops = { listen: () => () => {}, pictures: () => Promise.resolve([]) };
