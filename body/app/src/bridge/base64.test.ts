import { describe, expect, it } from "vitest";

import { fromBase64, toBase64 } from "./base64";

describe("toBase64", () => {
  it("encodes a short run with its padding", () => {
    expect(toBase64(new Uint8Array([0x89, 0x50, 0x4e, 0x47]))).toBe("iVBORw==");
  });

  it("encodes nothing as the empty string", () => {
    expect(toBase64(new Uint8Array())).toBe("");
  });

  it("keeps every byte of a run longer than one chunk", () => {
    const bytes = new Uint8Array(3 * 40_000).map((_unused, index) => index % 256);
    const oneByOne = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
    expect(toBase64(bytes)).toBe(btoa(oneByOne));
  });
});

describe("fromBase64", () => {
  it("reads back every byte value toBase64 wrote", () => {
    const bytes = new Uint8Array(256).map((_unused, index) => index);
    expect(fromBase64(toBase64(bytes))).toEqual(bytes);
  });

  it("reads the empty string as no bytes", () => {
    expect(fromBase64("")).toEqual(new Uint8Array());
  });
});
