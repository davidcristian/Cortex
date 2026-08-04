import type { Notice } from "../overlay/notice";

interface AnnouncerProps {
  readonly notice: Notice | null;
}

/** The overlay's polite live region: it says which conversation just arrived on the panel. */
export function Announcer({ notice }: AnnouncerProps) {
  return (
    <div className="announcer" role="status">
      {notice === null ? null : <span key={notice.count}>Switched to {notice.title}</span>}
    </div>
  );
}
