import { describe, expect, it } from "vitest";

import config from "../../src-tauri/tauri.conf.json";

function directives(policy: string): Map<string, string> {
  return new Map(
    policy.split(";").map((part) => {
      const [name = "", ...sources] = part.trim().split(/\s+/);
      return [name, sources.join(" ")] as const;
    }),
  );
}

const policy = directives(config.app.security.csp);

describe("the shell's content security policy", () => {
  it("lets the page fetch the IPC origins of Linux and Windows and nothing else", () => {
    expect(policy.get("connect-src")).toBe("ipc: http://ipc.localhost");
  });

  it("loads scripts and styles from the bundle only and denies every other kind of load", () => {
    expect(policy.get("default-src")).toBe("'none'");
    expect(policy.get("script-src")).toBe("'self'");
    expect(policy.get("style-src")).toBe("'self'");
  });

  it("draws the composer's thumbnails, which are data URLs", () => {
    expect(policy.get("img-src")).toBe("'self' data:");
  });

  it("allows no inline code, no eval, no base element and no form submission", () => {
    expect(config.app.security.csp).not.toMatch(/unsafe-/);
    expect(policy.get("base-uri")).toBe("'none'");
    expect(policy.get("form-action")).toBe("'none'");
  });
});
