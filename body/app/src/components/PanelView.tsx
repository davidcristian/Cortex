import type { ReactNode } from "react";

import { BackIcon } from "./icons";

interface PanelViewProps {
  /** The view's name, both its heading and how assistive tech announces the region. */
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
}

/**
 * The chrome every non-chat view of the panel wears: the chat's own header rhythm, with the
 * header buttons replaced by a single way back, and a quiet reminder that Esc does the same.
 */
export function PanelView({ title, onClose, children }: PanelViewProps) {
  return (
    <section className="pane" aria-label={title}>
      <header className="head">
        <button className="hbtn" onClick={onClose} aria-label="Back to chat" type="button">
          <BackIcon />
        </button>
        <span className="title">{title}</span>
      </header>
      {children}
      <p className="viewfoot">Esc closes</p>
    </section>
  );
}
