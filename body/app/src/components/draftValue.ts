/**
 * Render one confirm-card argument value as readable text (ADR-0022).
 *
 * The card's rule is that what you approve is what runs, so every value is shown verbatim.
 * `JSON.stringify` satisfies "shown" and fails "readable" the moment a value stops being a
 * string: an attached file arrives as `{"content":"# Week 30\n- one"}`, where the payload the
 * user is consenting to is buried behind escapes. This formats structure as indented lines and
 * leaves every string exactly as it is, so newlines are newlines.
 *
 * Deliberately generic: it knows about JSON shapes, never about `send_email` or attachments.
 * The card renders whatever gated tool the brain asks about.
 */

/** A string that needs its own line: it is multi-line, or it is nested structure. */
function needsOwnLine(text: string): boolean {
  return text.includes("\n");
}

export function formatDraftValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === null || typeof value !== "object") {
    return String(value);
  }
  if (Array.isArray(value)) {
    // One blank line between items, so several attachments stay visibly separate.
    return value.map((item: unknown) => formatDraftValue(item)).join("\n\n");
  }
  return Object.entries(value)
    .map(([key, nested]: [string, unknown]) => {
      const text = formatDraftValue(nested);
      return needsOwnLine(text) ? `${key}:\n${text}` : `${key}: ${text}`;
    })
    .join("\n");
}
