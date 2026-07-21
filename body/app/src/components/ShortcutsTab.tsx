import type { ReactNode } from "react";

import { DownArrowKey, ReturnKey, UpArrowKey } from "./icons";

/** One binding, as a soft filled card: what it does on the left, the keys that do it on the right.
 *  Cards are half-width tiles, which is what makes the tab a wall rather than a list, so a label is
 *  one short word wherever one will do. `wide` takes the whole row, for the one binding that earns
 *  it: the global hotkey is the only shortcut that works when the overlay is not on screen, and a
 *  three-key chord is the widest thing here. */
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

/** The console's shortcuts tab: every binding, grouped by what it is for.
 *
 *  Cards in a two-column grid rather than a hairline-separated list, so the tab is the same object
 *  as the appearance tab beside it: a wall of small filled tiles under a section legend. A list of
 *  full-width rules alongside a wall of swatches read as two different screens.
 *
 *  Each key is its OWN cap, and a cap whose glyph is not a letter carries the header's outline
 *  icon (`icons.tsx`), exactly as the hint strip under the composer draws them. So `Ctrl` `N` reads
 *  as two keys pressed together rather than one key called CtrlN, and the return and shift glyphs
 *  here are the same drawings the strip shows. Nothing here is a Unicode symbol.
 *
 *  The hint strip carries four of these as a convenience; this is the one place all of them are
 *  written down, so a binding that lives nowhere else has to live here. */
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
          <Key label="This list">
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
