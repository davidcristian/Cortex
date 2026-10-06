// A drag holding either type would otherwise end as the webview's own action: WebKitGTK and
// Chromium open a dropped file or link as the whole window, or type its address into a field.
const GUARDED_TYPES = ["Files", "text/uri-list"];

/** Cancels the webview's default for a drag that holds a file or an address; returns the undo. */
export function guardDrops(target: Window): () => void {
  const cancel = (event: DragEvent) => {
    if (event.dataTransfer?.types.some((type) => GUARDED_TYPES.includes(type))) {
      event.preventDefault();
    }
  };
  const kinds = ["dragenter", "dragover", "drop"] as const;
  for (const kind of kinds) {
    target.addEventListener(kind, cancel);
  }
  return () => {
    for (const kind of kinds) {
      target.removeEventListener(kind, cancel);
    }
  };
}
