import type { ReactNode } from "react";

import { CloseIcon } from "./icons";

interface PanelViewProps {
  /** The view's name, both its heading and how assistive tech announces the region. */
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
}

/** The chrome every non-chat view of the panel wears: the chat's own header rhythm, with the
 *  header buttons replaced by a single way back.
 *
 *  There is no "Esc closes" line under the content: the header carries a visible way out, and the
 *  shortcuts tab lists the key, so a standing caption repeating it is a third telling of one fact.
 *
 *  These views are not sheets laid over the panel any more; they ARE the panel while they are up,
 *  so the panel resizes to what they need and slides back to true centre (`usePanelMotion`). A
 *  view with two rows of swatches in it is therefore a small window rather than a tall one with
 *  its content pinned to the top and its footer stranded three hundred pixels below. */
export function PanelView({ title, onClose, children }: PanelViewProps) {
  return (
    <section className="pane" aria-label={title}>
      {/* The title opens the row and the way out closes it, which is the chat header's own shape:
          the name of the thing on the left against the panel's corner, the controls gathered on the
          right. A leading chevron was tried and puts the one control where the chat puts its title,
          so the two views disagree about which end of the header is which. */}
      <header className="head">
        <span className="title">{title}</span>
        <button className="hbtn" onClick={onClose} aria-label="Back to chat" type="button">
          <CloseIcon />
        </button>
      </header>
      {children}
    </section>
  );
}
