import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, UpArrowKey } from "./icons";

/** One binding, as a soft filled card: what it does on the left, the keys that do it on the
 *  right. `wide` takes the whole row, which the global hotkey needs: it is the only shortcut that
 *  works when the overlay is off screen, and its three-key chord is the widest content here. */
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

/** The console's shortcuts tab: every binding, grouped by what it is for. The hint strip under
 *  the composer shows four of them; this is the one place all of them are written down, so a
 *  binding that appears nowhere else has to appear here. */
export function ShortcutsTab() {
  return (
    <div className="rows">
      {/* The group legends: Ink is what the send and new-line keys put on the page, Chats is the
          product's own word for its conversations, and The window is the window's own actions. */}
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
        {/* Previous and next are two cards rather than one with both arrows, because the grid
            uses even tiles and a label with a slash plus three caps overflows one tile. */}
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
          {/* One card, because Esc does one thing: it leaves whatever surface is open, the
              console from the console and the panel from the chat. */}
          <Key label="Dismiss">
            <b>Esc</b>
          </Key>
        </div>
      </section>
    </div>
  );
}
