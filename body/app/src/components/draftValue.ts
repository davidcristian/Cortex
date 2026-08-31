/**
 * Render one confirm-card argument value as readable text (ADR-0022).
 *
 * The card's rule is that what you approve is what runs, so every value is shown verbatim.
 * `JSON.stringify` shows the value but stops being readable as soon as it is not a string: an
 * attached file arrives as `{"content":"# Week 30\n- one"}`, where the payload the user is
 * consenting to is buried behind escapes. This formats structure as indented lines and leaves every
 * string exactly as it is, so newlines render as newlines.
 *
 * It handles JSON shapes only and has no knowledge of `send_email` or attachments, because the card
 * renders whatever gated tool the brain asks about.
 */

/** Whether a rendered value needs its own line, which it does when it spans more than one. */
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
