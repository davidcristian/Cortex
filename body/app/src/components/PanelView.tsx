import type { ReactNode } from "react";

import { CloseIcon } from "./icons";

interface PanelViewProps {
  /** The view's name, both its heading and how assistive tech announces the region. */
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
}

/**
 * The chrome every non-chat view of the panel wears: the chat's own header rhythm, with the
 * header buttons replaced by a single way back.
 */
export function PanelView({ title, onClose, children }: PanelViewProps) {
  return (
    <section className="pane" aria-label={title}>
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
