/** Whether a rendered value needs its own line, which it does when it spans more than one. */
function needsOwnLine(text: string): boolean {
  return text.includes("\n");
}

/** Renders one confirm-card argument value as readable text. `JSON.stringify` hides an attached
 *  file behind escapes, so this formats structure as indented lines and leaves every string
 *  exactly as it is: what the user approves is what runs, so a newline renders as a newline. */
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
