import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, ShiftKey, UpArrowKey } from "./icons";
import { PanelView } from "./PanelView";

/** One shortcut row: the action, and the keys that do it. */
function Row({
  label,
  hint,
  children,
}: {
  readonly label: string;
  readonly hint?: string;
  readonly children: ReactNode;
}) {
  return (
    <div className="row">
      <span className="row-label">
        {label}
        {hint === undefined ? null : <small>{hint}</small>}
      </span>
      <span className="row-keys">{children}</span>
    </div>
  );
}

/** The complete list of bindings, reached from the hint strip's ? (or the ? key). The strip beside
 *  the composer carries four of these as a convenience; this is the one place all of them are. */
export function ShortcutsView({ onClose }: { readonly onClose: () => void }) {
  return (
    <PanelView title="Shortcuts" onClose={onClose}>
      <div className="rows">
        <Row label="Summon or focus">
          <b>Ctrl</b>
          <b>Alt</b>
          <b>Space</b>
        </Row>
        <Row label="Send">
          <b className="key">
            <ReturnKey />
          </b>
        </Row>
        <Row label="Newline">
          <b className="key">
            <ShiftKey />
            <ReturnKey />
          </b>
        </Row>
        <Row label="New chat">
          <b>Ctrl</b>
          <b>N</b>
        </Row>
        <Row label="Previous / next chat">
          <b>Ctrl</b>
          <b className="key">
            <UpArrowKey />
          </b>
          <b className="key">
            <DownArrowKey />
          </b>
        </Row>
        <Row label="Chat switcher">
          <b>Ctrl</b>
          <b>K</b>
        </Row>
        <Row label="Dismiss" hint="to the orb while a turn is running">
          <b>Esc</b>
        </Row>
        <Row label="This view">
          <b>?</b>
        </Row>
      </div>
    </PanelView>
  );
}
