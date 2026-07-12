import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, ShiftKey, UpArrowKey } from "./icons";

/** One sheet row: the action label and its keycaps. */
function Row({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    <div className="sheet-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The full shortcut sheet (design/overlay-ux.md §6), summoned by the hint strip's ? (or the ?
 *  key). It covers the panel; a click anywhere on it (or Esc, wired in Overlay) closes it. */
export function ShortcutSheet({ onClose }: { readonly onClose: () => void }) {
  return (
    <div className="sheet" role="dialog" aria-label="Keyboard shortcuts" onClick={onClose}>
      <p className="sheet-head">Keyboard shortcuts</p>
      <dl className="sheet-rows">
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
        <Row label="Dismiss (orb while working)">
          <b>Esc</b>
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
        <Row label="This sheet">
          <b>?</b>
        </Row>
      </dl>
      <p className="sheet-foot">Click anywhere or press Esc to close</p>
    </div>
  );
}
