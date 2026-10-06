import { fromBase64 } from "./base64";
import type { HostClipboard } from "./types";

/** The shell's `clipboard_picture` answer (matches `WirePicture` in clipboard.rs). */
export interface WirePicture {
  readonly dataBase64: string;
  readonly mimeType: string;
}

/** The picture a `clipboard_picture` answer holds, or null when it holds none. */
export function pictureBlob(wire: WirePicture | null): Blob | null {
  return wire === null ? null : new Blob([fromBase64(wire.dataBase64)], { type: wire.mimeType });
}

/** A clipboard with nothing on it, for the browser build, where the page reads a paste itself. */
export const NO_CLIPBOARD: HostClipboard = { picture: () => Promise.resolve(null) };
