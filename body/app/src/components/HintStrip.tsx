import type { ConsoleTab } from "../overlay/overlayState";
import { DownArrowKey, ReturnKey, SlidersIcon, UpArrowKey } from "./icons";

interface HintStripProps {
  /** Open (or close again) one console tab: each opener here owns its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
}

/** The row of keyboard affordances under the composer, plus the two doors into the console.
 *
 *  Esc is not listed: the strip is a convenience, it had run out of room once the settings button
 *  joined it, and Esc-to-dismiss is the most guessable of the five. The console's shortcuts tab
 *  still lists every binding, that one being the complete list. */
export function HintStrip({ onToggleConsole }: HintStripProps) {
  return (
    <div className="hints">
      <span>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        send
      </span>
      {/* Shift and Return are two caps, not one cap holding two glyphs: every other hint here
          already separates its keys, and the console's shortcut list separates all of them, so a
          single cap made this the one place a chord read as one key.

          Shift is SPELLED OUT, like Ctrl and Alt beside it. Its glyph is the one modifier with a
          drawing, so drawn it was the only modifier on the row you had to recognise rather than
          read, sitting against three that are words. The drawn glyphs left are the keys that have
          no name worth writing: return, and the two cycle arrows. */}
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
      {/* Two doors into the one console, each landing on the tab it names: the sliders on
          appearance, the ? on the shortcut list. A press here is always an open, because the
          console is a view and replaces this one outright (`.view.gone` is `display: none`), so
          neither button is reachable while it is up. They still dispatch the toggle rather than
          the open, so that the strip and the ? KEY, which IS live inside the console and is the
          binding that can close it that way, stay one behaviour with one name. */}
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
