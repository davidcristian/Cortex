import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, UpArrowKey } from "./icons";

/**
 * One binding, as a soft filled card: what it does on the left, the keys that do it on the right.
 */
function Key({
  label,
  wide = false,
  children,
}: {
  readonly label: string;
  readonly wide?: boolean;
  readonly children: ReactNode;
}) {
  return (
    <span className={`skey${wide ? " wide" : ""}`}>
      <span className="skey-label">{label}</span>
      <span className="row-keys">{children}</span>
    </span>
  );
}

/** The console's shortcuts tab: every binding, grouped by what it is for. */
export function ShortcutsTab() {
  return (
    <div className="rows">
      {/* The group legends: Ink is what the send and new-line keys put on the page; Chats is the
          product's own word for its conversations; The window is the window's own verbs. */}
      <section className="swatch">
        <h3 className="sect">Ink</h3>
        <div className="skeys">
          <Key label="Send">
            <b className="key">
              <ReturnKey />
            </b>
          </Key>
          <Key label="New line">
            <b>Shift</b>
            <b className="key">
              <ReturnKey />
            </b>
          </Key>
        </div>
      </section>
      <section className="swatch">
        <h3 className="sect">Chats</h3>
        {/* Previous and next are two cards, not one carrying both arrows: the grid wants even
            tiles, and a label with a slash in it plus three caps is what makes a card outgrow one. */}
        <div className="skeys">
          <Key label="New">
            <b>Ctrl</b>
            <b>N</b>
          </Key>
          <Key label="Switcher">
            <b>Ctrl</b>
            <b>K</b>
          </Key>
          <Key label="Previous">
            <b>Ctrl</b>
            <b className="key">
              <UpArrowKey />
            </b>
          </Key>
          <Key label="Next">
            <b>Ctrl</b>
            <b className="key">
              <DownArrowKey />
            </b>
          </Key>
        </div>
      </section>
      <section className="swatch">
        <h3 className="sect">The window</h3>
        <div className="skeys">
          <Key label="Summon" wide>
            <b>Ctrl</b>
            <b>Alt</b>
            <b>Space</b>
          </Key>
          <Key label="This tab">
            <b>?</b>
          </Key>
          {/* One card, because Esc does one thing: it backs out of wherever you are. From the
              console that is the console; from the chat it is the panel, to the orb if a turn is
              running. Two cards for one key said that twice and taught nothing the second time. */}
          <Key label="Dismiss">
            <b>Esc</b>
          </Key>
        </div>
      </section>
    </div>
  );
}
