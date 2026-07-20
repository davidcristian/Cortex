import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, ShiftKey, UpArrowKey } from "./icons";

/** One binding, as a soft filled card: what it does on the left, the keys that do it on the right.
 *  `wide` spans both columns, for a binding whose keys will not fit beside its label. */
function Key({
  label,
  hint,
  wide = false,
  children,
}: {
  readonly label: string;
  readonly hint?: string;
  readonly wide?: boolean;
  readonly children: ReactNode;
}) {
  return (
    <span className={`skey${wide ? " wide" : ""}`}>
      <span className="skey-label">
        {label}
        {hint === undefined ? null : <small>{hint}</small>}
      </span>
      <span className="row-keys">{children}</span>
    </span>
  );
}

/** The console's shortcuts tab: every binding, grouped by what it is for. */
export function ShortcutsTab() {
  return (
    <div className="rows">
      <section className="swatch">
        <h3 className="sect">Writing</h3>
        <div className="skeys">
          <Key label="Send">
            <b className="key">
              <ReturnKey />
            </b>
          </Key>
          <Key label="Newline">
            <b className="key">
              <ShiftKey />
            </b>
            <b className="key">
              <ReturnKey />
            </b>
          </Key>
        </div>
      </section>
      <section className="swatch">
        <h3 className="sect">Chats</h3>
        {/* Previous and next are two cards, not one row carrying both arrows: at half width the
            label has no room for a slash and three caps, and the pair fills the grid evenly. */}
        <div className="skeys">
          <Key label="New chat">
            <b>Ctrl</b>
            <b>N</b>
          </Key>
          <Key label="Chat switcher">
            <b>Ctrl</b>
            <b>K</b>
          </Key>
          <Key label="Previous chat">
            <b>Ctrl</b>
            <b className="key">
              <UpArrowKey />
            </b>
          </Key>
          <Key label="Next chat">
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
          <Key label="Summon or focus" wide>
            <b>Ctrl</b>
            <b>Alt</b>
            <b>Space</b>
          </Key>
          <Key label="This list">
            <b>?</b>
          </Key>
          {/* Two cards, one key, in the order the panel tries them: Esc leaves the console in a
              single press from either tab, and only a panel with no console up hears it as a
              dismiss. */}
          <Key label="Close the console">
            <b>Esc</b>
          </Key>
          <Key label="Dismiss" hint="to the orb mid-turn" wide>
            <b>Esc</b>
          </Key>
        </div>
      </section>
    </div>
  );
}
