import type { ConsoleTab } from "../overlay/overlayState";
import { DownArrowKey, ReturnKey, SlidersIcon, UpArrowKey } from "./icons";

interface HintStripProps {
  /** Open (or close again) one console tab: each button here opens its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
}

/** The row of keyboard hints under the composer, plus the two buttons that open the console.
 *
 *  Esc is not listed. The strip is a convenience and it had run out of room once the settings
 *  button joined it, and Esc-to-dismiss is the most guessable of the five. The console's shortcuts
 *  tab is the complete list and still names every binding. */
export function HintStrip({ onToggleConsole }: HintStripProps) {
  return (
    <div className="hints">
      <span>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        send
      </span>
      {/* Shift and Return are two caps rather than one cap holding two glyphs. Every other hint
          here separates its keys and the console's shortcut list separates all of them, so a single
          cap made this the one place a chord read as one key.

          Shift is spelled out, like Ctrl and Alt beside it. It is the one modifier with a standard
          glyph, so drawing it made it the only modifier on the row a reader had to recognise rather
          than read, next to three that are words. The keys still drawn as glyphs are the ones with
          no short name: return, and the two cycle arrows. */}
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
      {/* Two buttons into the one console, each landing on the tab it names: the sliders on
          appearance, the ? on the shortcut list. A press here is always an open, because the
          console is a view that replaces this one (`.view.gone` is `display: none`), so neither
          button is reachable while the console is up. They still dispatch the toggle rather than
          the open, so that these buttons and the ? key, which stays live inside the console and can
          close it, share one handler and one name. */}
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
