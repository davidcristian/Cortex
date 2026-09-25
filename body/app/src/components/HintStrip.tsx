import { hintStripRef } from "../overlay/measured";
import type { ConsoleTab } from "../overlay/overlayState";
import { DownArrowKey, ReturnKey, SlidersIcon, UpArrowKey } from "./icons";

interface HintStripProps {
  /** Open (or close again) one console tab: each button here opens its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
}

/** The row of keyboard hints under the composer, plus the two buttons that open the console. Esc
 *  is not listed: the strip ran out of room, and the console's shortcut tab is the full list. */
export function HintStrip({ onToggleConsole }: HintStripProps) {
  return (
    <div className="hints" ref={hintStripRef}>
      <span>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        send
      </span>
      {/* Shift and Return are two caps rather than one cap with two glyphs, so the chord does not
          read as one key. Shift is written out like Ctrl and Alt beside it; only the keys with no
          short name are drawn as glyphs, which are return and the two cycle arrows. */}
      <span>
        <b>Shift</b>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        new line
      </span>
      <span>
        <b>Ctrl</b>
        <b>N</b> new
      </span>
      <span>
        <b>Ctrl</b>
        <b className="key">
          <UpArrowKey />
        </b>
        <b className="key">
          <DownArrowKey />
        </b>{" "}
        chats
      </span>
      {/* Two buttons into the one console, each opening the tab it names. They send the toggle
          rather than the open, so that they and the ? key, which stays live inside the console and
          can close it, share one handler. */}
      <button
        className="qbtn"
        onClick={() => onToggleConsole("appearance")}
        aria-label="Settings"
        type="button"
      >
        <b className="key">
          <SlidersIcon />
        </b>
      </button>
      <button
        className="qbtn"
        onClick={() => onToggleConsole("shortcuts")}
        aria-label="Shortcuts"
        type="button"
      >
        <b>?</b>
      </button>
    </div>
  );
}
