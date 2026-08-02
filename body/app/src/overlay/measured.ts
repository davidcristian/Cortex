// The stylesheet's numbers that restate a box on screen, read off that box instead of frozen
// beside it.
//
// Two rules in overlay.css cannot express what they mean in CSS. `.log`'s floor is the empty
// state's own height, so that sending the first message does not shrink the panel out from under
// the composer; the settled "Thoughts" disclosure's floor is the live activity chip's own height,
// so that a turn completing swaps one row for another instead of resizing the log. Neither box is
// reachable from the rule that has to match it: CSS has no way to ask how tall a sibling, or an
// element that is not in the tree yet, comes out. So both were measured in a browser once and
// written down as constants, with the arithmetic in a comment and nothing checking it afterwards.
//
// This reads each of them off the real element instead, while that element is on screen.
//
// **It renders nothing of its own.** A probe that measured a hidden copy would reproduce the very
// defect it is here to fix, one layer down: the copy and the real thing would drift, and the copy
// is the one nobody looks at. Both elements are already in the tree exactly when their numbers are
// knowable, and each leaves exactly when its number starts to matter. The empty state stands for
// the whole life of an empty chat and is replaced by the first message. The live chip stands for
// the whole of a turn's deliberation and is replaced by the disclosure that has to match it. So
// there is nothing to run at startup, and no startup would be early enough anyway: measured at
// boot, the first reading of the empty state is 183px against the 185px it settles at two frames
// later, the example chips' row coming out 29px before the system font stack resolves and 31px
// after.
//
// **So the empty state is a reading plus a watch,** the shape `PanelEdge` already uses for its own
// box: once as the element is attached, so the number is never missing, and again whenever the box
// actually changes. **A chip is one reading**, and the difference is not an oversight. A chip
// cannot be on screen before the user has typed, so it is never measured through the settling the
// empty state sits in, and two of them (a tool and a status) can be up at once, which one watch per
// property could not hold honestly: a shared ref callback is told an element is leaving but never
// which one. Both chips are the same box, so a reading apiece says the same thing and the last
// mount is as good as the first.
//
// Neither publication can feed the element it came from, which is the care `panelWatch` documents.
// `--chat-floor` is spent by `.log`, and while the empty state is up the log is `.log.bare`, whose
// own `min-height: 0` outranks it; `--trace-row` is spent by a disclosure that is never on screen
// beside the chip publishing it. A reading changes nothing about the element it was taken from.
//
// **What it does when it cannot measure.** An element with no layout (jsdom, a `display: none`
// ancestor, a node not in a document) reports 0, and an element that never mounts at all reports
// nothing: a chat restored with messages in it never shows the empty state, and a reply that did
// not reason never shows a chip. In every one of those cases nothing is published and the value
// declared on `:root` in overlay.css stands, which is the same measured constant that used to be
// the only value there. The failure mode is therefore exactly today's behaviour rather than a
// zero-height floor, which is why the constants stay in the stylesheet as documented fallbacks
// rather than being deleted.

import { heightOf } from "./panelMemory";

/** The empty state's height, which is the floor under a chat's log. Read by overlay.css only. */
export const CHAT_FLOOR_PROPERTY = "--chat-floor";
/** The live activity chip's height, which the settled disclosure matches. overlay.css only. */
export const TRACE_ROW_PROPERTY = "--trace-row";

/**
 * Publish `element`'s laid-out height as `property`, or leave the standing value alone.
 *
 * The height is `offsetHeight` for the reason `panelMemory` gives it: it ignores transforms, and
 * both of these boxes are measured while one is running. The panel is scaled through a summon, and
 * a chip arrives under a 300ms `confirmin` that translates and scales it (measured mid-animation,
 * the chip's rect reads 23.883 against a laid-out 24).
 */
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

/**
 * A React ref that publishes whatever it is attached to and goes on publishing it.
 *
 * Built once at module scope rather than inside a render, so React sees one ref across a
 * component's renders and never detaches and re-attaches it, which would cost a fresh observer and
 * a forced layout read each time. One element at a time, which is what the empty state is: the
 * panel morphs between named views and a chat is one of them, so two of these are never on screen
 * together even mid-morph.
 */
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

/** Attached to each live activity chip, and read once apiece. */
export const traceRowRef = (element: HTMLElement | null): void => {
  publishHeight(TRACE_ROW_PROPERTY, element);
};
