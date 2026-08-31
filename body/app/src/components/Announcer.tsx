import type { Notice } from "../overlay/notice";

interface AnnouncerProps {
  readonly notice: Notice | null;
}

/**
 * The overlay's polite live region: it says which conversation just arrived on the panel.
 *
 * It sits outside the panel, at the overlay's root, and the placement is what makes it work. A
 * dismissed panel is `aria-hidden` and `inert` (`overlay/withdrawn.ts`), and the cycle keys are
 * global, so a press can open the panel and swap the chat in one commit. A region inside the panel
 * would enter the accessibility tree in the same frame as the words it carries, which is the
 * arrangement a live region is documented not to survive. Out here it is present from the first
 * render and only its contents change.
 *
 * `role="status"` implies polite delivery and `aria-atomic`, so neither is restated; it is the
 * connection dot's role one level up (`LinkDot.tsx`), the overlay's other standing announcement.
 * Measured over the devtools accessibility tree at 900x900, those two are the only live regions in
 * a resting overlay, and this one computes `live: "polite"`, `atomic: true`,
 * `relevant: "additions text"`.
 *
 * It renders a sentence built elsewhere rather than composing one: every string the region may
 * carry is built in `notice.ts`, so there is one place that states what it can say. The child is
 * keyed by the notice's count, so a swap into a chat titled like the last one, or a second delete
 * leaving the same number of rows, is still a mutation in this region rather than a re-render that
 * changes nothing (`notice.ts`).
 */
export function Announcer({ notice }: AnnouncerProps) {
  return (
    <div className="announcer" role="status">
      {notice === null ? null : <span key={notice.count}>{notice.text}</span>}
    </div>
  );
}
