// Three rules in overlay.css restate the height of a box on screen, and CSS cannot ask how tall a
// sibling or an element not in the tree yet comes out. This reads each one off the real element
// while it is showing. With nothing to measure, the constant declared on `:root` stands.

import { heightOf } from "./panelMemory";

/** The empty state's height, which is the floor under a chat's log. Read by overlay.css only. */
export const CHAT_FLOOR_PROPERTY = "--chat-floor";
/** The live activity chip's height, which the settled disclosure matches. overlay.css only. */
export const TRACE_ROW_PROPERTY = "--trace-row";
/** The hint strip's height, which the panel's budget reserves. Read by overlay.css only. */
export const HINT_STRIP_PROPERTY = "--hint-strip";

/** Publish `element`'s laid-out height as `property`, or leave the current value alone. The used
 *  height, because it ignores transforms and both of these boxes are measured while one runs. */
export function publishHeight(property: string, element: HTMLElement | null): void {
  if (element === null) {
    return;
  }
  const height = heightOf(element);
  if (height <= 0) {
    return;
  }
  element.ownerDocument.documentElement.style.setProperty(property, `${height}px`);
}

/** A React ref that publishes whatever it is attached to and goes on publishing it. Built once at
 *  module scope, so React sees one ref across a component's renders and never detaches it, which
 *  would cost a fresh observer and a forced layout read each time. */
function watched(property: string): (element: HTMLElement | null) => void {
  let watch: ResizeObserver | null = null;
  return (element: HTMLElement | null): void => {
    if (watch !== null) {
      watch.disconnect();
      watch = null;
    }
    if (element === null) {
      return;
    }
    publishHeight(property, element);
    watch = new ResizeObserver(() => {
      publishHeight(property, element);
    });
    watch.observe(element);
  };
}

/** Attached to the empty state itself, and watched for as long as it stands. */
export const chatFloorRef = watched(CHAT_FLOOR_PROPERTY);

/** Attached to the hint strip, and watched, because a narrow panel wraps it onto a second row. */
export const hintStripRef = watched(HINT_STRIP_PROPERTY);

/** Attached to each live activity chip, and read once apiece. */
export const traceRowRef = (element: HTMLElement | null): void => {
  publishHeight(TRACE_ROW_PROPERTY, element);
};
