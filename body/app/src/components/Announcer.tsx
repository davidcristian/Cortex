import type { Notice } from "../overlay/notice";

interface AnnouncerProps {
  readonly notice: Notice | null;
}

/**
 * The overlay's polite live region: it says which conversation just arrived on the panel.
 *
 * It sits OUTSIDE the panel, at the overlay's root, and that placement is the load-bearing part.
 * A dismissed panel is `aria-hidden` and `inert` (`overlay/withdrawn.ts`), and the cycle keys are
 * global, so a press can open the panel and swap the chat in one commit. A region inside it would
 * be introducing itself to the accessibility tree in the same frame as the words it wants read,
 * which is the one arrangement a live region is documented not to survive. Out here it is present
 * from the first render and only ever changes its contents.
 *
 * `role="status"` carries polite delivery and `aria-atomic` on its own, so neither is restated;
 * this is the connection dot's role one level up (`LinkDot.tsx`), which is the overlay's other
 * standing announcement. Measured over the devtools accessibility tree at 900x900, the two of them
 * are the whole live-region roster of a resting overlay, and this one computes `live: "polite"`,
 * `atomic: true`, `relevant: "additions text"`.
 *
 * It renders the sentence rather than composing one, and that is the point: every string the region
 * may carry is built in `notice.ts`, so the region has one contract and one place that states it.
 * The child is keyed by the notice's count so that a swap into a chat titled like the last one, or
 * a second delete leaving the same number of rows, is still a mutation in this region rather than a
 * re-render that changes nothing (`notice.ts`).
 */
export function Announcer({ notice }: AnnouncerProps) {
  return (
    <div className="announcer" role="status">
      {notice === null ? null : <span key={notice.count}>{notice.text}</span>}
    </div>
  );
}
