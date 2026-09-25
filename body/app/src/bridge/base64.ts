// Arguments to `String.fromCharCode`, a count well under every engine's argument limit.
const CHUNK = 0x8000;

/** Standard base64 of `bytes`, built in chunks so a large picture fits the argument limit. */
export function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let start = 0; start < bytes.length; start += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(start, start + CHUNK));
  }
  return btoa(binary);
}
