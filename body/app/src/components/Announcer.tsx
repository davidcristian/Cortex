import type { Notice } from "../overlay/notice";

interface AnnouncerProps {
  readonly notice: Notice | null;
}

/** The overlay's polite live region: it says which conversation just arrived on the panel. It
 *  renders at the overlay's root, because a region inside the dismissed panel would join the
 *  accessibility tree in the same frame as its text, and that is not announced. */
export function Announcer({ notice }: AnnouncerProps) {
  return (
    <div className="announcer" role="status">
      {notice === null ? null : <span key={notice.count}>{notice.text}</span>}
    </div>
  );
}
